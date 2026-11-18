import unittest
import test_missing_implementations as base
from toolkit.social_commands import dispatch
from toolkit.trusted_bridge import canonical,fingerprint

class Commands(unittest.TestCase):
    def setUp(self):
        fixture=base.SocialTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        for name in ('key','route','bridge','ledger','renders','sends','c','root'):
            setattr(self,name,getattr(fixture,name))
    event=base.SocialTests.event
    campaign=base.SocialTests.campaign
    def command(self,id,text,**extra):
        e,s=self.event(id,text);return dispatch(self.c,dict(event=e,signature=s,**extra))
    def create(self):return self.command('create','SOCIAL CREATE '+canonical(self.campaign()))
    def proof(self,r):return dict(self.route,delivered=True,message_id='native-proof',binding_digest=fingerprint(r['binding']))
    def test_exact_native_approval_no_dispatch(self):
        r=self.create();jid=r['job_id']
        c=self.command('review','SOCIAL REVIEW '+jid,review_receipt=self.proof(r))
        result=self.command('confirm',c['confirmation'])
        self.assertEqual(result['publication'],'NOT_DISPATCHED')
        self.command('revoke','SOCIAL REVOKE '+jid)
        self.assertTrue(self.ledger.submission_blocked(jid))
    def test_no_forged_delivery(self):
        r=self.create()
        with self.assertRaises(RuntimeError):self.command('review','SOCIAL REVIEW '+r['job_id'])
        self.assertIsNone(self.ledger.job(r['job_id']))
    def test_revision_new_review(self):
        r=self.create();jid=r['job_id']
        body={'expected':r['etag'],'campaign':self.campaign(2)}
        revised=self.command('revision','SOCIAL REVISE '+jid+' '+canonical(body))
        self.assertEqual(revised['revision'],2)
        with self.assertRaises(RuntimeError):self.command('review','SOCIAL REVIEW '+jid,review_receipt=self.proof(r))
    def test_status_no_private_path(self):
        r=self.create();status=self.command('status','SOCIAL STATUS '+r['job_id'])
        self.assertNotIn(str(self.root),canonical(status))
    def test_no_publish_alias(self):
        r=self.create()
        with self.assertRaises(ValueError):self.command('publish','SOCIAL PUBLISH '+r['job_id'])
