"""Map-only entry point and access to the preserved research UI."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.settings import Settings
from test_services import DATA

class FullscreenUITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.addCleanup(self.tmp.cleanup)
        self.settings=Settings(data_dir=DATA,chroma_dir=Path(self.tmp.name)/'chroma',api_key='')
    def test_default_map_has_no_legacy_controls_or_rag_calls(self):
        from streamlit.testing.v1 import AppTest
        with patch('src.settings.Settings.load',return_value=self.settings),patch('src.ui_rag.services',side_effect=AssertionError('Unexpected RAG initialization')):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.text_input);self.assertFalse(app.selectbox);self.assertFalse(app.radio)
            self.assertFalse(app.chat_input);self.assertFalse(app.sidebar.text_input)
            self.assertGreaterEqual(len(app.session_state['field_pool_ids']),60)
    def test_research_overlay_preserves_tools_and_closes(self):
        from streamlit.testing.v1 import AppTest
        with patch('src.settings.Settings.load',return_value=self.settings),patch('src.ui_rag.index_counts',return_value={}):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
            app.session_state['lab_panel']='tools';app.run()
            self.assertFalse(app.exception)
            self.assertTrue(app.selectbox(key='selected_pokemon'))
            self.assertTrue(app.radio(key='chat_mode'))
            self.assertTrue(any(t.label=='원하는 포켓몬 조건' for t in app.text_input))
            app.button(key='close_lab_panel').click().run()
            self.assertFalse(app.exception);self.assertFalse(app.text_input);self.assertFalse(app.radio)

if __name__=='__main__':unittest.main()
