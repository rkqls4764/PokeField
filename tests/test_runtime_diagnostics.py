import ast,inspect,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from src.catalog import Catalog
from src.rag import RagService,Answer,Claim
from src.llm import error_diagnostic,ServiceError
from src.settings import Settings
from test_services import DATA,FakeLLM

class RuntimeRegressionTests(unittest.TestCase):
    def test_cached_old_catalog_is_replaced_by_implementation_revision(self):
        import streamlit as st
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/'app.py').read_text(encoding='utf-8'))
        factory=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='catalog')
        class LegacyCatalog(Catalog):
            def profile_source(self,species_id): return super().profile_source(species_id)
        namespace={'st':st,'Catalog':LegacyCatalog}
        exec(compile(ast.Module(body=[factory],type_ignores=[]),str(root/'app.py'),'exec'),namespace)
        cached=namespace['catalog'];cached.clear();self.addCleanup(cached.clear)
        old=cached(str(DATA),'before-full-chain')
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            settings=Settings(data_dir=DATA,chroma_dir=Path(tmp)/'chroma',api_key='fake')
            with self.assertRaisesRegex(TypeError,'full_chain'):
                RagService(settings,old,None,None).ask_global('피카츄 진화는 뭐야?')
            namespace['Catalog']=Catalog
            self.assertIs(cached(str(DATA),'before-full-chain'),old)
            current=cached(str(DATA),'after-full-chain')
            self.assertIsNot(current,old);self.assertIn('full_chain',inspect.signature(current.profile_source).parameters)
            llm=FakeLLM({'generate_answer':Answer(claims=[Claim(text='피카츄는 라이츄로 진화한단다.',citations=[1])])})
            self.assertIn('라이츄',RagService(settings,current,None,llm).ask_global('피카츄 진화는 뭐야?')['answer'])
    def test_json_direction_is_explicit_not_reversed(self):
        profile=json.loads(Catalog(DATA).profile_source(25,full_chain=True)['text'])
        self.assertEqual(profile['direct_previous'],['피츄']);self.assertEqual(profile['direct_next'],['라이츄'])
    def test_actual_model_game_title_is_not_a_pokemon_claim(self):
        c=Catalog(DATA);evidence=c.profile_source(25,full_chain=True)['text']
        text='피카츄가 라이츄로 진화하려면 thunder-stone을 사용해야 한다. 레드·그린·블루(적용_버전그룹: red-blue) 기준이다.'
        self.assertEqual(c.unsupported_species(text,evidence),[])
        self.assertIn(209,c.unsupported_species('피카츄는 블루로 진화한다.',evidence))
        self.assertIn(209,c.unsupported_species(text,'피카츄 라이츄'))
    def test_diagnostics_keep_traceback_and_omit_secret_bodies(self):
        def fail(): raise TypeError("Catalog.profile_source() got an unexpected keyword argument 'full_chain'")
        try: fail()
        except Exception as error: diagnostic=error_diagnostic(error)
        self.assertEqual(diagnostic['category'],'code');self.assertEqual(diagnostic['code'],'unexpected_keyword:full_chain');self.assertEqual(diagnostic['traceback'][-1]['function'],'fail')
        try: raise ServiceError('SECRET_API_KEY_OR_PROMPT',stage='llm_request',category='connection')
        except Exception as error: diagnostic=error_diagnostic(error)
        self.assertEqual(diagnostic['stage'],'llm_request');self.assertEqual(diagnostic['category'],'connection');self.assertNotIn('SECRET_API_KEY_OR_PROMPT',json.dumps(diagnostic))
    def test_code_failure_is_not_offered_as_connection_retry(self):
        from streamlit.testing.v1 import AppTest
        script="""import streamlit as st
from src.ui_rag import render_conversation
def reply(question,prior): raise TypeError('internal detail')
render_conversation(st.session_state.setdefault('messages',[]),reply,prefix='test',placeholder='질문')
"""
        app=AppTest.from_string(script,default_timeout=30).run();app.chat_input[0].set_value('피카츄 진화는 뭐야?').run()
        self.assertFalse(app.exception);self.assertFalse(any(b.label=='다시 시도' for b in app.button));self.assertFalse(app.session_state['messages'][-1]['retryable'])

if __name__=='__main__':unittest.main()
