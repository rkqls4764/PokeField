"""Standard-library-only PokéAPI client; atomic, timestamped cache."""
import json, time, hashlib, threading
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
BASE = 'https://pokeapi.co/api/v2/'
ROOT = Path(__file__).resolve().parents[1]
def now(): return datetime.now(timezone.utc).isoformat()
def ident(ref): return int(ref['url'].rstrip('/').split('/')[-1]) if ref else None
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8'); tmp.replace(path)
class Client:
    def __init__(self, root=ROOT, interval=.08):
        self.root=Path(root); self.interval=interval; self.lock=threading.Lock(); self.last=0; self.failures=[]
    def get(self, url):
        if not url.startswith(BASE): raise ValueError('Untrusted API URL: '+url)
        path=self.root/'data/raw'/ (hashlib.sha256(url.encode()).hexdigest()+'.json')
        if path.exists(): return json.loads(path.read_text(encoding='utf-8'))['response']
        for attempt in range(4):
            try:
                with self.lock:
                    time.sleep(max(0,self.interval-(time.monotonic()-self.last))); self.last=time.monotonic()
                req=Request(url,headers={'User-Agent':'Mozilla/5.0 PokemonResearchCollector/1.0','Accept':'application/json'})
                with urlopen(req,timeout=45) as r: data=json.load(r)
                write(path,{'source_url':url,'collected_at':now(),'response':data}); return data
            except Exception as e:
                if attempt==3:
                    with self.lock: self.failures.append({'url':url,'error':str(e),'at':now()})
                    return None
                time.sleep(2**attempt)
    def listing(self, endpoint):
        url=BASE+endpoint+'/?limit=100'; found={}; expected=None
        while url:
            data=self.get(url)
            if data is None: break
            expected=data['count']
            for r in data['results']: found[r['url']]=r
            url=data['next']
        return list(found.values()), expected
def cached(root, endpoint):
    result={}
    for p in (Path(root)/'data/raw').glob('*.json'):
        e=json.loads(p.read_text(encoding='utf-8')); d=e['response']
        if e['source_url'].split('/api/v2/')[-1].startswith(endpoint+'/') and 'id' in d:
            result[d['id']] = (d,e)
    return result
