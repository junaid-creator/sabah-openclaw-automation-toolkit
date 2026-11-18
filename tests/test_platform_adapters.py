import contextlib,copy,io,json,socket,subprocess,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from toolkit import wordpress,blog_publication as blog,blog_gates,tiktok_publisher as tt,content_ledger

class PlatformTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
  def deny(*a,**k):raise AssertionError('Network/process execution forbidden')
  self.stack.enter_context(patch.object(socket,'socket',deny));self.stack.enter_context(patch.object(subprocess,'Popen',deny))
  self.now=datetime(2026,1,15,17,0,tzinfo=timezone.utc)
 def test_wp_network_default_closed(self):
  w=wordpress.WP('https://example.com','fixture','fixture')
  with self.assertRaises(RuntimeError):w.request('/wp-json/wp/v2/posts')
 def test_wp_write_default_closed(self):
  w=wordpress.WP('https://example.com','fixture','fixture',allow_network=True)
  with self.assertRaises(RuntimeError):w.request('/wp-json/wp/v2/posts',{'status':'publish'})
 def test_wp_mocked_read(self):
  class Opener:
   def open(self,request,timeout):self.request=request;return io.BytesIO(b'{"id":7}')
  o=Opener();w=wordpress.WP('https://example.com','fixture','fixture',allow_network=True,opener=o)
  self.assertEqual(w.request('/wp-json/wp/v2/users/me')['id'],7);self.assertEqual(o.request.method,'GET')
 def test_wp_invalid_origin_and_path(self):
  with self.assertRaises(ValueError):wordpress.WP('https://user:fixture@example.com','fixture','fixture')
  w=wordpress.WP('https://example.com','fixture','fixture',allow_network=True)
  with self.assertRaises(ValueError):w.request('//another.invalid/path')
 def setup_blog(self,posted=True,timeout=False):
  post=dict(id=101,title={'raw':'Fixture'},slug='fixture',content={'raw':'Fixture body'},excerpt={'raw':'Fixture'},categories=[1],tags=[],featured_media=2,status='draft',link='https://example.com/fixture/')
  class WP:
   writes=0
   def request(self,path,data=None):
    if data is not None:
     self.writes+=1
     if posted:post['status']='publish'
     if timeout:raise TimeoutError()
    if 'users/me' in path:return {'id':7}
    return copy.deepcopy(post)
   def posts(self):return []
  wp=WP();entry={k:'' for k in content_ledger.REQUIRED};entry.update(date='2026-01-15',created_at='2026-01-15T17:00:00Z',title='Fixture',slug='fixture',primary_keyword='fixture',secondary_keywords=[])
  plan=dict(run_id='fixture-run',post_id=101,run_type='production',post_hash=blog.fingerprint(post),ledger_entry=entry)
  approval=dict(owner_verified=True,explicit_activation=True,explicit_publish=True,owner='fixture-owner',account='fixture-account',source_message_id='fixture-message',post_id=101,run_id='fixture-run',local_date='2026-01-15',post_hash=plan['post_hash'])
  evidence={k:dict(passed=True,artifact='fixture-proof',verified_at=self.now.isoformat()) for k in blog.GATES};evidence.update(post_hash=plan['post_hash'],post_id=101)
  return wp,plan,approval,evidence
 def publish(self,wp,plan,approval,evidence,**kw):
  return blog.publish_existing(wp,plan,approval,evidence,lambda p:{'http':200,'content_verified':True},expected_owner='fixture-owner',expected_account='fixture-account',expected_wp_user=7,root=self.root/'runs',ledger_path=self.root/'ledger.jsonl',now=self.now,**kw)
 def test_blog_explicit_optin_required(self):
  args=self.setup_blog()
  with self.assertRaises(RuntimeError):self.publish(*args)
  self.assertEqual(args[0].writes,0)
 def test_blog_publish_and_replay(self):
  args=self.setup_blog();first=self.publish(*args,allow_publish=True);second=self.publish(*args,allow_publish=True)
  self.assertEqual(first,second);self.assertEqual(args[0].writes,1)
 def test_blog_timeout_reconciles_remote_success(self):
  args=self.setup_blog(timeout=True);self.assertEqual(self.publish(*args,allow_publish=True)['status'],'publish');self.assertEqual(args[0].writes,1)
 def test_blog_unknown_never_reposts(self):
  args=self.setup_blog(posted=False,timeout=True)
  for _ in range(2):
   with self.assertRaises(RuntimeError):self.publish(*args,allow_publish=True)
  self.assertEqual(args[0].writes,1)
 def test_blog_stale_gate_blocks(self):
  args=list(self.setup_blog());args[3]['content']['verified_at']=(self.now-timedelta(hours=1)).isoformat()
  with self.assertRaises(RuntimeError):self.publish(*args,allow_publish=True)
  self.assertEqual(args[0].writes,0)
 def test_blog_changed_approval_blocks(self):
  args=list(self.setup_blog());args[2]['post_hash']='changed'
  with self.assertRaises(RuntimeError):self.publish(*args,allow_publish=True)
  self.assertEqual(args[0].writes,0)
 def test_saved_robots(self):
  s=dict(post_type='post',status='draft',blog_public='1',password_protected=False,rankmath_active=True,post_robots=['index','follow'])
  blog_gates.snapshot_robots(s);s['post_robots']=['noindex']
  with self.assertRaises(blog_gates.Blocked):blog_gates.snapshot_robots(s)
 def test_saved_template_configurable(self):
  s=dict(post_type='post',status='draft',elementor_active=True,theme_builder_active=True,templates=[dict(id=321,kind='single-post',conditions=['include/singular/post'])])
  self.assertEqual(blog_gates.snapshot_template(s,321)['template_id'],321)
  with self.assertRaises(blog_gates.Blocked):blog_gates.snapshot_template(s,322)
 def client(self,*,live=False,approve=False,scope='video.publish,video.list'):
  calls=[];cfg=dict(client_id='10001',client_secret='fixture-only',expected_open_id='fixture-creator',approved_media_hosts=['example.com'])
  def transport(method,endpoint,**kw):
   calls.append(endpoint)
   if endpoint=='tt_user/token_info/get/':return dict(app_id='10001',creator_id='fixture-creator',scope=scope)
   if endpoint=='business/property/list/':return {'url_property_info_list':[dict(property_status=1,url='https://example.com',property_type=1)]}
   if endpoint=='business/video/settings/':return {'privacy_level_options':['PUBLIC_TO_EVERYONE']}
   if endpoint=='business/photo/publish/':return {'share_id':'fixture-task'}
   if endpoint=='business/video/list/':return {'videos':[dict(item_id='12345',share_url='https://www.tiktok.com/@example/photo/12345')]}
   raise AssertionError(endpoint)
  c=tt.Client(cfg,lambda **kw:dict(access_token='fixture-token',open_id='fixture-creator'),transport=transport,live_enabled=live,authorize=lambda payload:approve)
  return c,calls
 def test_tiktok_preflight_and_submission_guard(self):
  c,calls=self.client();payload=c.prepare('https://example.com/photo.jpg','Fixture caption')
  with self.assertRaises(tt.Blocked):c.submit(payload)
  self.assertNotIn('business/photo/publish/',calls)
 def test_tiktok_mocked_submit(self):
  c,calls=self.client(live=True,approve=True);p=c.prepare('https://example.com/photo.jpg','Fixture');self.assertEqual(c.submit(p),'fixture-task');self.assertEqual(calls.count('business/photo/publish/'),1)
 def test_tiktok_missing_list_permission_blocks(self):
  c,_=self.client(scope='video.publish')
  with self.assertRaises(tt.Blocked):c.prepare('https://example.com/photo.jpg','Fixture')
 def test_tiktok_url_and_owned_post(self):
  c,_=self.client()
  with self.assertRaises(tt.Blocked):c.verified_url('https://unapproved.invalid/photo.jpg')
  self.assertTrue(tt.verify_public_post(c,'12345').endswith('/12345'))
 def test_tiktok_invalid_photo(self):
  with self.assertRaises(tt.Blocked):tt.validate_photo(b'invalid')
