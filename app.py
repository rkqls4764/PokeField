"""Pokémon Lab: viewport field with on-demand research overlays."""
import streamlit as st
from src.catalog import Catalog
from src.settings import Settings
from src.game_ui import render_field

st.set_page_config(page_title='Pokémon Lab',page_icon='🔎',layout='wide',initial_sidebar_state='collapsed')
@st.cache_resource
def catalog(path): return Catalog(path)
try:
    config=Settings.load()
    db=catalog(str(config.data_dir))
except (FileNotFoundError,ValueError,KeyError):
    st.error('데이터를 불러오지 못했습니다. 데이터 경로와 원본 파일을 확인하세요.')
    st.stop()
render_field(config,db,config.data_dir.parent/'images')
