"""Independent alert-only monitor. No restart, recovery or business replay.

Source-derived from the original monitor; state, endpoints and recipient are
operator-configured. Telegram transport is optional, explicit and independent
of the monitored Gateway. Never invoke it merely to test installation.
"""
import argparse
from contextlib import contextmanager
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import sqlite3
import time
import urllib.request
from urllib.parse import urlsplit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def endpoint_url(value):
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        raise ValueError('Explicit credential-free health endpoint required')
    if parsed.scheme == 'http':
        try: valid = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError: valid = False
        if not valid: raise ValueError('Plain HTTP limited to numeric loopback')
    elif parsed.scheme != 'https':
        raise ValueError('HTTPS or numeric loopback HTTP required')
    return value


def probe(endpoints, *, allow_network=False, opener=None):
    if not allow_network:
        raise PermissionError('Health network access disabled')
    if not endpoints or len(endpoints)>8:
        raise ValueError('One to eight explicit health endpoints required')
    endpoints = [endpoint_url(value) for value in endpoints]
    opener = opener or urllib.request.build_opener(NoRedirect())
    try:
        for endpoint in endpoints:
            with opener.open(endpoint, timeout=3) as response:
                body = response.read(65537)
                if response.status != 200 or len(body)>65536 or not isinstance(json.loads(body), dict):
                    return False
        return True
    except Exception:
        return False


def integrity(manifest):
    """Missing/changed evidence suppresses sends, never changes the service."""
    if not manifest or not isinstance(manifest, dict): return False
    try:
        for name, expected in manifest.items():
            path = Path(name)
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 20_000_000:
                return False
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected: return False
        return True
    except OSError:
        return False


class Monitor:
    def __init__(self, state_dir, *, label, threshold=3, grace=180, clock=time.time):
        if not label or len(label)>80 or type(threshold) is not int or not 1<=threshold<=100 or not 0<=grace<=3600:
            raise ValueError('Bounded monitor configuration required')
        self.root = Path(state_dir).absolute()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.root.stat()
        if (self.root != self.root.resolve() or info.st_uid != os.geteuid() or info.st_mode & 0o077):
            raise ValueError('Private runtime-owned state directory required')
        self.path = self.root/'monitor.sqlite3'
        if self.path.exists() or self.path.is_symlink():
            if self.path.is_symlink() or self.path.stat().st_mode & 0o077:
                raise ValueError('Private regular state file required')
        self.label,self.threshold,self.grace,self.clock=label,threshold,grace,clock
        with self.db() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1), started REAL,
                failures INTEGER, incident INTEGER, last_tick REAL);
              CREATE TABLE IF NOT EXISTS incidents(id INTEGER PRIMARY KEY, started REAL, ended REAL);
              CREATE TABLE IF NOT EXISTS notices(id INTEGER PRIMARY KEY, incident INTEGER, kind TEXT,
                body TEXT, status TEXT, receipt TEXT, UNIQUE(incident,kind));
              CREATE TABLE IF NOT EXISTS ticks(id INTEGER PRIMARY KEY, at REAL, state TEXT);
            ''')
            db.execute('INSERT OR IGNORE INTO state VALUES(1,?,0,NULL,?)',(clock(),clock()))

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path, timeout=10)
        db.row_factory=sqlite3.Row
        os.chmod(self.path,0o600)
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db: yield db
        finally: db.close()

    def tick(self, healthy, *, maintenance=False, integrity_ok=False):
        if type(healthy) is not bool or type(maintenance) is not bool or type(integrity_ok) is not bool:
            raise ValueError('Boolean observations required')
        now=self.clock()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            state=db.execute('SELECT * FROM state WHERE id=1').fetchone()
            if now<state['last_tick']: raise ValueError('Clock moved backwards; inspect manually')
            incident=state['incident'];failures=state['failures']
            # Suppression precedes recovery too: maintenance never sends a notice.
            if maintenance or not integrity_ok:
                failures=0; result='SUPPRESSED'
            elif healthy:
                failures=0; result='HEALTHY'
                if incident:
                    db.execute('UPDATE incidents SET ended=? WHERE id=?',(now,incident))
                    confirmed=db.execute("SELECT 1 FROM notices WHERE incident=? AND kind='OUTAGE' AND status='SENT'",(incident,)).fetchone()
                    if confirmed:
                        db.execute("INSERT OR IGNORE INTO notices(incident,kind,body,status) VALUES(?,'RECOVERY',?,'PENDING')",(incident,self.label+': readiness recovered. Business task completion not inferred.'))
                    incident=None
            elif now-state['started']<self.grace:
                result='STARTUP_GRACE'
            else:
                failures+=1;result='SUSPECT'
                if failures>=self.threshold:
                    result='OUTAGE'
                    if not incident:
                        incident=db.execute('INSERT INTO incidents(started) VALUES(?)',(now,)).lastrowid
                        db.execute("INSERT INTO notices(incident,kind,body,status) VALUES(?,'OUTAGE',?,'PENDING')",(incident,self.label+': sustained readiness failure. Alert only; no restart attempted.'))
            db.execute('UPDATE state SET failures=?,incident=?,last_tick=? WHERE id=1',(failures,incident,now))
            db.execute('INSERT INTO ticks(at,state) VALUES(?,?)',(now,result))
            # Outage resolved while unsent => stale notice must not be dispatched.
            db.execute("UPDATE notices SET status='STALE' WHERE status='PENDING' AND kind='OUTAGE' AND incident IN (SELECT id FROM incidents WHERE ended IS NOT NULL)")
        return {'state':result,'failures':failures,'incident_id':incident}

    def dispatch_one(self, sender, *, enabled=False):
        if not enabled: return {'status':'DISABLED'}
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            last=db.execute('SELECT state FROM ticks ORDER BY id DESC LIMIT 1').fetchone()
            if not last or last['state']=='SUPPRESSED': return {'status':'SUPPRESSED'}
            row=db.execute("SELECT * FROM notices WHERE status='PENDING' ORDER BY id LIMIT 1").fetchone()
            if not row: return {'status':'IDLE'}
            db.execute("UPDATE notices SET status='SENDING' WHERE id=?",(row['id'],))
        # A crash after reservation cannot trigger replay. SENDING remains unknown.
        try:
            receipt=sender(row['body'])
            confirmed=isinstance(receipt,dict) and receipt.get('confirmed') is True and bool(receipt.get('message_id'))
        except Exception:
            receipt=None;confirmed=False
        with self.db() as db:
            db.execute('UPDATE notices SET status=?,receipt=? WHERE id=?',('SENT' if confirmed else 'UNKNOWN',json.dumps(receipt) if confirmed else None,row['id']))
        return {'notice_id':row['id'],'status':'SENT' if confirmed else 'UNKNOWN'}


class TelegramSender:
    def __init__(self, *, token_env, recipient, allowed_recipient, allow_network=False, opener=None):
        if not recipient or str(recipient)!=str(allowed_recipient):
            raise PermissionError('Explicit verified recipient binding required')
        self.token_env,self.recipient,self.allow_network=token_env,str(recipient),allow_network
        self.opener=opener or urllib.request.build_opener(NoRedirect())

    def __call__(self, text):
        if not self.allow_network: raise PermissionError('Notification network disabled')
        token=os.environ.get(self.token_env)
        if not token or len(token)>512 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_:-' for c in token):
            raise PermissionError('Configured token unavailable')
        request=urllib.request.Request('https://api.telegram.org/bot'+token+'/sendMessage',
            data=json.dumps({'chat_id':self.recipient,'text':text}).encode(),
            headers={'Content-Type':'application/json'},method='POST')
        try:
            with self.opener.open(request,timeout=8) as response:
                body=response.read(65537)
                if len(body)>65536: return {'confirmed':False}
                value=json.loads(body)
            result=value.get('result',{})
            confirmed=(value.get('ok') is True and str(result.get('chat',{}).get('id'))==self.recipient
                       and type(result.get('message_id')) is int and result['message_id']>0)
            return {'confirmed':confirmed,'message_id':str(result['message_id']) if confirmed else None}
        except Exception:
            return {'confirmed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True)
    p.add_argument('--enable-network',action='store_true')
    p.add_argument('--enable-alerts',action='store_true')
    a=p.parse_args()
    path=Path(a.config)
    if path.is_symlink() or path.stat().st_mode & 0o022 or path.stat().st_uid!=os.geteuid():
        raise PermissionError('Trusted local configuration required')
    cfg=json.loads(path.read_text())
    if not a.enable_network: raise PermissionError('Explicit network opt-in required')
    monitor=Monitor(cfg['state_dir'],label=cfg['label'],threshold=cfg.get('threshold',3),grace=cfg.get('grace',180))
    result=monitor.tick(probe(cfg['endpoints'],allow_network=True),maintenance=Path(cfg['maintenance_flag']).exists(),integrity_ok=integrity(cfg['integrity_sha256']))
    if a.enable_alerts:
        sender=TelegramSender(**cfg['telegram'],allow_network=True)
        result['notice']=monitor.dispatch_one(sender,enabled=True)
    print(json.dumps(result))


if __name__=='__main__': main()
