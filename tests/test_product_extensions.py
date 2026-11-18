import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
import test_product_workflow as base
from test_product_workflow import OWNER, Response
from toolkit.product_media import Media
from toolkit.trusted_bridge import canonical,fingerprint
from toolkit.source_reconciliation import snapshot,row_request,revalidate,mirror_once


class MediaTests(unittest.TestCase):
    event = base.ProductTests.event
    # Reuse the actual signed-owner/Woo HTTP fixture, not a boolean approval mock.
    def setUp(self):
        base.ProductTests.setUp(self)
        self.assets=Path(self.tmp.name)/'assets';self.assets.mkdir(mode=0o700)
        p=self.assets/'demo.webp';Image.new('RGB',(16,16),'blue').save(p,'WEBP');p.chmod(0o600)
        self.req={'site':'demo','file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rights':'owned','rights_reference':'fixture-author'}
        self.media=Media(self.engine,self.assets)
        original=self.http.open
        self.uploads=0;self.lose=False;self.saved=None
        def opened(req,timeout):
            if '/wp-json/wp/v2/media' not in req.full_url or '/80?' in req.full_url:
                return original(req,timeout)
            if req.method=='POST':
                self.uploads+=1
                name=req.get_header('Content-disposition').split('"')[1]
                self.saved={'id':801,'slug':name[:-5],'media_type':'image','mime_type':'image/webp','source_url':'https://shop.example/uploads/'+name}
                if self.lose: raise OSError('lost response')
            return Response(json.dumps(self.saved).encode())
        self.http.open=opened

    def prepared(self):
        r=self.media.plan(*self.event('MEDIA PLAN '+canonical(self.req)))
        jid=r['job_id'];proof={k:OWNER[k] for k in ('channel','account','peer')}
        proof.update(delivered=True,message_id='review-media',binding_digest=fingerprint(r['binding']))
        c=self.media.challenge(jid,*self.event('MEDIA REVIEW '+jid),proof)
        self.bridge.confirm(*self.event(c['confirmation']),c['challenge_id'])
        return jid,c

    def test_media_exact_upload_no_replay(self):
        jid,c=self.prepared()
        self.assertEqual(self.media.execute(jid,*self.event('MEDIA EXECUTE '+jid))['id'],801)
        self.media.execute(jid,*self.event('MEDIA EXECUTE '+jid))
        self.assertEqual(self.uploads,1)

    def test_media_unknown_and_readonly_recovery(self):
        jid,c=self.prepared();self.lose=True
        with self.assertRaises(RuntimeError):self.media.execute(jid,*self.event('MEDIA EXECUTE '+jid))
        with self.assertRaises(RuntimeError):self.media.execute(jid,*self.event('MEDIA EXECUTE '+jid))
        self.media.reconcile(jid,*self.event('MEDIA RECONCILE '+jid),lookup=lambda jid,sha:{**self.saved,'verified_sha256':sha})
        self.assertEqual(self.uploads,1)

    def test_media_revocation(self):
        jid,c=self.prepared();self.bridge.revoke(*self.event('REVOKE '+c['challenge_id']),c['challenge_id'])
        with self.assertRaises(PermissionError):self.media.execute(jid,*self.event('MEDIA EXECUTE '+jid))
        self.assertEqual(self.uploads,0)

    def test_media_no_rights_or_changed_asset(self):
        self.req['rights']='unknown'
        with self.assertRaises(PermissionError):self.media.plan(*self.event('MEDIA PLAN '+canonical(self.req)))
        self.req['rights']='owned';jid,c=self.prepared()
        (self.assets/'demo.webp').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.media.execute(jid,*self.event('MEDIA EXECUTE '+jid))
        self.assertEqual(self.uploads,0)

    def test_media_command_dispatch(self):
        from toolkit.product_commands import dispatch
        self.engine.media=self.media
        def command(text,**extra):
            e,s=self.event(text);return dispatch(self.engine,dict(event=e,signature=s,**extra))
        r=command('MEDIA PLAN '+canonical(self.req));jid=r['job_id']
        receipt=dict(OWNER,delivered=True,message_id='native-review',binding_digest=fingerprint(r['binding']))
        c=command('MEDIA REVIEW '+jid,review_receipt=receipt)
        command(c['confirmation'])
        command('MEDIA REVOKE '+jid)
        with self.assertRaises(PermissionError):command('MEDIA EXECUTE '+jid)
        self.assertEqual(self.uploads,0)

    def test_media_no_approval(self):
        r=self.media.plan(*self.event('MEDIA PLAN '+canonical(self.req)));jid=r['job_id']
        with self.assertRaises(PermissionError):self.media.execute(jid,*self.event('MEDIA EXECUTE '+jid))
        self.assertEqual(self.uploads,0)


class SourceTests(unittest.TestCase):
    def test_source_plan_and_formula_fence(self):
        s=snapshot([{'source_id':'row-a','title':'Device'}],formulas=[{'title':'=A1'}])
        r=row_request(s,'row-a',{'name':'title'},site='demo')
        self.assertEqual(r['request']['fields'],{'name':'Device'})
        self.assertTrue(revalidate(s,lambda:s))
        changed=snapshot(s['value']['rows'],formulas=[{'title':'=A2'}])
        with self.assertRaises(RuntimeError):revalidate(s,lambda:changed)
    def test_duplicate_rows(self):
        with self.assertRaises(ValueError):snapshot([{'source_id':'a'},{'source_id':'a'}])
    def test_mirror_response_loss_no_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            rows=[['before']];calls=[]
            b={'range':'Demo!A1','before':[['before']],'after':[['after']],'source_id':'a'}
            def writer(r,value):
                calls.append(r);rows[:]=value;raise OSError('response lost')
            for _ in range(2):self.assertEqual(mirror_once(Path(d)/'mirror.json',b,reader=lambda r:rows,writer=writer,exclusive_writer=True),'VERIFIED')
            self.assertEqual(len(calls),1)
    def test_mirror_unknown_fenced(self):
        with tempfile.TemporaryDirectory() as d:
            b={'range':'Demo!A1','before':[['before']],'after':[['after']],'source_id':'a'};calls=[]
            for _ in range(2):
                with self.assertRaises(RuntimeError):mirror_once(Path(d)/'mirror.json',b,reader=lambda r:[['before']],writer=lambda r,v:calls.append(r),exclusive_writer=True)
            self.assertEqual(len(calls),1)
