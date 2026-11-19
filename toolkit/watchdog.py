#!/usr/bin/env python3
"""Deterministic task/Gateway watchdog. Never calls an LLM or retries external work."""
import argparse, json, os, socket, sqlite3, subprocess, time
from pathlib import Path

ROOT = Path(os.environ.get('TOOLKIT_STATE_DIR', str(Path.home()/'.local/state/automation-toolkit')))
DATA = ROOT / 'data' / 'task-watchdog'
DB = DATA / 'watchdog.sqlite3'
DEFAULT_STALL = 600


def connect(path=DB):
    Path(path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS tasks(
        task_id TEXT PRIMARY KEY, source TEXT NOT NULL, execution_id TEXT NOT NULL,
        state TEXT NOT NULL, started_at REAL NOT NULL, last_progress REAL NOT NULL,
        deadline_at REAL NOT NULL, stall_seconds INTEGER NOT NULL,
        checkpoint TEXT, error TEXT, updated_at REAL NOT NULL,
        stall_alerted INTEGER NOT NULL DEFAULT 0, deadline_alerted INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS events(
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, kind TEXT NOT NULL,
        observed_at REAL NOT NULL, detail TEXT NOT NULL, dedupe_key TEXT UNIQUE);
      CREATE TABLE IF NOT EXISTS alerts(
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
        task_id TEXT, kind TEXT NOT NULL, body TEXT NOT NULL,
        created_at REAL NOT NULL, state TEXT NOT NULL DEFAULT 'PENDING');
      CREATE TABLE IF NOT EXISTS health(
        name TEXT PRIMARY KEY, state TEXT NOT NULL, checked_at REAL NOT NULL, detail TEXT NOT NULL);
    ''')
    return db


def alert(db, key, task_id, kind, body, now):
    db.execute('INSERT OR IGNORE INTO alerts(event_key,task_id,kind,body,created_at) VALUES(?,?,?,?,?)',
               (key, task_id, kind, body, now))


def event(db, task_id, kind, now, detail, dedupe=None):
    db.execute('INSERT OR IGNORE INTO events(task_id,kind,observed_at,detail,dedupe_key) VALUES(?,?,?,?,?)',
               (task_id, kind, now, json.dumps(detail, sort_keys=True), dedupe))


def start(db, task_id, source, execution_id, deadline_seconds, stall_seconds=DEFAULT_STALL, now=None):
    now = time.time() if now is None else float(now)
    if not task_id or not source or not execution_id or int(deadline_seconds) <= 0:
        raise ValueError('task_id, source, execution_id and positive deadline_seconds are required')
    with db:
        row = db.execute('SELECT state,execution_id FROM tasks WHERE task_id=?', (task_id,)).fetchone()
        if row and row['state'] == 'RUNNING':
            if row['execution_id'] == execution_id:
                return False
            raise ValueError('task_id already has a running execution')
        db.execute('''INSERT INTO tasks(task_id,source,execution_id,state,started_at,last_progress,
          deadline_at,stall_seconds,updated_at,checkpoint,error,stall_alerted,deadline_alerted)
          VALUES(?,?,?,'RUNNING',?,?,?,?,?,NULL,NULL,0,0)
          ON CONFLICT(task_id) DO UPDATE SET source=excluded.source,execution_id=excluded.execution_id,
          state='RUNNING',started_at=excluded.started_at,last_progress=excluded.last_progress,
          deadline_at=excluded.deadline_at,stall_seconds=excluded.stall_seconds,updated_at=excluded.updated_at,
          checkpoint=NULL,error=NULL,stall_alerted=0,deadline_alerted=0''',
          (task_id, source, execution_id, now, now, now+int(deadline_seconds), int(stall_seconds), now))
        event(db, task_id, 'TASK_STARTED', now, {'source':source,'execution_id':execution_id})
        alert(db, f'{task_id}:{execution_id}:TASK_STARTED', task_id, 'TASK_STARTED',
              f'Task {task_id} started via {source}; execution {execution_id}.', now)
    return True


def progress(db, task_id, checkpoint, now=None):
    now = time.time() if now is None else float(now)
    if not checkpoint or len(checkpoint) > 2000:
        raise ValueError('a bounded verified checkpoint is required')
    with db:
        row = db.execute('SELECT * FROM tasks WHERE task_id=?', (task_id,)).fetchone()
        if not row or row['state'] != 'RUNNING':
            raise ValueError('no running task')
        db.execute('UPDATE tasks SET last_progress=?,checkpoint=?,updated_at=?,stall_alerted=0 WHERE task_id=?',
                   (now, checkpoint, now, task_id))
        event(db, task_id, 'TASK_PROGRESS', now, {'checkpoint':checkpoint})
    return True


def finish(db, task_id, evidence, now=None):
    now = time.time() if now is None else float(now)
    if not evidence or len(evidence) > 2000:
        raise ValueError('verified completion evidence is required')
    with db:
        row = db.execute('SELECT * FROM tasks WHERE task_id=?', (task_id,)).fetchone()
        if not row or row['state'] != 'RUNNING':
            raise ValueError('no running task')
        db.execute("UPDATE tasks SET state='COMPLETED',last_progress=?,checkpoint=?,updated_at=? WHERE task_id=?",
                   (now, evidence, now, task_id))
        event(db, task_id, 'TASK_COMPLETED', now, {'evidence':evidence})
        alert(db, f"{task_id}:{row['execution_id']}:TASK_COMPLETED", task_id, 'TASK_COMPLETED',
              f'Task {task_id} execution ended. Recorded evidence (not independent verification): {evidence}', now)
    return True


def fail(db, task_id, error, kind='TASK_FAILED', now=None):
    now = time.time() if now is None else float(now)
    if kind not in {'TASK_FAILED','API_RATE_LIMITED','API_QUOTA_EXHAUSTED','MODEL_FALLBACK_FAILED'}:
        raise ValueError('unsupported failure kind')
    error = (str(error).strip() or 'Observed failure; specific cause unavailable.')[:2000]
    with db:
        row = db.execute('SELECT * FROM tasks WHERE task_id=?', (task_id,)).fetchone()
        if not row:
            raise ValueError('unknown task')
        db.execute("UPDATE tasks SET state='FAILED',error=?,updated_at=? WHERE task_id=?", (error,now,task_id))
        event(db, task_id, kind, now, {'error':error})
        alert(db, f"{task_id}:{row['execution_id']}:{kind}:{error}", task_id, kind,
              f'Task {task_id}: {kind}. Last verified progress: {row["checkpoint"] or "none recorded"}. Observed error: {error}. No external operation was retried.', now)
    return True


def check_gateway(db, now=None, connect_fn=None):
    now = time.time() if now is None else float(now)
    if connect_fn is None:
        def connect_fn():
            host=os.environ.get('TOOLKIT_GATEWAY_HOST')
            if not host: raise ValueError('Explicit gateway host required')
            with socket.create_connection((host,int(os.environ.get('TOOLKIT_GATEWAY_PORT','18789'))),timeout=2):
                return True
    try:
        connect_fn(); connected=True; detail='configured endpoint accepted TCP connection'
    except Exception as exc:
        connected=False; detail=type(exc).__name__
    with db:
        old=db.execute("SELECT state FROM health WHERE name='gateway'").fetchone()
        previous=old['state'] if old else None
        if connected:
            state='RECOVERING' if previous=='UNAVAILABLE' else 'HEALTHY'
            if previous=='RECOVERING':
                state='HEALTHY'
                event(db,None,'SERVICE_RECOVERED',now,{'service':'gateway','note':'health recovered; task completion not inferred'})
                alert(db,'gateway:recovered:'+str(int(now)),None,'SERVICE_RECOVERED','Gateway connectivity recovered after two successful checks. This does not declare any task complete.',now)
        else:
            state='UNAVAILABLE' if previous in ('SUSPECT','UNAVAILABLE','RECOVERING') else 'SUSPECT'
            if previous=='SUSPECT':
                event(db,None,'GATEWAY_UNAVAILABLE',now,{'error':detail})
                alert(db,'gateway:unavailable:'+str(int(now)),None,'GATEWAY_UNAVAILABLE',f'Gateway health check failed twice: {detail}. Next action: inspect Gateway service and logs.',now)
        db.execute('INSERT INTO health(name,state,checked_at,detail) VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET state=excluded.state,checked_at=excluded.checked_at,detail=excluded.detail',('gateway',state,now,detail))
    return state


def scan(db, now=None, connect_fn=None):
    now=time.time() if now is None else float(now)
    gateway=check_gateway(db,now,connect_fn)
    with db:
        rows=db.execute("SELECT * FROM tasks WHERE state='RUNNING'").fetchall()
        for r in rows:
            native = r['source'] == 'openclaw-native'
            checkpoint_label = 'Last observed runtime activity' if native else 'Last verified progress'
            progress_label = 'observed runtime activity' if native else 'verified progress'
            if now >= r['deadline_at'] and not r['deadline_alerted']:
                body=f"Task {r['task_id']} exceeded its deadline. {checkpoint_label}: {r['checkpoint'] or 'none recorded'}. No completion was inferred and no external work was repeated."
                alert(db,f"{r['task_id']}:{r['execution_id']}:TASK_STALLED:deadline",r['task_id'],'TASK_STALLED',body,now)
                event(db,r['task_id'],'TASK_STALLED',now,{'reason':'deadline_exceeded','last_progress':r['last_progress']})
                db.execute('UPDATE tasks SET deadline_alerted=1 WHERE task_id=?',(r['task_id'],))
            elif now-r['last_progress'] >= r['stall_seconds'] and not r['stall_alerted']:
                body=f"Task {r['task_id']} has no {progress_label} for {int(now-r['last_progress'])} seconds. Last checkpoint: {r['checkpoint'] or 'none recorded'}. Execution is not automatically retried."
                alert(db,f"{r['task_id']}:{r['execution_id']}:TASK_STALLED:progress:{int(r['last_progress'])}",r['task_id'],'TASK_STALLED',body,now)
                event(db,r['task_id'],'TASK_STALLED',now,{'reason':'progress_timeout','last_progress':r['last_progress']})
                db.execute('UPDATE tasks SET stall_alerted=1 WHERE task_id=?',(r['task_id'],))
    return {'gateway':gateway,'tracked_tasks':len(rows),'pending_alerts':db.execute("SELECT count(*) FROM alerts WHERE state='PENDING'").fetchone()[0]}


def scan_customer_failures(db, source, now=None):
    """Queue one staff alert per unresolved inquiry; never sends to a customer."""
    now=time.time() if now is None else now
    customer_db=sqlite3.connect(f'file:{source}?mode=ro', uri=True)
    customer_db.row_factory=sqlite3.Row
    try:
        columns={r[1] for r in customer_db.execute('PRAGMA table_info(inquiries)')}
        customer='i.customer' if 'customer' in columns else 'NULL'
        inbound='i.inbound_message_id' if 'inbound_message_id' in columns else 'NULL'
        rows=customer_db.execute(f'''SELECT i.id,i.error,i.updated,{customer} customer,
            {inbound} inbound_message_id,d.customer delivery_customer,d.status delivery_status,d.error delivery_error
            FROM inquiries i LEFT JOIN deliveries d ON d.turn_id=i.id
            WHERE i.status='needs_staff' ORDER BY i.updated''').fetchall()
    finally:
        customer_db.close()
    with db:
        db.execute('''CREATE TABLE IF NOT EXISTS customer_identity_review(
            inquiry_id TEXT PRIMARY KEY, reason TEXT NOT NULL, observed_at REAL NOT NULL)''')
        for row in rows:
            detail={'customer':row['customer'] or row['delivery_customer'] or 'UNKNOWN',
                    'inbound_message_id':row['inbound_message_id'] or 'UNKNOWN',
                    'inquiry_id':row['id'], 'error':row['error'] or 'UNKNOWN',
                    'delivery_status':row['delivery_status'] or 'NO_DELIVERY_RECORD',
                    'delivery_error':row['delivery_error'] or '',
                    'observed_at':row['updated'] / 1000 if row['updated'] > 100000000000 else row['updated']}
            if detail['customer']=='UNKNOWN' or detail['inbound_message_id']=='UNKNOWN':
                db.execute('INSERT OR IGNORE INTO customer_identity_review VALUES(?,?,?)',
                           (row['id'],'HISTORICAL_INBOUND_IDENTITY_UNAVAILABLE',now))
                continue
            alert(db,'customer-needs-staff:'+row['id'],None,'CUSTOMER_NEEDS_STAFF',json.dumps(detail,sort_keys=True),now)
    return len(rows)



def ingest_runtime(db, incoming, allowed_agents, now=None, max_age_seconds=300):
    """Trusted local SDK metadata only, not an HTTP/customer event intake.

    Runtime completion is NOT business-result or delivery verification. Retained
    run/event tombstones prevent duplicate and retired-execution resurrection.
    """
    import hashlib, math
    if db.in_transaction:
        raise ValueError('runtime ingestion owns its transaction')
    now = time.time() if now is None else float(now)
    if not isinstance(incoming, dict) or not allowed_agents:
        raise ValueError('explicit trusted event and agent allowlist required')
    def identity(name):
        value = incoming.get(name)
        if not isinstance(value, str) or not 0 < len(value) <= 256 or any(ord(c) < 32 for c in value):
            raise ValueError('missing bounded runtime identity: ' + name)
        return value
    agent, session, session_id, run = [identity(k) for k in ('agentId','sessionKey','sessionId','runId')]
    if agent not in allowed_agents or not session.startswith('agent:' + agent + ':'):
        raise ValueError('runtime agent/session not admitted')
    seq, ts, stream = incoming.get('seq'), incoming.get('ts'), incoming.get('stream')
    if type(seq) is not int or not 0 < seq <= 9007199254740991:
        raise ValueError('positive runtime sequence required')
    if type(ts) not in (int, float) or not math.isfinite(ts) or ts <= 0 or ts / 1000 > now + 30:
        raise ValueError('invalid runtime timestamp')
    raw = incoming.get('data')
    if not isinstance(raw, dict) or stream not in ('lifecycle', 'tool'):
        raise ValueError('unsupported runtime event')
    phase = raw.get('phase')
    if phase not in ('start','end','error','fallback','fallback_cleared'):
        return {'status':'IGNORED'}
    if stream == 'tool' and phase != 'end':
        return {'status':'IGNORED'}
    # Do not persist arbitrary tool/error/model output. Retain bounded metadata.
    data = {'phase':phase}
    for k in ('executionSettled','fallbackExhaustedFailure','aborted'):
        if k in raw:
            if type(raw[k]) is not bool: raise ValueError('invalid runtime boolean')
            data[k] = raw[k]
    for k in ('startedAt','endedAt'):
        if k in raw:
            if type(raw[k]) not in (int,float) or not math.isfinite(raw[k]) or raw[k] <= 0:
                raise ValueError('invalid producer timestamp')
            data[k] = raw[k]
    for k in ('status','stopReason','timeoutPhase','livenessState'):
        if k in raw:
            if not isinstance(raw[k],str) or len(raw[k]) > 100 or any(ord(c)<32 for c in raw[k]):
                raise ValueError('invalid runtime label')
            data[k] = raw[k]
    if stream == 'lifecycle' and phase == 'start' and 'startedAt' not in data:
        raise ValueError('producer start timestamp required')
    normalized = dict(agentId=agent, sessionKey=session, sessionId=session_id, runId=run,
                      seq=seq, ts=ts, stream=stream, data=data)
    digest = hashlib.sha256(json.dumps(normalized,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    task = 'native:' + hashlib.sha256(json.dumps([agent,session]).encode()).hexdigest()
    stamp = ts / 1000
    db.executescript('''
      CREATE TABLE IF NOT EXISTS runtime_runs(
        run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, session_id TEXT NOT NULL,
        started_at REAL NOT NULL, last_seq INTEGER NOT NULL, last_ts REAL NOT NULL,
        state TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS runtime_events(
        run_id TEXT NOT NULL, seq INTEGER NOT NULL, digest TEXT NOT NULL,
        disposition TEXT NOT NULL, observed_at REAL NOT NULL, PRIMARY KEY(run_id,seq));
    ''')
    with db:
        db.execute('BEGIN IMMEDIATE')
        prior=db.execute('SELECT digest,disposition FROM runtime_events WHERE run_id=? AND seq=?',(run,seq)).fetchone()
        if prior:
            if prior['digest'] != digest: raise ValueError('runtime event identity conflict')
            return {'status':'DUPLICATE','original_status':prior['disposition']}
        def result(status):
            db.execute('INSERT INTO runtime_events VALUES(?,?,?,?,?)',(run,seq,digest,status,now))
            return {'status':status,'task_id':task,'execution_id':run}
        current=db.execute('SELECT * FROM tasks WHERE task_id=?',(task,)).fetchone()
        known=db.execute('SELECT * FROM runtime_runs WHERE run_id=?',(run,)).fetchone()
        if known and (known['task_id'] != task or known['session_id'] != session_id):
            raise ValueError('runtime execution identity conflict')
        if now - stamp > max_age_seconds:
            return result('STALE_EVENT')
        if stream == 'lifecycle' and phase == 'start':
            started=data['startedAt']/1000
            if started > stamp + 30 or now - started > max_age_seconds:
                return result('STALE_START')
            if known: return result('RETIRED_OR_DUPLICATE_START')
            if current and started <= current['started_at']:
                return result('STALE_EXECUTION')
            if current and current['state'] == 'RUNNING':
                db.execute("UPDATE runtime_runs SET state='SUPERSEDED' WHERE run_id=?",(current['execution_id'],))
                alert(db,task+':'+current['execution_id']+':SUPERSEDED',task,'RUNTIME_SUPERSEDED',
                      'A newer native run superseded monitoring of this execution. No business completion inferred.',now)
            db.execute('''INSERT INTO tasks(task_id,source,execution_id,state,started_at,last_progress,
              deadline_at,stall_seconds,updated_at,checkpoint,error,stall_alerted,deadline_alerted)
              VALUES(?, 'openclaw-native', ?, 'RUNNING', ?, ?, ?, 600, ?, ?, NULL, 0, 0)
              ON CONFLICT(task_id) DO UPDATE SET source=excluded.source,execution_id=excluded.execution_id,
              state='RUNNING',started_at=excluded.started_at,last_progress=excluded.last_progress,
              deadline_at=excluded.deadline_at,stall_seconds=excluded.stall_seconds,updated_at=excluded.updated_at,
              checkpoint=excluded.checkpoint,error=NULL,stall_alerted=0,deadline_alerted=0''',
              (task,run,started,stamp,started+3600,now,'Native run started; business outcome unverified.'))
            db.execute('INSERT INTO runtime_runs VALUES(?,?,?,?,?,?,?)',(run,task,session_id,started,seq,stamp,'RUNNING'))
            event(db,task,'RUNTIME_STARTED',now,{'execution_id':run},run+':start')
            alert(db,run+':RUNTIME_STARTED',task,'RUNTIME_STARTED','Native run started; no business success inferred.',now)
            return result('STARTED')
        if not known or not current: return result('UNKNOWN_EXECUTION')
        if current['execution_id'] != run or known['state'] != 'RUNNING' or current['state'] != 'RUNNING':
            return result('STALE_EXECUTION')
        if seq <= known['last_seq'] or stamp < known['last_ts']:
            return result('OUT_OF_ORDER')
        db.execute('UPDATE runtime_runs SET last_seq=?,last_ts=? WHERE run_id=?',(seq,stamp,run))
        # Attempt errors may be followed by successful fallback. Never end the
        # whole run on an unsettled generic error or an individual tool failure.
        failed = (phase == 'error' or data.get('status') in ('error','failed','timeout','aborted','cancelled','canceled','superseded')
                  or data.get('aborted') is True or data.get('stopReason') in ('timeout','aborted','restart','superseded','stop','rpc','error')
                  or data.get('livenessState') in ('blocked','abandoned') or bool(data.get('timeoutPhase')))
        terminal = stream == 'lifecycle' and (phase == 'end' or (phase == 'error' and
                   (data.get('executionSettled') is True or data.get('fallbackExhaustedFailure') is True)))
        if terminal:
            state='FAILED' if failed else 'COMPLETED'
            note='Native execution failed.' if failed else 'Native execution ended; business outcome and delivery are NOT verified.'
            db.execute('UPDATE tasks SET state=?,last_progress=?,checkpoint=?,error=?,updated_at=? WHERE task_id=?',
                       (state,stamp,note,note if failed else None,now,task))
            db.execute('UPDATE runtime_runs SET state=? WHERE run_id=?',(state,run))
            kind='RUNTIME_FAILED' if failed else 'RUNTIME_ENDED'
            event(db,task,kind,now,{'execution_id':run},run+':terminal')
            alert(db,run+':terminal',task,kind,note,now)
            return result(state)
        note='Native '+stream+' '+phase+' observed; activity is not verified business progress.'
        db.execute('UPDATE tasks SET last_progress=?,checkpoint=?,updated_at=?,stall_alerted=0 WHERE task_id=?',(stamp,note,now,task))
        event(db,task,'RUNTIME_ACTIVITY',now,{'execution_id':run,'stream':stream,'phase':phase},run+':'+str(seq))
        return result('ACTIVITY')


def private_runtime_database(path):
    """Reject non-private/symlink state before CLI native ingestion."""
    import stat
    path=Path(path)
    if not path.is_absolute(): raise ValueError('absolute private database required')
    parent=path.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o077:
        raise ValueError('private state parent required')
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        os.close(fd)
    except FileExistsError: pass
    st=path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ValueError('private state database required')
    return path


def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('start'); s.add_argument('task_id'); s.add_argument('source'); s.add_argument('execution_id'); s.add_argument('--deadline',type=int,default=3600); s.add_argument('--stall',type=int,default=DEFAULT_STALL)
    s=sub.add_parser('progress'); s.add_argument('task_id'); s.add_argument('checkpoint')
    s=sub.add_parser('complete'); s.add_argument('task_id'); s.add_argument('evidence')
    s=sub.add_parser('fail'); s.add_argument('task_id'); s.add_argument('error'); s.add_argument('--kind',default='TASK_FAILED')
    s=sub.add_parser('ingest-runtime'); s.add_argument('--database',required=True); s.add_argument('--allowed-agent',action='append',required=True)
    sub.add_parser('scan'); sub.add_parser('status')
    a=p.parse_args()
    if a.cmd=='ingest-runtime':
        import sys
        raw=sys.stdin.read(16385)
        if len(raw)>16384: raise ValueError('runtime event too large')
        db=connect(private_runtime_database(a.database))
        try: print(json.dumps(ingest_runtime(db,json.loads(raw),a.allowed_agent),sort_keys=True))
        finally: db.close()
        return
    db=connect()
    if a.cmd=='start': result=start(db,a.task_id,a.source,a.execution_id,a.deadline,a.stall)
    elif a.cmd=='progress': result=progress(db,a.task_id,a.checkpoint)
    elif a.cmd=='complete': result=finish(db,a.task_id,a.evidence)
    elif a.cmd=='fail': result=fail(db,a.task_id,a.error,a.kind)
    elif a.cmd=='scan': result=scan(db)
    else: result=[dict(r) for r in db.execute('SELECT * FROM tasks ORDER BY updated_at DESC')]
    print(json.dumps(result,sort_keys=True)); db.close()

if __name__=='__main__': main()
