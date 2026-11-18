import tempfile, unittest
from pathlib import Path
from toolkit import watchdog as w

class WatchdogTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.db=w.connect(Path(self.tmp.name)/'watch.sqlite3')
 def tearDown(self): self.db.close(); self.tmp.cleanup()
 def test_start_is_durable_and_idempotent(self):
  self.assertTrue(w.start(self.db,'t1','openclaw','e1',100,now=1000)); self.assertFalse(w.start(self.db,'t1','openclaw','e1',100,now=1001)); self.db.close(); self.db=w.connect(Path(self.tmp.name)/'watch.sqlite3'); self.assertEqual(self.db.execute('select state from tasks').fetchone()[0],'RUNNING')
 def test_verified_progress_resets_stall_and_completion_requires_evidence(self):
  w.start(self.db,'t1','tool','e1',1000,now=1000); w.progress(self.db,'t1','checkpoint-1',now=1100); self.assertEqual(w.scan(self.db,now=1150,connect_fn=lambda:True)['pending_alerts'],1); w.finish(self.db,'t1','test fixture result verified',now=1200); self.assertEqual(self.db.execute('select state from tasks').fetchone()[0],'COMPLETED')
  with self.assertRaises(ValueError): w.finish(self.db,'t1','',now=1201)
 def test_stall_detected_once_and_recovery_does_not_complete_task(self):
  w.start(self.db,'t2','tool','e2',1000,stall_seconds=60,now=1000); w.scan(self.db,now=1061,connect_fn=lambda:True); w.scan(self.db,now=1062,connect_fn=lambda:True); self.assertEqual(self.db.execute("select count(*) from alerts where kind='TASK_STALLED'").fetchone()[0],1)
  self.assertEqual(self.db.execute('select state from tasks').fetchone()[0],'RUNNING')
 def test_gateway_transition_and_recovery(self):
     offline=lambda: (_ for _ in ()).throw(ConnectionError('offline'))
     self.assertEqual(w.scan(self.db,now=1000,connect_fn=offline)['gateway'],'SUSPECT')
     self.assertEqual(w.scan(self.db,now=1001,connect_fn=lambda:True)['gateway'],'HEALTHY')
     self.assertEqual(self.db.execute("select count(*) from alerts where kind='GATEWAY_UNAVAILABLE'").fetchone()[0],0)
     self.assertEqual(w.scan(self.db,now=1002,connect_fn=offline)['gateway'],'SUSPECT')
     self.assertEqual(w.scan(self.db,now=1003,connect_fn=offline)['gateway'],'UNAVAILABLE')
     self.assertEqual(w.scan(self.db,now=1004,connect_fn=offline)['gateway'],'UNAVAILABLE')
     self.assertEqual(self.db.execute("select count(*) from alerts where kind='GATEWAY_UNAVAILABLE'").fetchone()[0],1)
     self.assertEqual(w.scan(self.db,now=1005,connect_fn=lambda:True)['gateway'],'RECOVERING')
     self.assertEqual(w.scan(self.db,now=1006,connect_fn=offline)['gateway'],'UNAVAILABLE')
     self.assertEqual(self.db.execute("select count(*) from alerts where kind='SERVICE_RECOVERED'").fetchone()[0],0)
     self.assertEqual(w.scan(self.db,now=1007,connect_fn=lambda:True)['gateway'],'RECOVERING')
     self.assertEqual(w.scan(self.db,now=1008,connect_fn=lambda:True)['gateway'],'HEALTHY')
     self.assertEqual(self.db.execute("select count(*) from alerts where kind='SERVICE_RECOVERED'").fetchone()[0],1)
 def test_failure_classification_is_persisted(self):
  w.start(self.db,'t3','agent','e3',100,now=1000); w.fail(self.db,'t3','HTTP 429','API_RATE_LIMITED',now=1001); row=self.db.execute('select state,error from tasks').fetchone(); self.assertEqual(tuple(row),('FAILED','HTTP 429')); self.assertEqual(self.db.execute("select kind from alerts where task_id='t3' and kind='API_RATE_LIMITED'").fetchone()[0],'API_RATE_LIMITED')
 def test_no_unknown_completion_or_duplicate_execution(self):
  w.start(self.db,'t4','agent','e4',100,now=1000)
  with self.assertRaises(ValueError): w.start(self.db,'t4','agent','e5',100,now=1001)
  with self.assertRaises(ValueError): w.progress(self.db,'missing','fake',now=1002)

if __name__=='__main__': unittest.main()
