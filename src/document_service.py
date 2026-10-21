"""Wikipedia Action API only; conservative selection, provenance and durable caches."""
import html, json, re, threading, time
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
import requests
from .storage import Cache, Metrics, digest, now, write_json
from .llm import ServiceError
API='https://ko.wikipedia.org/w/api.php'
POLICY_URLS=['https://www.mediawiki.org/wiki/API:Etiquette','https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy','https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use']

class QueryPlan(BaseModel):
    model_config=ConfigDict(extra='forbid')
    queries:list[str]=Field(max_length=3)
class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    selected_ids:list[int]=Field(max_length=5)

def prompt(name): return (Path(__file__).resolve().parents[1]/'prompts'/name).read_text(encoding='utf-8')

def own_title(title, name):
    # 공백 제거
    normalized_title = re.sub(r'\s+', '', title)
    normalized_name = re.sub(r'\s+', '', name)

    # 포켓몬 이름 또는 포켓몬 전용 문서 제목
    return normalized_title in {
        normalized_name,
        f'{normalized_name}(포켓몬)'
    }


class DocumentService:
    lock=threading.Lock(); last=0.0
    def __init__(self,settings,catalog,store,llm):
        self.settings=settings; self.catalog=catalog; self.store=store; self.llm=llm
        self.cache=Cache(settings.runtime_dir); self.metrics=Metrics(settings.runtime_dir)
    def request(self,params):
        params={'format':'json','formatversion':2,'maxlag':5,**params}
        key='wiki:'+digest(params); old=self.cache.get(key)
        if old is not None: return old
        ua='PokemonLab/1.0'+(f' ({self.settings.wiki_contact})' if self.settings.wiki_contact else '')
        try: ua.encode('ascii')
        except UnicodeEncodeError: raise ServiceError('WIKI_CONTACT에는 영문 이메일 또는 URL을 사용하세요.') from None
        for attempt in range(3):
            try:
                with self.lock:
                    time.sleep(max(0,self.settings.wiki_interval-(time.monotonic()-type(self).last)))
                    type(self).last=time.monotonic()
                response=requests.get(API,params=params,headers={'User-Agent':ua},timeout=25)
                self.metrics.record('wiki_http',status=response.status_code)
                if response.status_code in (429,503):
                    if attempt==2: break
                    try: wait=float(response.headers.get('Retry-After',''))
                    except ValueError: wait=2**(attempt+1)
                    # Do not retry earlier than a long server-specified delay.
                    if wait>30: raise ServiceError('위키백과가 긴 대기 시간을 요청했습니다. 나중에 다시 시도하세요.')
                    time.sleep(wait); continue
                response.raise_for_status(); data=response.json()
                if 'error' in data:
                    if data['error'].get('code')=='maxlag': time.sleep(5); continue
                    raise ServiceError('위키백과 API가 요청을 처리하지 못했습니다.')
                self.cache.put(key,data); return data
            except ServiceError: raise
            except requests.RequestException:
                if attempt<2: time.sleep(2**attempt)
        raise ServiceError('위키백과 연결에 실패했습니다. 기존 캐시는 유지됩니다.')
    def collect(self,species_id,question,refresh=False):
        species=self.catalog.species[species_id]; name=species['name_ko']
        name=name or species['name_en']; collection_key='collection:'+digest([species_id,question.strip()])
        old=self.cache.get(collection_key)
        if old is not None and not refresh:
            return self.index_saved(old)
        # Rights are read from the actual source, not guessed from a generic license name.
        info=self.request({'action':'query','meta':'siteinfo','siprop':'rightsinfo'})['query']['rightsinfo']
        if not info.get('text') or not info.get('url'): raise ServiceError('문서 이용 조건을 확인하지 못했습니다.')
        plan=self.llm.structured(prompt('extract_query.txt'),{'name':name,'question':question},QueryPlan,'extract_queries')
        queries=list(dict.fromkeys([name]+[q.strip() for q in plan.queries if q.strip()]))[:4]
        candidates={}
        for query in queries:
            results=self.request({'action':'query','list':'search','srsearch':query,'srlimit':4})['query'].get('search',[])
            for r in results:
                candidates[r['pageid']]={'id':r['pageid'],'title':r['title'],'snippet':html.unescape(re.sub('<[^>]+>','',r.get('snippet','')))}
        
        # 선택한 포켓몬 자체 문서를 별도로 확인
        direct = self.request({
            'action': 'query',
            'prop': 'info|pageprops',
            'titles': name + '|' + name + ' (포켓몬)',
            'redirects': 1
        })

        own = set()

        for page in direct['query'].get('pages', []):
            # 존재하지 않는 문서는 제외
            if page.get('missing'):
                continue

            # 동음이의어 문서는 자체 문서로 인정하지 않음
            if 'disambiguation' in page.get('pageprops', {}):
                continue

            # 포켓몬 이름과 문서 제목 일치 여부 확인
            if not own_title(page['title'], name):
                continue

            page_id = page['pageid']

            # 검증된 자체 문서 ID 별도 저장
            own.add(page_id)

            # 검색 후보에도 반드시 포함
            candidates[page_id] = {
                'id': page_id,
                'title': page['title'],
                'snippet': '선택 포켓몬 자체 제목의 문서'
            }

        selected=self.llm.structured(prompt('select_documents.txt'),{'name':name,'question':question,'candidates':list(candidates.values())},Selection,'select_documents') if candidates else Selection(selected_ids=[])
        chosen=own|({i for i in selected.selected_ids if i in candidates})
        docs=[]; rejected=[]; own_collected=False
        for page_id in sorted(chosen):
            data=self.request({'action':'query','prop':'extracts|info|revisions','pageids':page_id,'explaintext':1,'inprop':'url','rvprop':'ids|timestamp','redirects':1})
            pages=data['query'].get('pages',[])
            if not pages or pages[0].get('missing'): continue
            
            page = pages[0]
            text = page.get('extract', '').strip()

            # 직접 조회하여 검증된 자체 문서인지 확인
            is_own = page_id in own

            # 1. 본문이 없으면 수집 불가
            if not text:
                rejected.append({
                    'page_id': page_id,
                    'reason': '본문 없음'
                })
                continue

            # 2. 자체 문서는 키워드 제외 조건을 적용하지 않음
            if not is_own:
                if name not in text or '포켓몬' not in text:
                    rejected.append({
                        'page_id': page_id,
                        'reason': '관련성 부족'
                    })
                    continue

            revision=(page.get('revisions') or [{}])[0]
            doc={'page_id':page['pageid'],'title':page['title'],'text':text,'source_url':page.get('fullurl',''),'source_type':'external_document','species_id':species_id,'collected_at':now(),'license':info['text'],'license_url':info['url'],'revision_id':revision.get('revid'),'revision_timestamp':revision.get('timestamp'),'is_own_document':is_own,'policy_urls':POLICY_URLS}
            
            if not doc['source_url']:
                rejected.append({
                    'page_id': page_id,
                    'reason': '원문 URL 없음'
                })
                continue

            path=self.settings.runtime_dir/'documents'/f'{species_id}_{page["pageid"]}.json'
            write_json(path,doc); docs.append(str(path)); own_collected|=is_own
        manifest={'species_id':species_id,'name':name,'queries':queries,'documents':docs,'own_document_collected':own_collected,'rejected':rejected,'status':'collected' if docs else 'no_documents','completed_at':now()}
        self.cache.put(collection_key,manifest)
        write_json(self.settings.runtime_dir/'document_status'/f'{species_id}.json',manifest)
        return self.index_saved(manifest)
    def index_saved(self,manifest):
        count=changed=0
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter=RecursiveCharacterTextSplitter(chunk_size=self.settings.chunk_size,chunk_overlap=self.settings.chunk_overlap)
        for path in manifest['documents']:
            doc=json.loads(Path(path).read_text(encoding='utf-8'))
            key=f"species:{doc['species_id']}:wiki:{doc['page_id']}"
            config=digest([self.settings.chunk_size,self.settings.chunk_overlap])[:10]
            chunks=[]
            for i,text in enumerate(splitter.split_text(doc['text'])):
                meta={k:doc[k] for k in ('species_id','title','source_url','source_type','collected_at','license','license_url')}
                meta.update(document_key=key,chunk_index=i,content_hash=digest(text),is_own_document=doc['is_own_document'])
                if doc.get('revision_id') is not None: meta['revision_id']=doc['revision_id']
                chunks.append({'id':f'{key}:{config}:{i}','text':text,'metadata':meta})
            result=self.store.replace_document(key,chunks); changed+=result['changed']; count+=len(chunks)
        return {**manifest,'chunks':count,'changed_chunks':changed}
    def status(self,species_id):
        p=self.settings.runtime_dir/'document_status'/f'{species_id}.json'
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'status':'not_collected','documents':[],'own_document_collected':False}
