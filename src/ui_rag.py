"""UI adapter: only user actions invoke paid APIs or external collection."""
from urllib.parse import urlparse
from dataclasses import replace
import streamlit as st
from .llm import LanguageModel, ServiceError
from .vector_store import VectorStore
from .document_service import DocumentService
from .natural_search import NaturalSearch
from .rag import RagService, cited_sources
from .catalog import TYPE_KO

@st.cache_resource
def store_for(settings): return VectorStore(settings)
def index_counts(settings):
    try: return store_for(settings).counts()
    except Exception: return {}
def services(settings,catalog):
    store=store_for(settings); llm=LanguageModel(settings)
    docs=DocumentService(settings,catalog,store,llm)
    return RagService(settings,catalog,store,llm,docs), docs
def render_sources(answer,sources,prefix='current'):
    used=cited_sources(answer,sources)
    if not used:
        st.caption('답변에 인용된 근거가 없습니다.'); return
    with st.expander(f'답변에 사용한 근거 {len(used)}개'):
        for n,s in used:
            kind='포켓몬 메타데이터' if s['source_type']=='pokemon_metadata' else '외부 설명 문서'
            st.markdown(f"**[근거 {n}] {s['title']}** · {kind}")
            url=s.get('source_url') or s.get('url')
            if url and urlparse(url).scheme in ('http','https'): st.link_button(f'원문 보기 · 근거 {n}',url,key=f'src_{prefix}_{n}_{s["id"]}_{hash(answer)}')
            else: st.caption('원문 URL이 제공되지 않았습니다.')
            st.text(s['text'][:1400])
            if s.get('license'): st.caption('이용 조건: '+s['license'])

def render_chat(settings,catalog,pokemon_id,generation):
    st.subheader('근거를 찾아 질문하기')
    if st.session_state.pop('show_chat_hint',False): st.success('검색 결과의 포켓몬을 선택했습니다. 이 탭에서 질문을 이어가세요.')
    key=f'{pokemon_id}:{generation}'
    histories=st.session_state.setdefault('histories',{}); messages=histories.setdefault(key,[])
    if st.button('이 포켓몬의 대화 지우기',key='clear_chat'):
        messages.clear(); st.rerun()
    collect_for_question=st.checkbox('질문에 맞는 외부 문서 추가 수집',value=settings.auto_collect,help='검색어 추출·후보 선별에 추가 API 호출이 발생합니다. 이미 수집한 검색어와 문서는 캐시를 사용합니다.')
    try: rag,docs=services(replace(settings,auto_collect=collect_for_question),catalog)
    except Exception:
        st.error('RAG 저장소를 열지 못했습니다. 설치 상태와 임베딩 설정을 확인하세요.'); return
    sid=catalog.varieties[pokemon_id]['species_id']
    status=docs.status(sid)
    if not status.get('documents'): st.info('이 포켓몬의 외부 문서는 아직 없습니다. 아래 버튼으로 문서를 수집하거나 메타데이터만으로 질문할 수 있습니다.')
    elif not status.get('own_document_collected'): st.warning('관련 문서는 있으나 선택 포켓몬 자체 문서를 아직 확보하지 못했습니다.')
    else: st.caption(f"외부 문서 {len(status['documents'])}개 · 검색 근거 최대 {settings.top_k}개")
    if st.button('이 포켓몬의 외부 문서 수집·색인',disabled=not bool(settings.api_key)):
        with st.status('검색어 추출 → 후보 선별 → 본문 수집 → 색인',expanded=True) as progress:
            try:
                result=docs.collect(sid,'특성, 진화, 세대별 특징을 설명해 줘.')
                progress.update(label=f"문서 {len(result['documents'])}개 · 청크 {result['chunks']}개",state='complete')
                if not result.get('own_document_collected'): st.warning('선택 포켓몬 자체 문서를 확인하지 못했습니다. 수집 결과를 확인하세요.')
                st.rerun()
            except ServiceError as e: progress.update(label='문서 수집을 완료하지 못했습니다.',state='error'); st.warning(str(e))
            except Exception: progress.update(label='문서 색인에 실패했습니다. 기존 데이터는 유지됩니다.',state='error')
    indexed=bool(rag.store.get_meta(pokemon_id,generation))
    if not settings.api_key: st.warning('AI 서비스 키가 없습니다. .env에서 LLM_PROVIDER와 해당 API 키를 설정하세요.')
    if not indexed: st.warning('선택한 포켓몬의 메타데이터 색인이 없습니다. scripts/index_pokemon.py를 먼저 실행하세요.')
    for position,m in enumerate(messages):
        with st.chat_message(m['role']):
            st.markdown(m['content'])
            if m['role']=='assistant':
                # A stable per-message container avoids duplicate link-button keys.
                with st.container(key=f'message_{key}_{position}'): render_sources(m['content'],m.get('sources',[]),prefix=f'{key}_{position}')
    question=st.chat_input('선택한 포켓몬에 대해 질문하세요.',disabled=not settings.api_key or not indexed,max_chars=2000,key='pokemon_question')
    if question:
        prior=list(messages)
        messages.append({'role':'user','content':question})
        with st.chat_message('user'): st.markdown(question)
        with st.chat_message('assistant'):
            with st.status('관련 근거를 검색하고 답변을 작성합니다…',expanded=False) as progress:
                try:
                    result=rag.ask(pokemon_id,generation,question,prior)
                    progress.update(label='답변과 근거 번호 확인 완료',state='complete')
                    st.markdown(result['answer']); render_sources(result['answer'],result['sources'])
                    for message in result.get('warnings',[]): st.caption(message)
                    messages.append({'role':'assistant','content':result['answer'],'sources':result['sources']})
                except ServiceError as e: progress.update(label='답변을 완료하지 못했습니다.',state='error'); st.warning(str(e))
                except Exception: progress.update(label='답변 처리에 실패했습니다.',state='error'); st.error('연결과 색인 상태를 확인한 뒤 다시 질문해 주세요.')

def render_natural_search(settings,catalog,ui_generation,image_dir):
    st.subheader('AI 자연어 포켓몬 탐색')
    with st.form('natural_search_form'):
        question=st.text_input('원하는 포켓몬 조건',placeholder='스피드 100 이상인 불꽃 타입 포켓몬 알려줘.',max_chars=2000)
        submitted=st.form_submit_button('AI로 찾아보기',disabled=not bool(settings.api_key))
    if not settings.api_key: st.caption('API 키 설정 후 자연어 검색을 사용할 수 있습니다. 위의 선택형 검색은 키 없이 동작합니다.')
    st.caption(f'상대 조건 기준: 빠름 {settings.high_speed}, 높은 공격 {settings.high_attack}, 높은 방어 {settings.high_defense}, 높은 특수공격 {settings.high_special_attack} 이상. .env에서 조정할 수 있습니다.')
    if submitted and question.strip():
        with st.status('조건 추출 → 실제 수치 필터 → AI 후보 선별',expanded=False) as progress:
            try:
                result=NaturalSearch(settings,catalog,LanguageModel(settings)).run(question,ui_generation)
                st.session_state['natural_result']=result
                progress.update(label=f"조건을 만족하는 후보 {result['candidate_count']}개",state='complete')
            except ServiceError as e: st.session_state.pop('natural_result',None); progress.update(label='검색을 완료하지 못했습니다.',state='error'); st.warning(str(e))
            except Exception: st.session_state.pop('natural_result',None); progress.update(label='검색 결과 처리에 실패했습니다.',state='error')
    result=st.session_state.get('natural_result')
    if not result: return
    st.caption(f"{result['generation']}세대 · 숫자/타입 조건을 실제 JSONL 데이터로 검증했습니다. 게임별 등장 여부는 미확인입니다.")
    with st.expander('추출한 조건 확인'): st.json({'filters':result['filters'],'applied_thresholds':result['thresholds']})
    if not result['results']: st.info('조건에 맞는 추천 결과가 없습니다. 조건을 바꿔 다시 검색해 주세요.'); return
    columns=st.columns(2)
    for i,item in enumerate(result['results']):
        r=item['row']; pid=r['pokemon_id']; name=catalog.species[r['species_id']]['name_ko']
        with columns[i%2],st.container(border=True):
            image=image_dir/'official'/f'{pid}.png'
            if image.is_file(): st.image(str(image),width=150)
            st.markdown(f'**{name} · 전국도감 #{r["species_id"]}**')
            st.caption(catalog.varieties[pid]['api_name']+f" · {r['generation']}세대")
            st.write(' / '.join(TYPE_KO.get(t,t) for t in r['types'] or []))
            st.write(f"공격 {r['stats'].get('attack')} · 방어 {r['stats'].get('defense')} · 특수공격 {r['stats'].get('special_attack')} · 스피드 {r['stats'].get('speed')}")
            st.write('AI 추천 이유: '+item['reason'])
            if item['verified_reason']: st.caption('수치 검증: '+item['verified_reason'])
            st.link_button('추천 근거 · 포켓몬 메타데이터',r['source_url'],key=f'natural_source_{pid}')
            if st.button('이 포켓몬 선택하고 질문하기',key=f'choose_{pid}'):
                st.session_state['pending_pokemon']={'pokemon_id':pid,'generation':r['generation']}; st.rerun()
