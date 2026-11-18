"""Durable approval/operation ledger. Callers must authenticate owners independently."""
import json,hashlib,time,email.utils,random
from contextlib import contextmanager
from . import meta_publisher as m
PLATFORMS=("facebook","instagram","tiktok")

def yes(v): return str(v).strip().upper() in {'TRUE','YES','1'}

def canonical(v): return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'))

def digest(v): return hashlib.sha256(canonical(v).encode()).hexdigest()

def report_status(saved):
    if not saved:return 'PROCESSING'
    state=saved.get('state')
    if state=='PUBLISHED' and saved.get('permalink'):return 'VERIFIED'
    if saved.get('error_code') in {'TIKTOK_VIDEO_LIST_PERMISSION_REQUIRED','SEND_TO_USER_INBOX','TIKTOK_SEND_TO_USER_INBOX'}:return 'NEEDS_ACTION'
    if state in {'FAILED_FINAL'}:return 'FAILED'
    if state in {'UNCERTAIN'}:return 'NEEDS_ACTION'
    return 'PROCESSING'

class Temporary(RuntimeError):
    def __init__(self,code='TEMPORARY',delay=60): super().__init__(code); self.code=code; self.delay=delay

class Permanent(RuntimeError): pass

class Uncertain(RuntimeError): pass

def require_review_reference(value):
    """Minimum delivery-reference check, not independent transport attestation.

    Never upgrade an inbound request/local preview ID into a delivery receipt.
    The caller still owns authentication and exact-content delivery validation.
    """
    if not isinstance(value,str) or not value.strip() or value.strip().lower().startswith('local-preview:'):
        raise Permanent('DELIVERED_REVIEW_MESSAGE_REQUIRED')
    return value.strip()

def require_receipt_review(receipt):
    """Fail closed on saved snapshots/schedules with invalid review provenance.

    Historical immediate approvals without snapshots are not rewritten here.
    This does not provide an existing-job approval-reassociation mechanism.
    """
    for key in ('local_snapshot','review'):
        if key in receipt:require_review_reference(receipt[key].get('review_message_id'))
    if 'schedule' in receipt:
        source=receipt.get('source')
        if not isinstance(source,dict):raise Permanent('DELIVERED_REVIEW_MESSAGE_REQUIRED')
        require_review_reference(source.get('review_ref') or source.get('review_message_id'))

def retry_after(headers,now=None):
    value=(headers or {}).get('Retry-After','')
    try: return max(0,float(value))
    except (ValueError,TypeError):
        try: return max(0,email.utils.parsedate_to_datetime(value).timestamp()-(now or time.time()))
        except (ValueError,TypeError,OverflowError): return 0

def sheet_error(exc):
    response=getattr(exc,'response',None); code=getattr(response,'status_code',0)
    if not code and (isinstance(exc,(TimeoutError,ConnectionError)) or exc.__class__.__name__ in {'ReadTimeout','ConnectTimeout','ConnectionError'}):return True,0
    reasons=set()
    if code==403:
        try: reasons={e.get('reason') for e in response.json().get('error',{}).get('errors',[])}
        except Exception:pass
    return code in {429,500,502,503,504} or bool(reasons & {'rateLimitExceeded','userRateLimitExceeded'}),retry_after(getattr(response,'headers',{}))

class SheetsRetry:
    def __init__(self,sleep=time.sleep,jitter=random.random,attempts=4):self.sleep,self.jitter,self.attempts=sleep,jitter,attempts
    def call(self,fn,operation="request"):
        for n in range(self.attempts):
            try:return fn()
            except Exception as exc:
                safe,after=sheet_error(exc)
                if not safe:raise Permanent('SHEETS_PERMANENT_ERROR:'+operation) from None
                delay=max(after,min(2**n+self.jitter(),32))
                if n+1==self.attempts or delay>16:raise Temporary('SHEETS_RETRY_DEFERRED:'+operation,max(60,delay)) from None
                self.sleep(delay)

class Ledger(m.PublishLedger):
    def reserve(self,job_id,platform,max_attempts):
        if self.submission_blocked(job_id):raise Permanent('OWNER_SUBMISSION_BLOCKED')
        if platform!='tiktok':return super().reserve(job_id,platform,max_attempts)
        with self._lock,self._connect() as db:
            row=db.execute('SELECT * FROM meta_posts WHERE job_id=? AND platform=?',(job_id,platform)).fetchone()
            if row is None:
                db.execute("INSERT INTO meta_posts VALUES (?,?,'POSTING',1,NULL,NULL,NULL,?)",(job_id,platform,m._now()));return 1
            if row['state']!='FAILED_RETRYABLE' or row['attempts']>=max_attempts:raise Permanent('TIKTOK_ALREADY_CLAIMED_OR_RETRY_LIMIT')
            attempt=row['attempts']+1
            db.execute("UPDATE meta_posts SET state='POSTING',attempts=?,error_code=NULL,updated_at=? WHERE job_id=? AND platform=?",(attempt,m._now(),job_id,platform));return attempt
    def __init__(self,path):
        super().__init__(str(path))
        with self._connect() as db:
            db.execute('PRAGMA synchronous=FULL')
            db.executescript('''CREATE TABLE IF NOT EXISTS publication_jobs (
              job_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, receipt TEXT NOT NULL,
              state TEXT NOT NULL, next_at REAL NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0,
              sheet_pending INTEGER NOT NULL DEFAULT 1, sheet_attempts INTEGER NOT NULL DEFAULT 0,
              sheet_next REAL NOT NULL DEFAULT 0, notify_state TEXT NOT NULL DEFAULT 'NONE',
              notify_attempts INTEGER NOT NULL DEFAULT 0, notify_next REAL NOT NULL DEFAULT 0,
              notify_id TEXT, last_error TEXT, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS publication_operations (
              job_id TEXT NOT NULL, platform TEXT NOT NULL, phase TEXT NOT NULL DEFAULT 'PENDING',
              container_id TEXT, started_at REAL, tries INTEGER NOT NULL DEFAULT 0,
              next_at REAL NOT NULL DEFAULT 0, checks INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(job_id,platform));
            CREATE TABLE IF NOT EXISTS publication_events (
              id INTEGER PRIMARY KEY, job_id TEXT, event TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS publication_owner_actions (id INTEGER PRIMARY KEY, job_id TEXT NOT NULL, platform TEXT, action TEXT NOT NULL, evidence TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS publication_health (key TEXT PRIMARY KEY, value TEXT NOT NULL);''')
    @contextmanager
    def _connect(self):
        with super()._connect() as db:
            db.execute('PRAGMA synchronous=FULL');yield db
    def job(self,job):
        with self._connect() as db:r=db.execute('SELECT * FROM publication_jobs WHERE job_id=?',(job,)).fetchone()
        return dict(r) if r else None
    def jobs(self):
        with self._connect() as db:return [dict(r) for r in db.execute('SELECT * FROM publication_jobs')]
    def setjob(self,job,**kw):
        allowed={'state','next_at','failures','sheet_pending','sheet_attempts','sheet_next','notify_state','notify_attempts','notify_next','notify_id','last_error'}
        if not kw or not set(kw)<=allowed: raise ValueError("Invalid job fields")
        with self._connect() as db:db.execute('UPDATE publication_jobs SET '+','.join(k+'=?' for k in kw)+',updated_at=? WHERE job_id=?',(*kw.values(),m._now(),job))
    def event(self,job,event,detail=''):
        with self._connect() as db:db.execute('INSERT INTO publication_events(job_id,event,detail,created_at) VALUES(?,?,?,?)',(job,event,detail,m._now()))
    def approve(self,job,receipt):
        if receipt.get('source',{}).get('authenticated') is not True: raise Permanent('AUTHENTICATED_APPROVAL_EVIDENCE_REQUIRED')
        require_review_reference(receipt.get('source',{}).get('review_ref'))
        targets=receipt.get('binding',{}).get('targets')
        if not isinstance(targets,list) or not targets or len(set(targets))!=len(targets) or not set(targets)<=set(PLATFORMS): raise Permanent('INVALID_TARGETS')
        fp=digest(receipt['binding']);old=self.job(job)
        if old:
            if self.submission_blocked(job) or old['fingerprint']!=fp or old['state']=='REVOKED':raise Permanent('EXISTING_APPROVAL_CONFLICT_OR_REVOKED')
            return old
        with self._connect() as db:
            db.execute("INSERT INTO publication_jobs(job_id,fingerprint,receipt,state,updated_at) VALUES(?,?,?,'PENDING_APPROVAL_SYNC',?)",(job,fp,canonical(receipt),m._now()))
            for p in receipt['binding']['targets']:db.execute('INSERT INTO publication_operations(job_id,platform) VALUES(?,?)',(job,p))
        self.event(job,'OWNER_APPROVED',fp);return self.job(job)
    def intake(self,job,snapshot,source):
        if self.job(job):return
        with self._connect() as db:
            db.execute("INSERT INTO publication_jobs(job_id,fingerprint,receipt,state,updated_at) VALUES(?,?,?,'AWAITING_SHEET_VALIDATION',?)",(job,digest(snapshot),canonical({'source':source,'local_snapshot':snapshot,'approved_at':m._now()}),m._now()))
        self.event(job,'OWNER_APPROVAL_INTAKE_SHEETS_UNAVAILABLE',digest(snapshot))
    def activate_intake(self,job,receipt):
        with self._connect() as db:
            db.execute("UPDATE publication_jobs SET fingerprint=?,receipt=?,state='PENDING_APPROVAL_SYNC',updated_at=? WHERE job_id=? AND state='AWAITING_SHEET_VALIDATION'",(digest(receipt['binding']),canonical(receipt),m._now(),job))
            for p in receipt['binding']['targets']:db.execute('INSERT OR IGNORE INTO publication_operations(job_id,platform) VALUES(?,?)',(job,p))
    def op(self,job,p):
        with self._connect() as db:r=db.execute('SELECT * FROM publication_operations WHERE job_id=? AND platform=?',(job,p)).fetchone()
        return dict(r) if r else None
    def setop(self,job,p,**kw):
        if not kw or not set(kw)<={'phase','container_id','started_at','tries','next_at','checks'}: raise ValueError('Invalid operation fields')
        with self._connect() as db:db.execute('UPDATE publication_operations SET '+','.join(k+'=?' for k in kw)+' WHERE job_id=? AND platform=?',(*kw.values(),job,p))
    def submission_blocked(self,job):
        with self._connect() as db:
            return bool(db.execute('SELECT 1 FROM publication_owner_actions WHERE job_id=? LIMIT 1',(job,)).fetchone())
    def owner_action(self,job,action,*,platform=None,owner_verified=False,confirmation=None,message_id=None):
        # Trusted inbound owner bridge must verify identity before calling.
        if owner_verified is not True or not message_id or not confirmation:raise Permanent('AUTHENTICATED_OWNER_CONFIRMATION_REQUIRED')
        if action not in {'OWNER_REJECTED','OWNER_DELETED'}:raise Permanent('INVALID_OWNER_ACTION')
        if not self.job(job):raise Permanent('NO_DURABLE_RECEIPT')
        if action=='OWNER_DELETED' and (platform not in PLATFORMS or not self.get(job,platform)):raise Permanent('EXACT_PLATFORM_RECEIPT_REQUIRED')
        evidence=canonical({'message_id':message_id,'confirmation':confirmation,'owner_verified':True})
        with self._connect() as db:
            old=db.execute('SELECT 1 FROM publication_owner_actions WHERE job_id=? AND action=? AND evidence=? AND platform IS ?',(job,action,evidence,platform)).fetchone()
            if not old:db.execute('INSERT INTO publication_owner_actions(job_id,platform,action,evidence,created_at) VALUES(?,?,?,?,?)',(job,platform,action,evidence,m._now()))
            db.execute("UPDATE publication_jobs SET state='REVOKED',last_error=?,sheet_pending=1,updated_at=? WHERE job_id=?",(action,m._now(),job))
        if not old:self.event(job,action,canonical({'platform':platform,'evidence':json.loads(evidence)}))
        return {'job_id':job,'action':action,'platform':platform,'remote_deletion_performed':False}
    def owner_deleted(self,job,platform):
        with self._connect() as db:
            return bool(db.execute("SELECT 1 FROM publication_owner_actions WHERE job_id=? AND platform=? AND action='OWNER_DELETED'",(job,platform)).fetchone())
    def heartbeat(self,value):
        with self._connect() as db:db.execute("INSERT OR REPLACE INTO publication_health VALUES('heartbeat',?)",(canonical(value),))
