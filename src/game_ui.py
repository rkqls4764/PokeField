"""Streamlit adapter for the browser field and the existing catalog/RAG."""
import base64
import logging
import random
import hashlib
import json
from io import BytesIO
from pathlib import Path
import streamlit as st
from PIL import Image
from .collection import Collection,dex_rows
from .catalog import TYPE_KO,STAT_KO
from .regions import REGIONS,region_candidates,capture_fact,target_regions
from .rotom_data import query_dex,DISPLAY

ASSETS=Path(__file__).parent/'field'
logger=logging.getLogger(__name__)

@st.cache_data(show_spinner=False)
def existing_raw(data_dir,url):
    """Read a single original collector cache by URL hash; never fetch missing data."""
    path=Path(data_dir).parent/'raw'/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    try:
        payload=json.loads(path.read_text(encoding='utf-8'))
        return payload.get('response',{}) if payload.get('source_url')==url else {}
    except (OSError,ValueError): return {}

@st.cache_data(show_spinner=False)
def image_uri(path):
    """Keep the existing alpha channel and white body parts; never overwrite images."""
    try:
        with Image.open(path) as original:
            image=original.convert('RGBA'); image.thumbnail((160,160))
            output=BytesIO(); image.save(output,format='PNG')
        return 'data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()
    except (OSError,ValueError): return ''

def field_component():
    from streamlit.components.v2 import component
    return component('pokemon_lab_field',html=(ASSETS/'field.html').read_text(encoding='utf-8'),css='/* Pokémon Lab */\n'+(ASSETS/'field.css').read_text(encoding='utf-8')+'\n'+(ASSETS/'rotom.css').read_text(encoding='utf-8'),js=(ASSETS/'rotom.js').read_text(encoding='utf-8')+'\n'+(ASSETS/'field.js').read_text(encoding='utf-8'))

def request_rotom():
    state=st.session_state.get('pokemon_field',{})
    request=state.get('rotom') if hasattr(state,'get') else None
    if not isinstance(request,dict): return
    try:
        catalog=st.session_state['_rotom_catalog'];directory=Path(st.session_state['_rotom_images'])
        records=Collection(st.session_state['collection_path']).all()
        st.session_state['rotom_response']=query_dex(catalog,records,request,lambda pid:image_uri(str(directory/'official'/f'{pid}.png')))
    except Exception as exc:
        logger.error('Rotom query failed: %s',type(exc).__name__)
        st.session_state['rotom_response']={'request_id':request.get('request_id'),'error':'도감 데이터를 불러오지 못했어요. 조건을 확인하고 다시 시도해 주세요.'}

def open_panel():
    state=st.session_state.get('pokemon_field',{})
    action=state.get('action') if hasattr(state,'get') else None
    if action and action.get('panel') in ('dex','professor','tools'):
        st.session_state['lab_panel']=action['panel']
        if action.get('region') in {r['id'] for r in REGIONS}: st.session_state['current_region']=action['region']
        if action['panel']=='tools' and action.get('pokemon_id') in st.session_state.get('field_facts',{}):
            st.session_state['pending_pokemon']={'pokemon_id':action['pokemon_id'],'generation':action.get('generation',9)}
        if action.get('panel')=='dex' and action.get('pokemon_id') in st.session_state.get('field_facts',{}):
            st.session_state['dex_detail_id']=action['pokemon_id']
            st.session_state['dex_query']=st.session_state['field_facts'][action['pokemon_id']]['name']
            st.session_state['dex_generation']=9

def record_capture():
    state=st.session_state.get('pokemon_field',{})
    event=state.get('capture') if hasattr(state,'get') else None
    if not event: return
    ack={'event_id':event.get('event_id'),'ok':False}
    try:
        collection=Collection(st.session_state['collection_path'])
        regions=st.session_state.get('field_region_ids')
        allowed=set(regions.get(event.get('region'),[])) if regions else set(st.session_state['field_pool_ids'])
        record=collection.catch(event.get('pokemon_id'),event.get('event_id'),allowed)
        ack['ok']=True
        ack['record']=record
        ack['detail']=st.session_state.get('field_facts',{}).get(event['pokemon_id'])
        target=st.session_state.get('hunt_target')
        if target and target['pokemon_id']==event['pokemon_id'] and target['region']==event.get('region') and (not event.get('target_request_id') or event['target_request_id']==target['request_id']): set_target(dict(target,status='captured'))
    except Exception as exc:
        logger.error('Capture persistence failure: %s',type(exc).__name__)
    st.session_state['capture_ack']=ack

def set_target(target):
    st.session_state['hunt_target']=target
    active=bool(target and target.get('status') in ('requested','active'))
    st.session_state['target_pokemon_id']=target.get('pokemon_id') if active else None
    st.session_state['target_region']=target.get('region') if active else None
    st.session_state['target_status']=target.get('status','none') if target else 'none'

def request_hunt(catalog,pokemon_id,verified_ids):
    from uuid import uuid4
    if pokemon_id not in verified_ids: return False
    regions=target_regions(catalog,pokemon_id,st.session_state.get('current_region'))
    if not regions: return False
    set_target({'pokemon_id':pokemon_id,'region':regions[0],'status':'requested','request_id':uuid4().hex})
    st.session_state['lab_panel']=None
    return True

def update_tracking():
    state=st.session_state.get('pokemon_field',{})
    event=state.get('tracking') if hasattr(state,'get') else None
    if not isinstance(event,dict): return
    if event.get('region') in {r['id'] for r in REGIONS}: st.session_state['current_region']=event['region']
    target=st.session_state.get('hunt_target')
    if not target or event.get('request_id')!=target['request_id'] or target['status'] in ('captured','cancelled','unavailable'): return
    status=event.get('status')
    if status=='active': set_target(dict(target,status='active'))
    elif status in ('cancelled','unavailable'): set_target(dict(target,status=status))
    # A browser event cannot acknowledge persistence; only record_capture clears a caught target.


def render_field(settings,catalog,image_dir):
    collection_path=settings.runtime_dir/'collection.sqlite3'
    st.session_state['collection_path']=str(collection_path)
    collection=Collection(collection_path); records=collection.all()
    st.session_state['_rotom_catalog']=catalog
    st.session_state['_rotom_images']=str(image_dir)
    allowed=[pid for pid,v in catalog.varieties.items() if v['is_default'] and catalog.records_for(pid)]
    if 'field_region_ids' not in st.session_state:
        st.session_state['field_region_ids']={r['id']:random.sample(ids,min(60,len(ids))) for r in REGIONS for ids in [[row['pokemon_id'] for row in region_candidates(catalog,r['id'])]]}
    target=st.session_state.get('hunt_target')
    if target and target['status'] in ('requested','active') and target['region'] in target_regions(catalog,target['pokemon_id']):
        ids=st.session_state['field_region_ids'][target['region']]
        if target['pokemon_id'] not in ids: ids.append(target['pokemon_id'])
    st.session_state['field_pool_ids']=sorted(set().union(*map(set,st.session_state['field_region_ids'].values())))
    pool=[]
    for pid in st.session_state['field_pool_ids']:
        sid=catalog.varieties[pid]['species_id']
        pool.append(dict(capture_fact(catalog,catalog.index[(pid,9)]),image=image_uri(str(image_dir/'official'/f'{pid}.png'))))
    st.session_state['field_facts']={pid:capture_fact(catalog,catalog.index[(pid,9)]) for pid in allowed if (pid,9) in catalog.index}
    regions=[dict(r,pool_ids=st.session_state['field_region_ids'][r['id']],background=f'app/static/regions/{r["id"]}.png') for r in REGIONS]
    st.markdown('''<style>
    html,body,[data-testid="stApp"],[data-testid="stAppViewContainer"]{margin:0!important;padding:0!important;width:100%;height:100%;overflow:hidden!important}
    [data-testid="stHeader"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],#MainMenu,footer{display:none!important}
    .stMain{overflow:hidden!important}.stMainBlockContainer{padding:0!important;margin:0!important;max-width:none!important;width:100%!important}
    div[data-testid="stDialog"] [role="dialog"]{border-radius:24px;max-height:calc(100dvh - 24px);max-width:calc(100vw - 24px);overflow-y:auto;overscroll-behavior:contain}
    @media(max-width:600px){div[data-testid="stDialog"] [role="dialog"]{width:calc(100vw - 12px);max-width:calc(100vw - 12px);max-height:calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom) - 12px);padding:12px;border-radius:16px}}
    </style>''',unsafe_allow_html=True)
    assets={'professor':'<img class="professor-photo" src="app/static/regions/professor.jpg" alt="오박사" draggable="false">','ball':'<img class="ball-photo" src="app/static/regions/ball.jpg" alt="몬스터볼" draggable="false">','dex':'<img src="app/static/rotom/closed.png" alt="닫힌 로토무 도감" draggable="false">'}
    rotom={'response':st.session_state.get('rotom_response'),'generations':catalog.generations,'types':TYPE_KO,'display':DISPLAY}
    field_component()(key='pokemon_field',data={'pool':pool,'regions':regions,'count':len(records),'total':len(allowed),'ack':st.session_state.get('capture_ack'),'panel':st.session_state.get('lab_panel'),'assets':assets,'rotom':rotom,'target':st.session_state.get('hunt_target')},on_capture_change=record_capture,on_action_change=open_panel,on_rotom_change=request_rotom,on_tracking_change=update_tracking,height='content')
    if st.session_state.get('lab_panel'): render_panel(settings,catalog,image_dir,collection)
    return records

def close_panel(): st.session_state['lab_panel']=None

@st.dialog('Pokémon Lab · 포켓몬 센터',width='large',on_dismiss=close_panel)
def render_panel(settings,catalog,image_dir,collection):
    if st.button('닫기 · 필드로 돌아가기',key='close_lab_panel'):
        close_panel(); st.rerun()
    if st.session_state.get('lab_panel')=='professor':
        from .ui_rag import render_global_chat
        render_global_chat(settings,catalog,key_prefix='professor')
    elif st.session_state.get('lab_panel')=='tools':
        from .lab_ui import render_lab
        render_lab(settings,catalog,image_dir)
    else:
        if st.button('검색·세대 비교·항목별 채팅',key='open_research_tools'):
            st.session_state['lab_panel']='tools'; st.rerun()
        render_dex(settings,catalog,image_dir,collection)

def render_dex(settings,catalog,image_dir,collection):
    st.subheader('포켓몬 백과사전')
    st.caption('수집하지 않은 포켓몬도 모든 제공 정보를 열람할 수 있어요. 일반형 기준으로 수집해요.')
    a,b=st.columns(2)
    query=a.text_input('이름 또는 도감 번호',key='dex_query')
    st.session_state.setdefault('dex_generation',catalog.generations[-1])
    gen=b.selectbox('도감 세대',catalog.generations,index=None,key='dex_generation')
    a,b=st.columns(2)
    kind=a.selectbox('도감 타입',['전체']+list(TYPE_KO),format_func=lambda t:TYPE_KO.get(t,t),key='dex_type')
    ownership=b.radio('수집 상태',['전체','수집','미수집'],horizontal=True,key='dex_owned')
    caught=collection.all(); rows=dex_rows(catalog,caught,gen,query,None if kind=='전체' else kind,ownership)
    st.caption(f'{gen}세대 데이터 · {len(rows)}종 · 전체 수집 {len(caught)}종')
    pages=max(1,(len(rows)+17)//18)
    page=st.selectbox('목록 페이지',range(1,pages+1),key=f'dex_page_{gen}_{kind}_{ownership}_{query}')
    columns=st.columns(3)
    for i,row in enumerate(rows[(page-1)*18:page*18]):
        pid=row['pokemon_id']
        with columns[i%3],st.container(border=True):
            uri=image_uri(str(image_dir/'official'/f'{pid}.png'))
            if uri: st.image(uri,width=110)
            else: st.caption('이미지 미확인')
            st.markdown(f"**#{row['species_id']:04d} {row['name_ko']}**")
            st.caption(' / '.join(TYPE_KO.get(t,t) for t in row['types'] or []))
            st.caption('● 수집 완료' if pid in caught else '○ 아직 미수집')
            if st.button('상세 보기',key=f'dex_detail_{pid}'):
                st.session_state['dex_detail_id']=pid
    if not rows: st.info('조건에 맞는 포켓몬이 없습니다.')
    pid=st.session_state.get('dex_detail_id')
    if pid and (pid,gen) in catalog.index:
        row=catalog.index[(pid,gen)]; species=catalog.species[row['species_id']]
        st.divider(); st.subheader(f"#{row['species_id']:04d} {row['name_ko']}")
        raw=existing_raw(str(catalog.data_dir),catalog.varieties[pid]['source_url'])
        height=raw.get('height');weight=raw.get('weight')
        st.write(f"키 {height/10:g} m" if isinstance(height,(int,float)) else '키 미확인')
        st.write(f"몸무게 {weight/10:g} kg" if isinstance(weight,(int,float)) else '몸무게 미확인')
        st.caption('키·몸무게는 기존 원문 캐시의 값이며 세대별 변화는 미확인입니다.')
        title,text=catalog.answer_metadata(row,'타입 특성 종족값')
        st.text(text)
        for ability in row.get('abilities') or []:
            detail=existing_raw(str(catalog.data_dir),f"https://pokeapi.co/api/v2/ability/{ability['name']}/")
            descriptions=[entry.get('flavor_text','').replace('\n',' ') for entry in detail.get('flavor_text_entries',[]) if entry.get('language',{}).get('name')=='ko']
            st.caption(f"{catalog.ability_names.get(ability['name'],'특성')}: "+(descriptions[0] if descriptions else '설명 미확인'))
        if species.get('flavor_texts_ko'): st.write(species['flavor_texts_ko'][0]['text'].replace('\n',' '))
        profile=catalog.profile_source(row['species_id'])
        relations=json.loads(profile['text']).get('evolutions',[])
        if relations: st.json(relations,expanded=False)
        else: st.caption('확인된 진화 관계가 없습니다.')
        record=caught.get(pid)
        if record:
            st.write(f"수집 완료 · 누적 {record['catch_count']}회")
            st.caption(f"최초 포획(UTC): {record['first_caught']} · 최근 포획(UTC): {record['last_caught']}")
        else: st.caption('미수집 · 포획 기록 없음')
        st.markdown('#### 세대별 정보')
        st.dataframe([{'세대':r['generation'],'타입':' / '.join(TYPE_KO.get(t,t) for t in r['types'] or []),'특성':', '.join(catalog.ability_names.get(a['name'],'미확인') for a in r.get('abilities') or []),**{STAT_KO.get(k,k):v for k,v in r['stats'].items() if v is not None}} for r in catalog.records_for(pid)],hide_index=True)
        st.caption('AI 변화 분석은 아래 이동 버튼을 누른 뒤 기존 세대 비교 탭에서 사용할 수 있어요.')
        if st.button('기존 도감·항목별 채팅으로 이동',key='dex_select_existing'):
            st.session_state['pending_pokemon']={'pokemon_id':pid,'generation':gen}
            st.session_state['lab_panel']='tools'; st.rerun()
