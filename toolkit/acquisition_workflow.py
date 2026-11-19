"""Explicit adapter assembly, not a scheduler or a provider/messaging API.

All destinations, acquisition opt-ins and exact Sheet approvals are caller supplied.
Persist state outside the source tree. See docs/acquisition-workflow.md.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .apify_budget import billing_guard
from .google_sheets import TABS
from .lead_qualification import HEADERS, qualify
from .lead_sheet_merge import merged
from .overture_adapter import download, qualify_features
from .reliability import Run, atomic_json, lock


def billing_evidence_status(evidence_path, *, now=None, warning=timedelta(days=1),
                            cap=0.20, reserve=0.30):
    """Read-only, fail-closed monitor. Never refresh evidence or approve spending."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or warning < timedelta(0):
        raise ValueError('Aware time and nonnegative warning required')
    try:
        evidence, _ = billing_guard(evidence_path, now=now, cap=cap, reserve=reserve)
        parse = lambda key: datetime.fromisoformat(evidence[key].replace('Z', '+00:00'))
        deadlines = {
            'policy': parse('policy_verified_at') + timedelta(days=30),
            'credit': parse('credit_verified_at') + timedelta(days=7),
            'cycle': parse('cycle_end'),
        }
        expiry = min(deadlines.values())
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {'status': 'BLOCKED', 'blocker': 'Billing evidence unavailable, unsafe or expired'}
    return {'status': 'EXPIRING' if expiry - now <= warning else 'VALID',
            'expires_at': expiry.isoformat(),
            'deadlines': {key: value.isoformat() for key, value in deadlines.items()}}


def monitor_billing(evidence_path, *, state_path, now=None, **limits):
    """Persist one observation/change flag; no notification or scheduler side effect."""
    observation = billing_evidence_status(evidence_path, now=now, **limits)
    path = Path(state_path)
    with lock(str(path) + '.lock'):
        previous = json.loads(path.read_text()) if path.exists() else {}
        changed = previous.get('observation') != observation
        atomic_json(path, {'observation': observation,
                          'checked_at': (now or datetime.now(timezone.utc)).isoformat()})
    return {**observation, 'changed': changed}


class OvertureSource:
    """Existing opt-in CLI adapter; output must be a caller-selected fresh path."""
    kind = 'overture'

    def __init__(self, executable, bbox, output, *, allow_download=False, runner=None):
        self.executable, self.bbox, self.output = str(executable), list(bbox), str(output)
        self.allow_download, self.runner = allow_download, runner

    def binding(self):
        return dict(kind=self.kind, executable=self.executable, bbox=self.bbox, output=self.output)

    def acquire(self, run_id):
        kwargs = {'allow_download': self.allow_download}
        if self.runner is not None:
            kwargs['runner'] = self.runner
        data = download(self.executable, self.bbox, self.output, **kwargs)
        if not isinstance(data, dict) or not isinstance(data.get('features'), list):
            raise ValueError('Invalid Overture collection')
        return {'status': 'COMPLETE', 'data': data, 'raw_count': len(data['features'])}


class ApifySource:
    """Reuse capped start/collect and its durable run key; never infer paid consent."""
    kind = 'apify'

    def __init__(self, client, payload, *, state_path, evidence_path, authorize,
                 cap=0.20, reserve=0.30, monthly_limit=1.00):
        self.client, self.payload = client, payload
        self.state_path, self.evidence_path = str(state_path), str(evidence_path)
        self.authorize = authorize
        self.limits = dict(cap=cap, reserve=reserve, monthly_limit=monthly_limit)

    def binding(self):
        return dict(kind=self.kind, actor=self.client.actor,
                    expected_actor_id=self.client.expected_actor_id, payload=self.payload,
                    state_path=self.state_path, evidence_path=self.evidence_path, **self.limits)

    def acquire(self, run_id):
        record = self.client.start(run_id, self.payload, state_path=self.state_path,
                                   evidence_path=self.evidence_path,
                                   authorize=self.authorize, **self.limits)
        if record['status'] in {'STARTING', 'UNCERTAIN_START', 'NEEDS_ACTION', 'FAILED'}:
            return {'status': record['status']}
        result = self.client.collect(run_id, state_path=self.state_path)
        if result['status'] != 'COMPLETE':
            return {'status': result['status']}
        if result.get('dataset_truncation_possible'):
            return {'status': 'TRUNCATED'}
        return {'status': 'COMPLETE', 'data': result['items'], 'raw_count': len(result['items'])}


def _qualified(source, acquired, profile, today, min_score, quantity):
    if source.kind == 'overture':
        rows = qualify_features(acquired['data'], profile, today)
    elif source.kind == 'apify':
        rows = [row for item in acquired['data'] if (row := qualify(item, profile, today))]
    else:
        raise ValueError('Unsupported source contract')
    # Existing merge contract deduplicates IDs/domain/phone/name and retains provenance.
    rows = merged(HEADERS, [HEADERS], rows)[1:]
    rows = sorted((row for row in rows if row[11] >= min_score),
                  key=lambda row: (-row[11], row[1].casefold()))
    return rows[:quantity], len(rows)


def weekly_leads(run_id, *, root, source, profile, today, sheets, sheet_id,
                 outbox, approved_digests=None, min_score=70, quantity=25):
    """One bounded tick. First tick prepares exact plans, later approved tick applies.

    Caller chooses one stable weekly run ID. No timer, implicit approvals or sender.
    Unknown Sheet writes only receive read-only reconciliation on subsequent ticks.
    """
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', run_id):
        raise ValueError('Invalid acquisition run ID')
    if type(quantity) is not int or quantity < 1 or type(min_score) is not int or not 0 <= min_score <= 100:
        raise ValueError('Explicit positive quantity and score 0..100 required')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', sheet_id):
        raise ValueError('Invalid Sheet ID')
    datetime.strptime(today, '%Y-%m-%d')
    binding = dict(source=source.binding(), profile=profile, today=today,
                   sheet_id=sheet_id, account=sheets.account, client=sheets.client,
                   report_account=outbox.account, report_recipient=outbox.recipient,
                   outbox_path=str(outbox.path), min_score=min_score, quantity=quantity)
    with Run(run_id, binding, root=root) as run:
        ops = run.data['operations']
        def save(operation, state, **values):
            run.checkpoint(operation, state, **values)
        def result(status, **values):
            return dict(run_id=run_id, status=status, sheet_url='https://docs.google.com/spreadsheets/d/' + sheet_id + '/edit', **values)
        if 'acquisition' not in ops or ops['acquisition']['state'] == 'PROCESSING':
            save('acquisition', 'ACQUIRING')
            try:
                acquired = source.acquire(run_id)
            except Exception:
                save('acquisition', 'NEEDS_ACTION', blocker='Acquisition failed or timed out; inspect adapter state without replay')
            else:
                state = acquired['status']
                if state in {'RUNNING', 'READY', 'PROCESSING'}:
                    save('acquisition', 'PROCESSING')
                elif state == 'COMPLETE':
                    save('acquisition', 'COMPLETE', acquired=acquired)
                else:
                    save('acquisition', 'NEEDS_ACTION', blocker='Source state: ' + state)
        acquisition = ops['acquisition']
        if acquisition['state'] != 'COMPLETE':
            return result('PROCESSING' if acquisition['state'] == 'PROCESSING' else 'NEEDS_ACTION',
                          blocker=acquisition.get('blocker', 'Interrupted acquisition requires reconciliation'))
        if 'qualification' not in ops:
            try:
                rows, matching = _qualified(source, acquisition['acquired'], profile, today, min_score, quantity)
            except Exception:
                save('qualification', 'FAILED', blocker='Qualification failed; inspect private source data')
            else:
                save('qualification', 'COMPLETE', rows=rows, matching=matching)
        qualification = ops['qualification']
        if qualification['state'] != 'COMPLETE':
            return result('NEEDS_ACTION', blocker=qualification['blocker'])
        rows = qualification['rows']
        if 'plans' not in ops:
            try:
                plans = [sheets.plan(sheet_id, tab, HEADERS, rows) for tab in TABS[:2]]
            except Exception:
                return result('NEEDS_ACTION', blocker='Sheet planning read failed; no write attempted')
            save('plans', 'PREPARED', plans=plans,
                 new_count=len(plans[0]['target']) - len(plans[0]['before'] or [HEADERS]))
        plans = ops['plans']['plans']
        counts = dict(matching=qualification['matching'], selected=len(rows), new=ops['plans']['new_count'],
                      collected=acquisition['acquired']['raw_count'])
        # Reconcile previously claimed writes without ever invoking apply again.
        for plan in plans:
            key = 'sheet:' + plan['tab']
            previous = ops.get(key, {})
            if previous.get('state') in {'WRITING', 'UNKNOWN'}:
                try:
                    matched = sheets.values(sheet_id, plan['tab']) == plan['target']
                except Exception:
                    matched = False
                if not matched:
                    return result('NEEDS_ACTION', blocker='Sheet write outcome unresolved; no replay', **counts)
                save(key, 'VERIFIED')
        needed = [p for p in plans if ops.get('sheet:' + p['tab'], {}).get('state') != 'VERIFIED']
        if any((approved_digests or {}).get(p['tab']) != p['digest'] for p in needed):
            return result('WAITING_APPROVAL', plans=plans, **counts)
        for plan in needed:
            key = 'sheet:' + plan['tab']
            save(key, 'WRITING')
            try:
                receipt = sheets.apply(plan, approved_digest=approved_digests[plan['tab']])
                if receipt.get('status') != 'VERIFIED':
                    raise RuntimeError('Unverified Sheet receipt')
            except Exception:
                save(key, 'UNKNOWN')
                return result('NEEDS_ACTION', blocker='Sheet apply unresolved; read-only reconciliation required', **counts)
            save(key, 'VERIFIED')
        if 'report' not in ops:
            payload = dict(title='Weekly lead acquisition', post_id=run_id, topic='Business prospects',
                           keyword='', status='Completed', url='', sheets=result('')['sheet_url'],
                           blocker='', counts=counts, purpose='lead_sheet_merge',
                           qualification='Prospects, not confirmed buyers; no outreach authorized')
            try:
                report_key = outbox.prepare('leads:' + run_id, payload)
            except Exception:
                return result('NEEDS_ACTION', blocker='Report preparation failed; Sheets already verified', **counts)
            save('report', 'PREPARED', key=report_key)
        return result('REPORT_PREPARED', report_key=ops['report']['key'], **counts)


def claim_report(outbox, key):
    """Claim before parent uses an authorized messaging tool; never send here."""
    with lock(str(outbox.path) + '.lock'):
        data = json.loads(outbox.path.read_text())
        row = data[key]
        if row['account'] != outbox.account or row['recipient'] != outbox.recipient:
            raise ValueError('Persisted report destination mismatch')
    return outbox.claim(key)


def report_receipt(outbox, key, message_id=None):
    """Unknown/timeouts stay fenced by existing Outbox; no automatic redelivery."""
    outbox.receipt(key, message_id, account=outbox.account, recipient=outbox.recipient)
