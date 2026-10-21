from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)

@dataclass(frozen=True)
class Settings:
    data_dir: Path
    chroma_dir: Path
    top_k: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 200
    provider: str = 'gms'
    api_key: str = field(default='', repr=False)
    base_url: str = 'https://gms.ssafy.io/gmsapi/api.openai.com/v1/'
    chat_model: str = 'gpt-5.4-nano'
    embedding_model: str = 'text-embedding-3-small'
    wiki_contact: str = ''
    wiki_interval: float = 6.2
    auto_collect: bool = False
    high_attack: int = 100
    high_defense: int = 100
    high_special_attack: int = 100
    high_special_defense: int = 100
    high_speed: int = 100
    candidate_limit: int = 25
    result_limit: int = 6
    @property
    def runtime_dir(self): return self.chroma_dir.parent / '.local/rag'
    @classmethod
    def load(cls):
        def path(name, default):
            p = Path(os.getenv(name, default))
            return p if p.is_absolute() else ROOT / p
        provider = os.getenv('LLM_PROVIDER', 'gms' if os.getenv('GMS_KEY') else 'openai').lower()
        if provider not in ('gms','openai'): raise ValueError('LLM_PROVIDER는 gms 또는 openai여야 합니다.')
        size=int(os.getenv('CHUNK_SIZE','1000')); overlap=int(os.getenv('CHUNK_OVERLAP','200'))
        top=int(os.getenv('TOP_K','5'))
        if not (100 <= size <= 6000 and 0 <= overlap < size and 1 <= top <= 20): raise ValueError('청크와 Top-k 설정을 확인하세요.')
        return cls(data_dir=path('POKEMON_DATA_DIR','pokemon-data/data/processed'),chroma_dir=path('CHROMA_DIR','chroma_db'),top_k=top,chunk_size=size,chunk_overlap=overlap,provider=provider,api_key=os.getenv('GMS_KEY' if provider=='gms' else 'OPENAI_API_KEY',''),base_url=os.getenv('GMS_BASE_URL','https://gms.ssafy.io/gmsapi/api.openai.com/v1/') if provider=='gms' else os.getenv('OPENAI_BASE_URL','https://api.openai.com/v1/'),chat_model=os.getenv('CHAT_MODEL','gpt-5.4-nano'),embedding_model=os.getenv('EMBEDDING_MODEL','text-embedding-3-small'),wiki_contact=os.getenv('WIKI_CONTACT',''),wiki_interval=max(1.0,float(os.getenv('WIKI_INTERVAL','6.2'))),auto_collect=os.getenv('AUTO_COLLECT_DOCUMENTS','false').lower()=='true',**{k:int(os.getenv(k.upper(),str(v))) for k,v in {'high_attack':100,'high_defense':100,'high_special_attack':100,'high_special_defense':100,'high_speed':100,'candidate_limit':25,'result_limit':6}.items()})
