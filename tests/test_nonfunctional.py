import unittest,tempfile
from pathlib import Path
from dataclasses import replace
from unittest.mock import Mock,patch
from src.settings import Settings
from src.document_service import DocumentService
from src.llm import ServiceError
from src.storage import digest
from test_services import DATA

class NonfunctionalTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.addCleanup(self.tmp.cleanup)
  self.settings=Settings(DATA,Path(self.tmp.name)/'chroma',wiki_contact='qa@example.org') # Mock HTTP only; not an operator contact.
 def service(self,contact=None):return DocumentService(replace(self.settings,wiki_contact=contact) if contact is not None else self.settings,None,None,None)
 def response(self,status=200,headers=None):
  return Mock(status_code=status,headers=headers or {},json=lambda:{'query':{'ok':True}})
 def test_missing_contact_blocks_only_new_http(self):
  with patch('src.document_service.requests.get') as get:
   with self.assertRaises(ServiceError) as error:self.service('').request({'action':'query'})
   self.assertEqual(error.exception.stage,'wiki_contact');self.assertIn('WIKI_CONTACT',str(error.exception));get.assert_not_called()
 def test_cached_wiki_response_works_without_contact(self):
  service=self.service('');params={'format':'json','formatversion':2,'maxlag':5,'action':'query'}
  service.cache.put('wiki:'+digest(params),{'query':{'cached':True}})
  with patch('src.document_service.requests.get',side_effect=AssertionError('HTTP forbidden')):self.assertTrue(service.request({'action':'query'})['query']['cached'])
 def test_contact_is_sent_and_repeated_request_cached(self):
  with patch('src.document_service.requests.get',return_value=self.response()) as get,patch('src.document_service.time.sleep'):
   service=self.service(' qa@example.org ');service.request({'action':'query'});service.request({'action':'query'})
   self.assertEqual(get.call_count,1);self.assertEqual(get.call_args.kwargs['headers']['User-Agent'],'PokemonLab/1.0 (qa@example.org)')
 def test_invalid_contact_never_reaches_http(self):
  for contact in ['  ','담당자@example.org','qa@example.org\r\nX-Test: injected','qa\t@example.org']:
   with patch('src.document_service.requests.get') as get:
    with self.assertRaises(ServiceError):self.service(contact).request({'action':'query'})
    get.assert_not_called()
 def test_retry_after_and_spacing_preserved(self):
  service=self.service();sleeps=[]
  with patch('src.document_service.requests.get',side_effect=[self.response(429,{'Retry-After':'2'}),self.response(503,{'Retry-After':'1'}),self.response()]) as get,patch('src.document_service.time.sleep',side_effect=sleeps.append),patch('src.document_service.time.monotonic',return_value=100):
   with patch.object(DocumentService,'last',100):self.assertTrue(service.request({'action':'query'})['query']['ok'])
   self.assertEqual(get.call_count,3);self.assertEqual(sleeps,[6.2,2.0,6.2,1.0,6.2])
 def test_long_retry_after_does_not_retry_early(self):
  with patch('src.document_service.requests.get',return_value=self.response(429,{'Retry-After':'60'})) as get,patch('src.document_service.time.sleep'):
   with self.assertRaises(ServiceError):self.service().request({'action':'query'})
   self.assertEqual(get.call_count,1)
 def test_timeout_retries_are_bounded(self):
  import requests
  with patch('src.document_service.requests.get',side_effect=requests.Timeout('PRIVATE_TRACE')) as get,patch('src.document_service.time.sleep'):
   with self.assertRaises(ServiceError) as error:self.service().request({'action':'query'})
   self.assertEqual(get.call_count,3);self.assertNotIn('PRIVATE_TRACE',str(error.exception))
 def test_chat_ui_never_exposes_error_body_or_prompt(self):
  from streamlit.testing.v1 import AppTest
  script="""import streamlit as st
from src.ui_rag import render_conversation
def reply(question,history): raise RuntimeError('PRIVATE_API_KEY PRIVATE_FULL_PROMPT PRIVATE_TRACE')
messages=st.session_state.setdefault('messages',[{'id':'q','role':'user','content':'test'},{'id':'a','role':'assistant','content':'','status':'pending','reply_to':'q','sources':[]}])
render_conversation(messages,reply,prefix='security',placeholder='test')
"""
  with patch('src.settings.Settings.load',return_value=self.settings):
   app=AppTest.from_string(script,default_timeout=30).run();self.assertFalse(app.exception)
   text='\n'.join(x.value for x in app.markdown)
   for marker in ['PRIVATE_API_KEY','PRIVATE_FULL_PROMPT','PRIVATE_TRACE','Traceback']:self.assertNotIn(marker,text)
