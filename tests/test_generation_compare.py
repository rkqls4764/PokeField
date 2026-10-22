"""F2010 tests: real JSONL/Chroma, existing fake API adapters; no paid calls."""
import copy
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from test_services import DATA,FakeEmbeddings,FakeLLM
from src.catalog import Catalog
from src.settings import Settings
from src.vector_store import VectorStore
from src.rag import RagService,cited_sources,validate_citations
from src.llm import ServiceError
from src.generation_compare import compare_generations,analyze_comparison,ComparisonAnswer,ComparisonClaim

class RecordingLLM(FakeLLM):
    def __init__(self,result):
        super().__init__({'generate_answer':result}); self.calls=[]
    def structured(self,prompt,payload,schema,purpose,cache=True):
        self.calls.append({'prompt':prompt,'payload':payload,'schema':schema})
        return super().structured(prompt,payload,schema,purpose,cache)

class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=Catalog(DATA)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup)
        self.settings=Settings(data_dir=DATA,chroma_dir=Path(self.tmp.name)/'chroma',api_key='test',auto_collect=True)
        self.emb=FakeEmbeddings(); self.store=VectorStore(self.settings,self.emb)
        self.store.upsert('pokemon_meta',[self.catalog.document(r) for r in self.catalog.records if r['pokemon_id'] in (25,35,94)])
        self.llm=RecordingLLM(ComparisonAnswer(claims=[ComparisonClaim(text='팬텀의 일반 특성이 부유에서 저주받은바디로 변경됐습니다.',citations=[1,2])]))
        self.documents=SimpleNamespace(collect=Mock(side_effect=AssertionError('Unexpected collection')))
        self.rag=RagService(self.settings,self.catalog,self.store,self.llm,self.documents)
        # Any accidental use of production clients must fail the test, even if .env exists.
        self.addCleanup(patch.stopall)
        patch('src.llm.LanguageModel.complete',side_effect=AssertionError('Paid LLM forbidden')).start()
        patch('src.llm.Embeddings.embed',side_effect=AssertionError('Paid embedding forbidden')).start()
    def comparison(self): return compare_generations(self.catalog,94,6,7)
    def field(self,result,key): return next(f for f in result['fields'] if f['key']==key)
    def add_external(self,text,hash_value='v1'):
        self.store.upsert('pokemon_docs',[{'id':'f2010:reason','text':text,'metadata':{'species_id':94,'title':'모의 외부 문서','source_url':'https://example.org/test-fixture','source_type':'external_document','content_hash':hash_value}}])
    def test_gengar_ability_change(self):
        result=self.comparison(); field=self.field(result,'abilities')
        self.assertEqual(field['before'],['levitate']); self.assertEqual(field['after'],['cursed-body'])
        self.assertEqual(field['status'],'changed'); self.assertIn('부유',field['before_display']); self.assertIn('저주받은바디',field['after_display'])
    def test_clefairy_type_change(self):
        result=compare_generations(self.catalog,35,5,6); field=self.field(result,'types')
        self.assertEqual((field['before_display'],field['after_display']),('노말','페어리')); self.assertEqual(field['status'],'changed')
    def test_pikachu_numeric_differences(self):
        result=compare_generations(self.catalog,25,5,6)
        self.assertEqual(self.field(result,'defense')['delta'],10)
        self.assertEqual(self.field(result,'special_defense')['delta'],10)
        self.assertEqual(self.field(result,'total')['delta'],20)
        self.assertEqual(self.field(result,'attack')['status'],'unchanged')
    def test_same_generation_skips_every_api(self):
        result=analyze_comparison(self.rag,compare_generations(self.catalog,94,6,6))
        self.assertTrue(result['skipped']); self.assertEqual(self.llm.calls,[])
    def test_missing_generation_skips_every_api(self):
        comparison=compare_generations(self.catalog,94,0,7)
        self.assertEqual(comparison['status'],'missing_generation')
        self.assertTrue(analyze_comparison(self.rag,comparison)['skipped']); self.assertEqual(self.llm.calls,[])
    def test_reversed_generation_is_not_analyzed(self):
        result=compare_generations(self.catalog,94,7,6)
        self.assertEqual(result['status'],'invalid_order'); self.assertFalse(result['has_changes'])
    def test_unchanged_data_skips_every_api(self):
        comparison=compare_generations(self.catalog,94,7,8)
        self.assertFalse(comparison['has_changes'])
        calls=self.emb.calls; self.assertTrue(analyze_comparison(self.rag,comparison)['skipped'])
        self.assertEqual(self.llm.calls,[]); self.assertEqual(self.emb.calls,calls)
    def test_missing_stat_is_unknown_not_a_change(self):
        catalog=copy.copy(self.catalog); catalog.index=dict(catalog.index)
        row=copy.deepcopy(catalog.index[(25,5)]); row['stats']['defense']=None; row['types']=None
        catalog.index[(25,5)]=row
        result=compare_generations(catalog,25,5,6)
        self.assertEqual(self.field(result,'defense')['status'],'unknown'); self.assertIsNone(self.field(result,'defense')['delta'])
        self.assertEqual(self.field(result,'types')['status'],'unknown')
    def test_gen_one_special_and_total_not_directly_compared(self):
        result=compare_generations(self.catalog,25,1,2)
        for key in ('special','special_attack','special_defense','total'):
            self.assertEqual(self.field(result,key)['status'],'not_comparable'); self.assertIsNone(self.field(result,key)['delta'])
    def test_hidden_abilities_are_separate(self):
        catalog=copy.copy(self.catalog); catalog.index=dict(catalog.index)
        row=copy.deepcopy(catalog.index[(25,6)]); row['abilities']=[a for a in row['abilities'] if not a['is_hidden']]
        catalog.index[(25,6)]=row
        result=compare_generations(catalog,25,5,6)
        self.assertEqual(self.field(result,'hidden_abilities')['status'],'changed')
        self.assertEqual(self.field(result,'abilities')['status'],'unchanged')
    def test_only_two_metadata_generations_and_one_llm_call(self):
        result=analyze_comparison(self.rag,self.comparison())
        self.assertEqual(len(self.llm.calls),1)
        ids={s['id'] for s in result['sources'] if s['source_type']=='pokemon_metadata'}
        self.assertEqual(ids,{'pokemon:94:gen:6','pokemon:94:gen:7'})
        self.assertEqual(self.documents.collect.call_count,0)
        self.assertEqual(self.llm.calls[0]['payload']['python_comparison']['before_generation'],6)
        self.assertNotIn('9세대',str(self.llm.calls[0]['payload']['evidence']))
        self.assertEqual(set(self.rag.graph.get_graph().nodes),{'__start__','retrieve','generate','__end__'})
    def test_analysis_cache_avoids_llm_and_query_embedding(self):
        self.add_external('팬텀의 특성에 대한 설명입니다.')
        first=analyze_comparison(self.rag,self.comparison()); before=self.emb.calls
        again=analyze_comparison(self.rag,self.comparison())
        self.assertFalse(first['cached']); self.assertTrue(again['cached'])
        self.assertEqual(len(self.llm.calls),1); self.assertEqual(self.emb.calls,before)
    def test_cache_invalidates_for_search_settings_and_corpus(self):
        analyze_comparison(self.rag,self.comparison())
        self.rag.settings=replace(self.settings,top_k=2)
        analyze_comparison(self.rag,self.comparison()); self.assertEqual(len(self.llm.calls),2)
        self.add_external('팬텀의 새로운 설명 문서입니다.')
        analyze_comparison(self.rag,self.comparison()); self.assertEqual(len(self.llm.calls),3)
    def test_reason_without_external_evidence_is_dropped(self):
        self.llm.outputs['generate_answer']=ComparisonAnswer(claims=[ComparisonClaim(text='밸런스를 위해 변경했습니다.',kind='reason',citations=[1,2])])
        result=analyze_comparison(self.rag,self.comparison())
        self.assertNotIn('밸런스를 위해',result['answer']); self.assertIn('이유는 검색된 외부 문서에서 확인되지',result['answer'])
    def test_reason_disguised_as_change_is_dropped(self):
        self.llm.outputs['generate_answer']=ComparisonAnswer(claims=[ComparisonClaim(text='밸런스 때문에 팬텀의 특성이 변경됐습니다.',citations=[1,2])])
        result=analyze_comparison(self.rag,self.comparison()); self.assertNotIn('밸런스 때문에',result['answer'])
    def test_external_fact_is_not_accepted_as_reason(self):
        quote='팬텀은 고스트 타입 포켓몬입니다.'; self.add_external(quote)
        self.llm.outputs['generate_answer']=ComparisonAnswer(claims=[ComparisonClaim(text='변경 이유입니다.',kind='reason',citations=[3],evidence_quote=quote)])
        result=analyze_comparison(self.rag,self.comparison()); self.assertNotIn('외부 문서에 명시된 변경 이유:',result['answer'])
    def test_exact_external_reason_quote_and_source_number(self):
        quote='게임 밸런스 조정을 위해 팬텀의 특성을 변경했다.'; self.add_external(quote)
        self.llm.outputs['generate_answer']=ComparisonAnswer(claims=[ComparisonClaim(text='추가로 지어낸 설명은 렌더링하지 않는다.',kind='reason',citations=[3],evidence_quote=quote)])
        result=analyze_comparison(self.rag,self.comparison())
        self.assertIn(quote,result['answer']); self.assertNotIn('지어낸 설명',result['answer'])
        self.assertTrue(validate_citations(result['answer'],result['sources']))
        self.assertEqual([(n,s['id']) for n,s in cited_sources(result['answer'],result['sources'])],[(3,'f2010:reason')])
    def test_invented_reason_quote_is_not_displayed(self):
        self.add_external('팬텀의 특성은 세대에 따라 다릅니다.')
        self.llm.outputs['generate_answer']=ComparisonAnswer(claims=[ComparisonClaim(text='밸런스 때문입니다.',kind='reason',citations=[3],evidence_quote='밸런스를 위해 변경했다.')])
        result=analyze_comparison(self.rag,self.comparison()); self.assertNotIn('밸런스를 위해',result['answer'])
    def test_invalid_citation_reuses_existing_guard(self):
        self.llm.outputs['generate_answer']=ComparisonAnswer(claims=[ComparisonClaim(text='변경됨',citations=[99])])
        with self.assertRaises(ServiceError): analyze_comparison(self.rag,self.comparison())
    def test_missing_second_metadata_stops_before_llm(self):
        self.store.collections['pokemon_meta'].delete(ids=['pokemon:94:gen:6'])
        with self.assertRaises(ServiceError): analyze_comparison(self.rag,self.comparison())
        self.assertEqual(self.llm.calls,[])
    def test_streamlit_selectors_no_call_button_one_call_and_cache(self):
        from streamlit.testing.v1 import AppTest
        root=Path(__file__).resolve().parents[1]
        docs=SimpleNamespace(status=lambda sid:{'documents':[]},collect=self.documents.collect)
        with patch('src.settings.Settings.load',return_value=self.settings),patch('src.ui_rag.services',return_value=(self.rag,docs)),patch('src.ui_rag.index_counts',return_value=self.store.counts()):
            app=AppTest.from_file(str(root/'app.py'),default_timeout=30)
            app.session_state['lab_panel']='tools'
            app.run()
            self.assertFalse(app.exception)
            app.text_input(key='name_query').set_value('팬텀').run()
            next(s for s in app.selectbox if s.label=='이전 세대').select(6).run()
            next(s for s in app.selectbox if s.label=='이후 세대').select(7).run()
            self.assertEqual(len(self.llm.calls),0)
            next(b for b in app.button if b.label=='AI 변화 분석').click().run()
            self.assertFalse(app.exception); self.assertEqual(len(self.llm.calls),1)
            self.assertTrue(any('답변에 사용한 근거' in e.label for e in app.expander))
            app.run(); self.assertEqual(len(self.llm.calls),1)
            next(b for b in app.button if b.label=='AI 변화 분석').click().run()
            self.assertFalse(app.exception); self.assertEqual(len(self.llm.calls),1)
            next(s for s in app.selectbox if s.label=='이전 세대').select(7).run()
            self.assertTrue(next(b for b in app.button if b.label=='AI 변화 분석').disabled)
            self.assertEqual(len(self.llm.calls),1)

if __name__=='__main__': unittest.main()
