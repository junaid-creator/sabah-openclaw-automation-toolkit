import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit, urlencode
from toolkit.badge_audit import audit_html, fetch_html, NoRedirect
from toolkit.tiktok_oauth import OAuth, OAuthError, TOKEN, OfficialTransport
from toolkit.voice_control import VoiceControl
from toolkit.isolated_store import Store
from toolkit.approval_ledger import Ledger, digest
from toolkit.trusted_bridge import Bridge, canonical
from toolkit.social_review import Controller, ReviewError, PublisherAdapters, LocalRenderer

class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

class BadgeTests(unittest.TestCase):
    def test_nested_attribute_order_entities(self):
        result=audit_html('<span class="badge" data-smgc-product="1"><b>Save</b> &amp; rent</span>',1,{'1':'Save & rent'})
        self.assertTrue(result['pass']);self.assertEqual(result['visual_visibility'],'NOT_TESTED')
    def test_missing_duplicate_generic_other_mismatch(self):
        good='<span data-smgc-product="1">Save</span>'
        for html in ('',good+good,good+'<span class="x onsale">Sale!</span>',good+'<span data-smgc-product="2">wrong</span>'):
            self.assertFalse(audit_html(html,1,{'1':'Save','2':'Right'})['pass'])
    def test_bad_urls_no_network(self):
        for url in ('http://shop.example/x','https://user:pass@shop.example/x','https://other.example/x','file:///etc/passwd','https://shop.example:8443/x'):
            with self.assertRaises(ValueError):fetch_html(url,{'shop.example'})
        with patch('socket.getaddrinfo',return_value=[(None,None,None,None,('127.0.0.1',443))]):
            with self.assertRaises(ValueError):fetch_html('https://shop.example/x',{'shop.example'})
        with self.assertRaises(ValueError):NoRedirect().redirect_request(None)
    def test_bound_and_expected(self):
        with self.assertRaises(ValueError):audit_html('x'*2100000,1,{'1':'Save'})
        with self.assertRaises(ValueError):audit_html('',2,{'1':'Save'})

class OAuthTests(Temp):
    def setUp(self):
        super().setUp();self.calls=[];self.now=1000
        self.response={'access_token':'fixture-access','refresh_token':'fixture-refresh','open_id':'fixture-user','scope':'user.info.basic,video.list','token_type':'Bearer','expires_in':7200,'refresh_expires_in':86400}
        def transport(url,form):self.calls.append((url,form));return copy.deepcopy(self.response)
        self.auth=OAuth(self.root,client_key='fixture-key',client_secret='fixture-secret',redirect_uri='https://app.example/callback',scopes=['user.info.basic','video.list'],transport=transport,clock=lambda:self.now)
        self.session='fixture-session-123456'
    def callback(self):
        uri=self.auth.start(self.session);state=parse_qs(urlsplit(uri).query)['state'][0]
        return 'https://app.example/callback?'+urlencode({'state':state,'code':'decoded+code'})
    def test_exchange_refresh_rotation_and_redaction(self):
        cb=self.callback();result=self.auth.finish(cb,self.session)
        self.assertEqual(result['phase'],'READY');self.assertNotIn('fixture-access',json.dumps(result))
        self.assertEqual(self.calls[0][0],TOKEN);self.assertEqual(self.calls[0][1]['code'],'decoded+code')
        self.assertEqual(self.auth.access_token(),'fixture-access');self.assertEqual(self.root.joinpath('oauth.json').stat().st_mode&0o777,0o600)
        self.auth.refresh();self.assertEqual(len(self.calls),1)
        self.response['refresh_token']='rotated';self.auth.refresh(force=True)
        self.auth.refresh(force=True);self.assertEqual(self.calls[-1][1]['refresh_token'],'rotated')
        with self.assertRaises(OAuthError):self.auth.finish(cb,self.session)
    def test_state_session_duplicate_redirect_and_expiry(self):
        cb=self.callback()
        for candidate,session in ((cb,'wrong-session'),(cb.replace('app.example','evil.example'),self.session),(cb+'&state=extra',self.session),(cb+'#x',self.session)):
            with self.assertRaises(OAuthError):self.auth.finish(candidate,session)
        self.assertFalse(self.calls);self.now+=300
        with self.assertRaises(OAuthError):self.auth.finish(cb,self.session)
    def test_uncertain_exchange_no_replay(self):
        cb=self.callback()
        def fail(*args):self.calls.append(args);raise TimeoutError('secret must not leak')
        self.auth.transport=fail
        with self.assertRaisesRegex(OAuthError,'RECONCILIATION'):self.auth.finish(cb,self.session)
        for action in (lambda:self.auth.finish(cb,self.session),lambda:self.auth.start(self.session),lambda:self.auth.refresh(force=True)):
            with self.assertRaises(OAuthError):action()
        self.assertEqual(len(self.calls),1);self.assertNotIn('secret must',self.root.joinpath('oauth.json').read_text())
    def test_identity_scope_expiry_negative(self):
        for change in ({'scope':'user.info.basic'},{'expires_in':True},{'token_type':'MAC'},{'access_token':''}):
            with self.assertRaises(OAuthError):self.auth._candidate({**self.response,**change})
        with self.assertRaises(OAuthError):self.auth._candidate(self.response,'different-user')
    def test_rotation_uncertainty_preserves_old_but_blocks_use(self):
        self.auth.finish(self.callback(),self.session)
        self.auth.transport=lambda *a: (_ for _ in ()).throw(TimeoutError())
        with self.assertRaises(OAuthError):self.auth.refresh(force=True)
        with self.assertRaises(OAuthError):self.auth.access_token()
        self.assertEqual(self.auth.status()['phase'],'UNKNOWN')
    def test_process_death_marker_blocks(self):
        cb=self.callback()
        def crash(*a):raise KeyboardInterrupt()
        self.auth.transport=crash
        with self.assertRaises(KeyboardInterrupt):self.auth.finish(cb,self.session)
        self.assertEqual(self.auth.status()['phase'],'EXCHANGING')
        with self.assertRaises(OAuthError):self.auth.finish(cb,self.session)
    def test_concurrent_finish_single_transport(self):
        cb=self.callback();entered=threading.Event();release=threading.Event();errors=[]
        def transport(*a):self.calls.append(a);entered.set();release.wait(3);return self.response
        self.auth.transport=transport
        def run():
            try:self.auth.finish(cb,self.session)
            except Exception as e:errors.append(e)
        thread=threading.Thread(target=run);thread.start();self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(RuntimeError):self.auth.finish(cb,self.session)
        finally:release.set();thread.join(3)
        self.assertFalse(errors);self.assertEqual(len(self.calls),1)
    def test_private_store_and_disabled_transport(self):
        with self.assertRaises(OAuthError):OfficialTransport()(TOKEN,{})
        self.root.joinpath('oauth.json').symlink_to(self.root/'absent')
        with self.assertRaises(PermissionError):self.auth.status()
    def test_wrong_application_store(self):
        self.callback()
        other=OAuth(self.root,client_key='other',client_secret='other',redirect_uri='https://app.example/callback',scopes=['video.list'])
        with self.assertRaises(OAuthError):other.status()

class VoiceTests(Temp):
    def test_optin_merge_cas_rollback(self):
        c=VoiceControl(self.root);etag=c.status()['etag']
        with self.assertRaises(PermissionError):c.apply({'profile':'male'},expected=etag)
        c.enabled=True
        first=c.apply({'profile':'male','local_voice':{'custom':{'a':1,'b':2}}},expected=etag)
        with self.assertRaises(ValueError):c.apply({'mode':'off'},expected=etag)
        second=c.apply({'local_voice':{'custom':{'a':3}}},expected=first['etag'])
        self.assertEqual(c.status()['settings']['local_voice']['custom'],{'a':3,'b':2})
        c.rollback(0,expected=second['etag']);self.assertEqual(c.status()['settings'],{'mode':'off','profile':'female'})
        self.assertFalse(c.status()['activated'])
    def test_invalid_patch_and_no_live_paths(self):
        c=VoiceControl(self.root,enabled=True);etag=c.status()['etag']
        for patch_value in ({'channels':{}},{'mode':'always'},{'mode':'inbound'},{'profile':'unknown'}):
            with self.assertRaises((ValueError,KeyError)):c.apply(patch_value,expected=etag)
        self.assertFalse((self.root/'voice.json').exists())
        with self.assertRaises(PermissionError):c.local_config({'channel':'x'})
    def test_concurrent_cas_only_one_winner(self):
        c=VoiceControl(self.root,enabled=True);etag=c.status()['etag'];out=[]
        def run():
            try:out.append(c.apply({'profile':'male'},expected=etag))
            except (ValueError,RuntimeError):out.append('blocked')
        threads=[threading.Thread(target=run) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sum(isinstance(x,dict) for x in out),1)
    def test_failed_save_and_tampered_rollback(self):
        c=VoiceControl(self.root,enabled=True);etag=c.status()['etag']
        with patch.object(c.store,'save',side_effect=OSError('disk')):
            with self.assertRaises(OSError):c.apply({'profile':'male'},expected=etag)
        self.assertEqual(c.status()['etag'],etag)
        c.apply({'profile':'male'},expected=etag);state=c.store.read();state['history'][0]['settings']['profile']='male';c.store.save(state)
        with self.assertRaises(ValueError):c.rollback(0,expected=c.status()['etag'])
    def test_local_voice_configuration_export(self):
        asset=self.root/'fixture-asset';asset.write_bytes(b'not executed');asset.chmod(0o600)
        cfg={k:str(asset) for k in ('ffmpeg','asr','encoder','decoder','tokens','piper')}
        cfg.update(model_license_reviewed=True,voices={'female':{'en':str(asset)}})
        route={'channel':'fixture','account':'test','peer':'owner'};c=VoiceControl(self.root,enabled=True)
        c.apply({'mode':'inbound','local_voice':cfg,'routes':[route]},expected=c.status()['etag'])
        self.assertEqual(c.local_config(route),(cfg,'female'))
        with self.assertRaises(PermissionError):c.local_config({**route,'peer':'other'})

class SocialTests(Temp):
    def setUp(self):
        super().setUp();self.key=b'f'*32;self.route={'channel':'fixture','account':'test','peer':'owner','role':'owner'}
        self.bridge=Bridge(self.root/'bridge.sqlite',self.key,[self.route],clock=lambda:1000)
        self.ledger=Ledger(self.root/'publish.sqlite');self.renders=[];self.sends=[]
        def renderer(campaign,key):
            self.renders.append(key);p=self.root/(key+'.jpg');p.write_bytes(b'fixture-photo');p.chmod(0o600)
            return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'url':'https://media.example/'+key+'.jpg','geometry_pass':True,'template':campaign['template']}
        def sender(route,binding):
            self.sends.append(binding);return {**route,'delivered':True,'message_id':'fixture-message','binding_digest':digest(binding)}
        self.c=Controller(self.root,bridge=self.bridge,ledger=self.ledger,renderer=renderer,sender=sender)
    def event(self,id,text='Draft equipment'):
        e={'id':id,**{k:self.route[k] for k in ('channel','account','peer')},'kind':'direct','timestamp':1000,'text':text}
        return e,hmac.new(self.key,canonical(e).encode(),hashlib.sha256).hexdigest()
    def campaign(self,n=1):
        return {'template':n,'content':{'headline':'Tools','subheadline':'For your project','cta':'Contact us','services':[{'en':'Tool '+str(i),'ar':'','icon':'tool'} for i in range(4)]},'targets':['facebook','instagram','tiktok'],'captions':{p:'Exact caption' for p in ('facebook','instagram','tiktok')}}
    def create(self,n=1,id='create'):return self.c.create(*self.event(id),self.campaign(n))
    def approve(self,state):
        job=state['job_id'];self.c.review(job);ch=self.c.challenge(job,*self.event('challenge'+job))
        self.c.approve(job,*self.event('confirm'+job,ch['confirmation']));return job
    def test_six_templates_idempotent_draft(self):
        for n in range(1,7):
            state=self.create(n,str(n));self.assertEqual(state['campaign']['template'],n)
            self.assertEqual(self.create(n,str(n)),state);self.assertIsNone(self.ledger.job(state['job_id']))
            self.assertEqual(state['phase'],'DRAFT');self.assertIsNone(state['schedule'])
        self.assertEqual(len(self.renders),6);self.assertFalse(self.sends)
    def test_create_collision_and_untrusted(self):
        self.create()
        with self.assertRaises(ReviewError):self.c.create(*self.event('create'),self.campaign(2))
        event,sig=self.event('evil');event['peer']='other'
        with self.assertRaises(PermissionError):self.c.create(event,sig,self.campaign())
    def test_review_exact_once_and_approval(self):
        state=self.create();job=self.approve(state)
        self.assertEqual(len(self.sends),1);self.assertEqual(self.ledger.job(job)['state'],'PENDING_APPROVAL_SYNC')
        with self.assertRaises(ReviewError):self.c.revise(job,*self.event('revise'),self.campaign(2),expected=self.c.status(job)['etag'])
        with self.assertRaises(PermissionError):self.c.dispatch(job,publisher=lambda *a:{})
    def test_revision_invalidates_old_review_and_challenge(self):
        state=self.create();job=state['job_id'];self.c.review(job);ch=self.c.challenge(job,*self.event('challenge'))
        new=self.c.revise(job,*self.event('revise'),self.campaign(2),expected=self.c.status(job)['etag'])
        self.assertEqual(new['revision'],2);self.assertNotIn('review',new);self.assertEqual(len(new['history']),1)
        with self.assertRaises(ReviewError):self.c.approve(job,*self.event('confirm',ch['confirmation']))
        self.c.review(job);self.assertEqual(len(self.sends),2)
    def test_review_uncertain_and_crash_no_resend(self):
        job=self.create()['job_id'];calls=[]
        def sender(*a):calls.append(a);raise TimeoutError()
        self.c.sender=sender
        for _ in range(2):
            with self.assertRaises(ReviewError):self.c.review(job)
        self.assertEqual(len(calls),1);self.assertEqual(self.c.status(job)['state']['phase'],'REVIEW_UNKNOWN')
    def test_dryrun_receipt_never_approval(self):
        job=self.create()['job_id'];old=self.c.sender
        self.c.sender=lambda *a:{**old(*a),'dryRun':True}
        with self.assertRaises(ReviewError):self.c.review(job)
        self.assertIsNone(self.ledger.job(job))
    def test_changed_media_blocks_review(self):
        state=self.create();Path(state['artifact']['path']).write_bytes(b'changed')
        with self.assertRaises(ReviewError):self.c.review(state['job_id'])
        self.assertFalse(self.sends)
    def test_dispatch_uncertain_and_false_success_no_retry(self):
        job=self.approve(self.create());calls=[]
        def publisher(*a):calls.append(a);return {p:{'status':'VERIFIED','url':'https://example.test/post'} for p in ('facebook','instagram','tiktok')}
        for _ in range(2):
            with self.assertRaises(ReviewError):self.c.dispatch(job,publisher=publisher,enabled=True)
        self.assertEqual(len(calls),1)
    def test_dispatch_records_per_platform_and_skips_duplicate(self):
        job=self.approve(self.create());calls=[]
        def publisher(job,binding,ledger):
            calls.append(job);result={}
            for p in binding['targets']:
                ledger.reserve(job,p,1);ledger.update(job,p,'PUBLISHED',remote_id='fixture-post',permalink='https://example.test/'+p)
                result[p]={'status':'VERIFIED','url':'https://example.test/'+p}
            return result
        result=self.c.dispatch(job,publisher=publisher,enabled=True)
        self.assertEqual(self.c.dispatch(job,publisher=publisher,enabled=True),result);self.assertEqual(len(calls),1)
    def test_concurrent_create_single_renderer(self):
        old=self.c.renderer;entered=threading.Event();release=threading.Event();errors=[]
        def renderer(*a):entered.set();release.wait(3);return old(*a)
        self.c.renderer=renderer
        def run():
            try:self.create()
            except Exception as e:errors.append(e)
        t=threading.Thread(target=run);t.start();self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(RuntimeError):self.create()
        finally:release.set();t.join(3)
        self.assertFalse(errors);self.assertEqual(len(self.renders),1)
    def test_existing_tiktok_advance_with_safe_client(self):
        from types import SimpleNamespace
        campaign=self.campaign();campaign['targets']=['tiktok'];campaign['captions']={'tiktok':'Exact caption'}
        state=self.c.create(*self.event('tiktok'),campaign);job=self.approve(state);calls=[]
        class Client:
            def prepare(self,url,caption):calls.append(('prepare',url,caption));return {'safe':'fixture'}
            def submit(self,payload):calls.append(('submit',payload));return 'fixture-task'
        engine=SimpleNamespace(ledger=self.ledger,tiktok=Client(),clock=lambda:1000,
            checked=lambda j:self.assertEqual(j,job),caption=lambda c,p:c[p+'_caption'])
        result=self.c.dispatch(job,publisher=PublisherAdapters(tiktok_engine=engine),enabled=True)
        self.assertEqual(result['tiktok']['status'],'PROCESSING')
        self.assertEqual(self.ledger.op(job,'tiktok')['container_id'],'fixture-task')
        self.c.dispatch(job,publisher=PublisherAdapters(tiktok_engine=engine),enabled=True)
        self.assertEqual(sum(x[0]=='submit' for x in calls),1)
    def test_existing_meta_publisher_dryrun_uses_no_transport(self):
        from toolkit import meta_publisher as meta
        from test_meta_publisher import FakeSheets,FakeSecrets,FakeMedia,FakeApproval,FakeTransport
        campaign=self.campaign();campaign['targets']=['facebook'];campaign['captions']={'facebook':'Exact caption'}
        state=self.c.create(*self.event('meta'),campaign);job=self.approve(state)
        sheets=FakeSheets(instagram='FALSE',tiktok='FALSE');sheets.content['final_master_asset_url']=state['artifact']['url']
        sheets.content.update(job_id=job,facebook_caption='Exact caption',facebook_hashtags='');sheets.queue['job_id']=job
        from toolkit.social_publish_gate import BoundApprovalGate
        gate=BoundApprovalGate(self.c,sheets,meta.SheetPublicationGate(sheets))
        self.assertTrue(gate.authorize(job,'facebook'))
        sheets.content['facebook_caption']='changed'
        self.assertFalse(gate.authorize(job,'facebook'))
        sheets.content['facebook_caption']='Exact caption'
        transport=FakeTransport()
        settings=meta.MetaSettings(api_version='v25.0',instagram_auth_mode=meta.InstagramAuthMode.FACEBOOK_LOGIN,
            page_id='12345678901',instagram_user_id='10987654321',expected_page_name='Fixture')
        publisher=meta.MetaPublisher(settings=settings,transport=transport,secrets=FakeSecrets(),sheets=sheets,
            ledger=self.ledger,media_verifier=FakeMedia(),approval_gate=gate,dry_run=True)
        result=self.c.dispatch(job,publisher=PublisherAdapters(meta=publisher),enabled=True)
        self.assertEqual(result['facebook']['status'],'PROCESSING');self.assertFalse(transport.calls)
    def test_preparation_crash_is_latched(self):
        def crash(*a):raise KeyboardInterrupt()
        self.c.renderer=crash
        with self.assertRaises(KeyboardInterrupt):self.create()
        state=self.create();self.assertEqual(state['phase'],'PREPARING')
        with self.assertRaises(ReviewError):self.c.review(state['job_id'])
    def test_local_renderer_calls_existing_six_layouts(self):
        from toolkit.social_review import plan
        calls=[]
        def render(n,content,brand,fonts,atlas,root,key,**kw):
            calls.append(n);return {'template':n,'geometry_pass':True,'outputs':{'poster.jpg':'fixture-hash'}}
        adapter=LocalRenderer(brand={},fonts={},atlas='unused',output_root=self.root,host=lambda *a:'https://media.example/fixture.jpg')
        with patch('toolkit.social_review.render',side_effect=render):
            for n in range(1,7):self.assertEqual(adapter(plan(self.campaign(n)),'fixture')['template'],n)
        self.assertEqual(calls,list(range(1,7)))

if __name__=='__main__':unittest.main()
