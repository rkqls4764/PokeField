import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.catalog import Catalog,TYPE_KO
from src.regions import REGIONS,canonical_type,region_candidates,capture_fact
from src.collection import Collection
from src.game_ui import record_capture,open_panel
from test_services import DATA

class RegionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.catalog=Catalog(DATA)
    def test_nine_regions_cover_all_eighteen_types(self):
        self.assertEqual(len(REGIONS),9)
        self.assertEqual(set().union(*(set(r['types']) for r in REGIONS)),set(TYPE_KO))
        self.assertEqual([r['name'] for r in REGIONS],['초원','바다','하늘','사막','동굴','눈','도시','전기','화산'])
    def test_each_region_only_matching_unique_generation_nine_defaults(self):
        for region in REGIONS:
            rows=region_candidates(self.catalog,region['id'])
            self.assertGreaterEqual(len(rows),10)
            self.assertEqual(len(rows),len({r['pokemon_id'] for r in rows}))
            self.assertTrue(all(r['generation']==9 and set(r['types'])&set(region['types']) and self.catalog.varieties[r['pokemon_id']]['is_default'] for r in rows))
    def test_dual_type_matches_either(self):
        self.assertIn(6,{r['pokemon_id'] for r in region_candidates(self.catalog,'volcano')})
        self.assertIn(6,{r['pokemon_id'] for r in region_candidates(self.catalog,'sky')})
        self.assertNotIn(25,{r['pokemon_id'] for r in region_candidates(self.catalog,'sea')})
    def test_korean_and_english_types(self):
        for identifier,ko in TYPE_KO.items():self.assertEqual(canonical_type(ko),identifier);self.assertEqual(canonical_type(identifier.upper()),identifier)
        from types import SimpleNamespace
        c=SimpleNamespace(records=[{'pokemon_id':1,'generation':9,'types':['물','비행']}],varieties={1:{'is_default':True}})
        self.assertEqual(len(region_candidates(c,'sea')),1);self.assertEqual(region_candidates(c,'electric'),[])
    def test_unknown_region_and_missing_generation(self):
        with self.assertRaises(ValueError):region_candidates(self.catalog,'unknown')
        self.assertEqual(region_candidates(self.catalog,'sea',99),[])
    def test_capture_facts_come_from_data(self):
        fact=capture_fact(self.catalog,self.catalog.index[(25,9)])
        self.assertEqual(fact['name'],'피카츄');self.assertEqual(fact['types'],['전기']);self.assertEqual(fact['generation'],9)
        self.assertEqual(fact['stats']['attack'],self.catalog.index[(25,9)]['stats']['attack'])
    def test_region_validation_commit_ack_and_duplicate_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'collection.sqlite3';db=Collection(path)
            state={'collection_path':str(path),'field_region_ids':{'electric':[25],'sea':[7]},'field_facts':{25:capture_fact(self.catalog,self.catalog.index[(25,9)])},'pokemon_field':{'capture':{'pokemon_id':25,'region':'electric','event_id':'region-event-001'}}}
            with patch('src.game_ui.st.session_state',state):record_capture()
            self.assertEqual(state['capture_ack']['record']['catch_count'],1);self.assertEqual(state['capture_ack']['detail']['name'],'피카츄')
            state['pokemon_field']['capture']['event_id']='region-event-002'
            with patch('src.game_ui.st.session_state',state):record_capture()
            self.assertEqual(state['capture_ack']['record']['catch_count'],2);self.assertEqual(len(db.all()),1)
            state['pokemon_field']['capture'].update(region='sea',event_id='region-event-003')
            with patch('src.game_ui.st.session_state',state),self.assertLogs('src.game_ui',level='ERROR'):record_capture()
            self.assertFalse(state['capture_ack']['ok']);self.assertEqual(db.all()[25]['catch_count'],2)
    def test_popup_opens_correct_dex_detail(self):
        state={'pokemon_field':{'action':{'panel':'dex','pokemon_id':25}},'field_facts':{25:{'name':'피카츄'}}}
        with patch('src.game_ui.st.session_state',state):open_panel()
        self.assertEqual(state['dex_detail_id'],25);self.assertEqual(state['dex_query'],'피카츄')
    def test_assets_are_real_files_and_static_serving_enabled(self):
        root=Path(__file__).resolve().parents[1]
        self.assertIn('enableStaticServing = true',(root/'.streamlit/config.toml').read_text(encoding='utf-8'))
        for name in [r['id']+'.png' for r in REGIONS]+['professor.jpg','ball.jpg']:
            self.assertTrue((root/'static/regions'/name).is_file(),name)
    def test_prefilled_dex_detail_has_no_widget_warning(self):
        from streamlit.testing.v1 import AppTest
        from src.settings import Settings
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            settings=Settings(data_dir=DATA,chroma_dir=Path(tmp)/'chroma',api_key='')
            with patch('src.settings.Settings.load',return_value=settings):
                app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
                app.session_state['lab_panel']='dex';app.session_state['dex_generation']=9
                app.session_state['dex_detail_id']=25;app.session_state['dex_query']='피카츄';app.run()
                self.assertFalse(app.exception);self.assertFalse(app.warning)
                self.assertEqual(app.selectbox(key='dex_generation').value,9)
                self.assertTrue(any('피카츄' in s.value for s in app.subheader))

if __name__=='__main__':unittest.main()
