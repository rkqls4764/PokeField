"""Based on the supplied step7 UI concepts; backed by the collected Pokémon data."""
import os
import streamlit as st
from src.catalog import Catalog, TYPE_KO
from src.settings import Settings
from src.rag import cited_sources

st.set_page_config(page_title='Pokémon Lab', page_icon='🔎', layout='wide')
st.title('Pokémon Lab')
st.caption('세대에 따라 달라지는 포켓몬 정보를 원본 데이터와 함께 살펴보세요.')

@st.cache_resource
def catalog(path): return Catalog(path)

try:
    config=Settings.load()
    with st.spinner('포켓몬 데이터를 불러오는 중…'): db=catalog(str(config.data_dir))
except (FileNotFoundError, ValueError, KeyError):
    st.error('데이터를 불러오지 못했습니다. .env의 POKEMON_DATA_DIR와 수집 데이터 파일을 확인하세요.')
    st.stop()

with st.sidebar:
    st.header('포켓몬 찾기')
    query=st.text_input('이름 검색',placeholder='피카츄 또는 pikachu')
    ids=[i for i in db.varieties if query.lower() in db.label(i).lower()]
    if not ids:
        st.info('일치하는 포켓몬이 없습니다.'); st.stop()
    pokemon_id=st.selectbox('포켓몬과 형태',ids,format_func=db.label)
    rows=db.records_for(pokemon_id)
    if not rows:
        st.info('이 형태의 세대 정보가 확인되지 않았습니다.'); st.stop()
    generation=st.selectbox('세대',[r['generation'] for r in rows],index=len(rows)-1,format_func=lambda x:f'{x}세대')
    st.divider()
    st.metric('수집된 포켓몬 종',len(db.species))
    st.caption('RAG 색인: 아직 연결되지 않음')
    if not (os.getenv('GMS_KEY') or os.getenv('OPENAI_API_KEY')):
        st.caption('AI 답변 연결에는 API 키 설정이 필요합니다.')

row=db.index[(pokemon_id,generation)]
overview, compare, search, chat=st.tabs(['도감','세대 비교','조건 검색','질문하기'])
with overview:
    st.subheader(db.label(pokemon_id))
    a,b,c=st.columns(3)
    a.metric('선택한 세대',f'{generation}세대')
    b.metric('타입',' / '.join(TYPE_KO.get(t,t) for t in row['types'] or []) or '미확인')
    c.metric('게임 등장 여부','미확인')
    st.info('이 정보는 세대별 규칙에 대한 기록입니다. 해당 세대의 모든 게임에 등장한다는 뜻은 아닙니다.')
    labels={'hp':'HP','attack':'공격','defense':'방어','special':'특수','special_attack':'특수공격','special_defense':'특수방어','speed':'스피드'}
    st.dataframe([{'능력치':labels[k],'값':v} for k,v in row['stats'].items() if v is not None],hide_index=True,width='stretch')
    abilities=row.get('abilities')
    st.write('특성: '+ ('도입 이전' if generation<3 else ', '.join(a['name']+(' (숨겨진 특성)' if a['is_hidden'] else '') for a in abilities) if abilities else '미확인'))
    st.link_button('PokéAPI 원본 보기',row['source_url'])
with compare:
    st.subheader('같은 포켓몬의 세대별 변화')
    table=[]
    for r in rows:
        table.append({'세대':r['generation'],'타입':', '.join(TYPE_KO.get(t,t) for t in r['types'] or []),'특성':', '.join(a['name'] for a in r['abilities'] or []),**r['stats']})
    st.dataframe(table,hide_index=True,width='stretch')
    st.caption('1세대의 특수는 이후 세대의 특수공격·특수방어와 별개로 표시합니다.')
    st.link_button('비교 데이터 출처',row['source_url'])
with search:
    st.subheader('조건으로 찾아보기')
    st.caption('기초 버전에서는 선택형 조건을 제공합니다. 자연어 조건 검색은 후속 구현 항목입니다.')
    target_gen=st.selectbox('검색 세대',db.generations,index=len(db.generations)-1)
    target_type=st.selectbox('타입',['전체']+list(TYPE_KO),format_func=lambda x:TYPE_KO.get(x,x))
    total=st.number_input('종족값 합계 최솟값',min_value=0,max_value=2000,value=0,step=10)
    matches=db.search(target_gen,None if target_type=='전체' else target_type,total)
    st.caption(f'{len(matches):,}개 형태 · 게임별 등장 여부는 확인되지 않았습니다.')
    st.dataframe(matches,hide_index=True,width='stretch')
with chat:
    st.subheader('근거를 찾아 질문하기')
    st.info('현재는 페이지 개발을 위한 기초 버전입니다. 외부 문서 수집·색인과 AI 답변 연결 후 질문할 수 있습니다.')
    key=f'{pokemon_id}:{generation}'
    histories=st.session_state.setdefault('histories',{})
    messages=histories.setdefault(key,[])
    if st.button('이 포켓몬의 대화 지우기'): messages.clear()
    for message in messages:
        with st.chat_message(message['role']):
            st.markdown(message['content'])
            if message['role']=='assistant':
                used=cited_sources(message['content'],message.get('sources',[]))
                if not used: st.caption('답변에 인용된 근거가 없습니다.')
                for n,s in used: st.markdown(f"[근거 {n}] {s['title']} · [원문]({s['url']})")
    st.chat_input('외부 문서와 RAG 연결을 준비 중입니다.',disabled=True)
