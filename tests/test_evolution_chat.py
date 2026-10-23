import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from src.catalog import Catalog
from src.settings import Settings
from src.rag import RagService,Answer,Claim,cited_sources
from src.llm import ServiceError
from test_services import DATA,FakeLLM

class EvolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=Catalog(DATA)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.addCleanup(self.tmp.cleanup)
        self.settings=Settings(data_dir=DATA,chroma_dir=Path(self.tmp.name)/'chroma',api_key='fake')
        def metadata(pid,gen):
            d=self.catalog.document(self.catalog.index[(pid,gen)])
            return [dict(id=d['id'],text=d['text'],**d['metadata'])]
        self.store=SimpleNamespace(get_meta=metadata,search_docs=lambda *a:(_ for _ in ()).throw(AssertionError('No vector search needed')))
    def service(self,text): return RagService(self.settings,self.catalog,self.store,FakeLLM({'generate_answer':Answer(claims=[Claim(text=text,citations=[1])])}))
    def test_evolution_questions_and_citations(self):
        cases=[('피카츄 진화하면 뭐야?','피카츄는 라이츄로 진화한단다.',(25,26)),('피카츄 진화 루트 알려줘.','피츄 → 피카츄 → 라이츄일세.',(172,25)),('라이츄 진화 전은?','라이츄의 진화 전은 피카츄일세.',(25,26)),('피츄는 어떻게 진화해?','피츄는 피카츄로 진화한단다.',(172,25)),('이브이 진화 종류 알려줘.','이브이는 샤미드, 쥬피썬더, 부스터로 진화하는 경로가 있네.',(133,134)),('파이리 진화 루트 알려줘.','파이리 → 리자드 → 리자몽일세.',(5,6))]
        for question,text,edge in cases:
            with self.subTest(question=question):
                result=self.service(text).ask_global(question)
                self.assertIn(text,result['answer']);self.assertEqual(len(cited_sources(result['answer'],result['sources'])),1)
                profile=json.loads(result['sources'][0]['text']);edges={(e['from_species_id'],e['to_species_id']) for e in profile['evolutions']}
                self.assertIn(edge,edges)
                if '이브이' in question: self.assertEqual(len({b for a,b in edges if a==133}),8)
    def test_selected_and_followup_use_species_id(self):
        result=self.service('피카츄는 라이츄로 진화한단다.').ask(25,9,'진화하면 뭐야?')
        self.assertIn('라이츄',result['answer'])
        result=self.service('피카츄는 라이츄로 진화한단다.').ask_global('그럼 진화하면?',history=[{'role':'user','content':'피카츄 타입 알려줘'},{'role':'assistant','content':'전기 타입일세.'}])
        self.assertEqual(result['search_context']['pokemon_ids'],[25]);self.assertIn('라이츄',result['answer'])
        pid=next(pid for pid,v in self.catalog.varieties.items() if v['species_id']==6 and not v['is_default'] and (pid,6) in self.catalog.index)
        result=self.service('리자몽의 진화 전은 리자드일세.').ask(pid,6,'진화 전은?')
        self.assertEqual(result['sources'][0]['species_id'],6)
    def test_cycles_missing_data_and_version_conditions(self):
        catalog=copy.copy(self.catalog);catalog.evolutions=list(catalog.evolutions)+[dict(catalog.evolutions[0],from_species_id=26,to_species_id=172)]
        profile=json.loads(catalog.profile_source(25,full_chain=True)['text'])
        self.assertLess(len(profile['evolutions']),10)
        self.assertTrue(any(e['조건'].get('적용_버전그룹',{}).get('name')=='sun-moon' and e['조건'].get('region',{}).get('name')=='alola' for e in profile['evolutions']))
        catalog.evolutions=[]
        rag=RagService(self.settings,catalog,self.store,FakeLLM({'generate_answer':Answer(claims=[],not_found=True)}))
        result=rag.ask_global('피카츄 진화하면 뭐야?');self.assertNotIn('[근거',result['answer']);self.assertIn('확인하기 어렵구나',result['answer'])
        with self.assertRaises(ServiceError): self.service('뮤츠로 진화한단다.').ask_global('피카츄 진화하면 뭐야?')
    def test_failed_evolution_cache_is_not_reused(self):
        rag=self.service('피카츄는 라이츄로 진화한단다.')
        with patch('src.storage.Cache.get',return_value='흠, 지금 가진 근거만으로는 질문한 내용을 확인하기 어렵구나.'),patch.object(rag.llm,'structured',wraps=rag.llm.structured) as generate:
            self.assertIn('라이츄',rag.ask_global('피카츄 진화하면 뭐야?')['answer']);self.assertEqual(generate.call_count,1)

class ChatLifecycleTests(unittest.TestCase):
    def app(self,reply):
        from streamlit.testing.v1 import AppTest
        script="""import streamlit as st
from src.ui_rag import render_conversation
messages=st.session_state.setdefault('messages',[])
show=st.checkbox('채팅 열기',value=True,key='show')
if show: render_conversation(messages,st.session_state['reply'],prefix='test',placeholder='질문')
"""
        app=AppTest.from_string(script,default_timeout=30);app.session_state['reply']=reply;return app.run()
    def test_three_turns_rerun_and_reentry(self):
        calls=[]
        def reply(question,prior):
            calls.append((question,list(prior)))
            return {'answer':'답변 '+question+' [근거 1]','sources':[dict(id=question,title='문서 '+question,text='원문 '+question,source_type='pokemon_metadata',source_url='https://example.com/'+question)]}
        app=self.app(reply)
        for question in ('one','two','three'):
            app.chat_input[0].set_value(question).run();self.assertFalse(app.exception)
        expected=['one','답변 one [근거 1]','two','답변 two [근거 1]','three','답변 three [근거 1]']
        self.assertEqual([m['content'] for m in app.session_state['messages']],expected)
        ids=[m['id'] for m in app.session_state['messages']];self.assertEqual(len(set(ids)),6)
        self.assertEqual([m.markdown[0].value for m in app.chat_message],expected)
        self.assertEqual([s['title'] for m in app.session_state['messages'] if m['role']=='assistant' for s in m['sources']],['문서 one','문서 two','문서 three'])
        app.run();app.checkbox[0].uncheck().run();app.checkbox[0].check().run()
        self.assertFalse(app.exception);self.assertEqual(len(calls),3);self.assertEqual([m['id'] for m in app.session_state['messages']],ids)
        self.assertEqual(len(calls[2][1]),4)
    def test_failure_retry_replaces_only_matching_answer(self):
        calls=[]
        def reply(question,prior):
            calls.append(question)
            if len(calls)==1: raise ServiceError('Do not expose credentials')
            return {'answer':'성공 답변','sources':[]}
        app=self.app(reply);app.chat_input[0].set_value('질문').run();self.assertFalse(app.exception)
        messages=app.session_state['messages'];self.assertEqual(len(messages),2);self.assertEqual(messages[1]['status'],'error');identity=messages[1]['id']
        next(b for b in app.button if b.label=='다시 시도').click().run()
        self.assertFalse(app.exception);self.assertEqual(len(app.session_state['messages']),2);self.assertEqual(app.session_state['messages'][1]['id'],identity);self.assertEqual(app.session_state['messages'][1]['content'],'성공 답변');self.assertEqual(calls,['질문','질문'])

if __name__=='__main__':unittest.main()
