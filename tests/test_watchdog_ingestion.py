import copy
import os
import tempfile
import unittest
from pathlib import Path
from toolkit import watchdog as w

class RuntimeIngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'watch.sqlite3'
        self.db = w.connect(self.path)
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def evt(self, phase='start', seq=1, run='run-one', stamp=1000000, **data):
        e = dict(agentId='main',sessionKey='agent:main:owner',sessionId='session-one',
                 runId=run,seq=seq,ts=stamp,stream='lifecycle',data=dict(phase=phase,**data))
        if phase=='start': e['data']['startedAt']=stamp
        return e
    def ingest(self,e,now=1001):
        return w.ingest_runtime(self.db,e,['main'],now=now)['status']
    def row(self):
        return self.db.execute('SELECT * FROM tasks').fetchone()
    def test_start_activity_terminal_are_real_durable_rows(self):
        self.assertEqual(self.ingest(self.evt()),'STARTED')
        e=self.evt('end',2,stamp=1000100);e['stream']='tool'
        self.assertEqual(self.ingest(e),'ACTIVITY')
        self.assertEqual(self.row()['state'],'RUNNING')
        self.assertEqual(self.ingest(self.evt('end',3,stamp=1000200)),'COMPLETED')
        self.assertIn('NOT verified',self.row()['checkpoint'])
        self.db.close(); self.db=w.connect(self.path)
        self.assertEqual(self.row()['state'],'COMPLETED')
    def test_dedup_and_conflict(self):
        e=self.evt();self.ingest(e)
        self.assertEqual(self.ingest(e),'DUPLICATE')
        changed=copy.deepcopy(e);changed['ts']+=1
        with self.assertRaisesRegex(ValueError,'identity conflict'): self.ingest(changed)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM alerts').fetchone()[0],1)
    def test_same_id_different_session_conflicts(self):
        self.ingest(self.evt())
        e=self.evt('end',2);e['sessionId']='reset-session'
        with self.assertRaisesRegex(ValueError,'identity conflict'):self.ingest(e)
    def test_new_run_retires_old_and_delayed_terminal_cannot_complete_new(self):
        self.ingest(self.evt())
        e=self.evt(run='run-two',stamp=1000100);e['sessionId']='reset-session'
        self.assertEqual(self.ingest(e),'STARTED')
        self.assertEqual(self.ingest(self.evt('end',2,stamp=1000200)),'STALE_EXECUTION')
        self.assertEqual(self.row()['execution_id'],'run-two')
        self.assertEqual(self.row()['state'],'RUNNING')
        self.assertEqual(self.ingest(self.evt(seq=3,stamp=1000300)),'RETIRED_OR_DUPLICATE_START')
    def test_out_of_order_sequence_and_clock_cannot_advance(self):
        self.ingest(self.evt())
        self.ingest(self.evt('fallback',4,stamp=1000300))
        self.assertEqual(self.ingest(self.evt('end',3,stamp=1000400)),'OUT_OF_ORDER')
        self.assertEqual(self.ingest(self.evt('end',5,stamp=1000200)),'OUT_OF_ORDER')
        self.assertEqual(self.row()['state'],'RUNNING')
    def test_stale_and_future_events(self):
        self.assertEqual(self.ingest(self.evt(),now=1500),'STALE_EVENT')
        with self.assertRaises(ValueError):self.ingest(self.evt(stamp=2000000))
        self.assertIsNone(self.row())
    def test_late_old_start_cannot_replace_current(self):
        self.ingest(self.evt(run='new',stamp=1000500))
        self.assertEqual(self.ingest(self.evt()),'STALE_EXECUTION')
        self.assertEqual(self.row()['execution_id'],'new')
    def test_attempt_error_is_not_terminal(self):
        self.ingest(self.evt())
        self.assertEqual(self.ingest(self.evt('error',2,stamp=1000100,error='SECRET')),'ACTIVITY')
        self.assertEqual(self.row()['state'],'RUNNING')
        self.assertEqual(self.ingest(self.evt('end',3,stamp=1000200)),'COMPLETED')
        self.assertNotIn('SECRET',''.join(self.db.iterdump()))
    def test_settled_error_and_fallback_exhaustion_fail(self):
        for key in ('executionSettled','fallbackExhaustedFailure'):
            run=key;stamp=1000000 if key=='executionSettled' else 1000300
            self.ingest(self.evt(run=run,stamp=stamp))
            self.assertEqual(self.ingest(self.evt('error',2,run,stamp+100,**{key:True})),'FAILED')
    def test_end_timeout_never_success(self):
        self.ingest(self.evt())
        self.assertEqual(self.ingest(self.evt('end',2,stamp=1000100,status='timeout')),'FAILED')
    def test_unknown_terminal_does_not_create_task(self):
        self.assertEqual(self.ingest(self.evt('end',2)),'UNKNOWN_EXECUTION')
        self.assertIsNone(self.row())
    def test_malformed_and_support_identities_fail_closed(self):
        for field,value in [('sessionId',None),('agentId','support'),('seq',True),('ts',float('nan')),('sessionKey','agent:support:owner')]:
            e=self.evt();e[field]=value
            with self.assertRaises(ValueError):self.ingest(e)
    def test_transaction_failure_does_not_leave_half_start(self):
        self.db.execute("CREATE TRIGGER reject_alert BEFORE INSERT ON alerts BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(Exception):self.ingest(self.evt())
        self.assertIsNone(self.row())
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM runtime_events').fetchone()[0],0)
    def test_private_database_rejects_symlink_and_public_state(self):
        target=Path(self.tmp.name)/'private.sqlite3'
        w.private_runtime_database(target)
        self.assertEqual(target.stat().st_mode&0o777,0o600)
        link=Path(self.tmp.name)/'link';link.symlink_to(target)
        with self.assertRaises(ValueError):w.private_runtime_database(link)
        target.chmod(0o644)
        with self.assertRaises(ValueError):w.private_runtime_database(target)

if __name__=='__main__':unittest.main()
