import hashlib,io,json,socket,subprocess,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from PIL import Image
from toolkit.blog_controller import Controller
from toolkit.report_outbox import Outbox
from toolkit.reliability import Run
from toolkit.draft_primitives import create_once
from toolkit.blog_assets import read_upload_image

class ControllerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.c=Controller('blog-daily-2026-01-15',self.root,account='fixture',recipient='fixture')
  def deny(*a,**k):raise AssertionError('External operations forbidden')
  for target in ['socket.socket','subprocess.Popen']:
   p=patch(target,deny);p.start();self.addCleanup(p.stop)
 def prerequisites(self):
  for x in ('inventory','research','article'):self.c.step(x,lambda state:{'fixture':True})
 def test_prerequisite_and_verified_replay(self):
  with self.assertRaises(RuntimeError):self.c.begin('draft')
  calls=[];self.c.step('inventory',lambda d:calls.append(1) or {'fixture':True});self.c.step('inventory',lambda d:calls.append(2));self.assertEqual(calls,[1])
 def test_interrupted_step_never_recalled(self):
  calls=[]
  def bad(d):calls.append(1);raise RuntimeError('SENSITIVE_FIXTURE')
  for _ in range(2):
   with self.assertRaises(RuntimeError):self.c.step('inventory',bad)
  self.assertEqual(calls,[1]);self.assertNotIn('SENSITIVE_FIXTURE',(self.root/'owner-outbox.json').read_text())
 def test_queued_images_not_verified(self):
  self.prerequisites()
  with self.assertRaises(ValueError):self.c.step('images',lambda d:{'status':'queued'})
  self.assertEqual(self.c.load()['stages']['images']['state'],'blocked')
 def test_task_identity_and_timeout_no_resubmit(self):
  self.prerequisites();self.c.begin('images');now=datetime(2026,1,15,tzinfo=timezone.utc);self.c.record_image_task('fixture-task',now)
  with self.assertRaises(RuntimeError):self.c.record_image_task('different-task',now)
  self.assertFalse(self.c.image_task_status(now+timedelta(hours=1))['resubmit'])
 def image(self,color,index):
  p=self.root/'assets'/self.c.rid/(str(index)+'.webp');p.parent.mkdir(parents=True,exist_ok=True);Image.new('RGB',(10,10),color).save(p,'WEBP',lossless=True)
  return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'alt':'Fixture','title':'Fixture','caption':'Fixture'}
 def test_recover_three_bound_images(self):
  self.prerequisites();self.c.begin('images');self.c.record_image_task('fixture-task');images=[self.image(c,i) for i,c in enumerate(['red','green','blue'])]
  self.c.recover_image_assets({'task_id':'fixture-task','status':'completed','images':images});self.c.verify_plan_images({'images':images})
  Path(images[0]['path']).write_bytes(b'changed')
  with self.assertRaises(ValueError):self.c.verify_plan_images({'images':images})
 def test_image_root_escape(self):
  image=self.image('red',1)
  with self.assertRaises(ValueError):read_upload_image(image,asset_root=self.root/'different')
 def test_create_once_unknown_latches(self):
  calls=[]
  def create():calls.append(1);raise TimeoutError()
  with Run('create',{},self.root/'run') as run:
   for _ in range(2):
    with self.assertRaises(RuntimeError):create_once(run,'post',create,lambda n:{'id':n})
  self.assertEqual(calls,[1])
 def test_create_once_known_reads_only(self):
  calls=[]
  with Run('create',{},self.root/'run') as run:
   for _ in range(2):self.assertEqual(create_once(run,'post',lambda:calls.append(1) or {'id':12},lambda n:{'id':n}),{'id':12})
  self.assertEqual(calls,[1])
 def box(self):
  b=Outbox(self.root/'out.json',account='fixture',recipient='fixture');p={k:'' for k in ('title','post_id','topic','keyword','url','sheets','blocker')};p['status']='Draft';b.prepare('r',p);return b
 def test_outbox_unknown_cannot_reclaim(self):
  b=self.box();b.claim('r');b.receipt('r',account='fixture',recipient='fixture')
  with self.assertRaises(RuntimeError):b.claim('r')
 def test_outbox_wrong_identity_rejected(self):
  b=self.box();b.claim('r')
  with self.assertRaises(ValueError):b.receipt('r','fake',account='other',recipient='fixture')
