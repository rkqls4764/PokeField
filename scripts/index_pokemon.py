import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.settings import Settings
from src.catalog import Catalog
from src.vector_store import VectorStore
from src.storage import write_json, now
PILOT=[25,35,94,133,1,4,7,39,52,150]
def run(ids=None):
    settings=Settings.load(); catalog=Catalog(settings.data_dir); store=VectorStore(settings)
    docs=[catalog.document(r) for r in catalog.records if ids is None or r['species_id'] in ids]
    result=store.upsert('pokemon_meta',docs)
    report={'at':now(),'scope':'all' if ids is None else ids,'records_requested':len(docs),'result':result,'collections':store.counts()}
    write_json(settings.runtime_dir/'metadata_index_report.json',report); print(json.dumps(report,ensure_ascii=True,indent=2)); return report
if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--pilot',action='store_true'); a.add_argument('--species',type=int,nargs='+'); x=a.parse_args(); run(x.species or (PILOT if x.pilot else None))
