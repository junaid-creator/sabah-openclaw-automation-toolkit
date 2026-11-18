"""Offline-testable application boundary, NOT a native OpenClaw API.

Only a trusted channel adapter may sign transport-verified events. Keep its
key inaccessible to models, customers and this public repository. No sender,
provider, daemon or channel is activated by importing this module.
"""
from contextlib import contextmanager
import hashlib
import hmac
import json
import sqlite3
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Bridge:
    def __init__(self, path, key, routes, *, clock=time.time):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError('Independent signing key of at least 32 bytes required')
        if not routes or any(r.get('role') not in {'owner', 'customer'} for r in routes):
            raise ValueError('Explicit trusted routes required')
        identities = [(r['channel'], r['account'], r['peer']) for r in routes]
        if len(set(identities)) != len(identities):
            raise ValueError('Ambiguous route')
        self.path, self.key, self.routes, self.clock = str(path), key, json.loads(canonical(routes)), clock
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS challenges(id TEXT PRIMARY KEY, owner TEXT NOT NULL,
              binding TEXT NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL, receipt TEXT);
            CREATE TABLE IF NOT EXISTS replies(id TEXT PRIMARY KEY, route TEXT NOT NULL,
              body TEXT NOT NULL, state TEXT NOT NULL, receipt TEXT);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def verify(self, event, signature):
        expected = hmac.new(self.key, canonical(event).encode(), hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(expected, signature):
            raise PermissionError('Invalid transport attestation')
        if (set(event) != {'id','channel','account','peer','kind','timestamp','text'}
            or not all(isinstance(event[k], str) and event[k] for k in ('id','channel','account','peer','text'))
            or event['kind'] != 'direct'
            or type(event['timestamp']) not in (int, float)
            or not 0 <= self.clock() - event['timestamp'] <= 300):
            raise PermissionError('Invalid or expired event')
        route = next((r for r in self.routes if all(r[k] == event[k]
                     for k in ('channel','account','peer'))), None)
        if route is None:
            raise PermissionError('Unconfigured peer')
        return dict(route)

    @staticmethod
    def remember(db, event):
        old = db.execute('SELECT digest FROM events WHERE id=?', (event['id'],)).fetchone()
        digest = fingerprint(event)
        if old and old['digest'] != digest:
            raise PermissionError('Event ID collision')
        if old:
            return False
        db.execute('INSERT INTO events VALUES (?,?)', (event['id'], digest))
        return True

    def challenge(self, event, signature, binding, *, review_receipt, ttl=300):
        """Freeze an operation after trusted delivery of its exact review.

        review_receipt is supplied by the adapter, NEVER extracted from chat.
        Execution is external and must recheck the returned bound approval.
        """
        route = self.verify(event, signature)
        if route['role'] != 'owner':
            raise PermissionError('Owner required')
        if not binding or not 0 < ttl <= 300:
            raise ValueError('Binding and bounded expiry required')
        if (review_receipt.get('delivered') is not True or review_receipt.get('dryRun')
            or not review_receipt.get('message_id')
            or review_receipt.get('binding_digest') != fingerprint(binding)
            or any(review_receipt.get(k) != route[k] for k in ('channel','account','peer'))):
            raise PermissionError('Exact delivered review required')
        cid = fingerprint({'event': event['id'], 'binding': binding})[:24]
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            fresh = self.remember(db, event)
            old = db.execute('SELECT * FROM challenges WHERE id=?', (cid,)).fetchone()
            if not fresh and not old:
                raise PermissionError('Event already consumed')
            if not old:
                db.execute('INSERT INTO challenges VALUES (?,?,?,?,?,NULL)',
                    (cid, canonical(route), canonical(binding), self.clock()+ttl, 'WAITING'))
        return {'challenge_id': cid, 'confirmation': 'CONFIRM '+cid,
                'binding_digest': fingerprint(binding)}

    def confirm(self, event, signature, challenge_id):
        route = self.verify(event, signature)
        if route['role'] != 'owner' or event['text'] != 'CONFIRM '+challenge_id:
            raise PermissionError('One exact owner confirmation required')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM challenges WHERE id=?', (challenge_id,)).fetchone()
            if not row or row['owner'] != canonical(route):
                raise PermissionError('Wrong challenge owner')
            if row['state'] == 'APPROVED':
                receipt = json.loads(row['receipt'])
                if receipt['event_digest'] != fingerprint(event):
                    raise PermissionError('Already confirmed')
                return receipt
            if row['state'] != 'WAITING' or self.clock() > row['expires']:
                raise PermissionError('Expired or revoked challenge')
            if not self.remember(db, event):
                raise PermissionError('Event already consumed')
            receipt = {'binding': json.loads(row['binding']), 'owner': route,
                       'event_id': event['id'], 'event_digest': fingerprint(event),
                       'challenge_id': challenge_id, 'approved_at': self.clock()}
            db.execute("UPDATE challenges SET state='APPROVED',receipt=? WHERE id=?",
                       (canonical(receipt), challenge_id))
            return receipt

    def revoke(self, event, signature, challenge_id):
        route = self.verify(event, signature)
        if route['role'] != 'owner' or event['text'] != 'REVOKE '+challenge_id:
            raise PermissionError('Exact owner revocation required')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT owner FROM challenges WHERE id=?', (challenge_id,)).fetchone()
            if not row or row['owner'] != canonical(route):
                raise PermissionError('Wrong owner')
            self.remember(db, event)
            db.execute("UPDATE challenges SET state='REVOKED' WHERE id=?", (challenge_id,))

    def authorized(self, challenge_id, binding):
        with self.db() as db:
            row = db.execute('SELECT * FROM challenges WHERE id=?', (challenge_id,)).fetchone()
        return bool(row and row['state'] == 'APPROVED' and row['binding'] == canonical(binding))

    def prepare_reply(self, event, signature, proposal, *, policy):
        """policy is an operator-owned semantic checker, not a model boolean.

        It must enforce the support profile (facts, price/stock, escalation,
        privacy and language). This boundary cannot certify free text itself.
        """
        route = self.verify(event, signature)
        if route['role'] != 'customer':
            raise PermissionError('Customer route required')
        if (set(proposal) != {'text','action'} or proposal['action'] != 'reply'
            or not isinstance(proposal['text'], str) or not 0 < len(proposal['text']) <= 4000
            or policy(event, proposal) is not True):
            raise PermissionError('Support policy denied')
        rid = 'reply:'+event['id']
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            fresh = self.remember(db, event)
            row = db.execute('SELECT * FROM replies WHERE id=?', (rid,)).fetchone()
            if not fresh and not row:
                raise PermissionError('Event already consumed')
            if row and (row['body'] != proposal['text'] or row['route'] != canonical(route)):
                raise PermissionError('Reply changed after preparation')
            if not row:
                db.execute('INSERT INTO replies VALUES (?,?,?,?,NULL)',
                           (rid, canonical(route), proposal['text'], 'PREPARED'))
        return rid

    def deliver(self, rid, *, sender, enabled=False):
        if enabled is not True:
            raise PermissionError('Delivery disabled')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM replies WHERE id=?', (rid,)).fetchone()
            if not row:
                raise ValueError('Unknown reply')
            if row['state'] != 'PREPARED':
                return {'state': row['state'], 'replayed': False}
            db.execute("UPDATE replies SET state='SENDING' WHERE id=?", (rid,))
        route = json.loads(row['route'])
        # Intent is durable before the callback; a crash stays SENDING, never resent.
        try:
            receipt = sender(dict(route), row['body'])
        except Exception:
            receipt = None
        exact = (isinstance(receipt, dict) and receipt.get('delivered') is True
                 and not receipt.get('dryRun')
                 and isinstance(receipt.get('message_id'), str) and receipt['message_id']
                 and all(receipt.get(k) == route[k] for k in ('channel','account','peer')))
        state = 'SENT' if exact else 'UNKNOWN'
        # Never persist raw provider errors, access tokens or message bodies as receipts.
        evidence = {k: receipt[k] for k in ('channel','account','peer','message_id')} if exact else None
        with self.db() as db:
            db.execute('UPDATE replies SET state=?,receipt=? WHERE id=?',
                       (state, canonical(evidence), rid))
        return {'state': state, 'receipt': evidence}
