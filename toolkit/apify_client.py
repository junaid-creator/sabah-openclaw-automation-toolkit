"""Portable adaptation of the original capped Actor start/collect workflow.
Paid starts require explicit trusted authorization, fresh evidence and a durable reservation.
"""
import hashlib,json,math,re,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
from .apify_budget import billing_guard,RunBudgetUnsafe
from .reliability import lock,atomic_json
from .meta_publisher import _NoRedirect

class ApifyClient:
    def __init__(self,actor,expected_actor_id,token_provider,*,transport=None,allow_network=False):
        if not re.fullmatch(r'[A-Za-z0-9_-]+(?:~[A-Za-z0-9_-]+)?',actor):raise ValueError('Invalid Actor identifier')
        self.actor,self.expected_actor_id,self.token_provider=actor,expected_actor_id,token_provider
        self.transport=transport;self.allow_network=allow_network
    def _api(self,path,payload=None):
        method='POST' if payload is not None else 'GET'
        if self.transport is not None:return self.transport(method,path,payload)
        if not self.allow_network:raise RuntimeError('Apify network disabled')
        token=self.token_provider()
        if not token:raise RuntimeError('Apify credential unavailable')
        req=urllib.request.Request('https://api.apify.com/v2/'+path,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},data=json.dumps(payload).encode() if payload is not None else None,method=method)
        try:
            with urllib.request.build_opener(_NoRedirect()).open(req,timeout=40) as r:
                raw=r.read(5_000_001)
                if len(raw)>5_000_000:raise ValueError('Bounded API response exceeded')
                data=json.loads(raw)
        except urllib.error.HTTPError as e:raise RuntimeError('Apify HTTP '+str(e.code)) from None
        except (OSError,ValueError):raise RuntimeError('Apify request outcome unknown') from None
        return data['data'] if isinstance(data,dict) and 'data' in data else data
    def account_runs(self, *, page_size=100, max_pages=20):
        """Bounded complete inventory; reject malformed, changing or active history.

        Ascending order avoids offset shifts from newly started runs. Rechecking
        the first page detects count/head changes, but no API read can atomically
        exclude another actor start immediately after this preflight.
        """
        if type(page_size) is not int or not 1 <= page_size <= 1000 or type(max_pages) is not int or not 1 <= max_pages <= 20:
            raise ValueError('Invalid pagination bound')
        total = None
        seen = set()
        items = []
        first = None
        terminal = {'SUCCEEDED','FAILED','TIMED-OUT','ABORTED'}
        def page(offset):
            result = self._api('actor-runs?limit='+str(page_size)+'&offset='+str(offset)+'&desc=0')
            if not isinstance(result, dict) or not isinstance(result.get('items'), list):
                raise RunBudgetUnsafe('Invalid account inventory shape')
            for field in ('total','offset','count','limit'):
                if type(result.get(field)) is not int or result[field] < 0:
                    raise RunBudgetUnsafe('Missing account pagination metadata')
            rows = result['items']
            if (result['offset'] != offset or result['limit'] != page_size
                or result.get('desc') is not False or result['count'] != len(rows)
                or len(rows) > page_size or offset+len(rows) > result['total']):
                raise RunBudgetUnsafe('Inconsistent account pagination')
            if any(not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id']
                   or row.get('status') not in terminal for row in rows):
                raise RunBudgetUnsafe('Active or unknown account run state')
            return result
        for index in range(max_pages):
            result = page(len(items))
            if total is None:
                total = result['total']
                first = result
                if total > page_size*max_pages:
                    raise RunBudgetUnsafe('Account inventory exceeds reviewed bound')
            if result['total'] != total:
                raise RunBudgetUnsafe('Account history changed during pagination')
            for row in result['items']:
                if row['id'] in seen:
                    raise RunBudgetUnsafe('Duplicate account run across pages')
                seen.add(row['id'])
                items.append(row)
            if len(items) == total:
                # Compare only admission-relevant fields, not changing provider metadata.
                check = page(0)
                identity = lambda value: [(r['id'],r['status']) for r in value['items']]
                if check['total'] != total or identity(check) != identity(first):
                    raise RunBudgetUnsafe('Account history changed before admission')
                return items
            if not result['items']:
                raise RunBudgetUnsafe('Account history ended prematurely')
        raise RunBudgetUnsafe('Account inventory incomplete at page bound')

    def start(self,run_key,payload,*,state_path,evidence_path,authorize,cap=0.20,reserve=0.30,monthly_limit=1.00,now=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',run_key):raise ValueError('Invalid run key')
        digest=hashlib.sha256(json.dumps({'actor':self.actor,'input':payload,'cap':cap},sort_keys=True).encode()).hexdigest()
        if not callable(authorize) or authorize(digest) is not True:raise RunBudgetUnsafe('Explicit paid-run authorization required')
        p=Path(state_path)
        with lock(str(p)+'.lock'):
            state=json.loads(p.read_text()) if p.exists() else {'runs':{}}
            old=state['runs'].get(run_key)
            if old:
                if old['fingerprint']!=digest:raise RunBudgetUnsafe('Run key bound to different input')
                if old['status']=='STARTING':old['status']='UNCERTAIN_START';atomic_json(p,state)
                return dict(old)
            evidence,balance=billing_guard(evidence_path,now=now,cap=cap,reserve=reserve)
            if not math.isfinite(monthly_limit) or monthly_limit<=0:raise RunBudgetUnsafe('Invalid monthly workflow limit')
            if any(r['status'] not in ('COMPLETE','FAILED') for r in state['runs'].values()):raise RunBudgetUnsafe('Existing run requires collection or reconciliation')
            reserved=sum(float(r['cap_usd']) for r in state['runs'].values() if r['cycle']==evidence['cycle_start'])
            if not math.isfinite(reserved) or reserved<0 or reserved+cap>monthly_limit:raise RunBudgetUnsafe('Monthly reserved-cap budget exceeded')
            actor=self._api('acts/'+self.actor)
            if actor.get('id')!=self.expected_actor_id:raise RunBudgetUnsafe('Actor identity changed')
            pricing=(actor.get('pricingInfos') or [{}])[-1]
            minimum=pricing.get('minimalMaxTotalChargeUsd') or 0
            if pricing.get('pricingModel')!='PAY_PER_EVENT' or not isinstance(minimum,(int,float)) or not math.isfinite(minimum) or minimum>cap:raise RunBudgetUnsafe('Actor pricing does not support reviewed cap')
            self.account_runs()
            record={'status':'STARTING','cycle':evidence['cycle_start'],'cap_usd':cap,'fingerprint':digest,'started_at':(now or datetime.now(timezone.utc)).isoformat()}
            state['runs'][run_key]=record;atomic_json(p,state)
            try:
                run=self._api('acts/'+self.actor+'/runs?maxTotalChargeUsd='+str(cap)+'&memory=512&timeout=300',payload)
                if not run.get('id') or not run.get('defaultDatasetId'):raise ValueError('Missing run identity')
            except Exception:
                record['status']='UNCERTAIN_START';atomic_json(p,state)
                raise RuntimeError('Ambiguous paid start; reconcile read-only, never retry') from None
            record.update(run_id=run['id'],dataset_id=run['defaultDatasetId'],status='RUNNING');atomic_json(p,state)
            options=run.get('options') or {}
            if options.get('maxTotalChargeUsd')!=cap or options.get('isMaxTotalChargeUsdSetByUser') is not True:
                record['status']='CAP_UNVERIFIED';atomic_json(p,state)
                raise RunBudgetUnsafe('Provider cap confirmation missing; run ID retained')
            record['cap_confirmed']=True;atomic_json(p,state)
            return dict(record)
    def collect(self,run_key,*,state_path):
        p=Path(state_path)
        with lock(str(p)+'.lock'):
            state=json.loads(p.read_text());record=state['runs'][run_key]
            if not record.get('run_id'):raise RunBudgetUnsafe('No accepted run ID; read-only reconciliation required')
            run=self._api('actor-runs/'+record['run_id']);record['actor_status']=run.get('status')
            if not record.get('cap_confirmed'):
                options=run.get('options') or {}
                if options.get('maxTotalChargeUsd')!=record['cap_usd'] or options.get('isMaxTotalChargeUsdSetByUser') is not True:
                    record['status']='CAP_UNVERIFIED';atomic_json(p,state);raise RunBudgetUnsafe('Run cap still unverified; no new paid start')
                record['cap_confirmed']=True
            if run.get('status') in ('READY','RUNNING'):record['status']='PROCESSING';atomic_json(p,state);return dict(record)
            cost=run.get('usageTotalUsd')
            if not isinstance(cost,(int,float)) or not math.isfinite(cost) or cost<0 or cost>record['cap_usd']:
                record['status']='NEEDS_ACTION';atomic_json(p,state);raise RunBudgetUnsafe('Cost evidence absent or exceeds reserved cap')
            record['cost_usd']=cost
            if run.get('status')!='SUCCEEDED':record['status']='FAILED';atomic_json(p,state);return dict(record)
            items=self._api('datasets/'+record['dataset_id']+'/items?format=json&clean=true&limit=100')
            if not isinstance(items,list):raise RuntimeError('Dataset shape invalid')
            record.update(status='COMPLETE',raw_count=len(items),dataset_truncation_possible=len(items)>=100);atomic_json(p,state)
            return {**record,'items':items}
