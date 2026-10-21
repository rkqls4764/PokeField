"""Persist representative live/cache schema observations without fabricated data."""
from common import *
def analyze(root=ROOT):
    targets={'pokemon':[25,35,94,10034,10091], 'pokemon-species':[25], 'generation':[1], 'version-group':[1], 'pokemon-form':[25,10034], 'evolution-chain':[10]}
    result={'analyzed_at':now(),'documentation':'https://pokeapi.co/docs/v2','history_semantics':'Inclusive last generation; sparse stat-name/ability-slot patches; type list replacement.','observations':['Pikachu past_stats contains generation-I special and generation-V defense/special-defense.','Clefairy past_types changes normal through V to fairy from VI.','Gengar ability slot 1 is levitate through VI, cursed-body from VII.','Form version_group is metadata evidence of introduction, not game availability.'],'samples':{}}
    for endpoint,ids in targets.items():
        for i,(d,e) in cached(root,endpoint).items():
            if i in ids:
                result['samples'][f'{endpoint}/{i}']={'source_url':e['source_url'],'collected_at':e['collected_at'],'fields':sorted(d),'history':{k:d[k] for k in ('past_stats','past_types','past_abilities') if k in d}}
    write(Path(root)/'reports/api_analysis.json',result)
if __name__=='__main__': analyze()
