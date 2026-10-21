"""F2010: deterministic comparisons and a cached adapter for the existing RAG graph."""
import json
import re
from dataclasses import replace
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from .catalog import TYPE_KO, STAT_KO, stat_total
from .llm import ServiceError
from .storage import Cache, digest

COMPARISON_INSTRUCTIONS = '''
이번 요청은 AI 세대별 변화 분석이다. python_comparison은 Python으로 판정한 결과다.
계산하거나 변경 여부를 다시 추측하지 말고 changed 항목만 간결하게 설명한다.
모든 change 주장에는 두 세대의 메타데이터 근거 번호를 모두 인용한다.
unknown/not_comparable은 실제 변경으로 해석하지 않는다. 1세대 특수와 이후 특수공격/특수방어를 비교하지 않는다.
변경 이유·의도·밸런스·성능 영향은 외부 문서가 명시한 경우에만 kind=reason으로 쓴다.
reason의 evidence_quote에는 그 이유를 직접 명시한 외부 문서의 원문을 그대로 복사한다.
이유의 근거가 없으면 reason 주장을 생성하지 않는다. 메타데이터는 변경 이유의 증거가 아니다.
각 주장은 text, citations, kind(change/reason), evidence_quote를 가진다. change의 evidence_quote는 빈 문자열이다.
'''
CAUSAL = re.compile(r'때문|이유|위해|위하여|의도|목적|밸런스|덕분|성능|유리|불리|강화|약화|because|due to|in order|reason',re.I)

class ComparisonClaim(BaseModel):
    model_config=ConfigDict(extra='forbid')
    text:str=Field(min_length=1,max_length=2000)
    citations:list[StrictInt]=Field(min_length=1,max_length=20)
    kind:Literal['change','reason']='change'
    evidence_quote:str=Field(default='',max_length=1200)

class ComparisonAnswer(BaseModel):
    model_config=ConfigDict(extra='forbid')
    claims:list[ComparisonClaim]=Field(max_length=20)
    not_found:bool=False

def compare_generations(catalog,pokemon_id,before_generation,after_generation):
    result={'pokemon_id':pokemon_id,'before_generation':before_generation,'after_generation':after_generation,'status':'ready','has_changes':False,'fields':[]}
    if before_generation==after_generation:
        return dict(result,status='same_generation',message='서로 다른 두 세대를 선택하세요.')
    if before_generation>after_generation:
        return dict(result,status='invalid_order',message='이후 세대는 이전 세대보다 뒤의 세대로 선택하세요.')
    before=catalog.index.get((pokemon_id,before_generation)); after=catalog.index.get((pokemon_id,after_generation))
    if before is None or after is None:
        return dict(result,status='missing_generation',message='선택한 포켓몬의 비교 대상 세대 데이터가 없습니다.')
    result.update(species_id=before['species_id'],name_ko=before['name_ko'])
    def add(key,label,a,b,display=None,comparable=True,note=''):
        status='not_comparable' if not comparable else 'unknown' if a is None or b is None else 'changed' if a!=b else 'unchanged'
        item={'key':key,'label':label,'before':a,'after':b,'status':status,'delta':b-a if status in ('changed','unchanged') and isinstance(a,(int,float)) and isinstance(b,(int,float)) else None,'note':note}
        fmt=display or (lambda v:'미확인' if v is None else str(v))
        item.update(before_display=fmt(a),after_display=fmt(b)); result['fields'].append(item)
    type_display=lambda v:'미확인' if v is None else ' / '.join(TYPE_KO.get(t,t) for t in v) or '없음'
    add('types','타입',sorted(before['types']) if before.get('types') is not None else None,sorted(after['types']) if after.get('types') is not None else None,type_display)
    for hidden,label in ((False,'일반 특성'),(True,'숨겨진 특성')):
        def ability_list(row):
            return None if row.get('abilities') is None else sorted({a['name'] for a in row['abilities'] if a['is_hidden']==hidden})
        introduced=5 if hidden else 3
        def fmt_ability(values): return '미확인' if values is None else ', '.join(catalog.ability_names.get(v,v) for v in values) or '없음'
        add('hidden_abilities' if hidden else 'abilities',label,ability_list(before),ability_list(after),fmt_ability,comparable=before_generation>=introduced,note='도입 이전 세대는 변경 판정에서 제외합니다.' if before_generation<introduced else '')
        if before_generation<introduced: result['fields'][-1]['before_display']='도입 이전'
        if after_generation<introduced: result['fields'][-1]['after_display']='도입 이전'
    for key in ('hp','attack','defense','special','special_attack','special_defense','speed'):
        if key=='special' and before_generation!=1 and after_generation!=1: continue
        comparable=(before_generation==after_generation==1) if key=='special' else before_generation>1 if key in ('special_attack','special_defense') else True
        note='1세대 특수와 이후 특수공격·특수방어는 서로 다른 항목입니다.' if not comparable else ''
        add(key,STAT_KO[key],before['stats'].get(key),after['stats'].get(key),comparable=comparable,note=note)
        if not comparable:
            field=result['fields'][-1]
            if field['before'] is None: field['before_display']='미정의'
            if field['after'] is None: field['after_display']='미정의'
    comparable_total=(before_generation==1)==(after_generation==1)
    add('total','종족값 합계',stat_total(before),stat_total(after),comparable=comparable_total,note='1세대 5항목 합계와 이후 6항목 합계는 직접 비교하지 않습니다.' if not comparable_total else '')
    result['has_changes']=any(f['status']=='changed' for f in result['fields'])
    if not result['has_changes']: result.update(status='unchanged',message='확인 가능한 항목에서 변경 사항이 없습니다. AI를 호출하지 않습니다.')
    result['input_hash']=digest([before,after,catalog.ability_names])
    return result

def comparison_snapshot(comparison,generation):
    side='before' if generation==comparison['before_generation'] else 'after'
    fields={f['label']:{'value':f[side],'한국어_표시':f[side+'_display']} for f in comparison['fields'] if f['status']!='unchanged'}
    return json.dumps({'포켓몬':comparison['name_ko'],'세대':generation,'비교_관련_메타데이터':fields},ensure_ascii=False)

def reason_quote(claim,sources):
    """Only render an exact, explicitly causal quote from a cited external chunk."""
    quote=claim.evidence_quote.strip()
    if not quote or not CAUSAL.search(quote): return None
    for number in claim.citations:
        source=sources[number-1]
        if source['source_type']=='external_document' and quote in source['text']:
            return quote,number
    return None

def analyze_comparison(rag,comparison):
    if not comparison.get('has_changes'):
        return {'answer':comparison.get('message','비교할 변경 사항이 없습니다.'),'sources':[],'skipped':True,'cached':False}
    sid=comparison['species_id']; pid=comparison['pokemon_id']
    meta=[rag.store.get_meta(pid,g) for g in (comparison['before_generation'],comparison['after_generation'])]
    docs=rag.store.collections['pokemon_docs'].get(where={'species_id':sid},include=['metadatas'])
    corpus=sorted(zip(docs['ids'],docs['metadatas']),key=lambda pair:pair[0])
    from .document_service import prompt
    settings=rag.settings
    key='generation-comparison:v1:'+digest([comparison,meta,corpus,str(settings.chroma_dir),settings.provider,settings.base_url,settings.chat_model,settings.embedding_model,settings.top_k,settings.chunk_size,settings.chunk_overlap,prompt('generate_answer.txt'),COMPARISON_INSTRUCTIONS])
    cache=Cache(settings.runtime_dir); old=cache.get(key)
    if old is not None: return dict(old,cached=True)
    rag.llm.check_key()
    question=f"{comparison['name_ko']}의 {comparison['before_generation']}세대에서 {comparison['after_generation']}세대까지 타입·일반/숨겨진 특성·종족값 변화와 문서에 명시된 변경 이유를 분석해 주세요."
    result=rag.graph.invoke({'pokemon_id':pid,'generation':comparison['after_generation'],'question':question,'history':[],'comparison':comparison})
    cache.put(key,result)
    return dict(result,cached=False)

def render_generation_analysis(settings,catalog,pokemon_id):
    import streamlit as st
    from .ui_rag import services,render_sources
    st.divider(); st.subheader('AI 세대별 변화 분석')
    generations=[r['generation'] for r in catalog.records_for(pokemon_id)]
    if len(generations)<2:
        st.info('비교 가능한 세대 데이터가 두 개 이상 필요합니다.'); return
    left,right=st.columns(2)
    before=left.selectbox('이전 세대',generations,index=max(0,len(generations)-2),format_func=lambda g:f'{g}세대',key=f'compare_before_{pokemon_id}')
    after=right.selectbox('이후 세대',generations,index=len(generations)-1,format_func=lambda g:f'{g}세대',key=f'compare_after_{pokemon_id}')
    comparison=compare_generations(catalog,pokemon_id,before,after)
    if comparison['fields']:
        statuses={'changed':'변경','unchanged':'동일','unknown':'데이터 미확인','not_comparable':'비교 불가'}
        st.dataframe([{'항목':f['label'],'이전':f['before_display'],'이후':f['after_display'],'차이':f"{f['delta']:+g}" if f['delta'] is not None else '—','판정':statuses[f['status']]} for f in comparison['fields']],hide_index=True,width='stretch')
        notes=list(dict.fromkeys(f['note'] for f in comparison['fields'] if f['note']))
        for note in notes: st.caption(note)
        if any(f['status']=='unknown' for f in comparison['fields']): st.caption('데이터 미확인은 변경이 없다는 뜻이 아닙니다.')
    if comparison['status']!='ready': st.info(comparison['message'])
    if not settings.api_key: st.caption('AI 분석에는 기존 API 키 설정이 필요합니다. 데이터 비교는 키 없이 동작합니다.')
    # Rendering and selector changes perform no retrieval, embedding, or LLM calls.
    result_key=digest([comparison,settings.provider,settings.base_url,settings.chat_model,settings.embedding_model,settings.top_k,settings.chunk_size,settings.chunk_overlap,str(settings.chroma_dir)])
    saved=st.session_state.setdefault('generation_analyses',{})
    if st.button('AI 변화 분석',key='analyze_generation_changes',disabled=not comparison['has_changes'] or not settings.api_key):
        with st.status('두 세대 근거 검색 → 확인된 변화 설명',expanded=False) as progress:
            try:
                rag,_=services(replace(settings,auto_collect=False),catalog)
                saved[result_key]=analyze_comparison(rag,comparison)
                progress.update(label='저장된 분석 결과' if saved[result_key].get('cached') else '분석과 인용 검증 완료',state='complete')
            except ServiceError as exc: progress.update(label='분석을 완료하지 못했습니다.',state='error'); st.warning(str(exc))
            except Exception: progress.update(label='분석 처리에 실패했습니다.',state='error'); st.error('색인과 연결 상태를 확인해 주세요.')
    result=saved.get(result_key)
    if result:
        st.markdown(result['answer'])
        render_sources(result['answer'],result['sources'],prefix=f'generation_compare_{result_key}')
        for warning in result.get('warnings',[]): st.caption(warning)
