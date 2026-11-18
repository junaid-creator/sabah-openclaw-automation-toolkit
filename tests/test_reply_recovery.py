import hashlib,hmac,tempfile,unittest
from pathlib import Path
from toolkit.trusted_bridge import Bridge,canonical,fingerprint
from toolkit.reply_recovery import Replies

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.route={'channel':'test','account':'support','peer':'customer','role':'customer'}
        self.key=b'only-a-disposable-fixture-key-00000000'
        self.bridge=Bridge(Path(self.tmp.name)/'bridge',self.key,[self.route],clock=lambda:100)
        self.r=Replies(Path(self.tmp.name)/'replies',self.bridge,policy=lambda e,p:p['text']=='Verified facts')
        self.e={'id':'inquiry-1','channel':'test','account':'support','peer':'customer','kind':'direct','timestamp':100,'text':'Question'}
        self.sig=hmac.new(self.key,canonical(self.e).encode(),hashlib.sha256).hexdigest();self.sent=[]
    def start(self):return self.r.start(self.e,self.sig,submit=lambda e:'task-1')
    def result(self,**changes):
        return dict(task_id='task-1',event_id=self.e['id'],route=self.route,status='completed',role='assistant',final=True,text='Verified facts',**changes)
    def receipt(self):return dict(self.route,delivered=True,message_id='remote-1',event_id=self.e['id'],text_sha256=fingerprint('Verified facts'))
    def sender(self,*args):self.sent.append(args);return self.receipt()
    def test_final_delivery_once(self):
        self.start()
        for _ in range(2):self.assertEqual(self.r.recover(self.e['id'],result_reader=lambda t:self.result(),sender=self.sender,enabled=True)['state'],'SENT')
        self.assertEqual(len(self.sent),1)
    def test_pending_not_resubmitted(self):
        self.start();self.r.start(self.e,self.sig,submit=lambda e:self.fail('resubmit'))
        self.assertEqual(self.r.recover(self.e['id'],result_reader=lambda t:{'status':'pending'},sender=self.sender)['state'],'WAITING_RESULT')
        self.assertFalse(self.sent)
    def test_wrong_inquiry_and_nonfinal(self):
        self.start()
        for change in ({'event_id':'other'},{'role':'tool'},{'final':False},{'route':dict(self.route,peer='other')}):
            result=self.result();result.update(change)
            with self.assertRaises(PermissionError):self.r.recover(self.e['id'],result_reader=lambda t:result,sender=self.sender,enabled=True)
        self.assertFalse(self.sent)
    def test_policy_denies(self):
        self.start();result=self.result();result['text']='Invented price'
        with self.assertRaises(PermissionError):self.r.recover(self.e['id'],result_reader=lambda t:result,sender=self.sender,enabled=True)
        self.assertFalse(self.sent)
    def test_unknown_delivery_readonly_recovery(self):
        self.start()
        def lost(*args):self.sent.append(args);raise OSError('lost')
        self.assertEqual(self.r.recover(self.e['id'],result_reader=lambda t:self.result(),sender=lost,enabled=True)['state'],'UNKNOWN_DELIVERY')
        self.r.recover(self.e['id'],result_reader=lambda t:self.fail(),sender=self.sender,enabled=True)
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.r.reconcile_delivery(self.e['id'],lookup=lambda *a:self.receipt())['state'],'SENT')
    def test_submit_unknown_not_retried(self):
        def lost(e):raise OSError('lost')
        with self.assertRaises(RuntimeError):self.r.start(self.e,self.sig,submit=lost)
        self.assertEqual(self.r.start(self.e,self.sig,submit=lambda e:self.fail())['state'],'UNKNOWN_TASK')
    def test_no_optin(self):
        self.start()
        with self.assertRaises(PermissionError):self.r.recover(self.e['id'],result_reader=lambda t:self.result(),sender=self.sender)
        self.assertFalse(self.sent)
