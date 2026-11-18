import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from toolkit.gateway_monitor import Monitor, TelegramSender, probe, endpoint_url, integrity


class Response(io.BytesIO):
    status=200

class Opener:
    def __init__(self, value): self.value=value;self.calls=[]
    def open(self, request, timeout):
        self.calls.append(request)
        if isinstance(self.value, Exception): raise self.value
        return Response(json.dumps(self.value).encode())

class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.time=0
        self.m=Monitor(self.root/'state',label='Example Gateway',threshold=3,grace=10,clock=lambda:self.time)
        self.calls=[]
    def tick(self,healthy=False,**kwargs): return self.m.tick(healthy,integrity_ok=kwargs.pop('integrity_ok',True),**kwargs)
    def sender(self,body):self.calls.append(body);return {'confirmed':True,'message_id':'123'}
    def outage(self):
        self.time=11
        for _ in range(3):result=self.tick()
        return result
    def test_grace_and_threshold(self):
        self.assertEqual(self.tick()['state'],'STARTUP_GRACE')
        self.time=11
        self.assertEqual(self.tick()['state'],'SUSPECT')
        self.assertEqual(self.tick()['state'],'SUSPECT')
        self.assertEqual(self.tick()['state'],'OUTAGE')
    def test_healthy_resets_failures(self):
        self.time=11;self.tick();self.tick()
        self.assertEqual(self.tick(True)['failures'],0)
        self.assertEqual(self.tick()['state'],'SUSPECT')
    def test_send_once_and_restart(self):
        self.outage()
        self.assertEqual(self.m.dispatch_one(self.sender,enabled=True)['status'],'SENT')
        for _ in range(4):self.tick();self.m.dispatch_one(self.sender,enabled=True)
        other=Monitor(self.root/'state',label='Example Gateway',clock=lambda:self.time)
        self.assertEqual(other.dispatch_one(self.sender,enabled=True)['status'],'IDLE')
        self.assertEqual(len(self.calls),1)
    def test_disabled_no_send(self):
        self.outage();self.assertEqual(self.m.dispatch_one(self.sender)['status'],'DISABLED');self.assertEqual(self.calls,[])
    def test_unknown_never_replays_or_sends_recovery(self):
        self.outage()
        def unknown(body):self.calls.append(body);raise TimeoutError()
        self.assertEqual(self.m.dispatch_one(unknown,enabled=True)['status'],'UNKNOWN')
        self.tick(True);self.m.dispatch_one(self.sender,enabled=True)
        self.assertEqual(len(self.calls),1)
    def test_recovery_only_after_confirmed_outage(self):
        self.outage();self.m.dispatch_one(self.sender,enabled=True)
        self.tick(True);self.m.dispatch_one(self.sender,enabled=True)
        self.tick(True);self.m.dispatch_one(self.sender,enabled=True)
        self.assertEqual(len(self.calls),2)
        self.assertIn('recovered',self.calls[-1])
    def test_maintenance_and_integrity_suppress(self):
        self.time=11
        for kwargs in [{'maintenance':True},{'integrity_ok':False}]:
            for _ in range(5):self.assertEqual(self.tick(**kwargs)['state'],'SUPPRESSED')
            self.assertEqual(self.m.dispatch_one(self.sender,enabled=True)['status'],'SUPPRESSED')
        self.assertEqual(self.calls,[])
    def test_suppression_blocks_pending_and_recovery(self):
        self.outage();self.tick(maintenance=True)
        self.assertEqual(self.m.dispatch_one(self.sender,enabled=True)['status'],'SUPPRESSED')
        self.tick(True,maintenance=True)
        self.assertEqual(self.m.dispatch_one(self.sender,enabled=True)['status'],'SUPPRESSED')
    def test_stale_outage_not_sent(self):
        self.outage();self.tick(True)
        self.assertEqual(self.m.dispatch_one(self.sender,enabled=True)['status'],'IDLE')
    def test_crash_reserved_send_not_reclaimed(self):
        self.outage()
        with self.m.db() as db:db.execute("UPDATE notices SET status='SENDING'")
        self.assertEqual(self.m.dispatch_one(self.sender,enabled=True)['status'],'IDLE')
    def test_clock_regression_rejected(self):
        self.outage();self.time=1
        with self.assertRaises(ValueError):self.tick()
    def test_new_outage_separate_receipt(self):
        self.outage();self.m.dispatch_one(self.sender,enabled=True);self.tick(True);self.m.dispatch_one(self.sender,enabled=True)
        self.time=20;self.outage();self.m.dispatch_one(self.sender,enabled=True)
        self.assertEqual(len(self.calls),3)
    def test_integrity_requires_actual_hash(self):
        p=self.root/'code';p.write_bytes(b'original')
        self.assertTrue(integrity({str(p):hashlib.sha256(b'original').hexdigest()}))
        self.assertFalse(integrity({str(p):'0'*64}))
        self.assertFalse(integrity({}))
    def test_probe_optin_and_shapes(self):
        with self.assertRaises(PermissionError):probe(['http://127.0.0.1:1234/health'])
        for value,expected in [({},True),([],False),({'ok':True},True),(TimeoutError(),False)]:
            self.assertEqual(probe(['http://127.0.0.1:1234/health'],allow_network=True,opener=Opener(value)),expected)
    def test_endpoint_policy(self):
        for value in ['http://example.com/health','file:///secret','https://u:p@example.com/health','https://example.com/health?secret=value']:
            with self.assertRaises(ValueError):endpoint_url(value)
    def test_telegram_recipient_and_receipt(self):
        with self.assertRaises(PermissionError):TelegramSender(token_env='EXAMPLE_BOT_TOKEN',recipient='123',allowed_recipient='456')
        with patch.dict(os.environ,{'EXAMPLE_BOT_TOKEN':'synthetic-test-value'}):
            for chat,expected in [('123',True),('456',False)]:
                opener=Opener({'ok':True,'result':{'chat':{'id':chat},'message_id':9}})
                send=TelegramSender(token_env='EXAMPLE_BOT_TOKEN',recipient='123',allowed_recipient='123',allow_network=True,opener=opener)
                self.assertEqual(send('fixture')['confirmed'],expected)
                self.assertEqual(len(opener.calls),1)
    def test_telegram_network_disabled(self):
        send=TelegramSender(token_env='EXAMPLE_BOT_TOKEN',recipient='123',allowed_recipient='123')
        with self.assertRaises(PermissionError):send('fixture')

if __name__=='__main__':unittest.main()
