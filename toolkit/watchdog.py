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
            if now >= r['deadline_at'] and not r['deadline_alerted']:
                body=f"Task {r['task_id']} exceeded its deadline. Last verified progress: {r['checkpoint'] or 'none recorded'}. No completion was inferred and no external work was repeated."
                alert(db,f"{r['task_id']}:{r['execution_id']}:TASK_STALLED:deadline",r['task_id'],'TASK_STALLED',body,now)
                event(db,r['task_id'],'TASK_STALLED',now,{'reason':'deadline_exceeded','last_progress':r['last_progress']})
                db.execute('UPDATE tasks SET deadline_alerted=1 WHERE task_id=?',(r['task_id'],))
            elif now-r['last_progress'] >= r['stall_seconds'] and not r['stall_alerted']:
                body=f"Task {r['task_id']} has no verified progress for {int(now-r['last_progress'])} seconds. Last checkpoint: {r['checkpoint'] or 'none recorded'}. Execution is not automatically retried."
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


def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('start'); s.add_argument('task_id'); s.add_argument('source'); s.add_argument('execution_id'); s.add_argument('--deadline',type=int,default=3600); s.add_argument('--stall',type=int,default=DEFAULT_STALL)
    s=sub.add_parser('progress'); s.add_argument('task_id'); s.add_argument('checkpoint')
    s=sub.add_parser('complete'); s.add_argument('task_id'); s.add_argument('evidence')
    s=sub.add_parser('fail'); s.add_argument('task_id'); s.add_argument('error'); s.add_argument('--kind',default='TASK_FAILED')
    sub.add_parser('scan'); sub.add_parser('status')
    a=p.parse_args(); db=connect()
    if a.cmd=='start': result=start(db,a.task_id,a.source,a.execution_id,a.deadline,a.stall)
    elif a.cmd=='progress': result=progress(db,a.task_id,a.checkpoint)
    elif a.cmd=='complete': result=finish(db,a.task_id,a.evidence)
    elif a.cmd=='fail': result=fail(db,a.task_id,a.error,a.kind)
    elif a.cmd=='scan': result=scan(db)
    else: result=[dict(r) for r in db.execute('SELECT * FROM tasks ORDER BY updated_at DESC')]
    print(json.dumps(result,sort_keys=True)); db.close()

if __name__=='__main__': main()
