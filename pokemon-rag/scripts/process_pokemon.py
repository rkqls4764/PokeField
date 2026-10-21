"""Reconstruct inclusive generation boundaries, applying sparse stat/ability patches."""
import argparse
from common import *
def reconstruct(p,g):
    stats={s['stat']['name'].replace('-','_'):s['base_stat'] for s in p.get('stats',[])}
    abilities={a['slot']:a for a in p.get('abilities',[])}
    types=p.get('types')
    for field in ('past_stats','past_abilities','past_types'):
        for h in sorted(p.get(field,[]),key=lambda h:ident(h['generation']),reverse=True):
            if g<=ident(h['generation']):
                if field=='past_stats': stats.update({s['stat']['name'].replace('-','_'):s['base_stat'] for s in h['stats']})
                elif field=='past_abilities': abilities.update({a['slot']:a for a in h['abilities']})
                else: types=h['types']
    keys=('hp','attack','defense','special','special_attack','special_defense','speed')
    stats={k:stats.get(k) for k in keys}
    if g==1: stats['special_attack']=stats['special_defense']=None
    else: stats['special']=None
    ab=[] if g<3 else [{'slot':a['slot'],'name':a['ability']['name'],'is_hidden':a['is_hidden']} for a in sorted(abilities.values(),key=lambda a:a['slot']) if a.get('ability') and (g>=5 or not a['is_hidden'])]
    status={k:('reconstructed_from_api_history' if 'past_'+k in p else 'unverified') for k in ('types','stats','abilities')}
    if g<3: status['abilities']='not_applicable'
    if g==1 and stats['special'] is None: status['stats']='unverified_special_missing'
    for k in ('types','stats','abilities'):
        if status[k]=='unverified':
            if k=='types': types=None
            elif k=='stats': stats={x:None for x in keys}
            else: ab=None
    return [t['type']['name'] for t in sorted(types,key=lambda t:t['slot'])] if types is not None else None,stats,ab,status
def process(root=ROOT):
    root=Path(root); out=root/'data/processed'; out.mkdir(parents=True,exist_ok=True)
    sp=cached(root,'pokemon-species'); pk=cached(root,'pokemon'); fm=cached(root,'pokemon-form'); vg=cached(root,'version-group'); gens=cached(root,'generation')
    def dump(name,rows):
        path=out/(name+'.jsonl'); temp=path.with_suffix('.tmp')
        with temp.open('w',encoding='utf-8') as f:
            for r in rows: f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
        temp.replace(path)
    def provenance(e): return {k:e[k] for k in ('source_url','collected_at')}
    species=[]; varieties=[]; forms=[]; records=[]
    for sid,(s,e) in sorted(sp.items()):
        name=lambda lang:next((n['name'] for n in s.get('names',[]) if n['language']['name']==lang),None)
        species.append(dict(species_id=sid,name_ko=name('ko'),name_en=name('en'),first_generation=ident(s['generation']),is_legendary=s.get('is_legendary'),is_mythical=s.get('is_mythical'),is_baby=s.get('is_baby'),color=(s.get('color') or {}).get('name'),habitat=(s.get('habitat') or {}).get('name'),evolves_from_species=ident(s.get('evolves_from_species')),variety_ids=[ident(v['pokemon']) for v in s.get('varieties',[])],flavor_texts_ko=[{'text':v['flavor_text'],'version':v['version']['name']} for v in s.get('flavor_text_entries',[]) if v['language']['name']=='ko'],**provenance(e)))
    for fid,(f,e) in sorted(fm.items()):
        forms.append(dict(form_id=fid,pokemon_id=ident(f['pokemon']),api_name=f['name'],form_name=f.get('form_name'),names=f.get('names'),form_names=f.get('form_names'),version_group=f.get('version_group'),is_default=f.get('is_default'),is_mega=f.get('is_mega'),is_battle_only=f.get('is_battle_only'),**provenance(e)))
    for pid,(p,e) in sorted(pk.items()):
        sid=ident(p['species'])
        if sid not in sp: continue
        s=sp[sid][0]; first=ident(s['generation']) if p['is_default'] else None
        evidence=[]
        for f in p.get('forms',[]):
            form=fm.get(ident(f),(None,None))[0]
            if form and form.get('version_group') and ident(form['version_group']) in vg:
                evidence.append(ident(vg[ident(form['version_group'])][0]['generation']))
        if not p['is_default'] and len(evidence)==len(p.get('forms',[])) and evidence: first=max(ident(s['generation']),min(evidence))
        varieties.append(dict(pokemon_id=pid,species_id=sid,api_name=p['name'],is_default=p['is_default'],form_ids=[ident(f) for f in p.get('forms',[])],first_generation=first,first_generation_verified=first is not None,first_generation_evidence='species.generation' if p['is_default'] else 'pokemon-form.version_group.generation',image_url=p.get('sprites',{}).get('other',{}).get('official-artwork',{}).get('front_default'),**provenance(e)))
        if first is None: continue
        for g in sorted(gens):
            if g<first: continue
            types,stats,abilities,status=reconstruct(p,g)
            records.append(dict(record_id=f'pokemon:{pid}:gen:{g}',species_id=sid,pokemon_id=pid,name_ko=next((n['name'] for n in s['names'] if n['language']['name']=='ko'),None),generation=g,types=types,stats=stats,abilities=abilities,game_presence=None,history_status='unverified' if any(v.startswith('unverified') for v in status.values()) else 'api_history_reconstructed',field_history_status=status,**provenance(e)))
    def moves():
        for pid,(p,e) in sorted(pk.items()):
            seen=set()
            for m in p.get('moves',[]):
                for v in m['version_group_details']:
                    key=(m['move']['name'],v['version_group']['name'],v['move_learn_method']['name'],v['level_learned_at'])
                    if key in seen: continue
                    seen.add(key); group=vg.get(ident(v['version_group']),(None,None))[0]
                    yield dict(pokemon_id=pid,species_id=ident(p['species']),generation=ident(group['generation']) if group else None,version_group=key[1],move=key[0],learn_method=key[2],level_learned_at=key[3],**provenance(e))
    def evolutions():
        for cid,(c,e) in sorted(cached(root,'evolution-chain').items()):
            def walk(node):
                for child in node.get('evolves_to',[]):
                    for d in child.get('evolution_details',[]) or [None]:
                        yield dict(chain_id=cid,from_species_id=ident(node['species']),to_species_id=ident(child['species']),trigger=(d.get('trigger') or {}).get('name') if d else None,min_level=d.get('min_level') if d else None,details=d,**provenance(e))
                    yield from walk(child)
            yield from walk(c['chain'])
    for name,rows in [('pokemon_species',species),('pokemon_varieties',varieties),('pokemon_forms',forms),('pokemon_generations',records),('pokemon_moves',moves()),('pokemon_evolutions',evolutions())]: dump(name,rows)
    for name,data in [('generations',gens),('version_groups',vg)]: write(out/(name+'.json'),[dict(d,**provenance(e)) for _,(d,e) in sorted(data.items())])
if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--root',type=Path,default=ROOT); process(a.parse_args().root)
