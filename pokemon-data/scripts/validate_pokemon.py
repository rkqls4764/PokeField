import argparse
from collections import Counter
from common import *
def validate(root=ROOT):
    root=Path(root); out=root/'data/processed'; data={}; counts={}; errors=[]
    for path in sorted(out.glob('*.jsonl')):
        if path.stem=='pokemon_moves': continue
        rows=[json.loads(x) for x in path.open(encoding='utf-8')]; counts[path.name]=len(rows); data[path.stem]=rows
    sp={r['species_id']:r for r in data['pokemon_species']}; pk={r['pokemon_id']:r for r in data['pokemon_varieties']}; fm={r['form_id']:r for r in data['pokemon_forms']}
    def check(condition,message):
        if not condition: errors.append(message)
    for name,key in [('pokemon_species','species_id'),('pokemon_varieties','pokemon_id'),('pokemon_forms','form_id'),('pokemon_generations','record_id')]:
        check(len({r[key] for r in data[name]})==len(data[name]),name+' duplicate IDs')
    for p in pk.values():
        check(p['species_id'] in sp,f"pokemon {p['pokemon_id']} missing species")
        check(all(i in fm for i in p['form_ids']),f"pokemon {p['pokemon_id']} missing forms")
    for s in sp.values(): check(all(i in pk for i in s['variety_ids']),f"species {s['species_id']} missing varieties")
    for f in fm.values(): check(f['pokemon_id'] in pk,f"form {f['form_id']} missing pokemon")
    for r in data['pokemon_generations']:
        p=pk.get(r['pokemon_id']); check(p is not None,'generation missing pokemon')
        if p: check(p['first_generation'] is not None and r['generation']>=p['first_generation'],'record predates form')
        if r['generation']<3: check(r['abilities']==[],'early abilities')
        if r['generation']==1: check(r['stats']['special_attack'] is None and r['stats']['special_defense'] is None,'gen1 split special')
    regressions={}
    for pid,label,field,before,after,boundary in [(35,'clefairy_type','types',['normal'],['fairy'],6),(94,'gengar_ability','abilities',['levitate'],['cursed-body'],7)]:
        rows=[r for r in data['pokemon_generations'] if r['pokemon_id']==pid]; checks=[]
        for r in rows:
            value=r[field] if field=='types' else [a['name'] for a in r[field] if not a['is_hidden']]
            if field=='abilities' and r['generation']<3: continue
            checks.append(value==(before if r['generation']<boundary else after))
        regressions[label]='passed' if checks and all(checks) else 'failed' if checks else 'not_collected'
        check(regressions[label]!='failed',label+' regression failed')
    manifest=json.loads((root/'reports/collection_manifest.json').read_text(encoding='utf-8'))
    groups=json.loads((out/'version_groups.json').read_text(encoding='utf-8')); group_names={g['name'] for g in groups}
    move_count=0; previous_pid=None; seen_moves=set()
    with (out/'pokemon_moves.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line); move_count+=1
            check(r['pokemon_id'] in pk and r['species_id'] in sp,'move reference missing')
            check(r['version_group'] in group_names,'move version group missing')
            if r['pokemon_id']!=previous_pid: seen_moves=set(); previous_pid=r['pokemon_id']
            key=(r['move'],r['version_group'],r['learn_method'],r['level_learned_at'])
            check(key not in seen_moves,'duplicate move'); seen_moves.add(key)
    counts['pokemon_moves.jsonl']=move_count
    if manifest['scope']=='all':
        for r in data['pokemon_evolutions']: check(r['from_species_id'] in sp and r['to_species_id'] in sp,'evolution species missing')
        check(len(groups)==manifest['expected'].get('version-group'),'version groups incomplete')
        check(len(json.loads((out/'generations.json').read_text(encoding='utf-8')))==manifest['expected'].get('generation'),'generations incomplete')
    check(not [i for i,s in sp.items() if not s['name_ko']],'missing Korean species names')
    pairs=[(r['pokemon_id'],r['generation']) for r in data['pokemon_generations']]
    check(len(pairs)==len(set(pairs)),'duplicate pokemon-generation pair')
    complete=manifest['scope']=='all' and len(sp)==manifest['expected'].get('pokemon-species') and not manifest['failures']
    if manifest['scope']=='all': check(complete,'collection incomplete')
    for name in ('generations','version_groups'): counts[name+'.json']=len(json.loads((out/(name+'.json')).read_text(encoding='utf-8')))
    report=dict(validated_at=now(),scope=manifest['scope'],collection_complete=complete,validation_passed=not errors,file_record_counts=counts,species_count=len(sp),variety_count=len(pk),form_count=len(fm),generation_counts=dict(sorted(Counter(r['generation'] for r in data['pokemon_generations']).items())),missing_korean_names=[i for i,s in sp.items() if not s['name_ko']],errors=errors,regressions=regressions,api_failures=manifest['failures'],unknown_first_generation=[i for i,p in pk.items() if p['first_generation'] is None],unverified_history_records=sum(r['history_status']=='unverified' for r in data['pokemon_generations']),unknown_game_presence_records=len(data['pokemon_generations']),limitations=['History follows API sparse patches; no independent game database audit.','Generation records describe mechanics, not confirmed game availability.','Evolution conditions are not assigned to game versions.','External wiki documents and ChromaDB indexing are deferred.'])
    write(root/'reports/collection_report.json',report); print(json.dumps(report,ensure_ascii=True,indent=2)); return report
if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--root',type=Path,default=ROOT); r=validate(a.parse_args().root); raise SystemExit(0 if r['validation_passed'] else 1)
