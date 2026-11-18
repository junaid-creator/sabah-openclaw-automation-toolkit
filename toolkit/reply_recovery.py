"""Durable inquiry/result correlation without importing private transcripts.

The host supplies an authorized final-result reader and delivery lookup; neither
callback is a guessed OpenClaw API. Pending and ambiguous work is never resubmitted.
"""
import json
from pathlib import Path
from .product_workflow import Products
from .reliability import atomic_json,lock
from .trusted_bridge import fingerprint


class Replies:
    def __init__(self, home, bridge, *, policy):
        self.home=Path(home);self.home.mkdir(mode=0o700,parents=True,exist_ok=True)
        Products._private(self.home,directory=True)
        self.bridge,self.policy=bridge,policy

    def path(self,key):
        return self.home/('inquiry-'+fingerprint(key)+'.json')

    def start(self,event,signature,*,submit):
        route=self.bridge.verify(event,signature)
        if route['role']!='customer':raise PermissionError('Configured customer only')
        p=self.path(event['id'])
        with lock(self.home/'replies.lock'):
            if p.exists():
                value=json.loads(p.read_text())
                if value['event_digest']!=fingerprint(event):raise PermissionError('Inquiry collision')
                return value
            value={'event':event,'event_digest':fingerprint(event),'route':route,'state':'SUBMITTING'}
            atomic_json(p,value)
            try:
                task=submit(dict(event))
                if not isinstance(task,str) or not task or len(task)>256:raise ValueError('Task ID required')
            except Exception:
                value['state']='UNKNOWN_TASK';atomic_json(p,value)
                raise RuntimeError('Task submission uncertain; never resubmit inquiry') from None
            value.update(task_id=task,state='WAITING_RESULT');atomic_json(p,value)
            return value

    def recover(self,event_id,*,result_reader,sender,enabled=False):
        p=self.path(event_id)
        with lock(self.home/'replies.lock'):
            Products._private(p);value=json.loads(p.read_text())
            if value['state'] in ('UNKNOWN_TASK','SENT','UNKNOWN_DELIVERY'):return value
            if value['state']=='SUBMITTING':raise RuntimeError('Interrupted task admission; reconcile without submitting')
            if value['state']=='WAITING_RESULT':
                result=result_reader(value['task_id'])
                if not result or result.get('status')=='pending':return value
                if (result.get('task_id')!=value['task_id'] or result.get('event_id')!=event_id
                    or result.get('route')!=value['route'] or result.get('status')!='completed'
                    or result.get('role')!='assistant' or result.get('final') is not True):
                    raise PermissionError('Only exact authorized final assistant result accepted')
                proposal={'text':result.get('text'),'action':'reply'}
                # Admission verified the event when fresh. Recovery does not forge a
                # fresh transport timestamp/signature; it checks immutable local binding.
                if fingerprint(value['event'])!=value['event_digest']:raise PermissionError('Event binding changed')
                text=proposal['text']
                if not isinstance(text,str) or not 0<len(text)<=4000 or self.policy(value['event'],proposal) is not True:
                    value['state']='POLICY_BLOCKED';atomic_json(p,value);raise PermissionError('Semantic policy denied')
                value.update(text=text,text_sha256=fingerprint(text),state='READY');atomic_json(p,value)
            if value['state']!='READY':return value
            if not enabled:raise PermissionError('Delivery disabled')
            # Recheck operator policy after recovery, before every new admission.
            if self.policy(value['event'],{'text':value['text'],'action':'reply'}) is not True:
                raise PermissionError('Policy changed; delivery withheld')
            value['state']='UNKNOWN_DELIVERY';atomic_json(p,value)
            try:receipt=sender(dict(value['route']),value['text'],event_id)
            except Exception:receipt=None
            if self.receipt(value,receipt):
                value.update(state='SENT',receipt={k:receipt[k] for k in ('channel','account','peer','message_id')})
                atomic_json(p,value)
            return value

    @staticmethod
    def receipt(value,receipt):
        return (isinstance(receipt,dict) and receipt.get('delivered') is True and not receipt.get('dryRun')
                and isinstance(receipt.get('message_id'),str) and bool(receipt['message_id'])
                and receipt.get('text_sha256')==value['text_sha256']
                and receipt.get('event_id')==value['event']['id']
                and all(receipt.get(k)==value['route'][k] for k in ('channel','account','peer')))

    def reconcile_delivery(self,event_id,*,lookup):
        p=self.path(event_id)
        with lock(self.home/'replies.lock'):
            Products._private(p);value=json.loads(p.read_text())
            if value['state']=='SENT':return value
            if value['state']!='UNKNOWN_DELIVERY':raise ValueError('No uncertain send')
            receipt=lookup(event_id,dict(value['route']),value['text_sha256'])
            if not self.receipt(value,receipt):raise RuntimeError('Exact delivery not established; no resend')
            value.update(state='SENT',receipt={k:receipt[k] for k in ('channel','account','peer','message_id')})
            atomic_json(p,value);return value
