"""Durable multi-tab workflow tracking through the existing GOG interface.

Only explicitly configured, exclusive-writer, formula-free tracker tabs are owned.
Read-only source sheets with formulas must remain separate. No inferred schemas.
"""
import json,re
from pathlib import Path
from .trusted_bridge import fingerprint
from .product_workflow import Products
from .reliability import atomic_json,lock
from .source_reconciliation import mirror_once

class Tracker:
    def __init__(self,root,gog,*,sheet_id,tabs,max_rows=1000,exclusive_writer=False):
        self.root=Path(root);self.root.mkdir(mode=0o700,parents=True,exist_ok=True);Products._private(self.root,directory=True)
        if not re.fullmatch(r'[A-Za-z0-9_-]{5,200}',sheet_id):raise ValueError('Explicit spreadsheet ID required')
        if not exclusive_writer or type(max_rows) is not int or not 2<=max_rows<=10000:raise PermissionError('Bounded exclusive tracker writer required')
        if not isinstance(tabs,dict) or not 1<=len(tabs)<=10:raise ValueError('Explicit tracker tabs required')
        for name,spec in tabs.items():
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9 _-]{0,60}',name) or set(spec)!={'headers','key'}:raise ValueError('Safe configured tab schema required')
            headers=spec['headers']
            if not isinstance(headers,list) or not 1<=len(headers)<=26 or len(set(headers))!=len(headers) or any(not isinstance(x,str) or not x for x in headers) or spec['key'] not in headers:raise ValueError('Unique headers/stable key required')
        self.gog,self.sheet,self.tabs,self.max_rows=gog,sheet_id,json.loads(json.dumps(tabs)),max_rows
    def range(self,tab,count=None):
        if tab not in self.tabs:raise ValueError('Unconfigured tab')
        return "'"+tab+"'!A1:"+chr(64+len(self.tabs[tab]['headers']))+str(count or self.max_rows)
    def values(self,tab,*,formulas=False):
        args=['get',self.sheet,self.range(tab)]
        if formulas:args+=['--render','FORMULA']
        result=self.gog._request(*args)
        rows=result.get('values') or []
        width=len(self.tabs[tab]['headers'])
        if not isinstance(rows,list) or any(not isinstance(r,list) or len(r)>width for r in rows) or len(rows)>=self.max_rows:raise ValueError('Incomplete/bounded tracker inventory')
        rows=[list(r)+['']*(width-len(r)) for r in rows]
        if not rows or rows[0]!=self.tabs[tab]['headers']:raise ValueError('Tracker header drift or missing header')
        if any(isinstance(c,str) and c.startswith('=') for r in rows for c in r):raise ValueError('Formula cells are not owned by tracker')
        return rows
    def plan(self,updates):
        if not isinstance(updates,dict) or not updates or not set(updates)<=set(self.tabs):raise ValueError('Configured updates required')
        items={}
        for tab,incoming in updates.items():
            old=self.values(tab);formula=self.values(tab,formulas=True)
            if formula!=old:raise ValueError('Formula/value views differ; refuse mixed source tabs')
            headers=self.tabs[tab]['headers'];key=self.tabs[tab]['key'];index=headers.index(key)
            rows={};order=[]
            for row in old[1:]:
                if not isinstance(row[index],str) or not row[index] or row[index] in rows:raise ValueError('Ambiguous tracker identity')
                rows[row[index]]=row;order.append(row[index])
            if not isinstance(incoming,list) or not incoming:raise ValueError('Tracker rows required')
            seen=set()
            for record in incoming:
                if not isinstance(record,dict) or set(record)!=set(headers):raise ValueError('Exact tracker columns required')
                if any(not isinstance(v,str) or len(v)>20000 or v.startswith('=') for v in record.values()):raise ValueError('Literal bounded strings only')
                identity=record[key]
                if not identity or identity in seen:raise ValueError('Duplicate update identity')
                seen.add(identity)
                if identity not in rows:order.append(identity)
                rows[identity]=[record[h] for h in headers]
            target=[headers]+[rows[k] for k in order]
            if len(target)>=self.max_rows:raise ValueError('Tracker capacity reached')
            items[tab]={'before':old,'after':target,'range':self.range(tab,len(target)),'source_id':fingerprint(incoming)}
        body={'sheet_id':self.sheet,'schemas':self.tabs,'tabs':items}
        return {'binding':body,'digest':fingerprint(body)}
    def apply(self,operation,plan,*,approved_digest):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',operation):raise ValueError('Stable safe operation ID required')
        if fingerprint(plan['binding'])!=plan.get('digest') or approved_digest!=plan['digest'] or plan['binding']['sheet_id']!=self.sheet or plan['binding']['schemas']!=self.tabs:raise PermissionError('Exact tracker plan approval required')
        if set(plan['binding'])!={'sheet_id','schemas','tabs'} or not plan['binding']['tabs'] or not set(plan['binding']['tabs'])<=set(self.tabs):raise ValueError('Unconfigured plan tabs')
        for tab,binding in plan['binding']['tabs'].items():
            if set(binding)!={'before','after','range','source_id'} or binding['range']!=self.range(tab,len(binding['after'])):raise ValueError('Tracker range changed')
            headers=self.tabs[tab]['headers'];index=headers.index(self.tabs[tab]['key'])
            for rows in (binding['before'],binding['after']):
                if not isinstance(rows,list) or not rows or rows[0]!=headers or len(rows)>=self.max_rows or any(not isinstance(row,list) or len(row)!=len(headers) for row in rows):raise ValueError('Tracker row shape changed')
                if any(not isinstance(c,str) or c.startswith('=') for row in rows for c in row):raise ValueError('Literal tracker cells required')
                ids=[row[index] for row in rows[1:]]
                if any(not x for x in ids) or len(set(ids))!=len(ids):raise ValueError('Tracker identity changed')
            if len(binding['after'])<len(binding['before']):raise ValueError('Tracker deletion not supported')
        if not self.gog.allow_writes:raise PermissionError('Tracker writes disabled')
        p=self.root/(operation+'.json')
        with lock(self.root/'tracker.lock'):
            prior=json.loads(p.read_text()) if p.exists() else None
            if prior and prior['digest']!=plan['digest']:raise ValueError('Tracker operation rebound')
            if not prior:
                # Preflight every tab before the first write, not after partial sync.
                for tab,binding in plan['binding']['tabs'].items():
                    if self.values(tab)!=binding['before'] or self.values(tab,formulas=True)!=binding['before']:raise RuntimeError('Tracker drift before admission')
                atomic_json(p,{'digest':plan['digest'],'state':'SYNCING'})
            results={}
            for tab,binding in plan['binding']['tabs'].items():
                if self.values(tab,formulas=True)!=self.values(tab):raise ValueError('Tracker formulas introduced')
                def writer(address,rows):
                    self.gog._request('update',self.sheet,address,'--values-json='+json.dumps(rows),'--input=RAW')
                key=operation+'-'+fingerprint(tab)[:16]
                results[tab]=mirror_once(self.root/(key+'.json'),binding,reader=lambda address,tab=tab:self.values(tab),writer=writer,exclusive_writer=True)
            atomic_json(p,{'digest':plan['digest'],'state':'VERIFIED','tabs':results});return results

    def social_draft_plan(self,state,*,queue_tab,content_tab):
        """Use explicitly configured dedicated schemas; never infer approval."""
        if state.get('phase')!='DRAFT' or state.get('approval_mode')!='MANUAL' or state.get('schedule') is not None:raise PermissionError('Unscheduled manual draft only')
        campaign=state['campaign'];job=state['job_id']
        queue={'job_id':job,'status':'WAITING_APPROVAL','approval_mode':'MANUAL','schedule':''}
        content={'job_id':job,'revision':str(state['revision']),'template':str(campaign['template']),'media_url':state['artifact']['url'],'content_sha256':fingerprint(campaign),'captions_json':json.dumps(campaign['captions'],sort_keys=True)}
        return self.plan({queue_tab:[queue],content_tab:[content]})

    def seo_draft_plan(self,result,article,*,draft_tab,topic_tab,run_tab,run_id):
        if result.get('status')!='draft' or type(result.get('post_id')) is not int or result['post_id']<=0:raise PermissionError('Verified CMS draft required')
        return self.plan({draft_tab:[{'run_id':run_id,'post_id':str(result['post_id']),'url':result['url'],'status':'Draft'}],topic_tab:[{'run_id':run_id,'topic':article['title'],'keyword':article['keyword']}],run_tab:[{'run_id':run_id,'plan_sha256':result['plan_sha256'],'status':'Draft'}]})

    def sync_frozen(self,operation,request,planner,*,enabled=False):
        if not enabled:raise PermissionError('Tracker workflow integration disabled')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',operation):raise ValueError('Stable operation required')
        p=self.root/(operation+'-plan.json')
        with lock(self.root/(operation+'-prepare.lock')):
            binding=fingerprint(request)
            if p.exists():
                Products._private(p);saved=json.loads(p.read_text())
                if saved['request_digest']!=binding:raise ValueError('Workflow tracker request changed')
                plan=saved['plan']
            else:
                plan=planner();atomic_json(p,{'request_digest':binding,'plan':plan})
            return self.apply(operation,plan,approved_digest=plan['digest'])

    def sync_social_draft(self,controller,job,*,queue_tab,content_tab,enabled=False):
        state=controller.status(job)['state']
        request={'job':job,'revision':state['revision'],'binding':controller._binding(state)}
        operation='social-'+fingerprint({'job':job,'revision':state['revision']})[:32]
        return self.sync_frozen(operation,request,lambda:self.social_draft_plan(state,queue_tab=queue_tab,content_tab=content_tab),enabled=enabled)

    def sync_seo_draft(self,result,article,*,draft_tab,topic_tab,run_tab,run_id,enabled=False):
        request={'result':result,'article':article,'run_id':run_id}
        operation='seo-'+fingerprint(run_id)[:32]
        return self.sync_frozen(operation,request,lambda:self.seo_draft_plan(result,article,draft_tab=draft_tab,topic_tab=topic_tab,run_tab=run_tab,run_id=run_id),enabled=enabled)
