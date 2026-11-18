"""Trusted-host social commands; draft and approval only, no publish transport."""
import argparse,json,os,sys
from pathlib import Path
from .trusted_bridge import Bridge,canonical
from .approval_ledger import Ledger
from .social_review import Controller,LocalRenderer
from .product_workflow import Products


def dispatch(controller,envelope):
    if not isinstance(envelope,dict) or set(envelope)-{'event','signature','review_receipt'} or not {'event','signature'}<=set(envelope):
        raise PermissionError('Exact trusted envelope required')
    event,signature=envelope['event'],envelope['signature'];route=controller._owner(event,signature);text=event['text']
    def view(job):
        info=controller.status(job);state=info['state']
        if state['owner']!=route:raise PermissionError('Wrong draft owner')
        return {'job_id':job,'phase':state['phase'],'revision':state['revision'],'etag':info['etag'],'binding':controller._binding(state),'image_url':state['artifact']['url']}
    if text.startswith('SOCIAL CREATE '):
        campaign=json.loads(text[14:]);state=controller.create(event,signature,campaign);return view(state['job_id'])
    parts=text.split(' ',3)
    if len(parts)>=3 and parts[0]=='SOCIAL':
        cmd,job=parts[1:3];state=controller.status(job)['state']
        if state['owner']!=route:raise PermissionError('Wrong draft owner')
        if cmd=='STATUS' and len(parts)==3:return view(job)
        if cmd=='REVISE' and len(parts)==4:
            body=json.loads(parts[3])
            if set(body)!={'expected','campaign'}:raise ValueError('Revision CAS and campaign required')
            controller.revise(job,event,signature,body['campaign'],expected=body['expected']);return view(job)
        if cmd=='REVIEW' and len(parts)==3:
            # Receipt comes from native message_sent hook, never command JSON.
            proof=envelope.get('review_receipt',{})
            controller.sender=lambda owner,binding:proof
            controller.review(job);return controller.challenge(job,event,signature)
        if cmd=='REVOKE' and len(parts)==3:
            # Persist local revocation before any external synchronization.
            with controller.bridge.db() as db:
                db.execute('BEGIN IMMEDIATE');controller.bridge.remember(db,event)
                db.execute("UPDATE challenges SET state='REVOKED' WHERE id=? AND owner=?",(state.get('challenge'),canonical(route)))
            if controller.ledger.job(job):
                controller.ledger.owner_action(job,'OWNER_REJECTED',owner_verified=True,confirmation=text,message_id=event['id'])
            return {'job_id':job,'revoked':True,'remote_undo':False}
    if text.startswith('CONFIRM ') and len(text.split())==2:
        cid=text.split()[1];matches=[]
        for path in controller.root.glob('SM-*.json'):
            state=controller._read(path.stem)
            if state.get('challenge')==cid and state['owner']==route:matches.append(state['job_id'])
        if len(matches)!=1:raise PermissionError('Unknown exact social challenge')
        controller.approve(matches[0],event,signature)
        return {'job_id':matches[0],'phase':'APPROVED','publication':'NOT_DISPATCHED'}
    raise ValueError('Unsupported social command; publication requires configured worker')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--state',required=True);p.add_argument('--network',action='store_true');p.add_argument('--writes',action='store_true');a=p.parse_args(argv)
    os.umask(0o077)
    try:
        if not a.writes:raise PermissionError('Explicit local workflow activation required')
        config_path=Path(a.config);Products._private(config_path)
        config=json.loads(config_path.read_text());home=Path(a.state);home.mkdir(mode=0o700,parents=True,exist_ok=True);Products._private(home,directory=True)
        render_root=home/'renders';render_root.mkdir(mode=0o700,exist_ok=True)
        key=os.environ[config['bridge_key_env']].encode();bridge=Bridge(home/'bridge.sqlite',key,config['routes']);ledger=Ledger(home/'publication.sqlite')
        from urllib.parse import urlsplit
        prefix=config['media_url_prefix'].rstrip('/');u=urlsplit(prefix)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('Owned HTTPS static media prefix required')
        # Deployment must map render_root to this read-only static origin. No
        # implicit upload, guessed service or remote publication is performed.
        renderer=LocalRenderer(brand=config['brand'],fonts=config['fonts'],atlas=config['atlas'],output_root=render_root,host=lambda path,sha,key:prefix+'/'+key+'/poster.jpg',chromium=config.get('chromium'))
        def no_send(*args):raise PermissionError('Native delivered review receipt required')
        controller=Controller(home,bridge=bridge,ledger=ledger,renderer=renderer,sender=no_send)
        raw=sys.stdin.read(131073)
        if len(raw)>131072:raise ValueError('Envelope too large')
        print(json.dumps(dispatch(controller,json.loads(raw)),ensure_ascii=False));return 0
    except Exception as error:
        print(json.dumps({'state':'BLOCKED','error_type':type(error).__name__}));return 2
if __name__=='__main__':raise SystemExit(main())
