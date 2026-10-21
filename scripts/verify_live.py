"""Explicit real-API integration verification; results separate from mocked tests."""
import argparse, hashlib, json, os, sys, time, uuid
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.settings import Settings, ROOT
from src.catalog import Catalog
from src.vector_store import VectorStore
from src.llm import LanguageModel, ServiceError
from src.document_service import DocumentService
from src.rag import RagService, validate_citations, cited_sources
from src.natural_search import NaturalSearch
from src.storage import now, write_json

def qa(settings):
    db=Catalog(settings.data_dir); store=VectorStore(settings); llm=LanguageModel(settings)
    service=RagService(settings,db,store,llm,DocumentService(settings,db,store,llm))
    cases=[(25,9,'피카츄의 특성은 무엇이야?'),(94,9,'팬텀의 특성은 6세대와 7세대에서 어떻게 달라졌어?'),(133,9,'이브이는 어떤 방법으로 진화할 수 있어?'),(35,9,'삐삐는 언제부터 페어리 타입이 되었어?'),(25,9,'실제 문서에 없는 가상의 포켓몬 특성을 알려줘.')]
    results=[]
    for pid,gen,question in cases:
        started=time.monotonic()
        try:
            r=service.ask(pid,gen,question)
            valid=validate_citations(r['answer'],r['sources'])
            terms={25:['정전기','피뢰침'],94:['부유','저주받은바디'],133:['샤미드','진화'],35:['6세대','페어리']}[pid]
            if '가상의' in question: valid=valid and not cited_sources(r['answer'],r['sources']) and '확인되지' in r['answer']
            else: valid=valid and all(t in r['answer'].replace(' ','') for t in terms)
            results.append({'question':question,'status':'passed' if valid else 'review_required','answer':r['answer'],'used_sources':[{'number':n,'title':s['title'],'source_url':s.get('source_url'),'source_type':s['source_type']} for n,s in cited_sources(r['answer'],r['sources'])],'seconds':round(time.monotonic()-started,2)})
        except Exception as e: results.append({'question':question,'status':'failed','error_type':type(e).__name__,'message':str(e) if isinstance(e,ServiceError) else 'integration failure'})
        print('QA',len(results),results[-1]['status'],flush=True)
    write_json(settings.runtime_dir/'live_qa_report.json',{'at':now(),'real_api':True,'results':results}); return results

def natural(settings):
    db=Catalog(settings.data_dir); service=NaturalSearch(settings,db,LanguageModel(settings)); results=[]
    cases=[('빠르고 공격력이 높은 전기 타입 포켓몬 찾아줘.',{'types':['electric'],'high_speed':True,'high_attack':True}),('9세대에서 공격력 120 이상인 포켓몬 추천해 줘.',{'generation':9,'min_attack':120}),('방어력이 높은 물 타입 포켓몬 찾아줘.',{'types':['water'],'high_defense':True}),('스피드 100 이상인 불꽃 타입 포켓몬 알려줘.',{'types':['fire'],'min_speed':100})]
    for question,expected in cases:
        try:
            r=service.run(question,9)
            valid=all(r['filters'].get(k)==v for k,v in expected.items()) and bool(r['results'])
            for item in r['results']:
                row=item['row']
                if expected.get('types'): valid=valid and set(expected['types'])<=set(row['types'])
                for stat in ('attack','defense','speed'):
                    minimum=expected.get('min_'+stat) or (getattr(settings,'high_'+stat) if expected.get('high_'+stat) else None)
                    if minimum: valid=valid and row['stats'][stat]>=minimum
            results.append({'question':question,'status':'passed' if valid else 'review_required','filters':r['filters'],'thresholds':r['thresholds'],'candidate_count':r['candidate_count'],'recommended_ids':[i['row']['pokemon_id'] for i in r['results']]})
        except Exception as e: results.append({'question':question,'status':'failed','error_type':type(e).__name__,'message':str(e) if isinstance(e,ServiceError) else 'integration failure'})
        print('NATURAL',len(results),results[-1]['status'],flush=True)
    write_json(settings.runtime_dir/'live_natural_report.json',{'at':now(),'real_api':True,'results':results}); return results

def ui(settings,live=False):
    from streamlit.testing.v1 import AppTest
    results={}
    a=AppTest.from_file(str(ROOT/'app.py'),default_timeout=120).run()
    results['initial_render']=not bool(a.exception); results['tabs']=[t.label for t in a.tabs]
    a.sidebar.text_input[0].set_value('피카츄').run(); results['pikachu_selection']=not bool(a.exception)
    a.sidebar.selectbox[1].select(1).run(); results['generation_one']=not bool(a.exception)
    a.sidebar.selectbox[1].select(9).run()
    if live:
        a.chat_input[0].set_value('피카츄의 특성은 무엇이야?').run()
        results['live_chat_render']=not bool(a.exception) and bool(a.session_state['histories'].get('25:9',[])) and len(a.session_state['histories']['25:9'])==2
        results['live_chat_source_expander']=any('답변에 사용한 근거' in e.label for e in a.expander)
        a.sidebar.text_input[0].set_value('팬텀').run()
        results['history_separation']=not bool(a.exception) and not a.session_state['histories'].get('94:9',[]) and len(a.session_state['histories']['25:9'])==2
        field=next(x for x in a.text_input if x.label=='원하는 포켓몬 조건')
        field.set_value('스피드 100 이상인 불꽃 타입 포켓몬 알려줘.')
        next(b for b in a.button if b.label=='AI로 찾아보기').click().run()
        results['natural_cards_render']=not bool(a.exception) and bool(a.session_state['natural_result']['results'])
        chosen=a.session_state['natural_result']['results'][0]['row']
        next(b for b in a.button if b.label=='이 포켓몬 선택하고 질문하기').click().run()
        results['card_navigation']=not bool(a.exception) and a.sidebar.selectbox[0].value==chosen['pokemon_id'] and a.sidebar.selectbox[1].value==chosen['generation'] and a.session_state['preferred_tab']=='질문하기'
    a.sidebar.text_input[0].set_value('없는이름테스트').run(); results['empty_search']=not bool(a.exception)
    from unittest.mock import patch
    with patch.dict(os.environ,{'LLM_PROVIDER':'gms','GMS_KEY':''}):
        b=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        results['missing_key_notice']=not bool(b.exception) and any('키가 없습니다' in x.value for x in b.warning) and b.chat_input[0].disabled
    with patch.dict(os.environ,{'CHROMA_DIR':str(settings.runtime_dir/('empty-ui-test-'+uuid.uuid4().hex))}):
        b=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        results['missing_index_notice']=not bool(b.exception) and any('메타데이터 색인이 없습니다' in x.value for x in b.warning) and b.chat_input[0].disabled
    write_json(settings.runtime_dir/('ui_live_report.json' if live else 'ui_report.json'),{'at':now(),'results':results,'exceptions':[str(e.value)[:200] for e in a.exception]})
    print(json.dumps(results,ensure_ascii=True)); return results

def report(settings):
    report={'at':now(),'collections':VectorStore(settings).counts(),'reports':{}}
    for name in ('metadata_index_report','document_collection_report','live_qa_report','live_natural_report','ui_live_report','ui_report'):
        p=settings.runtime_dir/(name+'.json')
        if p.exists(): report['reports'][name]=json.loads(p.read_text(encoding='utf-8'))
    logs=settings.runtime_dir/'usage.jsonl'; counts=Counter(); tokens=Counter()
    if logs.exists():
        for line in logs.read_text(encoding='utf-8').splitlines():
            r=json.loads(line); counts[r['kind']]+=1
            for k in ('input_tokens','output_tokens','total_tokens'): tokens[k]+=r.get(k) or 0
    report['usage']={'event_counts':dict(counts),'tokens':dict(tokens),'note':'Token fields are those returned by the services; retries may include additional server-side usage.'}
    backups=sorted((ROOT/'.local/backups').glob('*/protected_hashes.json'))
    if backups:
        hashes=json.loads(backups[0].read_text(encoding='utf-8')); changed=[p for p,h in hashes.items() if not (ROOT/p).exists() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
        report['protected_data']={'checked_files':len(hashes),'changed':changed}
    write_json(ROOT/'docs/RAG_VERIFICATION.json',report)
    print(json.dumps({'collections':report['collections'],'usage':report['usage'],'protected_data':report.get('protected_data')},ensure_ascii=True,indent=2)); return report

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--qa',action='store_true'); p.add_argument('--natural',action='store_true'); p.add_argument('--ui',action='store_true'); p.add_argument('--ui-live',action='store_true'); p.add_argument('--report',action='store_true'); a=p.parse_args(); s=Settings.load()
    if a.qa: qa(s)
    if a.natural: natural(s)
    if a.ui or a.ui_live: ui(s,a.ui_live)
    if a.report: report(s)
