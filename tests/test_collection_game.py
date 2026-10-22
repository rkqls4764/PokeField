import base64
import hashlib
from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from src.collection import Collection,dex_rows
from src.catalog import Catalog
from src.game_ui import image_uri,record_capture,open_panel,existing_raw
from src.natural_search import global_conditions,filter_rows
from test_services import DATA
from src.settings import Settings

class CollectionGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=Catalog(DATA)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'collection.sqlite3';self.db=Collection(self.path)
    def test_first_repeat_and_reload(self):
        a=self.db.catch(25,'event-0001',{25})
        b=self.db.catch(25,'event-0002',{25})
        self.assertEqual(a['first_caught'],b['first_caught']);self.assertEqual(b['catch_count'],2)
        self.assertEqual(Collection(self.path).all()[25],b)
        self.assertEqual(len(self.db.all()),1)
    def test_retry_idempotent_and_conflict_atomic(self):
        self.db.catch(25,'event-0001',{25,26});self.db.catch(25,'event-0001',{25,26})
        with self.assertRaises(ValueError):self.db.catch(26,'event-0001',{25,26})
        self.assertEqual(self.db.all()[25]['catch_count'],1);self.assertNotIn(26,self.db.all())
    def test_bad_event_does_not_write(self):
        for pid,event in [(99999,'event-0001'),(True,'event-0002'),(25,'x'),(25,None)]:
            with self.assertRaises(ValueError):self.db.catch(pid,event,{25})
        self.assertEqual(self.db.all(),{})
    def test_concurrent_catches_not_lost(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i:self.db.catch(25,f'event-{i:04}',{25}),range(12)))
        self.assertEqual(self.db.all()[25]['catch_count'],12)
    def test_all_dex_open_without_capture_and_filters(self):
        rows=dex_rows(self.catalog,{},9)
        self.assertEqual(len(rows),1025);self.assertEqual(len({r['pokemon_id'] for r in rows}),1025)
        self.assertEqual([r['pokemon_id'] for r in dex_rows(self.catalog,{},9,'피카츄')],[25])
        self.assertEqual([r['pokemon_id'] for r in dex_rows(self.catalog,{},9,'#0025')],[25])
        self.assertTrue(all('electric' in r['types'] for r in dex_rows(self.catalog,{},9,type_name='electric')))
        self.db.catch(25,'event-0001',{25});caught=self.db.all()
        self.assertEqual([r['pokemon_id'] for r in dex_rows(self.catalog,caught,9,ownership='수집')],[25])
        self.assertNotIn(25,[r['pokemon_id'] for r in dex_rows(self.catalog,caught,9,ownership='미수집')])
        self.assertTrue(all(r['generation']==1 for r in dex_rows(self.catalog,caught,1)))
    def test_callback_ack_after_commit(self):
        state={'collection_path':str(self.path),'field_pool_ids':[25],'pokemon_field':{'capture':{'pokemon_id':25,'event_id':'event-0001'}}}
        with patch('src.game_ui.st.session_state',state):record_capture()
        self.assertTrue(state['capture_ack']['ok']);self.assertEqual(self.db.all()[25]['catch_count'],1)
        with patch('src.game_ui.st.session_state',state):record_capture()
        self.assertEqual(self.db.all()[25]['catch_count'],1)
    def test_callback_failure_never_reports_success(self):
        state={'collection_path':str(self.path),'field_pool_ids':[25],'pokemon_field':{'capture':{'pokemon_id':26,'event_id':'event-0001'}}}
        with patch('src.game_ui.st.session_state',state),self.assertLogs('src.game_ui',level='ERROR'):record_capture()
        self.assertFalse(state['capture_ack']['ok']);self.assertEqual(self.db.all(),{})
    def test_panel_event(self):
        state={'pokemon_field':{'action':{'panel':'professor'}}}
        with patch('src.game_ui.st.session_state',state):open_panel()
        self.assertEqual(state['lab_panel'],'professor')
    def test_existing_transparency_preserved_without_source_write(self):
        from PIL import Image
        path=DATA.parent/'images/official/25.png';before=hashlib.sha256(path.read_bytes()).hexdigest()
        uri=image_uri(str(path));image=Image.open(BytesIO(base64.b64decode(uri.split(',')[1])))
        self.assertEqual(image.mode,'RGBA');self.assertEqual(image.getpixel((0,0))[3],0)
        self.assertTrue(any(r>220 and g>220 and b>220 and a>200 for r,g,b,a in image.getdata()))
        self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(image_uri(str(Path(self.tmp.name)/'missing.png')),'')
    def test_relative_search_examples(self):
        settings=Settings(data_dir=DATA,chroma_dir=Path(self.tmp.name)/'chroma')
        for q,stat,kind in [('공격력이 높은 불꽃 타입','attack','fire'),('스피드가 빠른 전기 타입','speed','electric'),('방어력이 높은 1세대 포켓몬','defense',None)]:
            _,gens,f,_=global_conditions(self.catalog,q);rows,_,limits=filter_rows(self.catalog,f,gens[-1] if gens else 9,settings)
            self.assertTrue(rows);self.assertEqual(limits[stat],100)
            self.assertTrue(all(r['stats'][stat]>=100 and (not kind or kind in r['types']) for r in rows))
    def test_detail_uses_existing_raw_cache_without_network(self):
        raw=existing_raw(str(DATA),'https://pokeapi.co/api/v2/pokemon/25/')
        self.assertEqual(raw.get('height'),4);self.assertEqual(raw.get('weight'),60)
        self.assertEqual(existing_raw(str(DATA),'https://pokeapi.co/api/v2/not-collected/unknown/'),{})

if __name__=='__main__': unittest.main()
