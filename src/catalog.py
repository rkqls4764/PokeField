import json
from pathlib import Path

TYPE_KO = dict(normal='노말', fire='불꽃', water='물', electric='전기', grass='풀', ice='얼음', fighting='격투', poison='독', ground='땅', flying='비행', psychic='에스퍼', bug='벌레', rock='바위', ghost='고스트', dragon='드래곤', dark='악', steel='강철', fairy='페어리')

def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]

class Catalog:
    def __init__(self, data_dir):
        data_dir = Path(data_dir)
        self.species = {r['species_id']: r for r in read_jsonl(data_dir / 'pokemon_species.jsonl')}
        self.varieties = {r['pokemon_id']: r for r in read_jsonl(data_dir / 'pokemon_varieties.jsonl')}
        self.records = read_jsonl(data_dir / 'pokemon_generations.jsonl')
        self.index = {(r['pokemon_id'], r['generation']): r for r in self.records}
        self.generations = sorted({r['generation'] for r in self.records})
    def records_for(self, pokemon_id):
        return sorted((r for r in self.records if r['pokemon_id'] == pokemon_id), key=lambda r: r['generation'])
    def label(self, pokemon_id):
        v = self.varieties[pokemon_id]; s = self.species[v['species_id']]
        return f"{s.get('name_ko') or s.get('name_en')} · {v['api_name']} (#{pokemon_id})"
    def search(self, generation, type_name=None, min_total=0):
        result=[]
        for r in self.records:
            if r['generation'] != generation or (type_name and type_name not in (r['types'] or [])): continue
            values = [r['stats'].get(k) for k in ('hp', 'attack', 'defense', 'special' if generation == 1 else 'special_attack', 'speed')]
            if generation != 1: values.append(r['stats'].get('special_defense'))
            total = sum(values) if all(v is not None for v in values) else None
            if min_total and (total is None or total < min_total): continue
            result.append({'포켓몬': self.label(r['pokemon_id']), '타입': ', '.join(TYPE_KO.get(t,t) for t in r['types'] or []), '종족값 합계': total, 'pokemon_id': r['pokemon_id']})
        return result

def metadata_document(row):
    """Stable ID and scalar metadata ready for the pokemon_meta collection."""
    return {'id': row['record_id'], 'text': f"이름: {row['name_ko']}\n세대: {row['generation']}\n타입: {json.dumps(row['types'],ensure_ascii=False)}\n종족값: {json.dumps(row['stats'],ensure_ascii=False)}\n특성: {json.dumps(row['abilities'],ensure_ascii=False)}\n게임 등장: 미확인\n이력 상태: {row['history_status']}", 'metadata': {k: row[k] for k in ('species_id','pokemon_id','generation','source_url')} | {'source_type':'pokemon_metadata'}}
