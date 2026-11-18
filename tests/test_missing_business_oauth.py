import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode
from toolkit.tiktok_business_oauth import BusinessOAuth,BusinessTransport,EXCHANGE,REFRESH,INFO
from toolkit.tiktok_oauth import OAuthError,OAuth
from toolkit.tiktok_publisher import Client

class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.calls=[];self.now=1000
        self.token={'access_token':'business-fixture','refresh_token':'refresh-fixture','open_id':'account-fixture','expires_in':86400}
        self.info={'app_id':'app-fixture','creator_id':'account-fixture','scope':'video.list,video.publish'}
        def transport(url,body):
            self.calls.append((url,body));return {'code':0,'data':copy.deepcopy(self.info if url==INFO else self.token)}
        self.auth=BusinessOAuth(self.root,client_id='app-fixture',client_secret='secret-fixture',redirect_uri='https://app.example/callback',
            scopes=['video.list','video.publish'],expected_open_id='account-fixture',transport=transport,clock=lambda:self.now)
        self.session='authenticated-fixture-session'
    def callback(self):
        start=self.auth.start(self.session)
        self.assertEqual(start['authorization_url'],'OPERATOR_REVIEW_REQUIRED')
        return 'https://app.example/callback?'+urlencode({'state':start['state'],'auth_code':'code-fixture'})
    def test_exchange_official_json_fields_and_publisher_provider(self):
        result=self.auth.finish(self.callback(),self.session)
        self.assertEqual(result['family'],'business-accounts-v1.3');self.assertIsNone(result['refresh_expires_at'])
        self.assertEqual(self.calls[0],(EXCHANGE,{'client_id':'app-fixture','client_secret':'secret-fixture','grant_type':'authorization_code','auth_code':'code-fixture','redirect_uri':'https://app.example/callback'}))
        client=Client({'client_id':'app-fixture','client_secret':'secret-fixture','expected_open_id':'account-fixture','approved_media_hosts':['media.example']},self.auth.token_provider)
        self.assertEqual(client.tokens()['open_id'],'account-fixture')
        self.assertFalse((self.root/'oauth.json').exists());self.assertEqual((self.root/'business-oauth.json').stat().st_mode&0o777,0o600)
        self.assertNotIn('business-fixture',json.dumps(self.auth.status()))
    def test_refresh_rotation_and_account_scope_check(self):
        self.auth.finish(self.callback(),self.session);self.token['refresh_token']='rotated'
        self.auth.refresh(force=True);self.auth.refresh(force=True)
        self.assertEqual(self.calls[-2][0],REFRESH);self.assertEqual(self.calls[-2][1]['refresh_token'],'rotated')
        self.info['scope']='video.list'
        with self.assertRaises(OAuthError):self.auth.refresh(force=True)
        with self.assertRaises(OAuthError):self.auth.token_provider()
    def test_callback_security_and_replay(self):
        cb=self.callback()
        for bad,session in ((cb+'&code=other',self.session),(cb+'&auth_code=other',self.session),(cb+'#fragment',self.session),(cb,'wrong')):
            with self.assertRaises(OAuthError):self.auth.finish(bad,session)
        self.assertFalse(self.calls);self.auth.finish(cb,self.session)
        with self.assertRaises(OAuthError):self.auth.finish(cb,self.session)
    def test_uncertain_exchange_no_replay(self):
        cb=self.callback();calls=[]
        def fail(*a):calls.append(a);raise TimeoutError()
        self.auth.transport=fail
        for _ in range(2):
            with self.assertRaises(OAuthError):self.auth.finish(cb,self.session)
        self.assertEqual(len(calls),1);self.assertEqual(self.auth.status()['phase'],'UNKNOWN')
    def test_bad_envelope_wrong_account_and_wrong_app(self):
        for mutation in ('envelope','account','app'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as root:
                def transport(url,body):
                    if mutation=='envelope':return {'code':False,'data':self.token}
                    value=copy.deepcopy(self.info if url==INFO else self.token)
                    if mutation=='account' and url!=INFO:value['open_id']='wrong'
                    if mutation=='app' and url==INFO:value['app_id']='wrong'
                    return {'code':0,'data':value}
                auth=BusinessOAuth(root,client_id='app-fixture',client_secret='secret-fixture',redirect_uri='https://app.example/callback',
                    scopes=['video.list'],expected_open_id='account-fixture',transport=transport)
                start=auth.start(self.session)
                with self.assertRaises(OAuthError):auth.finish('https://app.example/callback?'+urlencode({'state':start['state'],'code':'code'}),self.session)
    def test_concurrent_refresh_single_write(self):
        self.auth.finish(self.callback(),self.session);old=self.auth.transport;entered=threading.Event();release=threading.Event();errors=[]
        def transport(url,body):
            if url==REFRESH:entered.set();release.wait(3)
            return old(url,body)
        self.auth.transport=transport
        def run():
            try:self.auth.refresh(force=True)
            except Exception as exc:errors.append(exc)
        t=threading.Thread(target=run);t.start();self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(RuntimeError):self.auth.refresh(force=True)
        finally:release.set();t.join(3)
        self.assertFalse(errors);self.assertEqual(sum(url==REFRESH for url,_ in self.calls),1)
    def test_crash_after_claim_never_replays(self):
        cb=self.callback()
        def crash(*a):raise KeyboardInterrupt()
        self.auth.transport=crash
        with self.assertRaises(KeyboardInterrupt):self.auth.finish(cb,self.session)
        self.assertEqual(self.auth.status()['phase'],'EXCHANGING')
        with self.assertRaises(OAuthError):self.auth.start(self.session)
    def test_default_disabled_and_expiry(self):
        with self.assertRaises(OAuthError):BusinessTransport()(EXCHANGE,{})
        cb=self.callback();self.now+=300
        with self.assertRaises(OAuthError):self.auth.finish(cb,self.session)
    def test_family_store_separation(self):
        self.auth.finish(self.callback(),self.session)
        login=OAuth(self.root,client_key='login-app',client_secret='login-secret',redirect_uri='https://app.example/callback',scopes=['video.list'])
        self.assertEqual(login.status()['phase'],'EMPTY')
        self.assertEqual(self.auth.status()['phase'],'READY')

if __name__=='__main__':unittest.main()
