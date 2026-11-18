"""Explicit-time parsing and durable outbox schema; no scheduler activation."""
import json,re,time
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from .approval_ledger import Permanent,canonical,digest

def parse_schedule(text,received_at,timezone_name='UTC'):
    try: DUBAI=ZoneInfo(timezone_name)
    except Exception: raise Permanent('CONFIRM_TIMEZONE') from None
    now=datetime.fromisoformat(received_at.replace('Z','+00:00'))
    if now.tzinfo is None:raise Permanent('AWARE_RECEIVED_TIME_REQUIRED')
    local=now.astimezone(DUBAI);text=text.lower().strip()
    tonight=bool(re.search(r'\btonight\b',text))
    evening=bool(re.search(r'\bthis evening\b',text))
    if tonight and evening:raise Permanent('AMBIGUOUS_DATE')
    if tonight:text=re.sub(r'\btonight\b','today',text)
    if evening:text=re.sub(r'\bthis evening\b','today',text)
    matches=list(re.finditer(r'(?<![\d:])(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b',text))
    if len(matches)!=1:raise Permanent('CONFIRM_EXACT_TIME_AM_PM')
    match=matches[0];hour=int(match[1]);minute=int(match[2] or 0)
    if not 1<=hour<=12 or minute>59:raise Permanent('INVALID_TIME')
    hour=hour%12+(12 if match[3]=='pm' else 0)
    if tonight and not 18<=hour<=23:raise Permanent('TONIGHT_REQUIRES_EVENING_TIME')
    if evening and not 17<=hour<=23:raise Permanent('EVENING_REQUIRES_PM_TIME')
    dates=re.findall(r'\b\d{4}-\d{2}-\d{2}\b',text)
    weekdays=[i for i,n in enumerate(('monday','tuesday','wednesday','thursday','friday','saturday','sunday')) if re.search(r'\b'+n+r'\b',text)]
    modes=len(dates)+len(weekdays)+int('tomorrow' in text)+int(bool(re.search(r'\btoday\b',text)))
    if modes>1:raise Permanent('AMBIGUOUS_DATE')
    if dates:
        try:day=datetime.fromisoformat(dates[0]).date()
        except ValueError:raise Permanent('INVALID_DATE') from None
    elif 'tomorrow' in text:day=local.date()+timedelta(days=1)
    elif weekdays:
        delta=(weekdays[0]-local.weekday())%7
        if 'next ' in text or delta==0:delta=delta or 7
        day=local.date()+timedelta(days=delta)
    elif re.search(r'\btoday\b',text):day=local.date()
    else:raise Permanent('CONFIRM_EXACT_DATE')
    due=datetime.combine(day,datetime.min.time(),DUBAI).replace(hour=hour,minute=minute)
    if due<=local:raise Permanent('PAST_DUE_REQUIRES_NEW_CONFIRMATION')
    if due.fold or due.replace(fold=1).utcoffset()!=due.utcoffset() or due.astimezone(timezone.utc).astimezone(DUBAI).replace(tzinfo=None)!=due.replace(tzinfo=None):raise Permanent('AMBIGUOUS_OR_NONEXISTENT_LOCAL_TIME')
    return {'timezone':timezone_name,'local':due.isoformat(),'due_at':due.timestamp(),'utc':due.astimezone(timezone.utc).isoformat()}

def schema(db):
    db.executescript("""CREATE TABLE IF NOT EXISTS publication_schedule (
      job_id TEXT PRIMARY KEY, approval_event TEXT UNIQUE NOT NULL,
      due_at REAL NOT NULL, expires_at REAL NOT NULL, evidence TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS publication_outbox (
      event_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, kind TEXT NOT NULL,
      payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'PENDING',
      receipt TEXT, created_at REAL NOT NULL);
    """)

def outbox(ledger,job,kind,payload):
    event_id=job+':'+kind+':'+digest(payload)
    with ledger._connect() as db:
        schema(db);db.execute('INSERT OR IGNORE INTO publication_outbox(event_id,job_id,kind,payload,created_at) VALUES(?,?,?,?,?)',(event_id,job,kind,canonical(payload),time.time()))
    return event_id
