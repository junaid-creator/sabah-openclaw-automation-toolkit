"""Durable, per-channel delivery for Toolkit publication_outbox events.

All sends use a caller-provided authenticated transport callback. This
module never stores channel credentials and never retries an ambiguous send.
"""
from __future__ import annotations
import json, os, re, sqlite3, subprocess, time
from pathlib import Path

CHANNELS = {"whatsapp": os.environ.get("TOOLKIT_WHATSAPP_ACCOUNT", "default"), "telegram": os.environ.get("TOOLKIT_TELEGRAM_ACCOUNT", "default")}
MAX_ATTEMPTS = 5
LEASE_SECONDS = 120

DDL = """
CREATE TABLE IF NOT EXISTS publication_notification_delivery (
 event_id TEXT NOT NULL, channel TEXT NOT NULL, account_id TEXT NOT NULL,
 recipient TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 next_at REAL NOT NULL DEFAULT 0, claimed_at REAL, message_id TEXT, receipt TEXT,
 last_error TEXT, updated_at REAL NOT NULL,
 PRIMARY KEY(event_id, channel, account_id, recipient));
CREATE TABLE IF NOT EXISTS publication_notification_attempts (
 event_id TEXT, channel TEXT, attempt INTEGER, state TEXT, receipt TEXT, error TEXT, updated_at REAL,
 PRIMARY KEY(event_id,channel,attempt));
CREATE TABLE IF NOT EXISTS publication_notification_suppression (
 event_id TEXT PRIMARY KEY, reason TEXT NOT NULL, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_notification_delivery_due
 ON publication_notification_delivery(state,next_at);
"""

def ensure_schema(ledger):
    from .schedule_core import schema as publication_schema
    with ledger._connect() as db:
        publication_schema(db)
        db.executescript(DDL)


def ensure_deliveries(ledger, targets, now=None):
    now=time.time() if now is None else now
    ensure_schema(ledger)
    with ledger._connect() as db:
        rows=db.execute("SELECT event_id FROM publication_outbox WHERE event_id NOT IN (SELECT event_id FROM publication_notification_suppression)").fetchall()
        for row in rows:
            for channel,account in CHANNELS.items():
                target=targets.get(channel,{})
                recipient=target.get("recipient","") if target.get("account")==account else ""
                error=None if recipient else "AUTHORIZED_RECIPIENT_NOT_CONFIGURED_OR_AMBIGUOUS"
                if recipient:
                    db.execute("DELETE FROM publication_notification_delivery WHERE event_id=? AND channel=? AND account_id=? AND recipient='' AND state='BLOCKED' AND attempts=0 AND EXISTS (SELECT 1 FROM publication_notification_delivery WHERE event_id=? AND channel=? AND account_id=? AND recipient=?)",(row["event_id"],channel,account,row["event_id"],channel,account,recipient))
                    db.execute("UPDATE publication_notification_delivery SET recipient=?,state='PENDING',last_error=NULL,updated_at=? WHERE event_id=? AND channel=? AND account_id=? AND recipient='' AND state='BLOCKED' AND attempts=0",(recipient,now,row["event_id"],channel,account))
                    db.execute("UPDATE publication_notification_delivery SET state='PENDING',last_error=NULL,updated_at=? WHERE event_id=? AND channel=? AND account_id=? AND recipient=? AND state='BLOCKED' AND attempts=0",(now,row["event_id"],channel,account,recipient))
                else:
                    db.execute("UPDATE publication_notification_delivery SET state='BLOCKED',last_error=?,updated_at=? WHERE event_id=? AND channel=? AND account_id=? AND state IN ('PENDING','RETRY') AND attempts=0",(error,now,row["event_id"],channel,account))
                state="PENDING" if recipient else "BLOCKED"
                db.execute("INSERT OR IGNORE INTO publication_notification_delivery(event_id,channel,account_id,recipient,state,last_error,updated_at) VALUES(?,?,?,?,?,?,?)",(row["event_id"],channel,account,recipient,state,error,now))


def _aggregate(db,event_id):
    states=[r[0] for r in db.execute("SELECT state FROM publication_notification_delivery WHERE event_id=?",(event_id,))]
    if states and all(s=="SENT" for s in states): state="SENT"
    elif "UNKNOWN" in states: state="UNKNOWN"
    elif "SENDING" in states: state="SENDING"
    elif any(s in {"PENDING","RETRY"} for s in states): state="PENDING"
    elif "BLOCKED" in states: state="BLOCKED"
    elif "EXHAUSTED" in states: state="EXHAUSTED"
    else: state="FAILED"
    db.execute("UPDATE publication_outbox SET state=? WHERE event_id=?",(state,event_id))


def claim_delivery(ledger,event_id,channel,*,now=None,max_attempts=MAX_ATTEMPTS,lease_seconds=LEASE_SECONDS):
    now=time.time() if now is None else now
    if channel not in CHANNELS: raise ValueError("unsupported notification channel")
    with ledger._connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if str(event_id).startswith('owner-summary:'):
            from datetime import datetime
            from zoneinfo import ZoneInfo
            day=datetime.fromtimestamp(now,ZoneInfo(os.environ.get('TOOLKIT_TIMEZONE','UTC'))).date().isoformat()
            if event_id!='owner-summary:'+day:
                db.execute('INSERT OR IGNORE INTO publication_notification_suppression VALUES(?,?,?)',(event_id,'EXPIRED_DAILY_SUMMARY_NO_REPLAY',now))
                return None
        if db.execute("SELECT 1 FROM publication_notification_suppression WHERE event_id=?",(event_id,)).fetchone(): return None
        db.execute("UPDATE publication_notification_delivery SET state='UNKNOWN',last_error='SEND_LEASE_EXPIRED_OUTCOME_UNKNOWN',updated_at=? WHERE event_id=? AND channel=? AND state='SENDING' AND claimed_at<=?",(now,event_id,channel,now-lease_seconds))
        db.execute("UPDATE publication_notification_delivery SET state='EXHAUSTED',last_error='RETRY_LIMIT_REACHED',updated_at=? WHERE event_id=? AND channel=? AND state='RETRY' AND attempts>=?",(now,event_id,channel,max_attempts))
        row=db.execute("SELECT * FROM publication_notification_delivery WHERE event_id=? AND channel=? AND state IN ('PENDING','RETRY') AND next_at<=? AND attempts<? ORDER BY updated_at LIMIT 1",(event_id,channel,now,max_attempts)).fetchone()
        if not row: _aggregate(db,event_id); return None
        db.execute("UPDATE publication_notification_delivery SET state='SENDING',attempts=attempts+1,claimed_at=?,updated_at=?,last_error=NULL WHERE event_id=? AND channel=? AND account_id=? AND recipient=?",(now,now,event_id,channel,row['account_id'],row['recipient']))
        claimed=dict(db.execute("SELECT * FROM publication_notification_delivery WHERE event_id=? AND channel=? AND account_id=? AND recipient=?",(event_id,channel,row['account_id'],row['recipient'])).fetchone())
        db.execute("INSERT OR REPLACE INTO publication_notification_attempts VALUES(?,?,?,?,?,?,?)",(event_id,channel,claimed["attempts"],"SENDING",None,None,now))
        _aggregate(db,event_id)
        return claimed

def record_delivery(ledger,delivery,result,*,now=None,max_attempts=MAX_ATTEMPTS):
    now=time.time() if now is None else now
    event_id,channel,account,recipient=(delivery[k] for k in ('event_id','channel','account_id','recipient'))
    result=result if isinstance(result,dict) else {"error":"INVALID_SENDER_RESULT","ambiguous":True}
    exact=(result.get("channel")==channel and result.get("account")==account and result.get("recipient")==recipient)
    delivered=bool(result.get("delivered") is True and result.get("messageId") and exact and not result.get("dryRun"))
    if delivered: state="SENT"; error=None
    elif result.get("ambiguous"): state="UNKNOWN"; error=str(result.get("error") or "DELIVERY_OUTCOME_UNKNOWN")
    elif result.get("retryable"):
        # A failed external send can still have side effects. Staff alerts also
        # require a verified not-sent outcome before any manual resend.
        state="UNKNOWN" if str(event_id).startswith('watchdog:') else ("RETRY" if delivery["attempts"]<max_attempts else "EXHAUSTED")
        error=str(result.get("error") or "TEMPORARY_DELIVERY_FAILURE")
    elif result.get("blocked"): state="BLOCKED"; error=str(result.get("error") or "DELIVERY_BLOCKED")
    else: state="FAILED"; error=str(result.get("error") or "DELIVERY_FAILED_OR_RECEIPT_INVALID")
    delay=min(3600,30*(2**max(0,delivery["attempts"]-1))) if state=="RETRY" else 0
    receipt=json.dumps(result,sort_keys=True,separators=(",",":"))
    with ledger._connect() as db:
        current=db.execute("SELECT attempts,state FROM publication_notification_delivery WHERE event_id=? AND channel=? AND account_id=? AND recipient=?",(event_id,channel,account,recipient)).fetchone()
        if not current or current["state"]!="SENDING" or current["attempts"]!=delivery["attempts"]:raise ValueError("STALE_DELIVERY_CLAIM")
        db.execute("INSERT OR REPLACE INTO publication_notification_attempts VALUES(?,?,?,?,?,?,?)",(event_id,channel,delivery["attempts"],state,receipt,error,now))
        db.execute("UPDATE publication_notification_delivery SET state=?,next_at=?,claimed_at=NULL,message_id=?,receipt=?,last_error=?,updated_at=? WHERE event_id=? AND channel=? AND account_id=? AND recipient=? AND state='SENDING'",(state,now+delay,result.get("messageId") if delivered else None,receipt,error,now,event_id,channel,account,recipient))
        _aggregate(db,event_id)
    if state=="EXHAUSTED":
        with ledger._connect() as db:
            parent=db.execute("SELECT job_id,kind FROM publication_outbox WHERE event_id=?",(event_id,)).fetchone()
        if parent and parent["kind"]!="NOTIFICATION_RETRY_EXHAUSTED":
            emit_job_event(ledger,parent["job_id"],"NOTIFICATION_RETRY_EXHAUSTED",{"channel":channel,"source_event":event_id})
    return state

def _message(event):
    if str(event.get('event_id','')).startswith('owner-summary:') and event.get('kind')=='DAILY_SUMMARY':
        return json.loads(event['payload'])['body']
    if str(event.get('event_id','')).startswith('watchdog:'):
        payload=json.loads(event["payload"])
        return str(payload.get("body") or payload.get("reason") or "Staff review required")
    payload=json.loads(event["payload"] or "{}")
    if isinstance(payload.get("daily"),dict):
        daily=payload["daily"];lines=[f"DAILY SOCIAL POST — {daily['uae_date']}",
                                   f"Product: {daily['product_name']}",
                                   f"Template: Template {daily['template_number']}"]
        for platform in ("facebook","instagram","tiktok"):
            row=payload.get("platforms",{}).get(platform,{})
            status=row.get("report_status","PROCESSING")
            line=("TikTok" if platform=="tiktok" else platform.capitalize())+": "+status
            if status=="VERIFIED" and row.get("permalink"):line+=" — "+row["permalink"]
            elif row.get("error_code"):line+=" — "+row["error_code"].replace("_"," ").lower()
            lines.append(line)
        if payload.get("reason"):lines.append("Action: "+str(payload["reason"]))
        skipped_products=daily.get('skipped_products') or []
        for skipped in skipped_products[:5]:
            lines.append('Skipped product '+str(skipped['product_id'])+' — '+str(skipped['reason'])+
                         '; replacement '+str(skipped['replacement_product_id']))
        if len(skipped_products)>5:
            lines.append('Additional ineligible products skipped: '+str(len(skipped_products)-5)+
                         '; full list retained in daily ledger')
        nxt=daily.get("next") or {}
        if nxt.get("product_name"):lines.append("Next product: "+nxt["product_name"])
        if nxt.get("template_number"):lines.append("Next template: Template "+str(nxt["template_number"]))
        return "\n".join(lines)
    kind=str(event["kind"] or "UPDATE").upper()
    job=event["job_id"]
    reason=payload.get("reason") or payload.get("status") or ""
    lines=[f"Toolkit {job}: {payload.get('health') or kind}"]
    for platform,row in payload.get('platforms',{}).items():
        status=row.get('report_status','PROCESSING')
        line=f"{platform.capitalize()}: {status}"
        if status=='VERIFIED' and row.get('permalink'):line+=' — '+row['permalink']
        elif row.get('error_code'):line+=' — '+row['error_code'].replace('_',' ').lower()
        lines.append(line)
    if reason and not payload.get('platforms'):lines.append(str(reason))
    return "\n".join(lines)

def _find_message_id(value):
    if isinstance(value,dict):
        for key in ("messageId","message_id"):
            if value.get(key): return str(value[key])
        for child in value.values():
            found=_find_message_id(child)
            if found:return found
    if isinstance(value,list):
        for child in value:
            found=_find_message_id(child)
            if found:return found
    return None


def drain(ledger,targets,*,sender,now=None,max_attempts=MAX_ATTEMPTS,max_deliveries=None):
    if not isinstance(targets,dict) or not callable(sender): raise ValueError("Explicit trusted targets and sender required")
    ensure_deliveries(ledger,targets,now=now)
    results=[]
    with ledger._connect() as db: events=[dict(r) for r in db.execute("SELECT * FROM publication_outbox WHERE state!='SENT' AND event_id NOT IN (SELECT event_id FROM publication_notification_suppression) ORDER BY created_at")]
    for event in events:
        for channel in CHANNELS:
            if max_deliveries is not None and len(results)>=max_deliveries: return results
            delivery=claim_delivery(ledger,event["event_id"],channel,now=now,max_attempts=max_attempts)
            if delivery is None:continue
            message=_message(event)
            try: result=sender(channel,delivery["account_id"],delivery["recipient"],message)
            except Exception as exc: result={"ambiguous":True,"error":"SENDER_RAISED_AFTER_CLAIM","detail":type(exc).__name__,"channel":channel,"account":delivery["account_id"],"recipient":delivery["recipient"]}
            status=record_delivery(ledger,delivery,result,now=now,max_attempts=max_attempts)
            results.append({"event_id":event["event_id"],"channel":channel,"state":status})
    return results


def emit_job_event(ledger,job_id,kind,payload):
    """Create an idempotent result/blocked/approval alert in the durable outbox."""
    from .schedule_core import schema
    body=json.dumps(payload,sort_keys=True,separators=(",",":"))
    key=__import__("hashlib").sha256((str(kind)+chr(0)+body).encode()).hexdigest()
    event_id=f"{job_id}:status:{key}"
    now=time.time()
    with ledger._connect() as db:
        schema(db)
        db.execute("INSERT OR IGNORE INTO publication_outbox(event_id,job_id,kind,payload,created_at) VALUES(?,?,?,?,?)",(event_id,job_id,kind,body,now))
    return event_id


def job_snapshot(ledger,job):
    """Stable owner-facing evidence; excludes changing retry timestamps and counters."""
    from .approval_ledger import report_status
    saved=ledger.job(job)
    receipt=json.loads(saved['receipt'])
    targets=receipt.get('binding',receipt.get('local_snapshot',{})).get('targets',[])
    platforms={}
    for p in targets:
        row=ledger.get(job,p) or {}
        platforms[p]={k:row.get(k) for k in ('state','remote_id','permalink','error_code')}
        platforms[p]['report_status']=report_status(row or None)
        if row.get('error_code')=='TIKTOK_VIDEO_LIST_PERMISSION_REQUIRED':platforms[p]['report_status']='NEEDS_ACTION'
    statuses=[r['report_status'] for r in platforms.values()]
    if any(s in {'FAILED','NEEDS_ACTION'} for s in statuses):health='NEEDS_ACTION'
    elif statuses and all(s=='VERIFIED' for s in statuses):health='VERIFIED'
    elif saved['state'] in {'REVIEW_REQUIRED','REVOKED'}:health='NEEDS_ACTION'
    else:health='PROCESSING'
    result={'status':saved['state'],'health':health,'platforms':platforms,'reason':saved.get('last_error') or ''}
    source=receipt.get('source') or {}
    if isinstance(source,dict) and source.get('kind')=='DAILY_SERIES':
        from .product_rotation import assignment,next_expected,skips,SERIES
        row=assignment(ledger.database_path,source.get('uae_date',''))
        if row and row['job_id']==job and source.get('series_id')==SERIES:
            product=json.loads(row['product_snapshot'])
            result['daily']={'uae_date':row['uae_date'],'product_name':product['name'],
             'product_url':product['url'],'template_number':row['template_number'],
                             'skipped_products':skips(ledger.database_path,row['uae_date']),
                             'next':next_expected(ledger.database_path)}
    return result


def sync_job_events(ledger,job=None):
    """Notification-only reconciliation: never modifies approvals or social records."""
    ids=[]
    for saved in ([ledger.job(job)] if job else ledger.jobs()):
        if saved:ids.append(emit_job_event(ledger,saved['job_id'],'PUBLICATION_STATUS',job_snapshot(ledger,saved['job_id'])))
    return ids


def notification_health(ledger):
    ensure_schema(ledger)
    with ledger._connect() as db:
        return {r[0]:r[1] for r in db.execute("SELECT state,count(*) FROM publication_notification_delivery WHERE event_id NOT IN (SELECT event_id FROM publication_notification_suppression) GROUP BY state")}
