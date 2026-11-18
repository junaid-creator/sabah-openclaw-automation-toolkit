import json,subprocess,unittest
from toolkit.google_sheets import GogSheets
from toolkit.lead_sheet_merge import merged
from toolkit.lead_qualification import HEADERS
class SheetsTests(unittest.TestCase):
 def row(self,id='fixture-1'):
  row=['']*19;row[0]=id;row[1]='Example Company';row[5]='https://example.com';row[14]='2026-01-01';row[16]='REVIEWED';row[17]='NOT CONTACTED';return row
 def client(self,timeout=False):
  rows=[HEADERS,self.row()];writes=[]
  def run(cmd,**kw):
   if cmd[2]=='get':return type('R',(),{'returncode':0,'stdout':json.dumps({'values':rows})})()
   data=json.loads(next(x.split('=',1)[1] for x in cmd if x.startswith('--values-json=')));rows[:]=data;writes.append(1)
   if timeout:raise subprocess.TimeoutExpired(cmd,45)
   return type('R',(),{'returncode':0,'stdout':'{}'})()
  return GogSheets('fixture@example.com','fixture',runner=run,env={},allow_reads=True,allow_writes=True),rows,writes
 def test_merge_preserves_review_and_first_seen(self):
  old=self.row();new=self.row('new-source');new[14]='2026-02-01';new[16]='NOT REVIEWED';result=merged(HEADERS,[HEADERS,old],[new]);self.assertEqual(result[1][0],'fixture-1');self.assertEqual(result[1][14],'2026-01-01');self.assertEqual(result[1][16],'REVIEWED')
 def test_duplicate_old_ids_blocked(self):
  with self.assertRaises(ValueError):merged(HEADERS,[HEADERS,self.row(),self.row()],[])
 def test_writes_disabled(self):
  c=GogSheets('fixture@example.com','fixture',runner=lambda *a,**k:None)
  with self.assertRaises(RuntimeError):c.values('fixture','All Leads')
 def test_exact_digest_and_drift(self):
  c,rows,w=self.client();new=self.row();new[12]='New reason';p=c.plan('fixture','All Leads',HEADERS,[new])
  with self.assertRaises(ValueError):c.apply(p,approved_digest='wrong')
  rows[1][1]='Changed remotely'
  with self.assertRaises(RuntimeError):c.apply(p,approved_digest=p['digest'])
  self.assertEqual(w,[])
 def test_timeout_readback_and_replay(self):
  c,rows,w=self.client(timeout=True);new=self.row();new[12]='New reason';p=c.plan('fixture','All Leads',HEADERS,[new]);self.assertEqual(c.apply(p,approved_digest=p['digest'])['writes'],1);self.assertEqual(c.apply(p,approved_digest=p['digest'])['writes'],0);self.assertEqual(w,[1])
