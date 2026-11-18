import contextlib,json,socket,subprocess,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from toolkit import product_rotation as rotation,apify_budget as budget
from toolkit import approval_ledger as approval,schedule_core as schedule,notification_outbox as delivery

class EngineTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
  def deny(*a,**k):raise AssertionError('No external operations allowed')
  self.stack.enter_context(patch.object(socket,'socket',deny));self.stack.enter_context(patch.object(subprocess,'Popen',deny))
  self.now=datetime(2026,1,15,17,0,tzinfo=timezone.utc)
 def catalog(self):
  return {'records':[{'id':i,'post':{'post_type':'product'},'data':{'status':'publish','name':'Fixture '+str(i)},'url':'https://example.com/product/item-'+str(i)+'/'} for i in [101,102]],'storefront_ids':[101,102]}
 def test_rotation_requires_install(self):
  with self.assertRaises(ValueError):rotation.reserve(self.root/'r.db','2026-01-15',self.catalog(),now=self.now)
 def test_rotation_immutable_date(self):
  p=self.root/'r.db';rotation.install_series(p,self.catalog(),now=self.now)
  a=rotation.reserve(p,'2026-01-15',self.catalog(),now=self.now);b=rotation.reserve(p,'2026-01-15',self.catalog(),now=self.now)
  self.assertEqual(a,b);self.assertEqual(a['template_number'],1)
  c=rotation.reserve(p,'2026-01-16',self.catalog(),now=self.now+timedelta(days=1));self.assertEqual((c['product_id'],c['template_number']),(102,2))
 def test_rotation_cycles_independently(self):
  p=self.root/'r.db';rotation.install_series(p,self.catalog(),now=self.now)
  for i in range(7):
   now=self.now+timedelta(days=i);a=rotation.reserve(p,now.date().isoformat(),self.catalog(),now=now)
   self.assertEqual(a['product_id'],[101,102][i%2]);self.assertEqual(a['template_number'],i%6+1)
 def test_rotation_rejects_wrong_host_and_order(self):
  c=self.catalog();c['records'][0]['url']='https://untrusted.invalid/product/a/'
  with self.assertRaises(ValueError):rotation.install_series(self.root/'r.db',c,now=self.now)
 def proof(self):
  return dict(policy_verified_at='2026-01-01T00:00:00Z',credit_verified_at='2026-01-14T00:00:00Z',cycle_start='2026-01-01T00:00:00Z',cycle_end='2026-02-01T00:00:00Z',remaining_usd=2,monthly_limit_usd=5,free_plan_verified=True,no_overage_verified=True)
 def test_billing_fresh_proof(self):
  p=self.root/'proof.json';p.write_text(json.dumps(self.proof()));self.assertEqual(budget.billing_guard(p,now=self.now)[1],2)
 def test_billing_stale_credit(self):
  x=self.proof();x['credit_verified_at']='2026-01-01T00:00:00Z';p=self.root/'p.json';p.write_text(json.dumps(x))
  with self.assertRaises(budget.RunBudgetUnsafe):budget.billing_guard(p,now=self.now)
 def test_billing_no_overage_and_finite_caps(self):
  x=self.proof();x['no_overage_verified']=False;p=self.root/'p.json';p.write_text(json.dumps(x))
  with self.assertRaises(budget.RunBudgetUnsafe):budget.billing_guard(p,now=self.now)
  with self.assertRaises(budget.RunBudgetUnsafe):budget.billing_guard(p,cap=float('nan'),now=self.now)
 def test_schedule_exact_future(self):
  x=schedule.parse_schedule('tomorrow 6 pm','2026-01-15T17:00:00Z','UTC');self.assertEqual(x['local'],'2026-01-16T18:00:00+00:00')
 def test_schedule_ambiguity_and_past(self):
  for s in ['today 3 pm','today tomorrow 6 pm','tomorrow 6']:
   with self.assertRaises(approval.Permanent):schedule.parse_schedule(s,'2026-01-15T17:00:00Z')
 def test_schedule_dst_fold(self):
  with self.assertRaises(approval.Permanent):schedule.parse_schedule('2026-11-01 1:30 am','2026-10-31T00:00:00Z','America/New_York')
 def receipt(self):return {'source':{'authenticated':True,'review_ref':'fixture-review'},'binding':{'targets':['facebook'],'asset_sha256':'a'*64,'caption':'Fixture'}}
 def test_approval_requires_owner_and_review(self):
  ledger=approval.Ledger(self.root/'l.db');r=self.receipt();r['source']['authenticated']=False
  with self.assertRaises(approval.Permanent):ledger.approve('JOB-0001',r)
 def test_approval_immutable_and_revocable(self):
  l=approval.Ledger(self.root/'l.db');r=self.receipt();l.approve('JOB-0001',r);r['binding']['caption']='Changed'
  with self.assertRaises(approval.Permanent):l.approve('JOB-0001',r)
  l.owner_action('JOB-0001','OWNER_REJECTED',owner_verified=True,confirmation='cancel',message_id='fixture-cancel')
  with self.assertRaises(approval.Permanent):l.reserve('JOB-0001','facebook',2)
 def targets(self):return {c:{'account':a,'recipient':'fixture-recipient'} for c,a in delivery.CHANNELS.items()}
 def test_outbox_exact_receipts_and_no_replay(self):
  l=approval.Ledger(self.root/'l.db');schedule.outbox(l,'JOB-0001','STATUS',{'status':'fixture'});calls=[]
  def send(c,a,r,m):calls.append(c);return dict(channel=c,account=a,recipient=r,delivered=True,messageId='fixture-'+c)
  delivery.drain(l,self.targets(),sender=send,now=100);delivery.drain(l,self.targets(),sender=send,now=101);self.assertEqual(len(calls),2)
 def test_outbox_unknown_is_not_retried(self):
  l=approval.Ledger(self.root/'l.db');schedule.outbox(l,'JOB-0001','STATUS',{});calls=[]
  def send(c,a,r,m):calls.append(c);raise TimeoutError()
  delivery.drain(l,self.targets(),sender=send,now=100);delivery.drain(l,self.targets(),sender=send,now=10000);self.assertEqual(len(calls),2);self.assertEqual(delivery.notification_health(l),{'UNKNOWN':2})
 def test_outbox_wrong_recipient_not_delivered(self):
  l=approval.Ledger(self.root/'l.db');e=schedule.outbox(l,'JOB-0001','STATUS',{});delivery.ensure_deliveries(l,self.targets(),now=100);d=delivery.claim_delivery(l,e,'telegram',now=100)
  self.assertNotEqual(delivery.record_delivery(l,d,dict(delivered=True,messageId='fake',channel='telegram',account='default',recipient='wrong'),now=100),'SENT')

class CredentialAdapterTests(unittest.TestCase):
 def test_environment_store_no_file_fallback(self):
  import os
  from toolkit.meta_publisher import EnvironmentSecrets
  with patch.dict(os.environ, {"TOOLKIT_META_FACEBOOK_PAGE_ACCESS_TOKEN":"fixture-only"}, clear=True):
   store=EnvironmentSecrets();self.assertEqual(store.get_facebook_page_access_token(),"fixture-only");self.assertEqual(store.get_instagram_access_token(),"")
 def test_content_fingerprint_changes(self):
  from toolkit.meta_publisher import fingerprint_rows,MetaSettings,InstagramAuthMode
  config=MetaSettings(api_version="v25.0",instagram_auth_mode=InstagramAuthMode.FACEBOOK_LOGIN,page_id="12345678901",instagram_user_id="10987654321",expected_page_name="Example")
  self.assertNotEqual(fingerprint_rows(config,"JOB-0001",{}, {"facebook_caption":"A"}),fingerprint_rows(config,"JOB-0001",{}, {"facebook_caption":"B"}))
