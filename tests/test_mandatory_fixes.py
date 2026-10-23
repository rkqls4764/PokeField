import tempfile,unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import Mock,patch
from types import SimpleNamespace
from src.catalog import Catalog
from src.settings import Settings
from src.rag import RagService,Answer,Claim,validate_citations
from src.llm import ServiceError
from src.ui_rag import check_chat_request,chat_notice
from src.natural_search import NaturalSearch
from test_services import DATA,FakeLLM

class MandatoryFixTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.catalog=Catalog(DATA)
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.addCleanup(self.tmp.cleanup)
  self.settings=Settings(DATA,Path(self.tmp.name)/'chroma',api_key='fake')
  self.store=Mock();self.store.get_meta.side_effect=self.metadata;self.store.search_docs.return_value=[]
 def metadata(self,pid,gen):
  d=self.catalog.document(self.catalog.index[(pid,gen)])
  return [dict(id=d['id'],text=d['text'],**d['metadata'])]
 def service(self):return RagService(self.settings,self.catalog,self.store,FakeLLM({'generate_answer':Answer(claims=[Claim(text='피카츄에 관한 근거일세.',citations=[1])])}))
 def test_selected_evolution_type_move_and_general_require_index(self):
  for q in ['피카츄 진화는 뭐야?','피카츄 약점은?','피카츄는 어떤 기술을 배워?','피카츄 타입 알려줘']:
   r=self.service().ask(25,9,q)
   self.assertIn('pokemon:25:gen:9',[s['id'] for s in r['sources']]);self.assertTrue(validate_citations(r['answer'],r['sources']))
 def test_missing_selected_index_is_explicit_in_all_paths(self):
  self.store.get_meta.side_effect=None;self.store.get_meta.return_value=[]
  for q in ['진화는?','약점은?','어떤 기술을 배워?','타입은?']:
   with self.assertRaises(ServiceError) as e:self.service().ask(25,9,q)
   self.assertEqual(e.exception.stage,'metadata_index')
 def test_top_k_merge_dedup_and_numbering(self):
  d=dict(self.metadata(25,9)[0],id='external:test',source_type='external_document')
  self.store.search_docs.return_value=[d,d]
  for k in (1,3,7):
   service=self.service();service.settings=replace(self.settings,top_k=k)
   r=service.retrieve({'pokemon_id':25,'generation':9,'question':'타입은?'})
   self.store.search_docs.assert_called_with('타입은?',25,k)
   self.assertEqual(len(r['sources']),2);self.assertEqual([s['number'] for s in r['sources']],[1,2])
 def test_keyless_local_graphs_never_call_model(self):
  forbidden=Mock();forbidden.check_key.side_effect=AssertionError('paid');forbidden.structured.side_effect=AssertionError('paid')
  service=RagService(replace(self.settings,api_key=''),self.catalog,self.store,forbidden)
  for q in ['피카츄 약점은?','피카츄는 어떤 기술을 배워?']:
   self.assertTrue(service.ask_global(q)['answer']);self.assertTrue(service.ask(25,9,q)['answer'])
 def test_preflight_safe_messages_and_local_exemption(self):
  settings=replace(self.settings,api_key='')
  for q in ['피카츄 약점은?','피카츄는 어떤 기술을 배워?']:check_chat_request(settings,q,False)
  for indexed,stage in [(True,'api_key'),(False,'metadata_index')]:
   with self.assertRaises(ServiceError) as e:check_chat_request(settings,'피카츄 타입은?',indexed)
   self.assertEqual(e.exception.stage,stage);self.assertNotIn('Traceback',chat_notice(e.exception))
  self.assertIn('GMS_KEY',chat_notice(ServiceError('',stage='api_key')))
  self.assertIn('index_pokemon.py',chat_notice(ServiceError('',stage='metadata_index')))
  self.assertIn('다시 시도',chat_notice(ServiceError('SECRET',category='connection')))
  self.assertNotIn('SECRET',chat_notice(RuntimeError('SECRET')))
 def test_move_first_and_more_page_question_selection(self):
  from streamlit.testing.v1 import AppTest
  script="""from pathlib import Path
from src.settings import Settings
from src.catalog import Catalog
from src.ui_rag import render_natural_search
s=Settings.load();render_natural_search(s,Catalog(s.data_dir),9,Path('missing-image-directory'))
"""
  with patch('src.settings.Settings.load',return_value=replace(self.settings,api_key='')):
   app=AppTest.from_string(script,default_timeout=30).run()
   app.text_input[0].set_value('몸통박치기를 배우는 포켓몬 알려줘')
   app.button[0].click().run();self.assertFalse(app.exception)
   ids1={b.key for b in app.button if b.key and b.key.startswith('choose_')};self.assertTrue(ids1)
   app.button(key='natural_more_moves').click().run();self.assertFalse(app.exception)
   ids2={b.key for b in app.button if b.key and b.key.startswith('choose_')};self.assertTrue(ids2);self.assertNotEqual(ids1,ids2)
   key=next(iter(ids2));pid=int(key.split('_')[1]);app.button(key=key).click().run()
   self.assertEqual(app.session_state['pending_pokemon'],{'pokemon_id':pid,'generation':9})
 def test_empty_global_evidence_is_not_an_api_error(self):
  self.store.search_global.return_value=[]
  r=self.service().ask_global('알 수 없는 은하대회 정보')
  self.assertFalse(r['sources']);self.assertIn('근거',r['answer'])
