import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from common import *
def collect(root=ROOT, ids=None, workers=6):
    c=Client(root); manifest={'started_at':now(),'scope':'sample' if ids else 'all','expected':{}}
    def batch(urls):
        urls=sorted(set(urls)); out=[]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(c.get,u) for u in urls]
            for i,f in enumerate(as_completed(futures),1):
                d=f.result()
                if d: out.append(d)
                if i%100==0 or i==len(urls): print(f'Fetched {i}/{len(urls)}',flush=True)
        return out
    for ep in ('generation','version-group'):
        listing,n=c.listing(ep); manifest['expected'][ep]=n; batch(r['url'] for r in listing)
    listing,n=c.listing('pokemon-species'); manifest['expected']['pokemon-species']=n
    species=batch(r['url'] for r in listing if not ids or ident(r) in ids)
    pokemon=batch(v['pokemon']['url'] for s in species for v in s.get('varieties',[]))
    batch(f['url'] for p in pokemon for f in p.get('forms',[]))
    batch(s['evolution_chain']['url'] for s in species if s.get('evolution_chain'))
    manifest.update(completed_at=now(),failures=c.failures,collected_species=len(species),collected_pokemon=len(pokemon))
    write(Path(root)/'reports/collection_manifest.json',manifest)
    return manifest
if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--root',type=Path,default=ROOT); a.add_argument('--ids',type=int,nargs='+'); a.add_argument('--workers',type=int,default=6)
    x=a.parse_args(); collect(x.root,x.ids,x.workers)
