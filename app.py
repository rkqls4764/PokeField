"""PokéField: viewport field with on-demand research overlays."""
import streamlit as st
from pathlib import Path
from hashlib import sha256
from src.catalog import Catalog
from src.settings import Settings
from src.game_ui import render_field

st.set_page_config(page_title='PokéField',page_icon='🔎',layout='wide',initial_sidebar_state='collapsed')
@st.cache_resource
def catalog(path,implementation_revision): return Catalog(path)
try:
    config=Settings.load()
    # Imported-class changes do not invalidate Streamlit's resource cache by themselves.
    revision=sha256((Path(__file__).parent/'src/catalog.py').read_bytes()).hexdigest()
    db=catalog(str(config.data_dir),revision)
except (FileNotFoundError,ValueError,KeyError):
    st.error('데이터를 불러오지 못했습니다. 데이터 경로와 원본 파일을 확인하세요.')
    st.stop()
render_field(config,db,config.data_dir.parent/'images')
