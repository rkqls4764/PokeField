import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.settings import Settings
from src.catalog import Catalog, metadata_document
config=Settings.load(); catalog=Catalog(config.data_dir)
sample=metadata_document(catalog.index[(35,6)])
assert sample['id']=='pokemon:35:gen:6'
assert all(isinstance(v,(str,int,float,bool)) for v in sample['metadata'].values())
print(json.dumps({'species':len(catalog.species),'varieties':len(catalog.varieties),'generation_records':len(catalog.records),'metadata_document_sample':sample},ensure_ascii=True,indent=2))
