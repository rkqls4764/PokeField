import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.settings import Settings
from src.catalog import Catalog
from src.vector_store import VectorStore
from src.llm import LanguageModel, ServiceError
from src.document_service import DocumentService
from src.storage import write_json, now
from scripts.index_pokemon import PILOT
def run(ids, refresh=False):
    s=Settings.load(); db=Catalog(s.data_dir); store=VectorStore(s); service=DocumentService(s,db,store,LanguageModel(s)); results=[]
    for sid in ids:
        try: results.append(service.collect(sid,'특성, 진화, 세대별 특징을 설명해 줘.', refresh=refresh))
        except ServiceError as e: results.append({'species_id':sid,'status':'failed','message':str(e)})
        print(f'{len(results)}/{len(ids)} species processed',flush=True)
    completed=[r['species_id'] for r in results if r.get('documents')]
    report={'at':now(),'requested':ids,'results':results,'collected_species':completed,'uncollected_species':[i for i in db.species if i not in completed and not service.status(i).get('documents')],'collections':store.counts()}
    write_json(s.runtime_dir/'document_collection_report.json',report); print(json.dumps({'collected_species':completed,'collections':store.counts()},ensure_ascii=True)); return report

if __name__ == '__main__':
    p = argparse.ArgumentParser()

    p.add_argument(
        '--species',
        type=int,
        nargs='+',
        default=PILOT
    )

    p.add_argument(
        '--refresh',
        action='store_true',
        help='기존 수집 결과를 다시 평가합니다.'
    )

    a = p.parse_args()

    run(a.species, refresh=a.refresh)

