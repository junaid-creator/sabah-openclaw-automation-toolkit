import json,socket,subprocess,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from toolkit.apify_client import ApifyClient
from toolkit.apify_budget import RunBudgetUnsafe
from toolkit import overture_adapter as o

class AcquisitionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.state=self.root/'state.json';self.evidence=self.root/'evidence.json';self.now=datetime(2026,1,15,tzinfo=timezone.utc)
  self.evidence.write_text(json.dumps(dict(policy_verified_at='2026-01-01T00:00:00Z',credit_verified_at='2026-01-14T00:00:00Z',cycle_start='2026-01-01T00:00:00Z',cycle_end='2026-02-01T00:00:00Z',remaining_usd=2,monthly_limit_usd=5,free_plan_verified=True,no_overage_verified=True)))
  def deny(*a,**k):raise AssertionError('External operations denied')
  for target in ['socket.socket','subprocess.Popen']:
   p=patch(target,deny);p.start();self.addCleanup(p.stop)
 def client(self,unknown=False,cap_confirm=True):
  calls=[]
  def transport(method,path,payload):
   calls.append((method,path))
   if method=='POST':
    if unknown:raise TimeoutError()
    return {'id':'fixture-run','defaultDatasetId':'fixture-data','options':{'maxTotalChargeUsd':0.2,'isMaxTotalChargeUsdSetByUser':cap_confirm}}
   if path=='acts/fixture~actor':return {'id':'fixture-actor','pricingInfos':[{'pricingModel':'PAY_PER_EVENT','minimalMaxTotalChargeUsd':0.01}]}
   if path.startswith('actor-runs?'):return {'items':[],'total':0,'count':0,'offset':0,'limit':100,'desc':False}
   if path.startswith('actor-runs/'):return {'status':'SUCCEEDED','usageTotalUsd':0.1}
   if path.startswith('datasets/'):return [{'name':'Synthetic fixture'}]
   raise AssertionError(path)
  return ApifyClient('fixture~actor','fixture-actor',lambda:'fixture-token',transport=transport),calls
 def start(self,c,authorize=lambda _:True):return c.start('one',{'synthetic':True},state_path=self.state,evidence_path=self.evidence,authorize=authorize,now=self.now)
 def test_explicit_paid_approval(self):
  c,calls=self.client()
  with self.assertRaises(RunBudgetUnsafe):self.start(c,lambda _:False)
  self.assertEqual(calls,[])
 def test_unknown_start_no_retry(self):
  c,calls=self.client(unknown=True)
  with self.assertRaises(RuntimeError):self.start(c)
  self.assertEqual(self.start(c)['status'],'UNCERTAIN_START');self.assertEqual(sum(m=='POST' for m,p in calls),1)
 def test_start_collect_and_replay(self):
  c,calls=self.client();self.start(c);result=c.collect('one',state_path=self.state);self.assertEqual(result['raw_count'],1);self.start(c);self.assertEqual(sum(m=='POST' for m,p in calls),1)
 def test_missing_provider_cap_retains_id(self):
  c,calls=self.client(cap_confirm=False)
  with self.assertRaises(RunBudgetUnsafe):self.start(c)
  self.assertEqual(self.start(c)['run_id'],'fixture-run');self.assertEqual(sum(m=='POST' for m,p in calls),1)
 def test_stale_credit_blocks_post(self):
  x=json.loads(self.evidence.read_text());x['credit_verified_at']='2026-01-01T00:00:00Z';self.evidence.write_text(json.dumps(x));c,calls=self.client()
  with self.assertRaises(RunBudgetUnsafe):self.start(c)
  self.assertFalse(any(m=='POST' for m,p in calls))
 def test_input_change_rejected(self):
  c,_=self.client();self.start(c)
  with self.assertRaises(RunBudgetUnsafe):c.start('one',{'changed':True},state_path=self.state,evidence_path=self.evidence,authorize=lambda _:True,now=self.now)
 def test_overture_download_default_denied(self):
  with self.assertRaises(RuntimeError):o.download('/not-installed',(0,0,1,1),self.root/'out.json')
 def test_overture_mocked_cli(self):
  binary=self.root/'overture';binary.write_text('fixture');out=self.root/'out.json';calls=[]
  def runner(args,**kw):calls.append(args);out.write_text('{"features":[]}');return type('R',(),{'returncode':0})()
  self.assertEqual(o.download(binary,(0,0,1,1),out,allow_download=True,runner=runner),{'features':[]});self.assertIn('--bbox=0,0,1,1',calls[0])
 def test_overture_geometry_and_dedup(self):
  profile={'geographic_targets':dict(area='Fixture',latitude_min=0,latitude_max=1,longitude_min=0,longitude_max=1)}
  f={'id':'fixture-place','geometry':{'type':'Point','coordinates':[0.5,0.5]},'properties':{'names':{'primary':'Example Contracting'},'taxonomy':{'primary':'contractor'},'phones':['fixture-phone'],'websites':['https://example.com']}}
  self.assertEqual(len(o.qualify_features({'features':[f,f]},profile,'2026-01-15')),1)
