"""Local generation-aware encounters; no model calls or data mutation."""
from .catalog import TYPE_KO

REGIONS=(
    {'id':'grassland','name':'초원','types':['grass','normal','bug','fairy']},
    {'id':'sea','name':'바다','types':['water','ice']},
    {'id':'sky','name':'하늘','types':['flying','dragon','psychic']},
    {'id':'desert','name':'사막','types':['ground','rock','fighting']},
    {'id':'cave','name':'동굴','types':['rock','poison','ghost','dark']},
    {'id':'snow','name':'눈','types':['ice','steel','fairy']},
    {'id':'city','name':'도시','types':['normal','psychic','ghost','dark']},
    {'id':'electric','name':'전기','types':['electric','steel']},
    {'id':'volcano','name':'화산','types':['fire','ground','dragon','fighting']},
)

def canonical_type(name):
    inverse={ko:identifier for identifier,ko in TYPE_KO.items()}
    return inverse.get(name,name.casefold())

def region_candidates(catalog,region_id,generation=9):
    region=next((r for r in REGIONS if r['id']==region_id),None)
    if region is None: raise ValueError('Unknown region')
    allowed=set(region['types']);seen=set();rows=[]
    for row in catalog.records:
        pid=row['pokemon_id']
        if row['generation']!=generation or pid in seen or not catalog.varieties[pid]['is_default']: continue
        if allowed.intersection(canonical_type(t) for t in row.get('types') or []):
            rows.append(row);seen.add(pid)
    return rows

def capture_fact(catalog,row):
    return {'id':row['pokemon_id'],'number':row['species_id'],'name':row['name_ko'],'generation':row['generation'],
            'types':[TYPE_KO.get(canonical_type(t),t) for t in row.get('types') or []],
            'stats':{k:v for k,v in row['stats'].items() if v is not None}}

def target_regions(catalog,pokemon_id,current_region=None):
    row=catalog.index.get((pokemon_id,9));variety=catalog.varieties.get(pokemon_id)
    if not row or not variety or not variety['is_default']: return []
    types={canonical_type(t) for t in row.get('types') or []}
    regions=[r['id'] for r in REGIONS if types.intersection(r['types'])]
    return sorted(regions,key=lambda region:region!=current_region)
