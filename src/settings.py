from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
except ImportError:
    pass

@dataclass(frozen=True)
class Settings:
    data_dir: Path
    chroma_dir: Path
    top_k: int
    chunk_size: int
    chunk_overlap: int
    @classmethod
    def load(cls):
        data = Path(os.getenv('POKEMON_DATA_DIR', str(ROOT / 'pokemon-rag/data/processed')))
        if not data.is_absolute(): data = ROOT / data
        size = int(os.getenv('CHUNK_SIZE', '1000'))
        overlap = int(os.getenv('CHUNK_OVERLAP', '200'))
        top = int(os.getenv('TOP_K', '5'))
        if not 0 <= overlap < size or top < 1:
            raise ValueError('청크 크기·중복 길이·검색 개수 설정을 확인하세요.')
        return cls(data, ROOT / '.local/chroma', top, size, overlap)
