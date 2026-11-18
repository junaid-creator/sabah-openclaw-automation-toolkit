import copy
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch
from toolkit.product_api import Woo, ROOT, STATUSES, MARKER
from toolkit.product_workflow import Products
from toolkit.product_commands import dispatch
from toolkit.trusted_bridge import Bridge,canonical,fingerprint

OWNER={'channel':'test','account':'shop','peer':'owner','role':'owner'}
CUSTOMER={'channel':'test','account':'shop','peer':'buyer','role':'customer'}
SITE={'id':'demo','origin':'https://shop.example','wp_user_id':7,'owners':[OWNER],
      'metadata_keys':['display_note'],'exclusive_writer_confirmed':True}


def product(pid=10,**kw):
    p=dict(id=pid,name='Existing machine',sku='EXISTING',type='simple',status='draft',
           regular_price='10',price='10',sale_price='',manage_stock=True,stock_quantity=4,
           stock_status='instock',images=[{'id':80}],categories=[{'id':90}],meta_data=[],
           attributes=[],variations=[],description='Original',short_description='Summary',
           date_on_sale_from=None,date_on_sale_to=None,catalog_visibility='visible',
           permalink='https://shop.example/product/existing')
    p.update(kw); return p


class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self,*args): self.close()


class HTTP:
    def __init__(self):
        self.parents={10:product()};self.children={};self.calls=[];self.posts=0;self.fail_after=None
        self.fail_before=None;self.side_effect=None;self.user=7;self.next_id=100
        self.media={'id':80,'media_type':'image','mime_type':'image/webp','slug':'tool',
                    'source_url':'https://cdn.example/tool.webp','title':{'raw':'Verified tool'},'alt_text':'Tool','media_details':{'width':400}}
        self.category={'id':90,'name':'Machines','slug':'machines','parent':0}
    def open(self,req,timeout):
        u=urlsplit(req.full_url);q=parse_qs(u.query);path=u.path
        assert u.scheme=='https' and u.netloc=='shop.example','Unexpected egress'
        self.calls.append((req.method,path,q))
        if path=='/wp-json/wp/v2/users/me':out={'id':self.user}
        elif path=='/wp-json/wp/v2/media/80':out=self.media
        elif path==ROOT+'/categories/90':out=self.category
        elif path.startswith(ROOT):
            bits=path[len(ROOT):].strip('/').split('/') if path!=ROOT else []
            pid=int(bits[0]) if bits else None
            variation=len(bits)>1 and bits[1]=='variations'
            vid=int(bits[2]) if len(bits)>2 else None
            if req.method=='POST':
                self.posts+=1
                if self.fail_before==self.posts:raise OSError('synthetic prewrite failure')
                data=json.loads(req.data)
                if variation:
                    target=self.children.get(vid) if vid else None
                else:target=self.parents.get(pid) if pid else None
                if target is None:
                    new=self.next_id;self.next_id+=1
                    target=product(new,images=[],categories=[],manage_stock=False,stock_quantity=None,attributes=[],sku='',regular_price='',price='',variations=[],name='')
                    if variation:target.update(parent_id=pid);self.children[new]=target;self.parents[pid]['variations'].append(new)
                    else:self.parents[new]=target
                for k,v in data.items():
                    if k=='meta_data':
                        merged={m['key']:m['value'] for m in target[k]};merged.update({m['key']:m['value'] for m in v})
                        target[k]=[{'id':i+1,'key':a,'value':b} for i,(a,b) in enumerate(merged.items())]
                    else:target[k]=copy.deepcopy(v)
                if 'regular_price' in data:target['price']=data['regular_price']
                if variation:
                    values=[v['price'] for v in self.children.values() if v['parent_id']==pid and v['status']=='publish']
                    self.parents[pid]['price']=min(values,key=float) if values else ''
                if self.side_effect:self.side_effect(target)
                if self.fail_after==self.posts:raise OSError('synthetic lost response after write')
                out=target
            elif variation:
                rows=[v for v in self.children.values() if v['parent_id']==pid and v['status']==q.get('status',['publish'])[0]]
                page=int(q.get('page',['1'])[0]);out=rows[(page-1)*100:page*100]
            elif pid:out=self.parents[pid]
            else:
                rows=[v for v in self.parents.values() if v['status']==q['status'][0]]
                page=int(q.get('page',['1'])[0]);out=rows[(page-1)*100:page*100]
        else:raise AssertionError('Unexpected URL '+path)
        return Response(json.dumps(out).encode())


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=10000.;self.key=b'fixture-only-independent-key-00000000';self.counter=0
        self.bridge=Bridge(Path(self.tmp.name)/'bridge.sqlite3',self.key,[OWNER,CUSTOMER],clock=lambda:self.now)
        self.http=HTTP()
        self.api=Woo(SITE,'fixture-user','fixture-password',allow_network=True,allow_write=True,opener=self.http)
        self.engine=Products(Path(self.tmp.name)/'products',self.bridge,{'demo':SITE},lambda site:self.api,enabled=True,clock=lambda:self.now)
        self.egress=patch('socket.create_connection',side_effect=AssertionError('Real network denied'));self.egress.start();self.addCleanup(self.egress.stop)
    def event(self,text,**changes):
        self.counter+=1
        e={'id':str(self.counter),'channel':'test','account':'shop','peer':'owner','kind':'direct','timestamp':self.now,'text':text};e.update(changes)
        sig=hmac.new(self.key,canonical(e).encode(),hashlib.sha256).hexdigest();return e,sig
    def plan(self,request=None):
        request=request or {'site':'demo','operation':'edit','product_id':10,'fields':{'description':'Reviewed copy'}}
        e,s=self.event('PRODUCT PLAN '+canonical(request));return self.engine.plan(e,s)
    def approve(self,review):
        jid=review['job_id'];e,s=self.event('PRODUCT REVIEW '+jid)
        receipt={k:OWNER[k] for k in ('channel','account','peer')}
        receipt.update(delivered=True,message_id='review-'+jid,binding_digest=fingerprint(review['binding']))
        c=self.engine.challenge(jid,e,s,review_receipt=receipt)
        e,s=self.event(c['confirmation']);self.engine.confirm(jid,e,s)
        return jid
    def execute(self,jid):return self.engine.execute(jid,*self.event('PRODUCT EXECUTE '+jid))
    def reconcile(self,jid):return self.engine.reconcile(jid,*self.event('PRODUCT RECONCILE '+jid))
    def create_request(self,variable=False):
        r={'site':'demo','operation':'create','fields':{'name':'New device','sku':'NEW-DEVICE','type':'simple','regular_price':'25','categories':[{'id':90}],'images':[{'id':80}]}}
        if variable:
            r['fields'].update(type='variable',attributes=[{'name':'Size','options':['Small','Large'],'visible':True,'variation':True}]);r['fields'].pop('regular_price')
            r['variations']=[{'fields':{'sku':'NEW-'+size.upper(),'regular_price':price,'attributes':[{'name':'Size','option':size}]}} for size,price in [('Small','25'),('Large','40')]]
        return r
    def test_edit_preserves_id_stock_media_discount(self):
        old=copy.deepcopy(self.http.parents[10]);j=self.approve(self.plan());r=self.execute(j)
        self.assertEqual(r['state'],'VERIFIED');self.assertFalse(r['public_verified'])
        for k in ('id','sku','stock_quantity','manage_stock','images','sale_price'):self.assertEqual(old[k],self.http.parents[10][k])
        self.assertEqual(self.http.posts,1)
    def test_simple_create_draft_then_separate_publish(self):
        j=self.approve(self.plan(self.create_request()));r=self.execute(j);self.assertEqual(r['state'],'VERIFIED');pid=r['product_id']
        self.assertEqual(self.http.parents[pid]['status'],'draft')
        p=self.plan({'site':'demo','operation':'publish','product_id':pid});j2=self.approve(p);r=self.execute(j2)
        self.assertEqual(r['state'],'VERIFIED');self.assertEqual(self.http.parents[pid]['status'],'publish');self.assertFalse(r['public_verified'])
    def test_variable_create_exact_children(self):
        j=self.approve(self.plan(self.create_request(True)));r=self.execute(j)
        self.assertEqual(r['state'],'VERIFIED');self.assertEqual(self.http.posts,3);self.assertEqual(len(self.http.children),2)
    def test_partial_variation_never_replayed(self):
        self.http.fail_after=2;j=self.approve(self.plan(self.create_request(True)));r=self.execute(j)
        self.assertEqual(r['state'],'NEEDS_REVIEW');self.assertEqual(self.reconcile(j)['state'],'NEEDS_REVIEW')
        self.execute(j);self.assertEqual(self.http.posts,2);self.assertEqual(len(self.http.children),1)
    def test_failure_after_remote_edit_reconciles_readonly(self):
        self.http.fail_after=1;j=self.approve(self.plan());self.assertEqual(self.execute(j)['state'],'NEEDS_REVIEW')
        self.assertEqual(self.reconcile(j)['state'],'VERIFIED');self.execute(j);self.assertEqual(self.http.posts,1)
    def test_failure_after_create_finds_marker(self):
        self.http.fail_after=1;j=self.approve(self.plan(self.create_request()));self.execute(j)
        self.assertEqual(self.reconcile(j)['state'],'VERIFIED');self.assertEqual(self.http.posts,1)
    def test_failure_before_remote_write_still_no_retry(self):
        self.http.fail_before=1;j=self.approve(self.plan());self.execute(j)
        self.assertEqual(self.reconcile(j)['state'],'NEEDS_REVIEW');self.execute(j);self.assertEqual(self.http.posts,1)
    def test_durable_checkpoint_precedes_post(self):
        def check(_):
            j=self.engine.load(jid);self.assertEqual(j['state'],'WRITE_STARTED');self.assertEqual(j['receipt']['steps'][0]['state'],'WRITE_STARTED')
            path=self.engine.home/j['receipt']['backup']['file'];self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),j['receipt']['backup']['sha256'])
        self.http.side_effect=check;jid=self.approve(self.plan());self.assertEqual(self.execute(jid)['state'],'VERIFIED')
    def test_stale_plan_no_write(self):
        j=self.approve(self.plan());self.http.parents[10]['stock_quantity']=3
        with self.assertRaises(ValueError):self.execute(j)
        self.assertEqual(self.engine.load(j)['state'],'STALE');self.assertEqual(self.http.posts,0)
    def test_expired_plan(self):
        j=self.approve(self.plan());self.now+=1801
        with self.assertRaises(PermissionError):self.execute(j)
        self.assertEqual(self.http.posts,0)
    def test_expired_challenge(self):
        r=self.plan();e,s=self.event('PRODUCT REVIEW '+r['job_id']);receipt=dict(OWNER,delivered=True,message_id='m',binding_digest=fingerprint(r['binding']))
        c=self.engine.challenge(r['job_id'],e,s,review_receipt=receipt);self.now+=301
        with self.assertRaises(PermissionError):self.engine.confirm(r['job_id'],*self.event(c['confirmation']))
    def test_revoke_blocks_execution(self):
        j=self.approve(self.plan());self.engine.revoke(j,*self.event('PRODUCT REVOKE '+j));self.execute(j);self.assertEqual(self.http.posts,0)
    def test_bridge_revocation_blocks_execution(self):
        j=self.approve(self.plan());c=self.engine.load(j)['challenge'];self.bridge.revoke(*self.event('REVOKE '+c),c)
        with self.assertRaises(PermissionError):self.execute(j)
    def test_forged_owner_customer_group_quoted_rejected(self):
        text='PRODUCT PLAN '+canonical(self.create_request())
        for changes in ({'peer':'buyer'},{'kind':'group'},{'account':'other'},{'peer':'stranger'}):
            with self.assertRaises(PermissionError):self.engine.plan(*self.event(text,**changes))
        e,s=self.event(text)
        with self.assertRaises(PermissionError):self.engine.plan(e,'0'*64)
        with self.assertRaises(ValueError):dispatch(self.engine,dict(zip(('event','signature'),self.event('Quoted: '+text))))
        self.assertEqual(self.http.calls,[])
    def test_cross_site_and_account(self):
        r=self.create_request();r['site']='absent'
        with self.assertRaises(KeyError):self.plan(r)
        j=self.approve(self.plan());site=copy.deepcopy(SITE);site['origin']='https://other.example';self.engine.sites['demo']=site
        with self.assertRaises(PermissionError):self.execute(j)
        self.assertEqual(self.http.posts,0)
    def test_duplicate_trash_name_and_variation_sku(self):
        self.http.parents[20]=product(20,name='New device',sku='OLD',status='trash')
        with self.assertRaises(ValueError):self.plan(self.create_request())
        self.http.parents[20].update(name='Unrelated',type='variable',variations=[21])
        self.http.children[21]=product(21,parent_id=20,status='publish',sku='NEW-DEVICE')
        with self.assertRaises(ValueError):self.plan(self.create_request())
        self.assertEqual(self.http.posts,0)
    def test_raw_approval_boolean_is_not_admission(self):
        with self.assertRaises(PermissionError):dispatch(self.engine,{'owner_verified':True,'text':'publish'})
    def test_plan_event_replay_and_collision(self):
        e,s=self.event('PRODUCT PLAN '+canonical(self.create_request()));a=self.engine.plan(e,s);b=self.engine.plan(e,s)
        self.assertEqual(a['job_id'],b['job_id']);e['text']='PRODUCT PLAN '+canonical({'site':'demo','operation':'publish','product_id':10});s=hmac.new(self.key,canonical(e).encode(),hashlib.sha256).hexdigest()
        with self.assertRaises(PermissionError):self.engine.plan(e,s)
    def test_duplicate_active_site_job_blocked(self):
        self.plan()
        with self.assertRaises(ValueError):self.plan(self.create_request())
    def test_exact_review_receipt_required(self):
        r=self.plan()
        with self.assertRaises(PermissionError):self.engine.challenge(r['job_id'],*self.event('PRODUCT REVIEW '+r['job_id']),review_receipt={'delivered':True})
    def test_wrong_saved_write_protected_field_detected(self):
        self.http.side_effect=lambda target:target.update(stock_quantity=999)
        j=self.approve(self.plan());self.assertEqual(self.execute(j)['state'],'NEEDS_REVIEW');self.assertEqual(self.reconcile(j)['state'],'NEEDS_REVIEW')
    def test_verified_drift_not_cached_success(self):
        j=self.approve(self.plan());self.execute(j);self.http.parents[10]['description']='Unexpected'
        self.assertEqual(self.reconcile(j)['state'],'NEEDS_REVIEW');self.assertEqual(self.http.posts,1)
    def test_media_and_category_identity_drift(self):
        r=self.plan(self.create_request());j=self.approve(r);self.http.media['slug']='different'
        with self.assertRaises(ValueError):self.execute(j)
        self.assertEqual(self.http.posts,0)
    def test_attachment_url_forbidden(self):
        r=self.create_request();r['fields']['images']=[{'src':'http://127.0.0.1/private'}]
        with self.assertRaises(ValueError):self.plan(r)
    def test_stock_status_sale_and_metadata_protected(self):
        for bad in ({'stock_quantity':5},{'status':'publish'},{'sale_price':'3'},{'meta_data':[{'key':'_secret','value':'x'}]}):
            with self.assertRaises(ValueError):self.plan({'site':'demo','operation':'edit','product_id':10,'fields':bad})
    def test_sale_guard(self):
        self.http.parents[10].update(sale_price='8',price='8')
        with self.assertRaises(ValueError):self.plan({'site':'demo','operation':'edit','product_id':10,'fields':{'regular_price':'12'}})
    def test_allowed_metadata_merge_preserves_other_keys(self):
        self.http.parents[10]['meta_data']=[{'id':1,'key':'private_plugin','value':'retained'}]
        j=self.approve(self.plan({'site':'demo','operation':'edit','product_id':10,'fields':{'meta_data':[{'key':'display_note','value':'Reviewed'}]}}))
        self.assertEqual(self.execute(j)['state'],'VERIFIED');self.assertEqual(len(self.http.parents[10]['meta_data']),2)
    def test_defaults_network_writes_disabled(self):
        api=Woo(SITE,'u','p',opener=self.http)
        with self.assertRaises(RuntimeError):api.identity()
        api.wp.allow_network=True
        with self.assertRaises(RuntimeError):api.mutate(10,{'description':'x'})
        self.engine.enabled=False;j=self.approve(self.plan())
        with self.assertRaises(PermissionError):self.execute(j)
        self.assertEqual(self.http.posts,0)
    def test_wrong_api_identity(self):
        self.http.user=9
        with self.assertRaises(PermissionError):self.plan()
    def test_backup_failure_no_mutation(self):
        j=self.approve(self.plan())
        with patch.object(self.engine,'backup',side_effect=OSError):
            with self.assertRaises(OSError):self.execute(j)
        self.assertEqual(self.http.posts,0)
    def test_publish_cannot_edit_or_create(self):
        with self.assertRaises(ValueError):self.plan({'site':'demo','operation':'publish','product_id':10,'fields':{'description':'Changed'}})
        r=self.create_request();r['fields']['status']='publish'
        with self.assertRaises(ValueError):self.plan(r)
    def test_cli_dispatch_full_lifecycle(self):
        e,s=self.event('PRODUCT PLAN '+canonical(self.create_request()));r=dispatch(self.engine,{'event':e,'signature':s});j=self.approve(r)
        e,s=self.event('PRODUCT EXECUTE '+j);self.assertEqual(dispatch(self.engine,{'event':e,'signature':s})['state'],'VERIFIED')
    def test_private_state_required(self):
        path=Path(self.tmp.name)/'public';path.mkdir(mode=0o755)
        with self.assertRaises(PermissionError):Products(path,self.bridge,{'demo':SITE},lambda site:self.api)
    def test_all_status_inventory_queries(self):
        self.plan();queried={q['status'][0] for method,path,q in self.http.calls if path==ROOT}
        self.assertEqual(queried,set(STATUSES))
    def test_wrong_variation_parent_no_write(self):
        with self.assertRaises(ValueError):self.plan({'site':'demo','operation':'edit','product_id':10,'fields':{'description':'x'},'variations':[{'id':200,'fields':{'regular_price':'2'}}]})
    def variable_fixture(self):
        self.http.parents[10].update(type='variable',regular_price='',price='10',variations=[11,12],attributes=[{'name':'Size','options':['Small','Large'],'variation':True,'visible':True}])
        self.http.children[11]=product(11,parent_id=10,status='publish',sku='EXISTING-S',attributes=[{'name':'Size','option':'Small'}])
        self.http.children[12]=product(12,parent_id=10,status='publish',sku='EXISTING-L',regular_price='20',price='20',attributes=[{'name':'Size','option':'Large'}])
        return {'site':'demo','operation':'edit','product_id':10,'fields':{'description':'Exact options'},'variations':[{'id':11,'fields':{'regular_price':'15'}}]}
    def test_existing_variation_price_preserves_sibling_and_ids(self):
        r=self.variable_fixture();old=copy.deepcopy(self.http.children[12]);j=self.approve(self.plan(r))
        self.assertEqual(self.execute(j)['state'],'VERIFIED');self.assertEqual(self.http.children[12],old)
        self.assertEqual(self.http.parents[10]['variations'],[11,12]);self.assertEqual(self.http.parents[10]['price'],'15')
    def test_existing_variation_partial_edit_no_replay(self):
        r=self.variable_fixture();self.http.fail_before=2;j=self.approve(self.plan(r));self.assertEqual(self.execute(j)['state'],'NEEDS_REVIEW')
        self.assertEqual(self.reconcile(j)['state'],'NEEDS_REVIEW');self.execute(j);self.assertEqual(self.http.posts,2)
    def test_sibling_drift_stops_next_step(self):
        r=self.variable_fixture();self.http.side_effect=lambda target:self.http.children[12].update(stock_quantity=0)
        j=self.approve(self.plan(r));self.assertEqual(self.execute(j)['state'],'NEEDS_REVIEW');self.assertEqual(self.http.posts,1)
    def test_status_customer_cannot_read_owner_receipts(self):
        j=self.plan()['job_id']
        with self.assertRaises(PermissionError):self.engine.status(j,*self.event('PRODUCT STATUS '+j,peer='buyer'))
    def test_revocation_after_partial_does_not_release_uncertain_job(self):
        self.http.fail_after=1;j=self.approve(self.plan());self.execute(j);self.engine.revoke(j,*self.event('PRODUCT REVOKE '+j))
        self.assertEqual(self.engine.load(j)['state'],'NEEDS_REVIEW')
        with self.assertRaises(ValueError):self.plan(self.create_request())
        self.assertEqual(self.reconcile(j)['state'],'VERIFIED');self.assertEqual(self.http.posts,1)
    def test_created_unrequested_media_detected(self):
        r=self.create_request();r['fields'].pop('images');self.http.side_effect=lambda target:target.update(images=[{'id':80}])
        j=self.approve(self.plan(r));self.assertEqual(self.execute(j)['state'],'NEEDS_REVIEW');self.assertEqual(self.reconcile(j)['state'],'NEEDS_REVIEW')
    def test_plan_tamper_and_missing_approval_fail_closed(self):
        j=self.approve(self.plan())
        with self.engine.db() as db:db.execute('UPDATE product_jobs SET digest=? WHERE id=?',('0'*64,j))
        with self.assertRaises(PermissionError):self.execute(j)
        self.assertEqual(self.http.posts,0)
    def test_revocation_commits_while_remote_step_inflight(self):
        import threading
        started=threading.Event();release=threading.Event();out=[]
        def pause(target):
            started.set()
            if not release.wait(5):raise RuntimeError('test release timeout')
        self.http.side_effect=pause
        jid=self.approve(self.plan(self.create_request(True)))
        args=self.event('PRODUCT EXECUTE '+jid)
        worker=threading.Thread(target=lambda:out.append(self.engine.execute(jid,*args)))
        worker.start()
        try:
            self.assertTrue(started.wait(5))
            result=self.engine.revoke(jid,*self.event('PRODUCT REVOKE '+jid))
            self.assertIsNotNone(result['revocation'])
            self.assertTrue(worker.is_alive())
        finally:release.set();worker.join(5)
        self.assertFalse(worker.is_alive());self.assertEqual(out[0]['state'],'NEEDS_REVIEW')
        job=self.engine.load(jid)
        self.assertEqual(self.http.posts,1);self.assertEqual(len(self.http.children),0)
        self.assertEqual(job['receipt']['steps'][0]['remote_id'],100)
        self.assertEqual(job['receipt']['product_id'],100)
        self.assertIsNotNone(self.engine.revocation(jid))
        self.assertEqual(self.reconcile(jid)['state'],'NEEDS_REVIEW')
        with self.assertRaises(ValueError):self.plan()
    def test_revocation_during_backup_prevents_all_mutations(self):
        import threading
        started=threading.Event();release=threading.Event();out=[]
        original=self.engine.backup
        def backup(job):
            result=original(job);started.set()
            if not release.wait(5):raise RuntimeError('test release timeout')
            return result
        self.engine.backup=backup;jid=self.approve(self.plan())
        args=self.event('PRODUCT EXECUTE '+jid)
        def run():
            try:out.append(self.engine.execute(jid,*args))
            except PermissionError:out.append('revoked')
        worker=threading.Thread(target=run);worker.start()
        try:
            self.assertTrue(started.wait(5));self.engine.revoke(jid,*self.event('PRODUCT REVOKE '+jid))
            self.assertTrue(worker.is_alive())
        finally:release.set();worker.join(5)
        self.assertEqual(out,['revoked']);self.assertEqual(self.http.posts,0)
        self.assertEqual(self.engine.load(jid)['state'],'REVOKED')
    def test_stale_worker_save_cannot_erase_revocation(self):
        jid=self.approve(self.plan());stale=self.engine.load(jid)
        self.engine.revoke(jid,*self.event('PRODUCT REVOKE '+jid))
        self.engine.save(stale,'APPROVED')
        self.assertEqual(self.engine.load(jid)['state'],'REVOKED')
        self.assertIsNotNone(self.engine.revocation(jid));self.execute(jid);self.assertEqual(self.http.posts,0)
    def restore(self,jid):
        return self.plan({'site':'demo','operation':'restore','source_job':jid})
    def test_restore_requires_new_exact_approval_and_preserves_fields(self):
        before=copy.deepcopy(self.http.parents[10]);source=self.approve(self.plan());self.execute(source)
        review=self.restore(source);jid=review['job_id']
        self.assertEqual(review['plan']['operation'],'restore')
        self.assertEqual(review['plan']['recovery']['source_job'],source)
        self.execute(jid);self.assertEqual(self.http.posts,1)
        self.approve(review);self.assertEqual(self.execute(jid)['state'],'VERIFIED')
        self.assertEqual(self.http.parents[10],before);self.assertEqual(self.http.posts,2)
    def test_restore_existing_variation_price(self):
        request=self.variable_fixture();source=self.approve(self.plan(request));self.execute(source)
        jid=self.approve(self.restore(source));self.assertEqual(self.execute(jid)['state'],'VERIFIED')
        self.assertEqual(self.http.children[11]['price'],'10');self.assertEqual(self.http.children[12]['price'],'20')
    def test_restore_refuses_current_after_drift(self):
        source=self.approve(self.plan());self.execute(source);self.http.parents[10]['stock_quantity']=99
        with self.assertRaises(ValueError):self.restore(source)
        self.assertEqual(self.http.posts,1)
    def test_restore_refuses_drift_after_review(self):
        source=self.approve(self.plan());self.execute(source);jid=self.approve(self.restore(source))
        self.http.parents[10]['description']='Newer copy'
        with self.assertRaises(ValueError):self.execute(jid)
        self.assertEqual(self.http.posts,1)
    def test_restore_never_deletes_created_objects(self):
        source=self.approve(self.plan(self.create_request()));self.execute(source)
        with self.assertRaises(ValueError):self.restore(source)
        self.assertEqual(len(self.http.parents),2);self.assertEqual(self.http.posts,1)
    def test_restore_snapshot_tampering_rejected(self):
        source=self.approve(self.plan());self.execute(source)
        (self.engine.home/(source+'.before.json')).write_text('{}')
        with self.assertRaises(ValueError):self.restore(source)
        self.assertEqual(self.http.posts,1)
    def test_restore_cannot_delete_new_metadata_key(self):
        request={'site':'demo','operation':'edit','product_id':10,'fields':{'meta_data':[{'key':'display_note','value':'New'}]}}
        source=self.approve(self.plan(request));self.execute(source)
        with self.assertRaises(ValueError):self.restore(source)
    def test_restore_lost_response_reconciles_without_retry(self):
        source=self.approve(self.plan());self.execute(source);jid=self.approve(self.restore(source));self.http.fail_after=2
        self.assertEqual(self.execute(jid)['state'],'NEEDS_REVIEW');self.assertEqual(self.reconcile(jid)['state'],'VERIFIED')
        self.execute(jid);self.assertEqual(self.http.posts,2)
    def test_nonlisted_draft_future_trash_children_in_duplicate_inventory(self):
        self.http.parents[10].update(type='variable',variations=[])
        for vid,status in ((11,'draft'),(12,'future'),(13,'trash')):
            self.http.children[vid]=product(vid,parent_id=10,status=status,sku='CHILD-'+status)
        catalog=self.api.catalog();self.assertEqual(len(catalog[0]['variations']),3)
        r=self.create_request();r['fields']['sku']='CHILD-future'
        with self.assertRaises(ValueError):self.plan(r)
    def test_wrong_api_factory_site_rejected(self):
        self.api.site=dict(SITE,id='wrong')
        with self.assertRaises(PermissionError):self.plan()
        self.assertEqual(self.http.calls,[])
    def test_same_owner_route_not_authorized_for_other_site(self):
        site=dict(SITE,id='other',owners=[dict(OWNER,account='other-account')]);self.engine.sites['other']=site
        r=self.create_request();r['site']='other'
        with self.assertRaises(PermissionError):self.plan(r)
        self.assertEqual(self.http.calls,[])
    def test_pending_plan_expiry_prevents_new_challenge(self):
        r=self.plan();self.now+=1801
        with self.assertRaises(PermissionError):self.engine.challenge(r['job_id'],*self.event('PRODUCT REVIEW '+r['job_id']),review_receipt={})
    def test_concurrent_engine_cannot_execute_same_job(self):
        j=self.approve(self.plan())
        with self.engine.lock():
            with self.assertRaises(BlockingIOError):self.execute(j)
        self.assertEqual(self.http.posts,0)
    def test_unsupported_inventory_status_fails_closed(self):
        original=self.http.open
        def denied(req,timeout):
            if 'status=trash' in req.full_url:raise OSError('unsupported trash inventory')
            return original(req,timeout)
        self.http.open=denied
        with self.assertRaises(RuntimeError):self.plan()
        self.assertEqual(self.http.posts,0)
    def test_no_redirect_transport(self):
        from toolkit.wordpress import _NoRedirect
        self.assertIsNone(_NoRedirect().redirect_request(None,None,302,'',{},'https://evil.example'))
        for origin in ('http://shop.example','https://user:password@shop.example','https://shop.example/path'):
            with self.assertRaises(ValueError):Woo(dict(SITE,origin=origin),'u','p',opener=self.http)


if __name__=='__main__':unittest.main()
