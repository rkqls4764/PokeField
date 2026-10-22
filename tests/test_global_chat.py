import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.catalog import Catalog
from src.settings import Settings
from src.natural_search import global_conditions,filter_rows
from src.rag import RagService,Answer,Claim,cited_sources
from src.llm import ServiceError
from test_services import DATA,FakeLLM,FakeEmbeddings
from src.vector_store import VectorStore

class GlobalChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=Catalog(DATA)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup)
        self.settings=Settings(data_dir=DATA,chroma_dir=Path(self.tmp.name)/'chroma',api_key='fake')
    def test_names_and_types(self):
        self.assertEqual(set(global_conditions(self.catalog,'피카츄와 라이츄의 차이점은?')[0]),{25,26})
        self.assertEqual(global_conditions(self.catalog,'고스트 타입 포켓몬 알려줘')[0],[])
        self.assertEqual(global_conditions(self.catalog,'뮤츠 속성이 뭐야?')[0],[150])
        self.assertEqual(global_conditions(self.catalog,'없는몬 타입 알려줘')[0],[])
    def test_conditions(self):
        for q,ability,scope in [('부유 특성을 가진 포켓몬 알려줘','levitate','any'),('숨겨진 특성이 피뢰침인 포켓몬','lightning-rod','hidden')]:
            _,_,f,c=global_conditions(self.catalog,q)
            self.assertTrue(c); self.assertEqual(f.abilities,[ability]); self.assertEqual(f.ability_scope,scope)
            rows,g,_=filter_rows(self.catalog,f,9,self.settings)
            self.assertEqual(g,9); self.assertTrue(rows)
            self.assertTrue(all(any(a['name']==ability and (scope=='any' or a['is_hidden']) for a in r['abilities']) for r in rows))
        _,_,f,_=global_conditions(self.catalog,'9세대에서 공격력이 120 이상인 포켓몬은?')
        self.assertEqual(f.min_attack,120)
        rows,_,_=filter_rows(self.catalog,f,9,self.settings)
        self.assertTrue(all(r['stats']['attack']>=120 for r in rows))
        _,_,f,_=global_conditions(self.catalog,'빠르고 공격력이 높은 전기 타입 포켓몬 추천해 줘.')
        rows,_,limits=filter_rows(self.catalog,f,9,self.settings)
        self.assertEqual(limits,{'attack':100,'speed':100})
        self.assertTrue(all('electric' in r['types'] and r['stats']['speed']>=100 and r['stats']['attack']>=100 for r in rows))
    def service(self,answer=None):
        store=VectorStore(self.settings,FakeEmbeddings())
        store.upsert('pokemon_meta',[self.catalog.document(r) for r in self.catalog.records if r['pokemon_id'] in (25,26,94)])
        llm=FakeLLM({'generate_answer':answer or Answer(claims=[Claim(text='피카츄는 전기 타입이에요.',citations=[1])])})
        return RagService(self.settings,self.catalog,store,llm)
    def test_global_graph_citations_cache(self):
        service=self.service()
        with patch.object(service.llm,'structured',wraps=service.llm.structured) as generate:
            result=service.ask_global('피카츄 타입 알려줘.')
            again=service.ask_global('피카츄 타입 알려줘.')
            self.assertEqual(generate.call_count,1)
        self.assertEqual(result['answer'],again['answer'])
        self.assertEqual(result['generation'],9)
        self.assertEqual([s['pokemon_id'] for _,s in cited_sources(result['answer'],result['sources'])],[25])
        self.assertIn('전기',result['sources'][0]['text'])
        self.assertEqual(set(service.graph.get_graph().nodes),{'__start__','retrieve','generate','__end__'})
    def test_history_and_multiple(self):
        service=self.service()
        history=service.retrieve_global({'question':'팬텀의 특성이 언제 바뀌었어?'})
        rows={s['generation']:s['text'] for s in history['sources']}
        self.assertIn('부유',rows[6]); self.assertIn('저주받은바디',rows[7])
        result=service.retrieve_global({'question':'피카츄와 라이츄의 차이점은?'})
        self.assertEqual({s['pokemon_id'] for s in result['sources']},{25,26})
    def test_generation_filter_and_no_calls(self):
        service=self.service()
        for gen,count in [(6,1),(7,0)]:
            with patch.object(service.llm,'structured',side_effect=AssertionError('unexpected LLM')):
                state=service.retrieve_global({'question':f'{gen}세대 부유 특성을 가진 팬텀 찾아줘'})
                self.assertEqual(state['search_context']['candidate_count'],count)
                if not count: self.assertIn('찾지 못했구나',service.ask_global(f'{gen}세대 부유 특성을 가진 팬텀 찾아줘')['answer'])
        with patch.object(service.llm,'structured',side_effect=AssertionError('unexpected LLM')):
            self.assertEqual(service.ask_global('없는몬 타입 알려줘')['sources'],[])
            self.assertIn('찾지 못했구나',service.ask_global('공격력 9999 이상인 포켓몬')['answer'])
    def test_invalid_citations_and_api_error(self):
        service=self.service(Answer(claims=[Claim(text='전기 타입이에요.',citations=[99])]))
        with self.assertRaises(ServiceError): service.ask_global('피카츄 타입')
        service=self.service()
        with patch.object(service.llm,'structured',side_effect=ServiceError('test API error')):
            with self.assertRaises(ServiceError): service.ask_global('피카츄 타입')
    def test_global_semantic_store(self):
        service=self.service()
        self.assertTrue(service.store.search_global('포켓몬에 대해 설명해줘',9,2))
        self.assertTrue(all(s['generation']==9 for s in service.store.search_global('설명',9,2)))
    def test_unsupported(self):
        for q in ('공격력 120 이하인 전기 타입','10세대 피카츄','부유 특성 6세대와 7세대 포켓몬'):
            with self.assertRaises(ServiceError): global_conditions(self.catalog,q)
    def test_change_reasons_without_evidence_dropped(self):
        service=self.service(Answer(claims=[Claim(text='밸런스를 위해 특성이 변경됐어요.',citations=[1])]))
        result=service.ask_global('팬텀의 특성이 언제 바뀌었어?')
        self.assertNotIn('밸런스',result['answer'])
        self.assertEqual(cited_sources(result['answer'],result['sources']),[])
    def test_ui_default_no_selection_and_separate_history(self):
        from streamlit.testing.v1 import AppTest
        from types import SimpleNamespace
        service=self.service()
        docs=SimpleNamespace(status=lambda sid:{'documents':[]})
        root=Path(__file__).resolve().parents[1]
        with patch('src.settings.Settings.load',return_value=self.settings),patch('src.ui_rag.services',return_value=(service,docs)),patch('src.ui_rag.index_counts',return_value={}),patch('src.llm.LanguageModel.complete',side_effect=AssertionError('paid API')),patch('src.llm.Embeddings.embed',side_effect=AssertionError('paid embedding')):
            app=AppTest.from_file(str(root/'app.py'),default_timeout=30)
            app.session_state['lab_panel']='tools'
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.radio(key='chat_mode').value,'전체 포켓몬 질문')
            app.text_input(key='name_query').set_value('일치하지않는이름').run()
            self.assertFalse(app.exception)
            app.chat_input(key='global_pokemon_question').set_value('피카츄 타입 알려줘.').run()
            self.assertFalse(app.exception); self.assertEqual(len(app.session_state['global_history']),2)
            app.text_input(key='name_query').set_value('').run()
            app.selectbox(key='selected_pokemon').set_value(25).run()
            app.radio(key='chat_mode').set_value('선택한 포켓몬 질문').run()
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state['histories'])
            self.assertTrue(all(not history for history in app.session_state['histories'].values()))
            app.radio(key='chat_mode').set_value('전체 포켓몬 질문').run()
            self.assertEqual(len(app.session_state['global_history']),2)
            with patch.object(service,'ask_global',side_effect=AssertionError('rerun called ask')): app.run()
            self.assertFalse(app.exception)

if __name__=='__main__': unittest.main()
