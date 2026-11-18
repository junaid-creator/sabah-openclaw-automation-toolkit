"""Signed-owner product workflow with durable no-replay mutation checkpoints.

Integrate only behind a trusted transport host. This module installs no ingress.
"""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from contextlib import contextmanager
from .trusted_bridge import canonical, fingerprint
from .product_api import MARKER, matches, positive, stable
from .product_plan import build, group_stable, merged, duplicates


class Products:
    def __init__(self, home, bridge, sites, api_factory, *, enabled=False, clock=time.time):
        self.home = Path(home)
        self.home.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._private(self.home, directory=True)
        self.bridge, self.sites, self.api_factory = bridge, copy.deepcopy(sites), api_factory
        self.enabled, self.clock = enabled, clock
        for key, site in self.sites.items():
            if key != site['id'] or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', key):
                raise ValueError('Unique safe site ID required')
            if not site.get('owners') or not site.get('exclusive_writer_confirmed'):
                raise ValueError('Configured owner routes and exclusive writer prerequisite required')
        self.path = self.home / 'products.sqlite3'
        if self.path.exists():
            self._private(self.path)
        else:
            fd = os.open(self.path, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
            os.close(fd)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS product_jobs(
              id TEXT PRIMARY KEY, owner TEXT NOT NULL, plan TEXT NOT NULL,
              digest TEXT NOT NULL, created REAL NOT NULL, state TEXT NOT NULL,
              challenge TEXT, receipt TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS product_events(id TEXT PRIMARY KEY, digest TEXT NOT NULL, job TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS product_revocations(job TEXT PRIMARY KEY, receipt TEXT NOT NULL);
            ''')

    @staticmethod
    def _private(path, directory=False):
        st = path.lstat()
        if path.is_symlink() or st.st_uid != os.getuid() or st.st_mode & 0o077 or (directory and not path.is_dir()) or (not directory and not path.is_file()):
            raise PermissionError('Protected operator-owned local storage required')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def lock(self):
        path = self.home / 'workflow.lock'
        fd = os.open(path, os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW, 0o600)
        try:
            self._private(path)
            fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def api(self, site):
        api = self.api_factory(copy.deepcopy(site))
        if not hasattr(api, 'site') or api.site != site or api.wp.base != site['origin'].rstrip('/'):
            raise PermissionError('API adapter does not match the frozen site')
        return api

    def build_plan(self, request, site, api, owner):
        if request.get('operation') != 'restore':
            return build(request,site,api)
        from .product_recovery import restore_plan
        source = self.load(request['source_job'])
        if source['owner'] != owner or source['plan']['site'] != site:
            raise PermissionError('Restoration source belongs to another owner/site')
        backup = source['receipt'].get('backup',{})
        path = self.home / (source['id']+'.before.json')
        self._private(path)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != backup.get('sha256'):
            raise ValueError('Protected before snapshot changed')
        return restore_plan(source,request,site,api,json.loads(raw))

    def owner(self, event, signature, site):
        route = self.bridge.verify(event, signature)
        if route.get('role') != 'owner' or not any(all(route[k]==r[k] for k in ('channel','account','peer')) for r in site['owners']):
            raise PermissionError('Authenticated direct owner for this site required')
        return route

    def load(self, jid):
        with self.db() as db:
            row = db.execute('SELECT * FROM product_jobs WHERE id=?',(jid,)).fetchone()
        if not row:
            raise ValueError('Unknown product job')
        j = dict(row)
        j['plan'], j['receipt'], j['owner'] = json.loads(j['plan']), json.loads(j['receipt']), json.loads(j['owner'])
        if fingerprint(j['plan']) != j['digest'] or self.sites.get(j['plan']['site']['id']) != j['plan']['site']:
            raise PermissionError('Stored plan or site configuration changed')
        return j

    def save(self, j, state):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            revoked = db.execute('SELECT 1 FROM product_revocations WHERE job=?',(j['id'],)).fetchone()
            if revoked and state not in ('VERIFIED','NEEDS_REVIEW'):
                old = db.execute('SELECT state FROM product_jobs WHERE id=?',(j['id'],)).fetchone()['state']
                state = 'NEEDS_REVIEW' if old in ('WRITE_STARTED','NEEDS_REVIEW') or j['receipt'].get('steps') else 'REVOKED'
            db.execute('UPDATE product_jobs SET state=?, receipt=? WHERE id=?', (state,canonical(j['receipt']),j['id']))
        j['state'] = state

    def admit(self, j):
        # Short transaction orders admission against independent revocation commits.
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM product_revocations WHERE job=?',(j['id'],)).fetchone():
                raise PermissionError('Revoked before phase admission')
            db.execute("UPDATE product_jobs SET state='WRITE_STARTED',receipt=? WHERE id=?",(canonical(j['receipt']),j['id']))
        j['state'] = 'WRITE_STARTED'

    def revocation(self, jid):
        with self.db() as db:
            row = db.execute('SELECT receipt FROM product_revocations WHERE job=?',(jid,)).fetchone()
        return json.loads(row['receipt']) if row else None

    def binding(self, j):
        return {'workflow':'products-v1','job':j['id'],'site':j['plan']['site']['id'],
                'origin':j['plan']['site']['origin'],'plan_sha256':j['digest'],
                'operation':j['plan']['operation']}

    def plan(self, event, signature):
        # No extraction from quoted prose. The entire attested text is the command.
        prefix = 'PRODUCT PLAN '
        if not event.get('text','').startswith(prefix):
            raise ValueError('Exact PRODUCT PLAN JSON command required')
        request = json.loads(event['text'][len(prefix):])
        site = self.sites[request['site']]
        owner = self.owner(event, signature, site)
        with self.lock():
            with self.db() as db:
                prior = db.execute('SELECT * FROM product_events WHERE id=?',(event['id'],)).fetchone()
            if prior:
                if prior['digest'] != fingerprint(event):
                    raise PermissionError('Event collision')
                return self.review(self.load(prior['job']))
            api = self.api(site)
            plan = self.build_plan(request, site, api, owner)
            jid = 'product-' + fingerprint({'event':event,'site':site})[:24]
            with self.db() as db:
                for row in db.execute("SELECT * FROM product_jobs WHERE state NOT IN ('VERIFIED','REVOKED','EXPIRED','STALE')"):
                    old = json.loads(row['plan'])
                    if old['site']['id'] == site['id']:
                        # One unresolved operation per site, intentionally conservative.
                        raise ValueError('Unresolved site job must be revoked or reconciled first')
                db.execute('INSERT INTO product_jobs VALUES(?,?,?,?,?,?,?,?)',
                    (jid,canonical(owner),canonical(plan),fingerprint(plan),self.clock(),'WAITING_APPROVAL',None,'{}'))
                db.execute('INSERT INTO product_events VALUES(?,?,?)',(event['id'],fingerprint(event),jid))
            return self.review(self.load(jid))

    def review(self, j):
        return {'job_id':j['id'],'state':j['state'],'plan':j['plan'],'binding':self.binding(j),
                'expires_at':j['created']+1800,
                'scope':'Woo authenticated REST only; no frontend/checkout verification'}

    def challenge(self, jid, event, signature, *, review_receipt):
        with self.lock():
            j = self.load(jid)
            route = self.owner(event,signature,j['plan']['site'])
            if route != j['owner'] or event['text'] != 'PRODUCT REVIEW '+jid or j['state'] != 'WAITING_APPROVAL' or self.clock() >= j['created']+1800:
                raise PermissionError('Fresh exact owner review required')
            result = self.bridge.challenge(event, signature, self.binding(j), review_receipt=review_receipt,
                                           ttl=min(300, j['created']+1800-self.clock()))
            with self.db() as db:
                db.execute('UPDATE product_jobs SET challenge=? WHERE id=?',(result['challenge_id'],jid))
            return result

    def confirm(self, jid, event, signature):
        with self.lock():
            j = self.load(jid)
            if self.owner(event,signature,j['plan']['site']) != j['owner'] or self.clock() >= j['created']+1800 or j['state'] != 'WAITING_APPROVAL':
                raise PermissionError('Fresh pending owner plan required')
            receipt = self.bridge.confirm(event,signature,j['challenge'])
            if receipt['binding'] != self.binding(j):
                raise PermissionError('Wrong exact-content confirmation')
            j['receipt']['approval'] = receipt
            self.save(j,'APPROVED')
            return {'job_id':jid,'state':'APPROVED'}

    def revoke(self, jid, event, signature):
        # Deliberately independent of the long workflow flock and in-memory receipt.
        j = self.load(jid)
        if self.owner(event,signature,j['plan']['site']) != j['owner'] or event['text'] != 'PRODUCT REVOKE '+jid:
            raise PermissionError('Exact owner revocation required')
        receipt = {'event_digest':fingerprint(event),'at':self.clock()}
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO product_revocations VALUES(?,?)',(jid,canonical(receipt)))
            db.execute("UPDATE product_jobs SET state='REVOKED' WHERE id=? AND state IN ('WAITING_APPROVAL','APPROVED','EXPIRED','STALE')",(jid,))
        return self.status(jid,event,signature,exact=False)

    def status(self, jid, event, signature, *, exact=True):
        j = self.load(jid)
        if self.owner(event,signature,j['plan']['site']) != j['owner'] or (exact and event['text'] != 'PRODUCT STATUS '+jid):
            raise PermissionError('Exact owner status command required')
        return {'job_id':jid,'state':j['state'],'receipt':j['receipt'],'revocation':self.revocation(jid),
                'public_verified':False,'scope':'authenticated Woo REST readback only'}

    def authorized(self, j):
        if self.revocation(j['id']) or j['receipt'].get('revoked') or self.clock() >= j['created']+1800 or not j.get('challenge') or not self.bridge.authorized(j['challenge'],self.binding(j)):
            raise PermissionError('Approval expired, revoked, or unbound')

    def backup(self, j):
        path = self.home / (j['id']+'.before.json')
        raw = canonical({'binding':self.binding(j),'plan':j['plan']}).encode()
        fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        directory = os.open(self.home,os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
        self._private(path)
        if path.read_bytes()!=raw:
            raise ValueError('Protected snapshot readback mismatch')
        return {'file':path.name,'sha256':hashlib.sha256(raw).hexdigest(),'scope':'REST before-state, NOT a database backup','restore_tested':False}

    def dependencies(self, j, api):
        for d in j['plan']['dependencies']:
            if api.dependency(d['kind'],d['id']) != d['before']:
                raise ValueError('Media/category identity drift')

    def execute(self, jid, event, signature):
        with self.lock():
            j = self.load(jid)
            if self.owner(event,signature,j['plan']['site']) != j['owner'] or event['text'] != 'PRODUCT EXECUTE '+jid:
                raise PermissionError('Exact authenticated execution command required')
            if j['state'] != 'APPROVED':
                return {'job_id':jid,'state':j['state'],'replayed':False}
            if self.enabled is not True:
                raise PermissionError('Product writes disabled')
            self.authorized(j)
            api = self.api(j['plan']['site'])
            if self.build_plan(j['plan']['request'],j['plan']['site'],api,j['owner']) != j['plan']:
                self.save(j,'STALE')
                raise ValueError('Plan stale; fresh review required')
            j['receipt']['backup'] = self.backup(j)
            # Repeat exact preconditions after backup; never use backup as authorization.
            if self.build_plan(j['plan']['request'],j['plan']['site'],api,j['owner']) != j['plan']:
                self.save(j,'STALE')
                raise ValueError('Plan changed during backup')
            self.authorized(j)
            j['receipt']['steps'] = []
            self.admit(j)  # FULL SQLite commit, ordered against cancellation, BEFORE first POST.
            pid = j['plan']['product_id']
            previous = j['plan']['before']
            try:
                for index, step in enumerate(j['plan']['steps']):
                    self.authorized(j)
                    api.identity()
                    self.dependencies(j,api)
                    if previous is not None and group_stable(api.group(pid)) != previous:
                        raise ValueError('Concurrent target change before next mutation')
                    patch = copy.deepcopy(step['fields'])
                    if j['plan']['operation']=='create':
                        patch.setdefault('meta_data',[]).append({'key':MARKER,'value':jid+':'+str(index)})
                    checkpoint = {'index':index,'state':'WRITE_STARTED','parent_id':pid,'variation_id':step['variation_id']}
                    j['receipt']['steps'].append(checkpoint)
                    self.admit(j)
                    self.authorized(j)  # Fresh cancellation fence immediately before transport.
                    remote = api.mutate(pid,patch,step['variation_id'])
                    checkpoint.update(state='ACKNOWLEDGED',remote_id=remote['id'])
                    if pid is None: pid = remote['id']
                    j['receipt']['product_id'] = pid
                    self.save(j,'WRITE_STARTED')
                    self.authorized(j)  # Keep remote IDs, but admit no further phase after revocation.
                    current = group_stable(api.group(pid))
                    # Acknowledge only exact saved fields; mutation response is not proof.
                    target = current['parent'] if step['variation_id'] is None else next((v for v in current['variations'] if v['id']==remote['id']),{})
                    if not self.patch_matches(target,patch):
                        raise ValueError('Partial mutation readback')
                    if j['plan']['operation']!='create':
                        wanted = copy.deepcopy(previous)
                        if step['variation_id'] is None:
                            wanted['parent'] = merged(wanted['parent'],patch)
                        else:
                            for n,v in enumerate(wanted['variations']):
                                if v['id']==step['variation_id']: wanted['variations'][n]=merged(v,patch)
                            self.variable_price(wanted,current)
                        if current!=wanted:
                            raise ValueError('Protected fields changed')
                    elif index:
                        # Already-created objects cannot silently change while adding children.
                        wanted_parent = copy.deepcopy(previous['parent'])
                        wanted_parent['variations'] = current['parent'].get('variations',[])
                        wanted = {'parent':wanted_parent,'variations':previous['variations']+[target]}
                        wanted['variations'].sort(key=lambda v:v['id'])
                        self.variable_price(wanted,current)
                        if current!=wanted:
                            raise ValueError('Unexpected creation side effect')
                    previous = current
                return self._reconcile(j,api)
            except Exception as error:
                j['receipt']['error_type'] = type(error).__name__
                self.save(j,'NEEDS_REVIEW')
                return {'job_id':jid,'state':'NEEDS_REVIEW','replayed':False,'public_verified':False}

    @staticmethod
    def patch_matches(record, patch):
        patch = copy.deepcopy(patch)
        metadata = patch.pop('meta_data',[])
        # Woo enriches local attributes with id/position; project their reviewed keys.
        attrs = patch.pop('attributes',None)
        if attrs is not None:
            actual = record.get('attributes',[])
            if len(actual)!=len(attrs) or any(not any(all(a.get(k)==v for k,v in wanted.items()) for a in actual) for wanted in attrs):
                return False
        actual_meta = {m['key']:m['value'] for m in record.get('meta_data',[])}
        return matches(record,patch) and all(actual_meta.get(m['key'])==m['value'] for m in metadata)

    @staticmethod
    def variable_price(wanted, current):
        if wanted['parent'].get('type')=='variable':
            prices = [v.get('price') for v in current['variations'] if v.get('status')=='publish' and v.get('price') not in ('',None)]
            from decimal import Decimal
            expected = min(prices,key=Decimal) if prices else ''
            if current['parent'].get('price') != expected:
                raise ValueError('Unexpected variable effective price')
            wanted['parent']['price'] = expected

    def reconcile(self, jid, event, signature):
        with self.lock():
            j = self.load(jid)
            if self.owner(event,signature,j['plan']['site']) != j['owner'] or event['text'] != 'PRODUCT RECONCILE '+jid:
                raise PermissionError('Exact read-only reconciliation command required')
            if j['state'] not in ('WRITE_STARTED','NEEDS_REVIEW','VERIFIED'):
                raise ValueError('No mutation receipt to reconcile')
            try:
                return self._reconcile(j,self.api(j['plan']['site']))
            except Exception as error:
                j['receipt']['error_type'] = type(error).__name__
                self.save(j,'NEEDS_REVIEW')
                return {'job_id':jid,'state':'NEEDS_REVIEW','replayed':False,'public_verified':False}

    def _reconcile(self, j, api):
        approval = j['receipt'].get('approval', {})
        if approval.get('binding') != self.binding(j) or approval.get('owner') != j['owner'] or not j['receipt'].get('steps'):
            raise PermissionError('Bound approval and durable write intent required for reconciliation')
        api.identity()
        self.dependencies(j,api)
        p = j['plan']
        pid = p['product_id'] or j['receipt'].get('product_id')
        if pid is None:
            candidates = [g['parent']['id'] for g in api.catalog() if any(m['key']==MARKER and m['value']==j['id']+':0' for m in g['parent'].get('meta_data',[]))]
            if len(candidates)!=1:
                raise ValueError('Creation absent/ambiguous; never recreate')
            pid = candidates[0]
        current = group_stable(api.group(pid))
        if p['operation']=='create':
            if len(current['variations']) != len(p['steps'])-1:
                raise ValueError('Partial/extra variations; no replay')
            self.variable_price(copy.deepcopy(current),current)
            for index,step in enumerate(p['steps']):
                items = [current['parent']] if index==0 else current['variations']
                candidates = [v for v in items if any(m['key']==MARKER and m['value']==j['id']+':'+str(index) for m in v.get('meta_data',[]))]
                if len(candidates)!=1 or not self.patch_matches(candidates[0],step['fields']):
                    raise ValueError('Created object does not match exact plan and marker')
                obj = candidates[0]
                if obj.get('sale_price') or any(obj.get(k) for k in ('date_on_sale_from','date_on_sale_to','date_on_sale_from_gmt','date_on_sale_to_gmt')):
                    raise ValueError('Unexpected discount on created product')
                if 'regular_price' in step['fields'] and obj.get('price')!=step['fields']['regular_price']:
                    raise ValueError('Created effective price mismatch')
                if index and obj.get('parent_id')!=pid:
                    raise ValueError('Wrong child parent')
                acknowledged = next((x.get('remote_id') for x in j['receipt'].get('steps',[]) if x['index']==index),None)
                if acknowledged and acknowledged!=obj['id']:
                    raise ValueError('Recorded object identity changed')
        else:
            wanted = copy.deepcopy(p['expected'])
            self.variable_price(wanted,current)
            if current!=wanted:
                raise ValueError('Exact changed/protected readback mismatch')
        duplicates(api.catalog(),p['identity']['name'],p['identity']['skus'],except_id=pid)
        if group_stable(api.group(pid)) != current:
            raise ValueError('Target changed during verification')
        prior = j['receipt'].get('after')
        if prior is not None and prior != current:
            raise ValueError('Previously verified object drifted')
        j['receipt'].update(product_id=pid,after=current,verified_at=self.clock(),public_verified=False)
        self.save(j,'VERIFIED')
        return {'job_id':j['id'],'state':'VERIFIED','product_id':pid,'status':current['parent']['status'],
                'scope':'authenticated Woo REST only','public_verified':False,'replayed':False}
