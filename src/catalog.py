import json
from pathlib import Path
from .storage import digest

TYPE_KO = dict(normal='노말',fire='불꽃',water='물',electric='전기',grass='풀',ice='얼음',fighting='격투',poison='독',ground='땅',flying='비행',psychic='에스퍼',bug='벌레',rock='바위',ghost='고스트',dragon='드래곤',dark='악',steel='강철',fairy='페어리')
STAT_KO={'hp':'HP','attack':'공격','defense':'방어','special':'특수','special_attack':'특수공격','special_defense':'특수방어','speed':'스피드'}
def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as f: return [json.loads(line) for line in f if line.strip()]
def stat_total(row):
    keys=['hp','attack','defense','speed']+(['special'] if row['generation']==1 else ['special_attack','special_defense'])
    values=[row['stats'].get(k) for k in keys]
    return sum(values) if all(v is not None for v in values) else None

class Catalog:
    def __init__(self,data_dir):
        self.data_dir=Path(data_dir)
        self.species={r['species_id']:r for r in read_jsonl(self.data_dir/'pokemon_species.jsonl')}
        self.varieties={r['pokemon_id']:r for r in read_jsonl(self.data_dir/'pokemon_varieties.jsonl')}
        self.records=read_jsonl(self.data_dir/'pokemon_generations.jsonl')
        self.index={(r['pokemon_id'],r['generation']):r for r in self.records}
        self.generations=sorted({r['generation'] for r in self.records})
        self.by_pokemon={}
        for r in self.records: self.by_pokemon.setdefault(r['pokemon_id'],[]).append(r)
        self.ability_names={}
        for name in ('ability_names_ko.json','ability_names_manual_ko.json'):
            p=self.data_dir/name
            if p.exists(): self.ability_names.update(json.loads(p.read_text(encoding='utf-8')))
        p=self.data_dir/'pokemon_evolutions.jsonl'
        self.evolutions=read_jsonl(p) if p.exists() else []
    def records_for(self,pokemon_id): return sorted(self.by_pokemon.get(pokemon_id,[]),key=lambda r:r['generation'])
    def label(self,pokemon_id):
        v=self.varieties[pokemon_id]; s=self.species[v['species_id']]
        return f"{s.get('name_ko') or s.get('name_en')} · {v['api_name']} (#{pokemon_id})"
    def search(self,generation,type_name=None,min_total=0):
        result=[]
        for r in self.records:
            if r['generation']!=generation or (type_name and type_name not in (r['types'] or [])): continue
            total=stat_total(r)
            if min_total and (total is None or total<min_total): continue
            result.append({'포켓몬':self.label(r['pokemon_id']),'타입':', '.join(TYPE_KO.get(t,t) for t in r['types'] or []),'종족값 합계':total,'pokemon_id':r['pokemon_id']})
        return result
    def document(self,row): return metadata_document(row,self.ability_names,self.varieties[row['pokemon_id']]['api_name'])
    def profile_source(self,species_id):
        s=self.species[species_id]; relations=[]
        for e in self.evolutions:
            if species_id not in (e['from_species_id'],e['to_species_id']): continue
            details={k:v for k,v in (e.get('details') or {}).items() if v not in (None,'',False)}
            translations={'min_happiness':'친밀도_최솟값','min_affection':'애정도_최솟값','min_beauty':'아름다움_최솟값','min_level':'최소_레벨','time_of_day':'시간대','version_group':'적용_버전그룹','known_move_type':'알고_있어야_할_기술타입','near_special_rock':'특수한_바위_근처','item':'사용_아이템','held_item':'지닌_아이템','trigger':'진화_계기'}
            details={translations.get(k,k):v for k,v in details.items()}
            relations.append({'from':self.species.get(e['from_species_id'],{}).get('name_ko',e['from_species_id']),'to':self.species.get(e['to_species_id'],{}).get('name_ko',e['to_species_id']),'조건':details,'source_url':e['source_url']})
        profile={'name_ko':s['name_ko'],'name_en':s['name_en'],'species_id':species_id,'first_generation':s['first_generation'],'evolutions':relations,'evolution_version_warning':'조건에 명시된 버전 그룹 이외의 게임으로 일반화하지 않는다. 버전 그룹이 없으면 적용 게임은 미확인.'}
        return {'id':f'species:{species_id}:profile','title':f"{s['name_ko']} 종·진화 정보",'text':json.dumps(profile,ensure_ascii=False),'source_type':'pokemon_metadata','source_url':relations[0]['source_url'] if relations else s['source_url'],'species_id':species_id}

def metadata_document(row,ability_names=None,api_name=''):
    names=ability_names or {}
    abilities=None if row.get('abilities') is None else [{'name':a['name'],'name_ko':names.get(a['name'],a['name']),'is_hidden':a['is_hidden']} for a in row['abilities']]
    text=f"{row['name_ko']} ({api_name}) | species_id={row['species_id']}, pokemon_id={row['pokemon_id']} | {row['generation']}세대\n타입: "+', '.join(f'{TYPE_KO.get(t,t)}({t})' for t in row['types'] or [])+'\n종족값: '+json.dumps({STAT_KO.get(k,k):v for k,v in row['stats'].items()},ensure_ascii=False)+'\n특성: '+json.dumps(abilities,ensure_ascii=False)+'\n게임별 등장 여부: 미확인. 이력 상태: '+row['history_status']
    title=f"{row['name_ko']} ({api_name}) · {row['generation']}세대"
    meta={k:row[k] for k in ('species_id','pokemon_id','generation','source_url')} | {'source_type':'pokemon_metadata','title':title,'content_hash':digest(text)}
    return {'id':row['record_id'],'text':text,'metadata':meta}
