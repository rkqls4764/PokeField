import os, json, tempfile, unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from src.catalog import Catalog
from src.settings import Settings
from src.vector_store import VectorStore
from src.llm import ServiceError
from src.natural_search import Filters, Picks, Pick, NaturalSearch, filter_rows
from src.rag import RagService, Answer, Claim, cited_sources, validate_citations
from src.document_service import DocumentService, QueryPlan, Selection
from src.storage import write_json

DATA=Path(os.getenv('TEST_POKEMON_DATA_DIR',r'C:\SSAFY\pennant_race_ai_core_2\pokemon-data\data\processed'))
class FakeEmbeddings:
    signature='test-vector-v1'
    def __init__(self): self.calls=0
    def embed(self,texts): self.calls+=1; return [[1.0,0.1,0.01] for _ in texts]
class FakeLLM:
    def __init__(self,outputs): self.outputs=outputs
    def check_key(self): pass
    def structured(self,prompt,payload,schema,purpose,cache=True):
        obj=self.outputs[purpose]
        return obj(payload) if callable(obj) else obj

class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=Catalog(DATA)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup)
        self.settings=Settings(data_dir=DATA,chroma_dir=Path(self.tmp.name)/'chroma',api_key='test')
        self.emb=FakeEmbeddings(); self.store=VectorStore(self.settings,self.emb)
        docs=[self.catalog.document(r) for r in self.catalog.records if r['pokemon_id'] in (25,35,94,133)]
        self.store.upsert('pokemon_meta',docs)
    def test_actual_catalog_counts(self):
        self.assertEqual(len(self.catalog.species),1025); self.assertEqual(len(self.catalog.records),6260)
    def test_history_and_korean_abilities(self):
        self.assertEqual(self.catalog.index[(35,5)]['types'],['normal']); self.assertEqual(self.catalog.index[(35,6)]['types'],['fairy'])
        self.assertIn('부유',self.catalog.document(self.catalog.index[(94,6)])['text'])
        self.assertEqual(self.catalog.index[(94,7)]['abilities'][0]['name'],'cursed-body')
    def test_duplicate_index_skips_embedding(self):
        before=self.emb.calls; count=self.store.counts()['pokemon_meta']
        r=self.store.upsert('pokemon_meta',[self.catalog.document(self.catalog.index[(25,9)])])
        self.assertEqual(r['changed'],0); self.assertEqual(self.emb.calls,before); self.assertEqual(self.store.counts()['pokemon_meta'],count)
    def test_filter_numeric_and_type(self):
        rows,gen,limits=filter_rows(self.catalog,Filters(types=['fire'],min_speed=100),9,self.settings)
        self.assertTrue(rows); self.assertTrue(all('fire' in r['types'] and r['stats']['speed']>=100 for r in rows))
    def test_relative_conditions(self):
        rows,_,limits=filter_rows(self.catalog,Filters(types=['electric'],high_speed=True,high_attack=True),9,self.settings)
        self.assertTrue(rows); self.assertEqual(limits,{'attack':100,'speed':100})
        self.assertTrue(all(r['stats']['attack']>=100 and r['stats']['speed']>=100 for r in rows))
    def test_unknown_generation_rejected(self):
        with self.assertRaises(ServiceError): filter_rows(self.catalog,Filters(generation=99),9,self.settings)
    def test_missing_gen_one_special_stats_not_recommended(self):
        rows,_,_=filter_rows(self.catalog,Filters(min_special_attack=1),1,self.settings)
        self.assertEqual(rows,[])
    def test_citation_validation(self):
        sources=[{'id':'a'},{'id':'b'}]
        self.assertEqual([n for n,_ in cited_sources('주장 [근거 2]',sources)],[2])
        self.assertFalse(validate_citations('가짜 [근거 99]',sources))
        self.assertEqual(cited_sources('모릅니다',sources),[])
    def test_graph_comparison(self):
        service=RagService(self.settings,self.catalog,self.store,FakeLLM({}))
        state=service.retrieve({'pokemon_id':94,'generation':9,'question':'6세대와 7세대에서 어떻게 달라졌어?'})
        ids={s['id'] for s in state['sources']}
        self.assertTrue({'pokemon:94:gen:6','pokemon:94:gen:7','pokemon:94:gen:9'}<=ids)
    def test_species_filter_excludes_unrelated_docs(self):
        doc={'id':'unrelated','text':'다른 포켓몬','metadata':{'species_id':133,'title':'이브이','source_url':'https://example.com','source_type':'external_document','content_hash':'x'}}
        self.store.upsert('pokemon_docs',[doc])
        self.assertEqual(self.store.search_docs('피카츄',25,5),[])
    def test_unknown_citation_blocks_answer(self):
        llm=FakeLLM({'generate_answer':Answer(claims=[Claim(text='주장',citations=[99])])})
        service=RagService(self.settings,self.catalog,self.store,llm)
        with self.assertRaises(ServiceError): service.ask(25,9,'특성은?')
    def test_actual_langgraph_nodes(self):
        llm=FakeLLM({'generate_answer':Answer(claims=[Claim(text='피카츄의 정보입니다.',citations=[1])])})
        service=RagService(self.settings,self.catalog,self.store,llm)
        self.assertEqual(set(service.graph.get_graph().nodes),{'__start__','retrieve','generate','__end__'})
        result=service.ask(25,9,'특성은?'); self.assertIn('[근거 1]',result['answer'])
    def test_no_fabricated_answer_without_evidence(self):
        service=RagService(self.settings,self.catalog,self.store,FakeLLM({'generate_answer':Answer(claims=[],not_found=True)}))
        result=service.ask(25,9,'가상의 특성을 알려줘'); self.assertNotIn('[근거',result['answer']); self.assertIn('확인하기 어렵구나',result['answer'])
    def test_inline_valid_citation_is_normalized(self):
        llm=FakeLLM({'generate_answer':Answer(claims=[Claim(text='피카츄의 정보입니다. [근거 1]',citations=[1])])})
        result=RagService(self.settings,self.catalog,self.store,llm).ask(25,9,'설명')
        self.assertEqual(result['answer'].count('[근거 1]'),1)
    def test_wrong_species_name_is_rejected(self):
        llm=FakeLLM({'generate_answer':Answer(claims=[Claim(text='이브이의 정보입니다.',citations=[1])])})
        with self.assertRaises(ServiceError): RagService(self.settings,self.catalog,self.store,llm).ask(25,9,'설명')
    def test_explicit_low_minimum_is_not_raised(self):
        rows,_,_=filter_rows(self.catalog,Filters(min_attack=50),9,self.settings)
        chosen=rows[0]
        llm=FakeLLM({'extract_filters':Filters(min_attack=50,high_attack=True),'select_candidates':Picks(candidates=[Pick(pokemon_id=chosen['pokemon_id'],reason='수치 조건 충족')])})
        result=NaturalSearch(self.settings,self.catalog,llm).run('공격 50 이상',9)
        self.assertEqual(result['thresholds']['attack'],50)
    def test_evolution_profile_uses_actual_data(self):
        source=self.catalog.profile_source(133)
        self.assertIn('샤미드',source['text']); self.assertIn('water-stone',source['text'])
    def test_natural_search_rejects_outside_candidate(self):
        llm=FakeLLM({'extract_filters':Filters(min_attack=120,generation=9),'select_candidates':Picks(candidates=[Pick(pokemon_id=999999,reason='가짜')])})
        self.assertEqual(NaturalSearch(self.settings,self.catalog,llm).run('9세대 공격 120 이상',9)['results'],[])
    def test_natural_no_invented_minimum(self):
        llm=FakeLLM({'extract_filters':Filters(min_speed=123)})
        with self.assertRaises(ServiceError): NaturalSearch(self.settings,self.catalog,llm).run('빠른 포켓몬',9)
    def test_natural_preserves_valid_candidate(self):
        rows,_,_=filter_rows(self.catalog,Filters(types=['fire'],min_speed=100),9,self.settings); chosen=rows[0]
        llm=FakeLLM({'extract_filters':Filters(types=['fire'],min_speed=100),'select_candidates':Picks(candidates=[Pick(pokemon_id=chosen['pokemon_id'],reason='불꽃 타입이고 스피드 조건을 충족합니다.')])})
        result=NaturalSearch(self.settings,self.catalog,llm).run('스피드 100 이상인 불꽃 타입',9)
        self.assertEqual(result['results'][0]['row'],chosen)
    def test_missing_index_explained(self):
        service=RagService(self.settings,self.catalog,self.store,FakeLLM({}))
        with self.assertRaisesRegex(ServiceError,'색인'): service.ask(1,9,'특성')

class DocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=Catalog(DATA)
    setUp=CoreTests.setUp
    def test_own_document_cannot_be_rejected_by_model(self):
        llm=FakeLLM({'extract_queries':QueryPlan(queries=[]),'select_documents':Selection(selected_ids=[])})
        service=DocumentService(self.settings,self.catalog,self.store,llm); calls=[]
        def request(params):
            calls.append(params)
            if params.get('meta'): return {'query':{'rightsinfo':{'text':'CC BY-SA','url':'https://creativecommons.org/licenses/by-sa/4.0/'}}}
            if params.get('list'): return {'query':{'search':[{'pageid':25,'title':'피카츄','snippet':'포켓몬'}]}}
            if params.get('prop')=='info|pageprops': return {'query':{'pages':[{'pageid':25,'title':'피카츄'}]}}
            return {'query':{'pages':[{'pageid':25,'title':'피카츄','extract': '양쪽 볼에 있는 전기주머니에 전기를 저장한다.','fullurl':'https://ko.wikipedia.org/wiki/피카츄','revisions':[{'revid':1,'timestamp':'2026-01-01'}]}]}}
        service.request=request
        result=service.collect(25,'설명'); self.assertTrue(result['own_document_collected']); self.assertGreater(result['chunks'],0)
        before=len(calls); embeds=self.emb.calls; again=service.collect(25,'설명')
        self.assertEqual(len(calls),before); self.assertEqual(self.emb.calls,embeds); self.assertEqual(again['changed_chunks'],0)
    def test_chunk_replacement_removes_stale(self):
        base={'species_id':25,'title':'피카츄','source_url':'https://example.org','source_type':'external_document','content_hash':'a','document_key':'d'}
        self.store.replace_document('d',[{'id':'old:0','text':'예전 문서','metadata':base},{'id':'old:1','text':'예전 문서2','metadata':base}])
        self.store.replace_document('d',[{'id':'new:0','text':'새 문서','metadata':dict(base,content_hash='b')}])
        self.assertEqual(self.store.collections['pokemon_docs'].get(where={'document_key':'d'},include=[])['ids'],['new:0'])

if __name__=='__main__': unittest.main()
