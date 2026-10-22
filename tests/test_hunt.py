import tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from src.catalog import Catalog
from src.rag import catch_targets
from src.regions import target_regions
from src import game_ui
from src.collection import Collection
from test_services import DATA

class HuntTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=Catalog(DATA)
    def meta(self,pid):
        doc=self.catalog.document(self.catalog.index[(pid,9)])
        return dict(doc['metadata'],id=doc['id'],text=doc['text'])
    def test_exact_cited_targets_not_uncited_candidates(self):
        sources=[self.meta(25),self.meta(26),self.meta(150)]
        self.assertEqual([t['pokemon_id'] for t in catch_targets(self.catalog,'피카츄는 전기 타입일세. [근거 1]',sources)],[25])
        self.assertEqual([t['pokemon_id'] for t in catch_targets(self.catalog,'피카츄와 라이츄일세. [근거 1][근거 2]',sources)],[25,26])
        self.assertEqual(catch_targets(self.catalog,'뮤츠도 있네. [근거 1]',sources),[])
        self.assertEqual(catch_targets(self.catalog,'포켓몬에 관한 연구란다. [근거 1]',sources),[])
        self.assertEqual(catch_targets(self.catalog,'피카츄일세.',sources),[])
        self.assertEqual(catch_targets(self.catalog,'피카츄몬이 있네. [근거 1]',sources),[])
        self.assertEqual({t['pokemon_id'] for t in catch_targets(self.catalog,'라이츄는 피카츄에서 진화하네. [근거 1]',[self.catalog.profile_source(26,full_chain=True)])},{25,26})
    def test_game_name_is_not_species_and_form_is_not_substituted(self):
        source=self.catalog.profile_source(25,full_chain=True)
        self.assertEqual(catch_targets(self.catalog,'레드·그린·블루 기준일세. [근거 1]',[source]),[])
        self.assertEqual(target_regions(self.catalog,10034),[])
    def test_region_rules_and_current_preference(self):
        self.assertEqual(target_regions(self.catalog,25),['electric'])
        self.assertEqual(target_regions(self.catalog,133,'city')[0],'city')
        self.assertEqual(target_regions(self.catalog,133,'grassland')[0],'grassland')
        self.assertEqual(target_regions(self.catalog,-1),[])
    def test_request_and_late_events(self):
        state={'current_region':'electric','lab_panel':'professor'}
        with patch.object(game_ui.st,'session_state',state):
            self.assertFalse(game_ui.request_hunt(self.catalog,25,{26}))
            self.assertTrue(game_ui.request_hunt(self.catalog,25,{25}));request=state['hunt_target']['request_id'];self.assertIsNone(state['lab_panel'])
            self.assertEqual(state['target_pokemon_id'],25)
            self.assertTrue(game_ui.request_hunt(self.catalog,26,{26}));new=state['hunt_target']['request_id']
            state['pokemon_field']={'tracking':{'request_id':request,'status':'cancelled','region':'electric'}};game_ui.update_tracking();self.assertEqual(state['target_pokemon_id'],26)
            state['pokemon_field']['tracking']['request_id']=new;game_ui.update_tracking();self.assertIsNone(state['target_pokemon_id']);self.assertEqual(state['target_status'],'cancelled')
            state['pokemon_field']['tracking']['status']='active';game_ui.update_tracking();self.assertIsNone(state['target_pokemon_id']);self.assertEqual(state['target_status'],'cancelled')
    def test_capture_commit_controls_target_clear(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            state={'collection_path':str(Path(tmp)/'collection.sqlite3'),'field_region_ids':{'electric':[25]},'field_facts':{25:{'id':25}},'pokemon_field':{'capture':{'pokemon_id':25,'event_id':'hunt-save-test','region':'electric'}}}
            with patch.object(game_ui.st,'session_state',state):
                game_ui.set_target({'pokemon_id':25,'region':'electric','status':'active','request_id':'request'})
                with patch.object(Collection,'catch',side_effect=OSError('disk unavailable')): game_ui.record_capture()
                self.assertFalse(state['capture_ack']['ok']);self.assertEqual(state['target_pokemon_id'],25)
                game_ui.record_capture();self.assertTrue(state['capture_ack']['ok']);self.assertIsNone(state['target_pokemon_id']);self.assertEqual(state['target_status'],'captured');self.assertEqual(Collection(state['collection_path']).all()[25]['catch_count'],1)
    def test_buttons_remain_attached_to_messages(self):
        from streamlit.testing.v1 import AppTest
        script="""import streamlit as st
from src.ui_rag import render_conversation
from src.catalog import Catalog
from pathlib import Path
c=Catalog(Path(r'C:\SSAFY\pennant_race_ai_core_2\pokemon-data\data\processed'))
def reply(question,prior):
 d=c.document(c.index[(25,9)])
 return {'answer':'피카츄는 전기 타입일세. [근거 1]','sources':[dict(d['metadata'],id=d['id'],text=d['text'])]}
render_conversation(st.session_state.setdefault('messages',[]),reply,prefix='test',placeholder='질문',catalog=c)
"""
        app=AppTest.from_string(script,default_timeout=30).run()
        for q in ('질문1','질문2'):app.chat_input[0].set_value(q).run()
        self.assertFalse(app.exception);buttons=[b for b in app.button if b.label=='이 포켓몬을 잡으러 가볼까?'];self.assertEqual(len(buttons),2)
        keys=[b.key for b in buttons];app.run();self.assertEqual([b.key for b in app.button if b.label=='이 포켓몬을 잡으러 가볼까?'],keys)
        buttons[0].click().run();self.assertFalse(app.exception);self.assertEqual(app.session_state['target_pokemon_id'],25)

if __name__=='__main__':unittest.main()
