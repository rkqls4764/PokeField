"""Build additive structured battle data from existing cache + explicitly fetched PokéAPI CSVs."""
from pathlib import Path
import csv,json,hashlib
import argparse,urllib.request
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--csv-dir',type=Path,default=ROOT/'.local/battle-source-csv')
parser.add_argument('--output',type=Path,default=ROOT/'pokemon-data/data/processed')
args=parser.parse_args();D=args.csv_dir;OUT=args.output
D.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
for name in ['move_names','moves','version_groups','versions','version_names','type_efficacy','type_efficacy_past','move_changelog']:
    dest=D/(name+'.csv')
    if not dest.exists():dest.write_bytes(urllib.request.urlopen('https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'+name+'.csv',timeout=30).read())
def csvrows(name):return list(csv.DictReader((D/(name+'.csv')).open(encoding='utf-8')))
def dump(name,data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
types=['normal','fighting','flying','poison','ground','rock','bug','ghost','steel','fire','water','grass','electric','psychic','ice','dragon','dark','fairy']
current={(int(r['damage_type_id']),int(r['target_type_id'])):int(r['damage_factor'])/100 for r in csvrows('type_efficacy')}
past=csvrows('type_efficacy_past');charts={}
for gen in range(1,10):
 active=[i for i in range(1,19) if not(gen<2 and i in (9,17) or gen<6 and i==18)]
 chart={types[a-1]:{types[b-1]:current[a,b] for b in active} for a in active}
 for row in sorted(past,key=lambda r:-int(r['generation_id'])):
  a,b=int(row['damage_type_id']),int(row['target_type_id'])
  if gen<=int(row['generation_id']) and a in active and b in active:chart[types[a-1]][types[b-1]]=int(row['damage_factor'])/100
 charts[str(gen)]=chart
sources={n:'https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'+n+'.csv' for n in ['move_names','moves','version_groups','versions','version_names','type_efficacy','type_efficacy_past','move_changelog']}
dump('type_chart.json',{'sources':[sources['type_efficacy'],sources['type_efficacy_past']],'charts':charts})
names={int(r['move_id']):r['name'] for r in csvrows('move_names') if r['local_language_id']=='3'}
vg={int(r['id']):{'name':r['identifier'],'generation':int(r['generation_id']),'order':int(r['order'])} for r in csvrows('version_groups')}
vnames={int(r['version_id']):r['name'] for r in csvrows('version_names') if r['local_language_id']=='3'}
versions={r['identifier']:{'group':int(r['version_group_id']),'ko':vnames.get(int(r['id']),r['identifier'])} for r in csvrows('versions')}
moves={int(r['id']):{'id':int(r['id']),'name':r['identifier'],'ko':names.get(int(r['id']),r['identifier']),'type':types[int(r['type_id'])-1] if int(r['type_id'])<=18 else None,'power':int(r['power']) if r['power'] else None,'accuracy':int(r['accuracy']) if r['accuracy'] else None} for r in csvrows('moves')}
changes={}
for r in csvrows('move_changelog'):
 change={k:((types[int(r[k])-1] if int(r[k])<=18 else None) if k=='type_id' else int(r[k])) for k in ['type_id','power','accuracy'] if r[k]}
 if change:changes.setdefault(r['move_id'],[]).append({'order':vg[int(r['changed_in_version_group_id'])]['order'],**change})
dump('move_catalog.json',{'sources':sources,'versions':versions,'groups':vg,'moves':moves,'changes':changes})
varieties=[json.loads(line) for line in (ROOT/'pokemon-data/data/processed/pokemon_varieties.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
count=details=missing=0
with (OUT/'pokemon_learnsets.jsonl').open('w',encoding='utf-8') as out:
 for v in varieties:
  pid=v['pokemon_id'];url=f'https://pokeapi.co/api/v2/pokemon/{pid}/';p=ROOT/'pokemon-data/data/raw'/(hashlib.sha256(url.encode()).hexdigest()+'.json')
  if not p.exists():missing+=1;continue
  raw=json.loads(p.read_text(encoding='utf-8'));d=raw['response'];learn=[]
  if 'moves' not in d:missing+=1;continue
  for m in d['moves']:
   mid=int(m['move']['url'].rstrip('/').split('/')[-1])
   for x in m['version_group_details']:
    group=int(x['version_group']['url'].rstrip('/').split('/')[-1])
    if group not in vg or vg[group]['generation']>9:continue
    learn.append([mid,group,x['move_learn_method']['name'],x['level_learned_at']])
  out.write(json.dumps({'pokemon_id':pid,'source_url':url,'learnsets':learn},ensure_ascii=False,separators=(',',':'))+'\n');count+=1;details+=len(learn)
dump('battle_data_manifest.json',{'sources':sources,'csv_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in D.glob('*.csv')},'cached_pokemon':count,'missing_cache':missing,'learnset_records':details,'note':'Existing cached learnsets only; absent version entries do not establish learnability. CSV fields use PokéAPI source snapshot.'})
print('pokemon',count,'missing',missing,'learnset records',details)

