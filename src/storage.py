"""Thread-safe durable caches; no prompts, keys or raw errors in telemetry."""
import hashlib, json, sqlite3, threading
from datetime import datetime, timezone
from pathlib import Path

def now(): return datetime.now(timezone.utc).isoformat()
def digest(value): return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def write_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp'); temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); temp.replace(path)

class Cache:
    def __init__(self, directory):
        directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
        self.path=directory/'cache.sqlite3'
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    def connect(self): return sqlite3.connect(self.path,timeout=30)
    def get(self,key):
        with self.connect() as c: row=c.execute('SELECT value FROM cache WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None
    def put(self,key,value):
        with self.connect() as c: c.execute('INSERT OR REPLACE INTO cache VALUES (?,?)',(key,json.dumps(value,ensure_ascii=False)))

class Metrics:
    lock=threading.Lock()
    def __init__(self,directory): self.path=Path(directory)/'usage.jsonl'
    def record(self,kind,**values):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.lock,self.path.open('a',encoding='utf-8') as f:
            f.write(json.dumps({'at':now(),'kind':kind,**values},ensure_ascii=False)+'\n')
