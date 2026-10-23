import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.collection import BrowserCollection,Collection
from src import game_ui
from src.catalog import Catalog
from test_services import DATA

STAMP='2026-10-23T01:02:03+00:00'
def event(pid=25,eid='capture-event-001',stamp=STAMP):
    return {'pokemon_id':pid,'event_id':eid,'caught_at':stamp}

class BrowserCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.catalog=Catalog(DATA)
    def test_restore_counts_and_idempotent_retry(self):
        c=BrowserCollection([event(),event()],{25})
        original=c.all()[25]
        self.assertEqual(original['catch_count'],1)
        self.assertEqual(c.catch(25,'capture-event-001',{25}),original)
        c.catch(25,'capture-event-002',{25})
        self.assertEqual(c.all()[25]['catch_count'],2)
        self.assertEqual(len(c.all()),1)
        self.assertEqual(BrowserCollection(list(c.events.values())).all(),c.all())
    def test_conflict_and_invalid_payload(self):
        with self.assertRaises(ValueError):BrowserCollection([event(),event(26)],{25,26})
        for entries in [[event(True)], [event(99999)], [event(eid='bad')], [event(stamp='invalid')], [event(stamp='2026-10-23T01:00:00')], None]:
            with self.assertRaises(ValueError):BrowserCollection(entries,{25})
    def test_order_independent_records_and_signature(self):
        a=event(stamp='2026-10-23T01:00:00+00:00');b=event(eid='capture-event-002',stamp='2026-10-23T02:00:00+00:00')
        x=BrowserCollection([a,b]);y=BrowserCollection([b,a])
        self.assertEqual(x.all(),y.all());self.assertEqual(x.signature,y.signature)
        self.assertEqual(x.all()[25]['first_caught'],a['caught_at'])
        self.assertEqual(x.all()[25]['last_caught'],b['caught_at'])
    def test_two_sessions_never_inherit_shared_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'shared.sqlite3';Collection(path).catch(94,'shared-event-001',{94})
            a={'collection_backend':'browser','collection_path':str(path),'browser_capture_events':[event()]}
            b={'collection_backend':'browser','collection_path':str(path),'browser_capture_events':[]}
            with patch.object(game_ui.st,'session_state',a):self.assertEqual(set(game_ui.current_collection().all()),{25})
            with patch.object(game_ui.st,'session_state',b):self.assertEqual(game_ui.current_collection().all(),{})
            self.assertEqual(set(Collection(path).all()),{94})
    def state(self,events=()):
        return {'collection_backend':'browser','browser_capture_events':list(events),'browser_collection_ready':True,'_rotom_catalog':self.catalog,'field_region_ids':{'electric':[25]},'field_facts':{25:{'id':25}},'pokemon_field':{'capture':{'pokemon_id':25,'event_id':'capture-event-001','region':'electric'}}}
    def test_capture_is_proposal_until_browser_storage_confirms(self):
        state=self.state();game_ui_state={'pokemon_id':25,'region':'electric','request_id':'hunt-1','status':'active'}
        state['hunt_target']=game_ui_state
        with patch.object(game_ui.st,'session_state',state),patch.object(game_ui,'Collection',side_effect=AssertionError('Shared DB forbidden')):
            game_ui.record_capture()
            self.assertTrue(state['capture_ack']['ok'])
            self.assertEqual(state['browser_capture_events'],[])
            self.assertEqual(state['hunt_target']['status'],'active')
            saved=state['capture_ack']['persist_event']
            state['pokemon_field']['collection']={'status':'ready','events':[saved]}
            game_ui.sync_browser_collection()
            self.assertEqual(game_ui.current_collection().all()[25]['catch_count'],1)
            self.assertEqual(state['hunt_target']['status'],'captured')
    def test_capture_is_blocked_before_hydration(self):
        state=self.state();state['browser_collection_ready']=False
        with patch.object(game_ui.st,'session_state',state),self.assertLogs('src.game_ui',level='ERROR'):game_ui.record_capture()
        self.assertFalse(state['capture_ack']['ok']);self.assertEqual(state['browser_capture_events'],[])
    def test_unavailable_storage_does_not_fall_back_or_clear_existing(self):
        state=self.state([event()]);state['pokemon_field']={'collection':{'status':'unavailable'}}
        with patch.object(game_ui.st,'session_state',state),self.assertLogs('src.game_ui',level='WARNING'):game_ui.sync_browser_collection()
        self.assertFalse(state['browser_collection_ready']);self.assertEqual(state['browser_capture_events'],[event()])
    def test_invalid_snapshot_rejected_and_new_session_restores(self):
        state=self.state();state['pokemon_field']={'collection':{'status':'ready','events':[event(99999)]}}
        with patch.object(game_ui.st,'session_state',state),self.assertLogs('src.game_ui',level='WARNING'):game_ui.sync_browser_collection()
        self.assertFalse(state['browser_collection_ready'])
        state['pokemon_field']['collection']['events']=[event()]
        with patch.object(game_ui.st,'session_state',state):game_ui.sync_browser_collection()
        self.assertTrue(state['browser_collection_ready']);self.assertEqual(state['browser_capture_events'],[event()])

if __name__=='__main__':unittest.main()
