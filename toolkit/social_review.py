"""Durable create/revise/review/approval dispatch via explicit trusted adapters.
No default renderer, sender, Sheet writer, publisher, account or network client.
Caller owns transport attestation; content alone never grants authority.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
from .approval_ledger import PLATFORMS, digest
from .poster_render import normalized, render
from .reliability import atomic_json, lock
from .image_intake import read_attachment, _trusted

class ReviewError(RuntimeError): pass

def plan(value):
    if set(value)!={'template','content','targets','captions'}: raise ValueError('Exact campaign schema required')
    targets=value['targets']
    if not isinstance(targets,list) or not targets or len(set(targets))!=len(targets) or not set(targets)<=set(PLATFORMS): raise ValueError('Explicit target set required')
    if set(value['captions'])!=set(targets) or any(not isinstance(c,str) or not c.strip() or len(c)>5000 for c in value['captions'].values()): raise ValueError('Exact platform captions required')
    return {'template':value['template'],'content':normalized(value['content'],value['template']),
            'targets':sorted(targets),'captions':copy.deepcopy(value['captions'])}

class LocalRenderer:
    """Connect all six existing layouts; operator supplies local assets and host.
    host(path, sha256, revision_key) must return a stable HTTPS media URL.
    Its uncertain effects are latched by Controller, never automatically replayed.
    """
    def __init__(self,*,brand,fonts,atlas,output_root,host,chromium=None):
        self.brand,self.fonts,self.atlas,self.root,self.host,self.chromium=brand,fonts,atlas,Path(output_root),host,chromium
    def __call__(self,campaign,key):
        report=render(campaign['template'],campaign['content'],self.brand,self.fonts,self.atlas,self.root,key,chromium=self.chromium)
        path=self.root/key/'poster.jpg';sha=report['outputs']['poster.jpg']
        return {'path':str(path),'sha256':sha,'url':self.host(path,sha,key),'template':report['template'],'geometry_pass':report['geometry_pass']}

class Controller:
    def __init__(self,root,*,bridge,ledger,renderer,sender):
        self.root=_trusted(root,directory=True);self.bridge,self.ledger,self.renderer,self.sender=bridge,ledger,renderer,sender
        if self.root.stat().st_mode & 0o077: raise PermissionError('Private draft root required')
    def _path(self,job):
        if not re.fullmatch(r'SM-[0-9a-f]{20}',job): raise ValueError('Invalid local job ID')
        return self.root/(job+'.json')
    def _read(self,job): return json.loads(read_attachment(self._path(job),[self.root],max_bytes=2*1024*1024))
    def _save(self,state):
        from .isolated_store import Store
        Store.check(self._path(state['job_id']))
        atomic_json(self._path(state['job_id']),state)
    def _owner(self,event,signature):
        route=self.bridge.verify(event,signature)
        if route['role']!='owner': raise PermissionError('Authenticated owner required')
        return route
    def _unapproved(self,job):
        if self.ledger.job(job) or any(self.ledger.get(job,p) for p in PLATFORMS): raise ReviewError('APPROVAL_OR_ATTEMPT_EXISTS')
    def _artifact(self,artifact,campaign):
        from urllib.parse import urlsplit
        if not isinstance(artifact,dict) or artifact.get('geometry_pass') is not True or artifact.get('template')!=campaign['template']: raise ReviewError('RENDER_PROOF_REQUIRED')
        raw=read_attachment(artifact['path'],[self.root])
        if hashlib.sha256(raw).hexdigest()!=artifact.get('sha256'): raise ReviewError('MEDIA_CHANGED')
        p=urlsplit(artifact['url'])
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.fragment: raise ReviewError('HTTPS_MEDIA_REQUIRED')
        return {k:artifact[k] for k in ('path','sha256','url','template','geometry_pass')}
    def _binding(self,state):
        artifact=self._artifact(state['artifact'],state['campaign'])
        return {'job_id':state['job_id'],'revision':state['revision'],'template':state['campaign']['template'],
                'content':state['campaign']['content'],'targets':state['campaign']['targets'],
                'captions':state['campaign']['captions'],'image_sha256':artifact['sha256'],'url':artifact['url']}
    def _prepare(self,state):
        state['phase']='PREPARING';self._save(state)
        try:
            artifact=self.renderer(copy.deepcopy(state['campaign']),state['job_id']+'-r'+str(state['revision']))
            state['artifact']=self._artifact(artifact,state['campaign']);state['phase']='DRAFT';self._save(state)
        except Exception:
            state['phase']='PREPARATION_UNKNOWN';self._save(state);raise ReviewError('PREPARATION_RECONCILIATION_REQUIRED') from None
        return copy.deepcopy(state)
    def create(self,event,signature,campaign):
        route=self._owner(event,signature);campaign=plan(campaign)
        job='SM-'+digest({'event':event['id'],'route':route})[:20]
        with lock(self.root/'social.lock'):
            path=self._path(job)
            if path.exists():
                state=self._read(job)
                if state['create_event']!=digest(event) or state['initial_plan']!=digest(campaign): raise ReviewError('REQUEST_ID_COLLISION')
                return state
            state={'job_id':job,'create_event':digest(event),'initial_plan':digest(campaign),'owner':route,
                   'revision':1,'campaign':campaign,'history':[],'phase':'NEW','approval_mode':'MANUAL','schedule':None}
            self._save(state)
            return self._prepare(state)
    def revise(self,job,event,signature,campaign,*,expected):
        route=self._owner(event,signature);campaign=plan(campaign)
        with lock(self.root/'social.lock'):
            state=self._read(job);self._unapproved(job)
            if route!=state['owner'] or digest(state)!=expected: raise ReviewError('STALE_OR_WRONG_OWNER_REVISION')
            if state['phase'] not in {'DRAFT','REVIEWED'}: raise ReviewError('UNRESOLVED_OPERATION')
            state['history'].append(copy.deepcopy({k:v for k,v in state.items() if k!='history'}))
            state.update(campaign=campaign,revision=state['revision']+1,revision_event=digest(event))
            for k in ('review','challenge','artifact','approval'):state.pop(k,None)
            return self._prepare(state)
    def review(self,job):
        with lock(self.root/'social.lock'):
            state=self._read(job);self._unapproved(job)
            if state['phase']=='REVIEWED':self._binding(state);return state['review']
            if state['phase']!='DRAFT':raise ReviewError('REVIEW_OUTCOME_UNRESOLVED')
            binding=self._binding(state);state['phase']='REVIEW_SENDING';self._save(state)
            try:
                receipt=self.sender(copy.deepcopy(state['owner']),copy.deepcopy(binding))
                if not isinstance(receipt,dict) or receipt.get('delivered') is not True or receipt.get('dryRun') or not receipt.get('message_id') or receipt.get('binding_digest')!=digest(binding) or any(receipt.get(k)!=state['owner'][k] for k in ('channel','account','peer')):
                    raise ReviewError('EXACT_DELIVERY_RECEIPT_REQUIRED')
                state['review']={k:receipt[k] for k in ('delivered','message_id','binding_digest','channel','account','peer')}
                state['phase']='REVIEWED';self._save(state)
            except Exception:
                state['phase']='REVIEW_UNKNOWN';self._save(state);raise ReviewError('REVIEW_RECONCILIATION_REQUIRED') from None
            return state['review']
    def challenge(self,job,event,signature):
        route=self._owner(event,signature)
        with lock(self.root/'social.lock'):
            state=self._read(job);self._unapproved(job)
            if state['phase']!='REVIEWED' or route!=state['owner']:raise ReviewError('CURRENT_OWNER_REVIEW_REQUIRED')
            result=self.bridge.challenge(event,signature,self._binding(state),review_receipt=state['review'])
            state['challenge']=result['challenge_id'];self._save(state);return result
    def approve(self,job,event,signature):
        self._owner(event,signature)
        with lock(self.root/'social.lock'):
            state=self._read(job)
            if state['phase'] not in {'REVIEWED','APPROVED'}:raise ReviewError('REVIEW_REQUIRED')
            binding=self._binding(state)
            approved=self.bridge.confirm(event,signature,state['challenge'])
            if approved['binding']!=binding:raise ReviewError('APPROVAL_CONTENT_CHANGED')
            receipt={'binding':binding,'source':{'authenticated':True,'review_ref':state['review']['message_id'],'event_id':event['id']},'owner':approved['owner']}
            self.ledger.approve(job,receipt)
            state['approval']=approved;state['phase']='APPROVED';self._save(state);return receipt
    def dispatch(self,job,*,publisher,enabled=False):
        """One adapter invocation only; errors/process death require reconciliation.
        publisher(job, binding, ledger) returns per-platform result dictionaries.
        It must reuse this ledger and enforce provider/media/account contracts.
        """
        if not enabled:raise PermissionError('Explicit dispatch opt-in required')
        with lock(self.root/'social.lock'):
            state=self._read(job);binding=self._binding(state)
            if state['phase']=='DISPATCHED':return state['result']
            if state['phase']!='APPROVED' or not self.bridge.authorized(state['challenge'],binding):raise ReviewError('CURRENT_APPROVAL_REQUIRED')
            saved=self.ledger.job(job)
            if not saved or saved['fingerprint']!=digest(binding) or saved['state']=='REVOKED' or self.ledger.submission_blocked(job):raise ReviewError('DURABLE_APPROVAL_REQUIRED')
            state['phase']='DISPATCHING';self._save(state)
            try:
                result=publisher(job,copy.deepcopy(binding),self.ledger)
                if not isinstance(result,dict) or set(result)!=set(binding['targets']):raise ReviewError('EXACT_PLATFORM_RESULTS_REQUIRED')
                # Never invent publication success from a submission/task ID.
                for platform,row in result.items():
                    if not isinstance(row,dict) or row.get('status') not in {'VERIFIED','PROCESSING','FAILED','NEEDS_ACTION'}:raise ReviewError('PLATFORM_STATUS_REQUIRED')
                    known=self.ledger.get(job,platform)
                    if row['status']=='VERIFIED' and (not known or known['state']!='PUBLISHED' or not known.get('permalink') or row.get('url')!=known['permalink']):raise ReviewError('PUBLICATION_RECEIPT_REQUIRED')
                state.update(phase='DISPATCHED',result=result);self._save(state);return result
            except Exception:
                state['phase']='DISPATCH_UNKNOWN';self._save(state);raise ReviewError('DISPATCH_RECONCILIATION_REQUIRED') from None
    def status(self,job):
        with lock(self.root/'social.lock'):
            state=self._read(job);return {'state':state,'etag':digest(state)}

class PublisherAdapters:
    """Adapter to existing MetaPublisher.run_job and TikTok advance(engine,...).
    Inject preconfigured provider clients with safe transports for offline use.
    Meta Sheets adapter must expose exact frozen rows; TikTok engine.checked
    must validate this controller's approval and exact content before submission.
    """
    def __init__(self,*,meta=None,tiktok_engine=None):self.meta,self.engine=meta,tiktok_engine
    def __call__(self,job,binding,ledger):
        from .approval_ledger import report_status
        from .tiktok_publisher import advance
        targets=binding['targets']
        if set(targets)&{'facebook','instagram'}:
            if self.meta is None or self.meta.ledger is not ledger:raise ReviewError('SHARED_META_LEDGER_REQUIRED')
            queue=self.meta.sheets.read_queue_job(job);content=self.meta.sheets.read_content_job(job)
            from .social_publish_gate import BoundApprovalGate, verify_rows
            if not isinstance(self.meta.approval_gate,BoundApprovalGate) or self.meta.approval_gate.controller.ledger is not ledger:raise ReviewError('BOUND_META_APPROVAL_GATE_REQUIRED')
            if not verify_rows(binding,queue,content):raise ReviewError('FROZEN_SHEET_CONTENT_REQUIRED')
            self.meta.run_job(job)
        if 'tiktok' in targets:
            if self.engine is None or self.engine.ledger is not ledger:raise ReviewError('SHARED_TIKTOK_LEDGER_REQUIRED')
            self.engine.checked(job)
            content={'final_master_asset_url':binding['url'],'tiktok_caption':binding['captions']['tiktok'],'tiktok_hashtags':''}
            advance(self.engine,job,content)
        return {p:{'status':report_status(ledger.get(job,p)),'url':(ledger.get(job,p) or {}).get('permalink')} for p in targets}
