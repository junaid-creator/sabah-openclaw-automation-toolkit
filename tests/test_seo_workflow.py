import hashlib,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from toolkit.seo_workflow import SEO
from toolkit.blog_controller import Controller
from toolkit.trusted_bridge import fingerprint

class CMS:
    base='https://cms.example'
    def __init__(self):self.media={};self.post=None;self.creates=0;self.lose=False
    def posts(self):return []
    def request(self,path,data=None,binary=None,filename=None):
        if path.startswith('/wp-json/wp/v2/users/me'):return {'id':7}
        if binary is not None:
            mid=len(self.media)+1;self.creates+=1
            self.media[mid]={'id':mid,'media_type':'image','mime_type':'image/webp','source_url':self.base+'/'+filename}
            if self.lose:raise TimeoutError()
            return dict(self.media[mid])
        if path.startswith('/wp-json/wp/v2/media/'):
            mid=int(path.split('/')[-1].split('?')[0])
            if data:self.media[mid].update(data)
            return dict(self.media[mid])
        if path=='/wp-json/wp/v2/posts' and data:
            self.creates+=1;self.post=dict(data,id=10,link=self.base+'/draft');return dict(self.post)
        if path.startswith('/wp-json/wp/v2/posts/10'):return dict(self.post)
        raise AssertionError(path)

class SEOTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.c=Controller('blog-daily-2026-01-01',self.root,account='owner-account',recipient='owner')
        self.cms=CMS();self.s=SEO(self.c,self.cms,expected_wp_user=7,enabled=True);self.starts=0
        self.images=[]
        d=self.c.asset_root/self.c.rid;d.mkdir(parents=True)
        for i,color in enumerate(('red','green','blue')):
            p=d/(str(i)+'.webp');Image.new('RGB',(12,12),color).save(p,'WEBP',lossless=True)
            self.images.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'alt':'Example '+color,'title':'Example '+color,'caption':'Synthetic fixture'})
        self.article={'title':'Example guide','content':'<p>Original fixture guide.</p>','excerpt':'Summary','slug':'example-guide','keyword':'example'}
    def start(self,a):self.starts+=1;return 'image-task'
    def prepare(self,pending=False):
        return self.s.prepare(research=lambda state:{'sources':['https://example.com/reference']},article=lambda state:self.article,start_images=self.start,read_images=lambda task:({'status':'pending'} if pending else {'status':'completed','task_id':task,'images':self.images}))
    def test_integrated_draft_and_owner_receipt(self):
        self.prepare();self.prepare();self.assertEqual(self.starts,1)
        validate=lambda result,plan:{'passed':True,'plan_sha256':fingerprint(plan)}
        result=self.s.draft(validate=validate);self.assertEqual(result['status'],'draft');self.assertEqual(self.cms.creates,4)
        self.s.draft(validate=validate);self.assertEqual(self.cms.creates,4)
        calls=[]
        def sender(a,r,p):calls.append(p);return {'delivered':True,'account':a,'recipient':r,'message_id':'receipt-1'}
        self.s.deliver(sender=sender,enabled=True);self.s.deliver(sender=sender,enabled=True)
        self.assertEqual(len(calls),1);self.assertEqual(self.c.load()['stages']['report']['state'],'verified')
    def test_three_tab_tracker_before_owner_report(self):
        import test_workflow_tracker as tracker_fixture
        fixture=tracker_fixture.TrackerTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.prepare()
        for _ in range(2):
            self.s.draft(validate=lambda result,plan:{'passed':True,'plan_sha256':fingerprint(plan)},tracker=fixture.t,tracker_tabs={'draft_tab':'Drafts','topic_tab':'Topics','run_tab':'Runs'})
        self.assertEqual(len(fixture.calls),3)
        rows=json.loads((self.root/'owner-outbox.json').read_text())
        self.assertEqual(rows[self.c.rid]['payload']['sheets'],'Three tracker tabs VERIFIED')

    def test_pending_images_resume_same_task(self):
        self.assertEqual(self.prepare(True)['state'],'WAITING_IMAGES');self.prepare();self.assertEqual(self.starts,1)
    def test_unknown_upload_no_repeat(self):
        self.prepare();self.cms.lose=True
        for _ in range(2):
            with self.assertRaises(RuntimeError):self.s.draft(validate=lambda *a:{})
        self.assertEqual(self.cms.creates,1)
    def test_unbound_validator_rejected(self):
        self.prepare()
        with self.assertRaises(ValueError):self.s.draft(validate=lambda *a:{'passed':True})
    def test_changed_images_rejected(self):
        self.prepare();Path(self.images[0]['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.s.draft(validate=lambda *a:{})
        self.assertEqual(self.cms.creates,0)
