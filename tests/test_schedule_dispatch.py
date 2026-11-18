import hashlib,hmac,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from toolkit.schedule_dispatch import Schedule
from toolkit.trusted_bridge import Bridge,canonical,fingerprint
class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=datetime(2026,1,1,12,tzinfo=timezone.utc).timestamp();self.n=0
        self.route={'channel':'test','account':'shop','peer':'owner','role':'owner'};self.key=b'fixture-only-key-schedule-000000000000'
        self.bridge=Bridge(Path(self.tmp.name)/'bridge',self.key,[self.route],clock=lambda:self.now)
        self.s=Schedule(Path(self.tmp.name)/'schedule',self.bridge,clock=lambda:self.now)
        self.content={'job_id':'job-1','artifact_sha256':'a'*64,'targets':['facebook']}
    def event(self,text):
        self.n+=1;e=dict(id=str(self.n),channel='test',account='shop',peer='owner',kind='direct',timestamp=self.now,text=text)
        return e,hmac.new(self.key,canonical(e).encode(),hashlib.sha256).hexdigest()
    def approved(self):
        j=self.s.plan(*self.event('SCHEDULE today 1 pm'),self.content,timezone_name='UTC')
        receipt=dict(self.route,delivered=True,message_id='review',binding_digest=fingerprint(j['binding']))
        c=self.s.challenge(j['id'],*self.event('SCHEDULE REVIEW '+j['id']),review_receipt=receipt)
        self.bridge.confirm(*self.event(c['confirmation']),c['challenge_id']);return j,c
    def test_due_once(self):
        j,c=self.approved();calls=[]
        args=dict(content_reader=lambda jid:self.content,publish=lambda *a:calls.append(a),enabled=True)
        self.s.dispatch_due(j['id'],**args);self.assertFalse(calls)
        self.now+=3600
        self.s.dispatch_due(j['id'],**args);self.s.dispatch_due(j['id'],**args);self.assertEqual(len(calls),1)
    def test_revoke(self):
        j,c=self.approved();self.bridge.revoke(*self.event('REVOKE '+c['challenge_id']),c['challenge_id']);self.now+=3600
        with self.assertRaises(PermissionError):self.s.dispatch_due(j['id'],content_reader=lambda jid:self.content,publish=lambda *a:self.fail(),enabled=True)
    def test_expired_no_catchup(self):
        j,c=self.approved();self.now+=7200
        self.assertEqual(self.s.dispatch_due(j['id'],content_reader=lambda jid:self.content,publish=lambda *a:self.fail(),enabled=True)['state'],'EXPIRED')
    def test_drift_no_publish(self):
        j,c=self.approved();self.now+=3600
        with self.assertRaises(ValueError):self.s.dispatch_due(j['id'],content_reader=lambda jid:{},publish=lambda *a:self.fail(),enabled=True)
    def test_optin(self):
        j,c=self.approved()
        with self.assertRaises(PermissionError):self.s.dispatch_due(j['id'],content_reader=lambda jid:self.content,publish=lambda *a:self.fail())
