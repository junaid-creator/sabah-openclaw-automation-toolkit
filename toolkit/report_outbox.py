"""Durable claim/receipt outbox; no built-in sender."""
import json,time
from pathlib import Path
from .reliability import lock,atomic_json

class Outbox:
    """Tool-aware parent only: prepare -> claim -> OpenClaw message tool -> receipt.
    No CLI, network, scheduler or automatic send. Unknown/sending is never reclaimable.
    """
    def __init__(self, path, *, account, recipient):
        if not account or not recipient: raise ValueError("Explicit report destination required")
        self.account,self.recipient=account,recipient
        self.path = Path(path)
    def update(self, fn):
        with lock(str(self.path) + '.lock'):
            data = json.loads(self.path.read_text()) if self.path.exists() else {}
            result = fn(data)
            atomic_json(self.path, data)
            return result
    def prepare(self, run_id, payload):
        required = {'title','post_id','topic','keyword','status','url','sheets','blocker'}
        if not required <= payload.keys():
            raise ValueError('Missing owner report fields')
        if payload['status'] not in {'Published','Draft','Blocked','Failed'}:
            raise ValueError('Invalid report status')
        key = run_id
        def apply(data):
            if key in data and data[key]['payload'] != payload:
                raise RuntimeError('Notification run ID already bound to another payload')
            data.setdefault(key, dict(state='pending', run_id=run_id, payload=payload,
                                      account=self.account, recipient=self.recipient,
                                      deliveries={c: dict(state='pending', attempts=0, next_at=0)
                                                  for c in ('whatsapp','telegram')} if payload['status'] != 'Draft' else {}))
            return key
        return self.update(apply)
    def claim(self, key):
        def apply(data):
            row = data[key]
            if row['state'] != 'pending':
                raise RuntimeError('Notification already claimed; reconcile receipt, never resend')
            row['state'] = 'sending'
            return dict(row)
        return self.update(apply)
    def receipt(self, key, message_id=None, *, account, recipient):
        def apply(data):
            row = data[key]
            if row['state'] not in {'sending','unknown'}:
                raise RuntimeError('Receipt not expected')
            if account != self.account or recipient != self.recipient:
                raise ValueError('Owner/account mismatch')
            row.update(state='sent' if message_id else 'unknown', message_id=message_id,
                       receipt_time=time.time())
        self.update(apply)
