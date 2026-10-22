"""UI adapter: only user actions invoke paid APIs or external collection."""
from urllib.parse import urlparse
from dataclasses import replace
import logging
import traceback
import streamlit as st
from .llm import LanguageModel, ServiceError, error_diagnostic
from .vector_store import VectorStore
from .document_service import DocumentService
from .natural_search import NaturalSearch
from .rag import RagService, cited_sources, catch_targets
from .catalog import TYPE_KO
logger=logging.getLogger(__name__)

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

def render_conversation(messages,reply,*,prefix,placeholder,disabled=False,avatar=None,scrolling=False,catalog=None):
    """Render only persisted messages; each turn keeps a stable DOM/source identity."""
    from uuid import uuid4
    for message in messages: message.setdefault('id',uuid4().hex)
    conversation=st.container(height=400,key='oak_messages',autoscroll=True) if scrolling else st.container()
    busy=any(m.get('status')=='pending' for m in messages)
    with conversation:
        if not messages and scrolling: st.caption('트레이너, 궁금한 포켓몬을 물어보게. 세대를 생략하면 9세대 기준으로 살펴보겠네.')
        for position,message in enumerate(messages):
            with st.container(key=f'chat_{prefix}_{message["id"]}'):
                with st.chat_message(message['role'],avatar=avatar if message['role']=='assistant' else None):
                    if avatar and message['role']=='assistant': st.caption('오박사')
                    if message.get('status')=='pending':
                        parent=next(m for m in messages if m['id']==message['reply_to'])
                        prior=[m for m in messages[:messages.index(parent)] if m.get('status')!='error']
                        with st.spinner('오박사가 연구 자료를 살펴보고 있네…'):
                            try:
                                result=reply(parent['content'],prior)
                                message.update(content=result['answer'],sources=result.get('sources',[]),basis=result.get('basis',''),warnings=result.get('warnings',[]),status='complete')
                            except Exception as error:
                                diagnostic=error_diagnostic(error)
                                logger.error('Chat request failed: %s',diagnostic)
                                from .storage import Metrics
                                from .settings import Settings
                                try: Metrics(Settings.load().runtime_dir).record('chat_failure',**diagnostic)
                                except OSError: logger.error('Chat diagnostic file unavailable')
                                category=diagnostic['category']
                                notice='연결이 잠시 원활하지 않구나. 잠시 후 다시 시도해 보게.' if category=='connection' else 'AI 연결 설정을 확인해야겠구나. 관리자에게 알려 주게.' if category=='configuration' else '근거 또는 답변 검증 중 문제가 생겼구나. 관리자에게 알려 주게.' if category=='validation' else '데이터 처리 중 오류가 발생했구나. 관리자에게 알려 주게.'
                                message.update(content=notice,sources=[],status='error',retryable=category in ('connection','validation'))
                        st.rerun()
                    st.markdown(message['content'])
                    if message['role']=='assistant':
                        if catalog is not None and message.get('status')!='error':
                            targets=message.setdefault('catch_targets',catch_targets(catalog,message['content'],message.get('sources',[])))
                            if targets:
                                choices={t['pokemon_id']:t['name']+(' · '+t['form'] if t['form']!='일반형' else '') for t in targets}
                                pid=next(iter(choices)) if len(choices)==1 else st.selectbox('잡으러 갈 포켓몬',list(choices),format_func=choices.get,key=f'hunt_choice_{message["id"]}')
                                label='이 포켓몬을 잡으러 가볼까?' if len(choices)==1 else '잡으러 가기'
                                if st.button(label,key=f'hunt_{message["id"]}',disabled=busy):
                                    from .game_ui import request_hunt
                                    if request_hunt(catalog,pid,set(choices)): st.rerun(scope='app')
                                    st.info('현재 9세대 일반형 출현 데이터에서 이 포켓몬이 등장할 지역을 확인하지 못했네.')
                        if message.get('basis'): st.caption(message['basis'])
                        if message.get('status')!='error': render_sources(message['content'],message.get('sources',[]),prefix=message['id'])
                        for warning in message.get('warnings',[]): st.caption(warning)
                        if message.get('status')=='error' and message.get('retryable',True) and st.button('다시 시도',key=f'retry_{message["id"]}',disabled=busy or disabled):
                            message.update(content='',status='pending'); st.rerun()
    question=st.chat_input(placeholder,disabled=disabled or busy,max_chars=2000,key=f'{prefix}_pokemon_question' if prefix!='selected' else 'pokemon_question')
    if question and not busy:
        question_id=uuid4().hex
        messages.extend([{'id':question_id,'role':'user','content':question},{'id':uuid4().hex,'reply_to':question_id,'role':'assistant','content':'','status':'pending','sources':[]}])
        st.rerun()


def render_global_chat(settings,catalog,key_prefix='global'):
    from pathlib import Path
    oak_avatar=str(Path(__file__).resolve().parents[1]/'static/regions/professor.jpg')
    css=(Path(__file__).parent/'oak_chat.css').read_text(encoding='utf-8')
    st.markdown('<style>'+css+'</style>',unsafe_allow_html=True)
    with st.container(key='oak_chat'):
        with st.container(key='oak_header',horizontal=True,vertical_alignment='center'):
            st.image(oak_avatar,width=48)
            st.markdown('**오박사의 연구실**  \n포켓몬에 대해 무엇이든 물어보세요')
        messages=st.session_state.setdefault('global_history',[])
        if st.button('전체 포켓몬 대화 지우기',key=f'clear_{key_prefix}_chat'):
            messages.clear(); st.rerun()
        def reply(question,prior):
            rag,_=services(replace(settings,auto_collect=False),catalog)
            result=rag.ask_global(question,prior)
            gens=sorted({source['generation'] for source in result.get('sources',[]) if source.get('generation')})
            basis=' · '.join(f'{g}세대' for g in gens) if len(gens)>1 else f"{result['generation']}세대 기준"
            context=result.get('search_context',{})
            if 'candidate_count' in context: basis+=f" · 조건 일치 {context['candidate_count']}개 형태 · 최대 {settings.result_limit}개 근거 제시"
            return dict(result,basis=basis)
        render_conversation(messages,reply,prefix=key_prefix,placeholder='포켓몬 이름, 비교 또는 원하는 조건을 자유롭게 질문하세요.',avatar=oak_avatar,scrolling=True,catalog=catalog)


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
    render_conversation(messages,lambda question,prior:rag.ask(pokemon_id,generation,question,prior),prefix='selected',placeholder='선택한 포켓몬에 대해 질문하세요.',disabled=not settings.api_key or not indexed,catalog=catalog)


def render_natural_search(settings,catalog,ui_generation,image_dir):
    st.subheader('AI 자연어 포켓몬 탐색')
    with st.form('natural_search_form'):
        question=st.text_input('원하는 포켓몬 조건',placeholder='스피드 100 이상인 불꽃 타입 포켓몬 알려줘.',max_chars=2000)
        submitted=st.form_submit_button('AI로 찾아보기')
    if not settings.api_key: st.caption('명확한 특성 검색은 API 키 없이 사용할 수 있어요. 복잡한 자연어 조건에는 API 키가 필요해요.')
    st.caption(f'상대 조건 기준: 빠름 {settings.high_speed}, 높은 공격 {settings.high_attack}, 높은 방어 {settings.high_defense}, 높은 특수공격 {settings.high_special_attack} 이상. .env에서 조정할 수 있습니다.')
    if submitted and question.strip():
        with st.status('조건 추출 → 실제 수치 필터 → AI 후보 선별',expanded=False) as progress:
            try:
                result=NaturalSearch(settings,catalog,LanguageModel(settings)).run(question,ui_generation)
                st.session_state['natural_result']=result
                progress.update(label=f"조건을 만족하는 후보 {result['candidate_count']}개",state='complete')
            except ServiceError as e:
                logger.warning('Natural search service/validation failure: %s',str(e))
                st.session_state.pop('natural_result',None); progress.update(label='검색 조건이나 연결 상태를 확인해 주세요.',state='error'); st.warning(str(e))
            except Exception as e:
                frames=[(f.filename,f.lineno,f.name) for f in traceback.extract_tb(e.__traceback__)]
                logger.error('Natural search unexpected failure: %s; frames=%s',type(e).__name__,frames)
                st.session_state.pop('natural_result',None); progress.update(label='검색 처리 중 오류가 발생했어요.',state='error'); st.error('검색을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.')
    result=st.session_state.get('natural_result')
    if not result: return
    st.caption(f"{result['generation']}세대 기준 검색 결과 · 타입·특성·수치 조건을 실제 데이터로 검증했어요. 게임별 등장 여부는 미확인이에요.")
    with st.expander('추출한 조건 확인'): st.json({'filters':result['filters'],'applied_thresholds':result['thresholds']})
    if not result['results']: st.info('조건에 맞는 포켓몬이 없습니다. 조건이나 검색 세대를 바꿔 주세요.'); return
    columns=st.columns(2)
    for i,item in enumerate(result['results']):
        r=item['row']; pid=r['pokemon_id']; name=catalog.species[r['species_id']]['name_ko']
        with columns[i%2],st.container(border=True):
            image=image_dir/'official'/f'{pid}.png'
            if image.is_file(): st.image(str(image),width=150)
            st.markdown(f'**{name} · 전국도감 #{r["species_id"]}**')
            st.caption(catalog.varieties[pid]['api_name']+f" · {r['generation']}세대")
            st.write(' / '.join(TYPE_KO.get(t,t) for t in r['types'] or []))
            stat=lambda k:'미확인' if r['stats'].get(k) is None else r['stats'][k]
            st.write(f"공격 {stat('attack')} · 방어 {stat('defense')} · 특수공격 {stat('special_attack')} · 스피드 {stat('speed')}")
            for ability in item.get('matched_abilities',[]):
                st.write(f"일치한 특성: {ability['name_ko']} · {'숨겨진 특성' if ability['is_hidden'] else '일반 특성'}")
            st.write(('조건 일치 이유: ' if result.get('selection_mode')=='local_ability' else 'AI 추천 이유: ')+item['reason'])
            if item['verified_reason']: st.caption('수치 검증: '+item['verified_reason'])
            st.link_button('추천 근거 · 포켓몬 메타데이터',r['source_url'],key=f'natural_source_{pid}')
            if st.button('이 포켓몬 선택하고 질문하기',key=f'choose_{pid}'):
                st.session_state['pending_pokemon']={'pokemon_id':pid,'generation':r['generation']}; st.rerun()
