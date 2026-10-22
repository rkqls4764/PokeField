"""Independent, idempotent collection records. Source Pokémon data stays read-only."""
import sqlite3
from datetime import datetime,timezone
from pathlib import Path
from contextlib import contextmanager

class Collection:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS collection(
                    pokemon_id INTEGER PRIMARY KEY, first_caught TEXT NOT NULL,
                    last_caught TEXT NOT NULL, catch_count INTEGER NOT NULL CHECK(catch_count>0));
                CREATE TABLE IF NOT EXISTS capture_events(
                    event_id TEXT PRIMARY KEY, pokemon_id INTEGER NOT NULL, caught_at TEXT NOT NULL);
            ''')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=20); db.row_factory=sqlite3.Row
        try:
            with db: yield db
        finally: db.close()
    def catch(self,pokemon_id,event_id,allowed_ids):
        if type(pokemon_id) is not int or pokemon_id not in allowed_ids: raise ValueError('Invalid Pokémon ID')
        if not isinstance(event_id,str) or not 8<=len(event_id)<=100: raise ValueError('Invalid event ID')
        timestamp=datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT pokemon_id FROM capture_events WHERE event_id=?',(event_id,)).fetchone()
            if existing:
                if existing['pokemon_id']!=pokemon_id: raise ValueError('Capture event conflict')
            else:
                db.execute('INSERT INTO capture_events VALUES(?,?,?)',(event_id,pokemon_id,timestamp))
                db.execute('''INSERT INTO collection VALUES(?,?,?,1) ON CONFLICT(pokemon_id) DO UPDATE
                    SET last_caught=excluded.last_caught,catch_count=collection.catch_count+1''',(pokemon_id,timestamp,timestamp))
            row=db.execute('SELECT * FROM collection WHERE pokemon_id=?',(pokemon_id,)).fetchone()
        return dict(row)
    def all(self):
        with self.connect() as db: return {r['pokemon_id']:dict(r) for r in db.execute('SELECT * FROM collection')}

def dex_rows(catalog,collection,generation,query='',type_name=None,ownership='전체'):
    query=query.strip().casefold().lstrip('#')
    result=[]
    for row in catalog.records:
        pid=row['pokemon_id']; variety=catalog.varieties[pid]
        if row['generation']!=generation or not variety['is_default']: continue
        species=catalog.species[row['species_id']]
        if query and not ((query.isdigit() and int(query)==row['species_id']) or query in (species.get('name_ko') or '').casefold() or query in (species.get('name_en') or '').casefold()): continue
        if type_name and type_name not in (row.get('types') or []): continue
        caught=pid in collection
        if ownership=='수집' and not caught or ownership=='미수집' and caught: continue
        result.append(row)
    return sorted(result,key=lambda r:r['species_id'])
