import hashlib
import hmac
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from toolkit.trusted_bridge import Bridge, canonical, fingerprint
from toolkit.setup_scaffold import scaffold


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = bytes(range(32))  # synthetic test key only
        self.now = 1000
        self.routes = [dict(channel='telegram', account='test', peer=p, role=r)
                       for p,r in [('owner-test','owner'),('customer-test','customer')]]
        self.bridge = Bridge(Path(self.tmp.name)/'state', self.key, self.routes, clock=lambda:self.now)
        self.addCleanup(patch.stopall)
        patch('socket.socket', side_effect=AssertionError('Network forbidden')).start()
        patch('subprocess.Popen', side_effect=AssertionError('Process forbidden')).start()

    def event(self, peer='owner-test', **kw):
        return dict(dict(id='request-1',channel='telegram',account='test',peer=peer,
                         kind='direct',timestamp=self.now,text='review'), **kw)

    def sign(self, event):
        return hmac.new(self.key, canonical(event).encode(), hashlib.sha256).hexdigest()

    def challenge(self):
        event = self.event()
        binding = {'operation':'publish','job':'demo','targets':['facebook','instagram'], 'hash':'example'}
        review = dict(self.routes[0],delivered=True,message_id='review-1',binding_digest=fingerprint(binding))
        result = self.bridge.challenge(event,self.sign(event),binding,review_receipt=review)
        return result['challenge_id'],binding

    def reply(self):
        e=self.event('customer-test')
        return self.bridge.prepare_reply(e,self.sign(e),{'action':'reply','text':'Staff must confirm.'},policy=lambda e,p:True)

    def test_reject_invalid_signature(self):
        with self.assertRaises(PermissionError): self.bridge.verify(self.event(),'not-a-signature')

    def test_reject_changed_event(self):
        e=self.event();sig=self.sign(e);e['peer']='customer-test'
        with self.assertRaises(PermissionError): self.bridge.verify(e,sig)

    def test_reject_stale_future_and_group(self):
        for kw in ({'timestamp':0},{'timestamp':1001},{'kind':'group'},{'timestamp':float('nan')}):
            e=self.event(**kw)
            with self.assertRaises(PermissionError): self.bridge.verify(e,self.sign(e))

    def test_unconfigured_peer(self):
        e=self.event('unknown')
        with self.assertRaises(PermissionError):self.bridge.verify(e,self.sign(e))

    def test_customer_cannot_approve(self):
        cid,_=self.challenge();e=self.event('customer-test',id='confirm',text='CONFIRM '+cid)
        with self.assertRaises(PermissionError):self.bridge.confirm(e,self.sign(e),cid)

    def test_single_confirmation_replay_and_binding(self):
        cid,binding=self.challenge();e=self.event(id='confirm',text='CONFIRM '+cid)
        r=self.bridge.confirm(e,self.sign(e),cid)
        self.assertEqual(r,self.bridge.confirm(e,self.sign(e),cid))
        self.assertTrue(self.bridge.authorized(cid,binding))
        self.assertFalse(self.bridge.authorized(cid,dict(binding,hash='changed')))
        e['id']='second-confirm'
        with self.assertRaises(PermissionError):self.bridge.confirm(e,self.sign(e),cid)

    def test_expired_confirmation(self):
        cid,_=self.challenge();self.now+=301;e=self.event(id='confirm',text='CONFIRM '+cid)
        with self.assertRaises(PermissionError):self.bridge.confirm(e,self.sign(e),cid)

    def test_revocation(self):
        cid,b=self.challenge();e=self.event(id='confirm',text='CONFIRM '+cid)
        self.bridge.confirm(e,self.sign(e),cid)
        e=self.event(id='revoke',text='REVOKE '+cid);self.bridge.revoke(e,self.sign(e),cid)
        self.assertFalse(self.bridge.authorized(cid,b))

    def test_review_receipt_required(self):
        e=self.event()
        with self.assertRaises(PermissionError):self.bridge.challenge(e,self.sign(e),{'a':1},review_receipt={})

    def test_policy_denial(self):
        e=self.event('customer-test')
        with self.assertRaises(PermissionError):self.bridge.prepare_reply(e,self.sign(e),{'action':'reply','text':'Guaranteed stock'},policy=lambda e,p:False)

    def test_proposal_cannot_select_recipient_or_tool(self):
        e=self.event('customer-test')
        for p in ({'action':'exec','text':'anything'}, {'action':'reply','text':'anything','peer':'other'}):
            with self.assertRaises(PermissionError):self.bridge.prepare_reply(e,self.sign(e),p,policy=lambda e,p:True)

    def test_delivery_disabled(self):
        with self.assertRaises(PermissionError):self.bridge.deliver(self.reply(),sender=lambda *a:self.fail('Sent'))

    def test_receipt_and_no_repeat(self):
        rid=self.reply();calls=[]
        def send(route,body):
            calls.append(body);return dict(route,delivered=True,message_id='receipt-1',secret='not-persisted')
        result=self.bridge.deliver(rid,sender=send,enabled=True)
        self.assertEqual(result['state'],'SENT');self.assertNotIn('secret',result['receipt'])
        self.bridge.deliver(rid,sender=send,enabled=True);self.assertEqual(len(calls),1)

    def test_uncertain_delivery_no_repeat(self):
        rid=self.reply();calls=[]
        def send(*args):calls.append(1);raise TimeoutError('ambiguous')
        self.assertEqual(self.bridge.deliver(rid,sender=send,enabled=True)['state'],'UNKNOWN')
        self.bridge.deliver(rid,sender=send,enabled=True);self.assertEqual(calls,[1])

    def test_wrong_receipt_destination(self):
        for index, extra in enumerate(({'peer':'other'}, {'dryRun':True})):
            e=self.event('customer-test',id='receipt-'+str(index))
            rid=self.bridge.prepare_reply(e,self.sign(e),{'action':'reply','text':'Check with staff'},policy=lambda e,p:True)
            r=self.bridge.deliver(rid,sender=lambda route,body:dict(dict(route,delivered=True,message_id='x'),**extra),enabled=True)
            self.assertEqual(r['state'],'UNKNOWN')

    def test_crash_claim_no_replay(self):
        rid=self.reply()
        def crash(*args):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.bridge.deliver(rid,sender=crash,enabled=True)
        result=self.bridge.deliver(rid,sender=lambda *a:self.fail('repeat'),enabled=True)
        self.assertEqual(result['state'],'SENDING')

    def test_event_collision(self):
        self.reply();e=self.event('customer-test',text='changed')
        with self.assertRaises(PermissionError):self.bridge.prepare_reply(e,self.sign(e),{'action':'reply','text':'Staff must confirm.'},policy=lambda e,p:True)

    def test_ambiguous_route_rejected(self):
        with self.assertRaises(ValueError):Bridge(Path(self.tmp.name)/'bad',self.key,self.routes+self.routes)


class ScaffoldTests(unittest.TestCase):
    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'new';self.assertFalse(scaffold(p)['applied']);self.assertFalse(p.exists())

    def test_fresh_install_inert(self):
        with tempfile.TemporaryDirectory() as root, patch('subprocess.Popen',side_effect=AssertionError('no process')), patch('socket.socket',side_effect=AssertionError('no network')):
            p=Path(root)/'new';r=scaffold(p,apply=True)
            self.assertTrue(r['applied']);self.assertFalse(r['activated'])
            for k in ('network','paid_apis','schedules','publishing','customer_sending'):self.assertFalse(r[k])
            self.assertEqual(p.stat().st_mode & 0o777,0o700)
            self.assertTrue((p/'customer-support/AGENTS.md').exists())
            self.assertEqual((p/'activation-plan.json').stat().st_mode & 0o777,0o600)

    def test_existing_destination_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):scaffold(root,apply=True)

    def test_profile_destination_rejected(self):
        with self.assertRaises(ValueError):scaffold('/tmp/.openclaw/not-created')
