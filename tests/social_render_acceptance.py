"""Actual six-template rendering through draft/review/approval dispatch.

Synthetic local assets; fake media hosting and publication transports explicitly.
"""
import argparse,hashlib,hmac,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from toolkit.social_review import Controller,LocalRenderer
from toolkit.trusted_bridge import Bridge,canonical,fingerprint
from toolkit.approval_ledger import Ledger
p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--chromium');a=p.parse_args()
cfg=json.loads(Path(a.config).read_text());root=Path(a.output).absolute();root.mkdir(mode=0o700,parents=True,exist_ok=False)
route={'channel':'fixture','account':'owner','peer':'owner','role':'owner'};key=b'synthetic-social-acceptance-key-000000';now=1000
bridge=Bridge(root/'bridge.sqlite',key,[route],clock=lambda:now);ledger=Ledger(root/'publication.sqlite');sent=[];posts=[]
def event(i,text):
 e={k:route[k] for k in ('channel','account','peer')};e.update(id=i,kind='direct',timestamp=now,text=text)
 return e,hmac.new(key,canonical(e).encode(),hashlib.sha256).hexdigest()
def sender(owner,binding):
 sent.append(binding);return dict(owner,delivered=True,message_id='fixture-'+binding['job_id'],binding_digest=fingerprint(binding))
def publish(job,binding,store):
 result={}
 for platform in binding['targets']:
  posts.append((job,platform));store.reserve(job,platform,1)
  url='https://fixture.example/'+platform+'/'+job
  store.update(job,platform,'PUBLISHED',remote_id='synthetic-'+job,permalink=url)
  result[platform]={'status':'VERIFIED','url':url}
 return result
(root/'renders').mkdir(mode=0o700)
renderer=LocalRenderer(brand=cfg['brand'],fonts=cfg['fonts'],atlas=cfg['atlas'],output_root=root/'renders',chromium=a.chromium,host=lambda path,sha,key:'https://fixture.example/media/'+key+'.jpg')
controller=Controller(root,bridge=bridge,ledger=ledger,renderer=renderer,sender=sender);results=[]
for template in range(1,7):
 campaign={'template':template,'content':cfg['content'],'targets':['facebook','instagram','tiktok'],'captions':{p:'Synthetic acceptance only' for p in ('facebook','instagram','tiktok')}}
 state=controller.create(*event('create-'+str(template),'Draft fixture'),campaign);job=state['job_id']
 assert controller.create(*event('create-'+str(template),'Draft fixture'),campaign)==state
 controller.review(job);challenge=controller.challenge(job,*event('challenge-'+str(template),'Review fixture'))
 controller.approve(job,*event('confirm-'+str(template),challenge['confirmation']))
 result=controller.dispatch(job,publisher=publish,enabled=True)
 assert controller.dispatch(job,publisher=publish,enabled=True)==result
 results.append({'template':template,'actual_render':True,'artifact_sha256':state['artifact']['sha256'],'simulated_platforms':3,'duplicate_submissions':0})
assert len(sent)==6 and len(posts)==18
report={'cases':results,'rendered':6,'simulated_review_receipts':6,'simulated_platform_submissions':18,'replay_submissions':0,'live_provider_acceptance':False}
(root/'acceptance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
