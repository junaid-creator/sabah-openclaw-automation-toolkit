"""Explicit exact-content/time approval and one-shot due admission.

No daemon installation or standing publication permission. Dispatcher callbacks
must use the underlying publication ledger for platform outcome reconciliation.
"""
from datetime import datetime,timezone
import json,time
from pathlib import Path
from .schedule_core import parse_schedule
from .trusted_bridge import fingerprint
from .product_workflow import Products
from .reliability import atomic_json,lock

class Schedule:
    def __init__(self,home,bridge,*,clock=time.time):
        self.home=Path(home);self.home.mkdir(mode=0o700,parents=True,exist_ok=True)
        Products._private(self.home,directory=True);self.bridge=bridge;self.clock=clock
    def path(self,sid):
        import re
        if not re.fullmatch(r'schedule-[a-f0-9]{24}',sid):raise ValueError('Invalid schedule ID')
        return self.home/(sid+'.json')
    def plan(self,event,signature,content,*,timezone_name):
        route=self.bridge.verify(event,signature)
        if route['role']!='owner' or not event['text'].startswith('SCHEDULE '):raise PermissionError('Exact owner schedule required')
        if not isinstance(content,dict) or not content.get('job_id') or not content.get('artifact_sha256'):
            raise ValueError('Reviewed content identity required')
        due=parse_schedule(event['text'][9:],datetime.fromtimestamp(event['timestamp'],timezone.utc).isoformat(),timezone_name)
        binding={'kind':'schedule','owner':route,'content':content,'time':due}
        sid='schedule-'+fingerprint({'event_id':event['id'],'binding':binding})[:24]
        with lock(self.home/'schedule.lock'):
            p=self.path(sid)
            if p.exists():
                j=json.loads(p.read_text())
                if j['binding']!=binding:raise ValueError('Schedule identity conflict')
            else:
                j={'id':sid,'binding':binding,'state':'DRAFT'};atomic_json(p,j)
        return j
    def challenge(self,sid,event,signature,*,review_receipt):
        with lock(self.home/'schedule.lock'):
            p=self.path(sid);Products._private(p);j=json.loads(p.read_text())
            route=self.bridge.verify(event,signature)
            if route!=j['binding']['owner'] or event['text']!='SCHEDULE REVIEW '+sid or j['state']!='DRAFT':raise PermissionError('Exact scheduled review required')
            c=self.bridge.challenge(event,signature,j['binding'],review_receipt=review_receipt)
            j['challenge']=c['challenge_id'];atomic_json(p,j);return c
    def dispatch_due(self,sid,*,content_reader,publish,enabled=False,grace=300):
        if not enabled or not 0<grace<=3600:raise PermissionError('Explicit dispatcher activation required')
        with lock(self.home/'schedule.lock'):
            p=self.path(sid);Products._private(p);j=json.loads(p.read_text())
            if j['state']!='DRAFT':return j
            if not self.bridge.authorized(j.get('challenge'),j['binding']):raise PermissionError('Bound schedule approval required')
            delta=self.clock()-j['binding']['time']['due_at']
            if delta<0:return j
            if delta>grace:
                j['state']='EXPIRED';atomic_json(p,j);return j
            if content_reader(j['binding']['content']['job_id'])!=j['binding']['content']:
                raise ValueError('Scheduled content changed; new review required')
            if not self.bridge.authorized(j.get('challenge'),j['binding']):raise PermissionError('Revoked before admission')
            j['state']='DISPATCHED_UNKNOWN';atomic_json(p,j)
            # The schedule grants no new unbound approval: pass exact original binding.
            try:result=publish(j['binding']['content'],j['challenge'])
            except Exception:return j
            if isinstance(result,dict) and result.get('job_id')==j['binding']['content']['job_id']:
                j['result']=result;atomic_json(p,j)
            return j
