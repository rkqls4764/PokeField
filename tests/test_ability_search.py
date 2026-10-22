"""Ability search and answer presentation regressions: no paid API calls."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from test_services import DATA,FakeLLM,FakeEmbeddings
from src.catalog import Catalog
from src.settings import Settings
from src.natural_search import Filters,Picks,Pick,NaturalSearch,filter_rows
from src.llm import ServiceError
from src.rag import RagService,Answer,Claim,cited_sources,validate_citations
from src.vector_store import VectorStore

class CountingLLM(FakeLLM):
    def __init__(self,outputs=None): super().__init__(outputs or {}); self.calls=[]
    def structured(self,prompt,payload,schema,purpose,cache=True):
        self.calls.append((purpose,prompt,payload))
        return super().structured(prompt,payload,schema,purpose,cache)

class AbilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=Catalog(DATA)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup)
        self.settings=Settings(data_dir=DATA,chroma_dir=Path(self.tmp.name)/'chroma',api_key='')
        self.llm=CountingLLM(); self.search=NaturalSearch(self.settings,self.catalog,self.llm)
        self.addCleanup(patch.stopall)
        patch('src.llm.LanguageModel.complete',side_effect=AssertionError('Paid LLM forbidden')).start()
        patch('src.llm.Embeddings.embed',side_effect=AssertionError('Paid embedding forbidden')).start()
    def assert_ability_results(self,result,name,hidden=None):
        self.assertGreater(result['candidate_count'],0); self.assertTrue(result['results'])
        for item in result['results']:
            matches=[a for a in item['row']['abilities'] if a['name']==name and (hidden is None or a['is_hidden']==hidden)]
            self.assertTrue(matches); self.assertTrue(item['matched_abilities'])
            self.assertEqual(item['row']['generation'],result['generation'])
    def test_default_ui_generation_and_local_levitate(self):
        result=self.search.run('부유를 특성으로 가지는 포켓몬 찾아줘',9)
        self.assertEqual(result['generation'],9); self.assertEqual(result['filters']['abilities'],['levitate'])
        self.assert_ability_results(result,'levitate'); self.assertEqual(self.llm.calls,[])
    def test_generation_six_includes_gengar_in_actual_matches(self):
        result=self.search.run('6세대에 부유 특성을 가진 포켓몬 찾아줘',9)
        rows,gen,_=filter_rows(self.catalog,Filters.model_validate(result['filters']),9,self.settings)
        self.assertEqual(gen,6); self.assertIn(94,[r['pokemon_id'] for r in rows]); self.assertEqual(self.llm.calls,[])
    def test_generation_seven_named_gengar_has_no_levitate(self):
        result=self.search.run('7세대에서 부유 특성을 가진 팬텀 찾아줘',9)
        self.assertEqual(result['filters']['species_ids'],[94]); self.assertEqual(result['generation'],7)
        self.assertEqual(result['candidate_count'],0); self.assertEqual(result['results'],[]); self.assertEqual(self.llm.calls,[])
    def test_intimidate_uses_full_mapping(self):
        result=self.search.run('위협 특성을 가진 포켓몬 찾아줘',9)
        self.assert_ability_results(result,'intimidate'); self.assertEqual(self.llm.calls,[])
    def test_hidden_lightning_rod(self):
        result=self.search.run('숨겨진 특성이 피뢰침인 포켓몬 찾아줘',9)
        self.assertEqual(result['filters']['ability_scope'],'hidden'); self.assert_ability_results(result,'lightning-rod',True)
        self.assertTrue(all(a['is_hidden'] for item in result['results'] for a in item['matched_abilities']))
        self.assertEqual(self.llm.calls,[])
    def test_ghost_type_is_not_mistaken_for_haunter_species(self):
        result=self.search.run('부유 특성을 가진 고스트 타입 포켓몬 찾아줘',6)
        self.assertEqual(result['filters']['types'],['ghost']); self.assertEqual(result['filters']['species_ids'],[])
        self.assert_ability_results(result,'levitate')
        self.assertTrue(all('ghost' in item['row']['types'] for item in result['results'])); self.assertEqual(self.llm.calls,[])
    def test_english_identifier_search(self):
        result=self.search.run('6세대에서 Levitate 특성을 가진 포켓몬 찾아줘',9)
        self.assertEqual(result['filters']['abilities'],['levitate']); self.assertEqual(result['generation'],6); self.assertEqual(self.llm.calls,[])
    def test_aliases_share_catalog_mapping_including_manual_file(self):
        self.assertEqual(self.catalog.resolve_ability('부유'),'levitate')
        self.assertEqual(self.catalog.resolve_ability('Lightning Rod'),'lightning-rod')
        for identifier,ko in self.catalog.ability_names.items():
            self.assertEqual(self.catalog.resolve_ability(identifier),identifier)
            normalized=__import__('re').sub(r'[\s_-]+','',ko.casefold())
            if len(self.catalog.ability_aliases[normalized])==1: self.assertEqual(self.catalog.resolve_ability(ko),identifier)
    def test_normal_and_hidden_filters_are_different(self):
        rows,_,_=filter_rows(self.catalog,Filters(abilities=['lightning-rod'],ability_scope='normal'),9,self.settings)
        self.assertTrue(rows); self.assertTrue(all(any(a['name']=='lightning-rod' and not a['is_hidden'] for a in r['abilities']) for r in rows))
        self.assertNotIn(25,[r['pokemon_id'] for r in rows])
        hidden,_,_=filter_rows(self.catalog,Filters(abilities=['lightning-rod'],ability_scope='hidden'),9,self.settings)
        self.assertIn(25,[r['pokemon_id'] for r in hidden])
    def test_unknown_generation_ability_data_is_excluded(self):
        catalog=copy.copy(self.catalog); catalog.records=copy.deepcopy(self.catalog.records)
        row=next(r for r in catalog.records if r['pokemon_id']==94 and r['generation']==6); row['abilities']=None
        rows,_,_=filter_rows(catalog,Filters(abilities=['levitate']),6,self.settings)
        self.assertNotIn(94,[r['pokemon_id'] for r in rows])
        early,_,_=filter_rows(catalog,Filters(abilities=['levitate']),2,self.settings); self.assertEqual(early,[])
        early_hidden,_,_=filter_rows(catalog,Filters(abilities=['lightning-rod'],ability_scope='hidden'),4,self.settings); self.assertEqual(early_hidden,[])
    def test_complex_ability_numeric_filter_uses_only_extraction_call(self):
        self.llm.outputs['extract_filters']=Filters(generation=6,min_attack=100,types=['ghost'])
        result=self.search.run('6세대에서 부유 특성을 가진 고스트 타입 중 공격력 100 이상인 포켓몬 찾아줘',9)
        self.assertEqual(result['filters']['abilities'],['levitate']); self.assertEqual(result['filters']['types'],['ghost'])
        self.assertEqual([c[0] for c in self.llm.calls],['extract_filters'])
        self.assertTrue(all(item['row']['stats']['attack']>=100 for item in result['results']))
    def test_complex_known_ability_conditions_not_dropped(self):
        self.llm.outputs['extract_filters']=Filters(generation=6,min_attack=50,types=['ghost'])
        result=self.search.run('6세대에서 부유 특성을 가진 고스트 타입 중 공격력 50 이상인 포켓몬 찾아줘',9)
        self.assertEqual(result['filters']['abilities'],['levitate']); self.assertTrue(result['results'])
        self.assertEqual([c[0] for c in self.llm.calls],['extract_filters'])
        self.assertTrue(all(item['row']['stats']['attack']>=50 and 'ghost' in item['row']['types'] for item in result['results']))
    def test_existing_numeric_electric_search(self):
        self.llm.outputs['extract_filters']=Filters(types=['electric'],min_attack=120)
        self.llm.outputs['select_candidates']=lambda p:Picks(candidates=[Pick(pokemon_id=p['candidates'][0]['pokemon_id'],reason='전기 타입이고 공격 조건을 충족해요.')])
        result=self.search.run('공격력 120 이상인 전기 타입 포켓몬 찾아줘',9)
        self.assertTrue(result['results']); self.assertEqual([c[0] for c in self.llm.calls],['extract_filters','select_candidates'])
        self.assertTrue(all('electric' in i['row']['types'] and i['row']['stats']['attack']>=120 for i in result['results']))
    def test_unknown_ability_is_not_invented(self):
        self.llm.outputs['extract_filters']=Filters(abilities=['우주무적능력'])
        with self.assertRaisesRegex(ServiceError,'특성 이름'): self.search.run('우주무적능력 특성을 가진 포켓몬 찾아줘',9)
    def test_korean_ability_from_llm_is_normalized(self):
        self.llm.outputs['extract_filters']=Filters(abilities=['부유'],min_speed=50)
        result=self.search.run('부유 특성을 가진 스피드 50 이상인 포켓몬 찾아줘',9)
        self.assertEqual(result['filters']['abilities'],['levitate']); self.assertTrue(result['results']); self.assertEqual(len(self.llm.calls),1)
    def test_unsupported_condition_is_not_ignored(self):
        self.llm.outputs['extract_filters']=Filters(abilities=['levitate'],unsupported_conditions=['색상 우선 정렬'])
        with self.assertRaisesRegex(ServiceError,'지원하지 않는'): self.search.run('부유 특성에 색상 우선으로 찾아줘',9)
        with self.assertRaises(ServiceError): self.search.run('부유 특성이 아닌 포켓몬 찾아줘',9)
    def test_ui_empty_result_is_not_a_system_error(self):
        from streamlit.testing.v1 import AppTest
        script="""from src.ui_rag import render_natural_search
from src.settings import Settings
from src.catalog import Catalog
s=Settings.load()
render_natural_search(s,Catalog(s.data_dir),9,s.data_dir.parent/'images')
"""
        with patch('src.settings.Settings.load',return_value=self.settings),patch('src.ui_rag.LanguageModel',return_value=self.llm):
            app=AppTest.from_string(script,default_timeout=30).run()
            app.text_input[0].set_value('7세대에서 부유 특성을 가진 팬텀 찾아줘')
            next(b for b in app.button if b.label=='AI로 찾아보기').click().run()
            self.assertFalse(app.exception); self.assertFalse(app.error)
            self.assertTrue(any('조건에 맞는 포켓몬이 없습니다' in i.value for i in app.info)); self.assertEqual(self.llm.calls,[])
    def test_ui_error_logs_safe_diagnostics_not_secret_values(self):
        from streamlit.testing.v1 import AppTest
        script="""from src.ui_rag import render_natural_search
from src.settings import Settings
from src.catalog import Catalog
s=Settings.load()
render_natural_search(s,Catalog(s.data_dir),9,s.data_dir.parent/'images')
"""
        with patch('src.settings.Settings.load',return_value=self.settings),patch('src.ui_rag.NaturalSearch.run',side_effect=RuntimeError('SECRET_API_KEY_OR_PROMPT')):
            app=AppTest.from_string(script,default_timeout=30).run(); app.text_input[0].set_value('검색 조건')
            with self.assertLogs('src.ui_rag',level='ERROR') as captured:
                next(b for b in app.button if b.label=='AI로 찾아보기').click().run()
            self.assertFalse(app.exception); self.assertTrue(app.error)
            self.assertIn('RuntimeError',' '.join(captured.output)); self.assertNotIn('SECRET_API_KEY_OR_PROMPT',' '.join(captured.output))
            self.assertNotIn('SECRET_API_KEY_OR_PROMPT',' '.join(e.value for e in app.error))
    def test_local_cards_and_navigation_without_key_or_llm(self):
        from streamlit.testing.v1 import AppTest
        root=Path(__file__).resolve().parents[1]
        mock_rag=SimpleNamespace(store=SimpleNamespace(get_meta=lambda *args:[]))
        docs=SimpleNamespace(status=lambda sid:{'documents':[]})
        with patch('src.settings.Settings.load',return_value=self.settings),patch('src.ui_rag.LanguageModel',return_value=self.llm),patch('src.ui_rag.services',return_value=(mock_rag,docs)),patch('src.ui_rag.index_counts',return_value={}):
            app=AppTest.from_file(str(root/'app.py'),default_timeout=30)
            app.session_state['lab_panel']='tools'
            app.run()
            field=next(t for t in app.text_input if t.label=='원하는 포켓몬 조건')
            field.set_value('숨겨진 특성이 피뢰침인 포켓몬 찾아줘')
            next(b for b in app.button if b.label=='AI로 찾아보기').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('일치한 특성: 피뢰침 · 숨겨진 특성' in m.value for m in app.markdown))
            self.assertTrue(any('9세대 기준 검색 결과' in c.value for c in app.caption))
            chosen=app.session_state['natural_result']['results'][0]['row']
            next(b for b in app.button if b.label=='이 포켓몬 선택하고 질문하기').click().run()
            self.assertFalse(app.exception); self.assertEqual(app.selectbox(key='selected_pokemon').value,chosen['pokemon_id'])
            self.assertEqual(app.selectbox(key='selected_generation').value,9); self.assertEqual(app.session_state['preferred_tab'],'질문하기')
            app.run(); self.assertEqual(self.llm.calls,[])

class ChatPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=Catalog(DATA)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup)
        self.settings=Settings(data_dir=DATA,chroma_dir=Path(self.tmp.name)/'chroma',api_key='test')
        self.emb=FakeEmbeddings(); self.store=VectorStore(self.settings,self.emb)
        self.store.upsert('pokemon_meta',[self.catalog.document(r) for r in self.catalog.records if r['species_id'] in (25,94,150)])
        self.llm=CountingLLM(); self.rag=RagService(self.settings,self.catalog,self.store,self.llm)
        self.addCleanup(patch.stopall)
        patch('src.llm.LanguageModel.complete',side_effect=AssertionError('Paid LLM forbidden')).start()
        patch('src.llm.Embeddings.embed',side_effect=AssertionError('Paid embedding forbidden')).start()
    def reply(self,pid,question,text,citations=None):
        self.llm.outputs['generate_answer']=Answer(claims=[Claim(text=text,citations=citations or [1])])
        return self.rag.ask(pid,9,question)
    def test_mewtwo_type_question_gets_focused_localized_evidence(self):
        result=self.reply(150,'뮤츠 속성이 뭐야?','에스퍼 타입이에요.')
        self.assertIn('에스퍼 타입이에요.',result['answer']); self.assertTrue(validate_citations(result['answer'],result['sources']))
        payload=self.llm.calls[0][2]; evidence=payload['evidence'][0]['text']
        self.assertIn('타입: 에스퍼',evidence); self.assertNotIn('특성:',evidence); self.assertNotIn('종족값:',evidence)
        for token in ('null','None','species_id','pokemon_id','psychic'): self.assertNotIn(token,evidence)
        self.assertEqual(payload['selected_form']['form'],'일반형'); self.assertEqual(len(self.llm.calls),1)
        self.assertIn('오박사',self.llm.calls[0][1]); self.assertIn('~일세',self.llm.calls[0][1]); self.assertNotIn('해요체',self.llm.calls[0][1]); self.assertIn('1~3문장',self.llm.calls[0][1])
    def test_pikachu_ability_question_uses_korean_names(self):
        result=self.reply(25,'피카츄 특성이 뭐야?','일반 특성은 정전기이고, 숨겨진 특성은 피뢰침이에요.')
        text=self.llm.calls[0][2]['evidence'][0]['text']
        self.assertIn('일반 특성: 정전기',text); self.assertIn('숨겨진 특성: 피뢰침',text)
        self.assertNotIn('타입:',text); self.assertNotIn('종족값:',text); self.assertEqual(len(self.llm.calls),1)
        self.assertEqual([n for n,_ in cited_sources(result['answer'],result['sources'])],[1])
    def test_gengar_comparison_keeps_both_generations_and_one_call(self):
        result=self.reply(94,'팬텀의 6세대와 7세대 특성 차이 알려줘.','6세대는 부유, 7세대는 저주받은바디예요.',[2,3])
        self.assertEqual(len(self.llm.calls),1); self.assertIn('부유',result['sources'][1]['text']); self.assertIn('저주받은바디',result['sources'][2]['text'])
        self.assertTrue(validate_citations(result['answer'],result['sources']))
    def test_selected_mega_form_does_not_use_default_form_metadata(self):
        pid=next(i for i,v in self.catalog.varieties.items() if v['api_name']=='mewtwo-mega-x')
        result=self.reply(pid,'뮤츠 속성이 뭐야?','선택한 메가진화 X형은 에스퍼·격투 타입이에요.')
        payload=self.llm.calls[0][2]
        self.assertEqual(payload['selected_form']['form'],'메가진화 X형')
        self.assertIn('격투',payload['evidence'][0]['text']); self.assertEqual(result['sources'][0]['id'],f'pokemon:{pid}:gen:9')
        self.assertNotIn('mewtwo-mega-x',payload['evidence'][0]['text']); self.assertEqual(len(self.llm.calls),1)
    def test_english_ability_and_missing_literals_are_localized(self):
        result=self.reply(25,'피카츄 특성이 뭐야?','static와 lightning-rod가 특성이고, null은 미확인이에요.')
        self.assertIn('정전기',result['answer']); self.assertIn('피뢰침',result['answer'])
        self.assertNotIn('static',result['answer']); self.assertNotIn('lightning-rod',result['answer']); self.assertNotIn('null',result['answer'])
        self.assertEqual(len(self.llm.calls),1)
    def test_undefined_values_are_not_sent_as_null(self):
        row=copy.deepcopy(self.catalog.index[(25,9)]); row['abilities']=None; row['types']=None; row['stats']['defense']=None
        _,text=self.catalog.answer_metadata(row,'타입과 특성, 능력치를 알려줘')
        self.assertNotIn('None',text); self.assertNotIn('null',text); self.assertIn('정보 미확인',text)
    def test_invalid_citations_still_blocked(self):
        with self.assertRaises(ServiceError): self.reply(150,'뮤츠 속성이 뭐야?','에스퍼 타입이에요.',[99])

if __name__=='__main__': unittest.main()
