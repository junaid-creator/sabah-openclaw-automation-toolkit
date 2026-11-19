"""Bounded, opt-in recovery of exact social_review approvals.

Uses existing MetaPublisher and TikTok advance, not a second publication API.
No scheduler, credentials, sender or network transport is installed here.
"""
import json
import math
import re
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from . import meta_publisher as meta
from . import tiktok_publisher as tiktok
from .approval_ledger import digest, report_status
from .reliability import lock
from .social_publish_gate import BoundApprovalGate, verify_rows
from .social_review import ReviewError


class Recovery:
    """All workers for a controller must share its root AND durable ledger.

    media_digest(url) is a trusted, bounded fetch/verification adapter returning
    SHA256 of the hosted JPEG bytes; it must enforce allowed hosts/SSRF policy.
    It is deliberately mandatory, never inferred from a mutable URL.
    """
    def __init__(self, controller, *, meta_publisher=None, tiktok_client=None,
                 media_digest, clock=time.time, retry_delay=60, max_checks=480):
        if not callable(media_digest) or not 1 <= retry_delay <= 86400 or not 1 <= max_checks <= 480:
            raise ValueError('Bounded recovery configuration required')
        self.controller, self.ledger = controller, controller.ledger
        self.meta, self.tiktok = meta_publisher, tiktok_client
        self.media_digest, self.clock = media_digest, clock
        self.retry_delay, self.max_checks = retry_delay, max_checks

    def _binding(self, job):
        state = self.controller._read(job)
        binding = self.controller._binding(state)
        saved = self.ledger.job(job)
        if (state['phase'] not in {'APPROVED', 'DISPATCHING', 'DISPATCH_UNKNOWN', 'DISPATCHED'}
                or not saved or saved['fingerprint'] != digest(binding)
                or json.loads(saved['receipt']).get('binding') != binding):
            raise ReviewError('UNCHANGED_DURABLE_APPROVAL_REQUIRED')
        return state, binding

    def _authorized(self, job, state, binding):
        saved = self.ledger.job(job)
        return bool(saved and saved['state'] != 'REVOKED'
                    and not self.ledger.submission_blocked(job)
                    and self.controller.bridge.authorized(state.get('challenge'), binding))

    def checked(self, job):
        state, binding = self._binding(job)
        if not self._authorized(job, state, binding):
            raise ReviewError('CURRENT_OWNER_APPROVAL_REQUIRED')
        if self.media_digest(binding['url']) != binding['image_sha256']:
            raise ReviewError('HOSTED_MEDIA_CHANGED')
        return binding

    def _validate_adapters(self, targets):
        if set(targets) & {'facebook', 'instagram'}:
            p = self.meta
            if (not isinstance(p, meta.MetaPublisher) or p.ledger is not self.ledger
                    or not isinstance(p.approval_gate, BoundApprovalGate)
                    or p.approval_gate.controller is not self.controller
                    or p.approval_gate.sheets is not p.sheets):
                raise ReviewError('SHARED_BOUND_META_ADAPTER_REQUIRED')
            if (p.dry_run or not meta.LIVE_ENABLEMENT_APPROVED
                    or not p.settings.live_enablement_approved or not p.settings.api_contracts_verified):
                raise PermissionError('META_EXPLICIT_ENABLEMENT_REQUIRED')
        if 'tiktok' in targets and not isinstance(self.tiktok, tiktok.Client):
            raise ReviewError('TIKTOK_CLIENT_REQUIRED')

    @staticmethod
    def _public_url(url, platform):
        parsed = urlsplit(url or '')
        domains = {'facebook': 'facebook.com', 'instagram': 'instagram.com', 'tiktok': 'tiktok.com'}
        domain = domains[platform]
        return bool(parsed.scheme == 'https' and parsed.hostname
                    and (parsed.hostname == domain or parsed.hostname.endswith('.' + domain))
                    and not parsed.username and not parsed.password and not parsed.fragment)

    def _meta_step(self, job, platform, binding, known):
        p = self.meta
        if known and known['state'] == 'PUBLISHED':
            if known.get('permalink'):
                return
            # A confirmed remote ID is never sent through the publishing path.
            if not known.get('remote_id'):
                raise ReviewError('CONFIRMED_REMOTE_ID_REQUIRED')
            kind = meta.Platform(platform)
            field = 'permalink_url' if platform == 'facebook' else 'permalink'
            body = p._api_request('GET', p._base(kind) + '/' + known['remote_id'],
                                  p._token(kind), params={'fields': 'id,' + field})
            if str(body.get('id')) != known['remote_id'] or not self._public_url(body.get(field), platform):
                raise ReviewError('PUBLIC_LINK_READBACK_REQUIRED')
            self.ledger.update(job, platform, 'PUBLISHED', permalink=body[field])
            return
        if known and known['state'] not in {'FAILED_RETRYABLE'}:
            return
        if known and known['attempts'] >= p.max_attempts:
            self.ledger.update(job, platform, 'FAILED_FINAL', error_code='RETRY_LIMIT')
            return
        self.checked(job)
        queue, content = p._read_approved_job(job)
        if not verify_rows(binding, queue, content) or not p.approval_gate.authorize(job, platform):
            raise ReviewError('FROZEN_ROWS_AND_OPERATIONAL_APPROVAL_REQUIRED')
        # Existing adapter performs media validation, reservation and durable
        # outcome journaling. No aggregate Sheet status is rewritten here.
        p._publish_one(job, meta.Platform(platform), queue, content)

    def _step(self, job, platform, binding):
        known = self.ledger.get(job, platform)
        op = self.ledger.op(job, platform)
        if not op:
            raise ReviewError('DURABLE_OPERATION_REQUIRED')
        if known and known['state'] in {'UNCERTAIN', 'FAILED_FINAL'}:
            return
        if known and known['state'] == 'PUBLISHED' and known.get('permalink'):
            return
        # Interrupted Meta POST/container is not permission to submit again.
        # TikTok can resume only an accepted, durably journaled task ID.
        if known and known['state'] in {'POSTING', 'CONTAINER_CREATED'}:
            if platform != 'tiktok' or not op.get('container_id'):
                self.ledger.update(job, platform, 'UNCERTAIN', error_code='INTERRUPTED_OUTCOME_NO_REPLAY')
                return
        if op['next_at'] > self.clock():
            return
        if op['checks'] >= self.max_checks:
            if known and known['state'] != 'PUBLISHED':
                self.ledger.update(job, platform, 'UNCERTAIN', error_code='RECOVERY_CHECK_LIMIT')
            self.ledger.setop(job, platform, phase='NEEDS_ACTION', next_at=0)
            return
        # Persist the next admission BEFORE any adapter call, including reads.
        self.ledger.setop(job, platform, checks=op['checks'] + 1,
                          next_at=self.clock() + self.retry_delay)
        try:
            if platform == 'tiktok':
                engine = SimpleNamespace(ledger=self.ledger, tiktok=self.tiktok, clock=self.clock,
                                         checked=self.checked, caption=lambda c, p: c[p + '_caption'])
                tiktok.advance(engine, job, {'final_master_asset_url': binding['url'],
                                           'tiktok_caption': binding['captions']['tiktok']})
            else:
                self._meta_step(job, platform, binding, known)
        except Exception:
            # Never persist arbitrary provider exception text (may contain secrets).
            current = self.ledger.get(job, platform)
            current_op = self.ledger.op(job, platform)
            if current and current['state'] in {'POSTING', 'CONTAINER_CREATED'}:
                if platform != 'tiktok' or not current_op.get('container_id'):
                    self.ledger.update(job, platform, 'UNCERTAIN', error_code='ADAPTER_OUTCOME_UNKNOWN')
            self.ledger.event(job, 'RECOVERY_DEFERRED', platform)

    def _report(self, job, binding, *, blocked=False):
        result = {}
        for platform in binding['targets']:
            known = self.ledger.get(job, platform)
            op = self.ledger.op(job, platform) or {}
            status = report_status(known)
            if status == 'VERIFIED' and not self._public_url(known.get('permalink'), platform):
                status = 'NEEDS_ACTION'
            if status != 'VERIFIED' and (blocked or op.get('phase') == 'NEEDS_ACTION'
                    or op.get('checks', 0) >= self.max_checks):
                status = 'NEEDS_ACTION'
            if known and known.get('error_code') == 'TIKTOK_CREATOR_IN_APP_ACTION_REQUIRED':
                status = 'NEEDS_ACTION'
            result[platform] = {'status': status,
                                'url': known.get('permalink') if known and status == 'VERIFIED' else None,
                                'remote_id': known.get('remote_id') if known else None,
                                'next_at': op.get('next_at', 0)}
        return result

    def _notify(self, job, result, *, blocked=False):
        """Prepare only; never call a sender or configure notification targets.

        Hash only stable owner-facing evidence, not attempts/checks/next_at.
        No captions, local paths, media origins or provider diagnostics escape.
        """
        from .notification_outbox import emit_job_event
        platforms = {}
        for platform, row in sorted(result.items()):
            status = row['status']
            remote = row.get('remote_id')
            remote = remote if isinstance(remote, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,256}', remote) else None
            url = row.get('url')
            if status == 'VERIFIED':
                try:
                    parsed = urlsplit(url or '')
                    safe = (isinstance(url, str) and len(url) <= 2048
                            and not any(ord(c) < 33 or ord(c) == 127 for c in url)
                            and self._public_url(url, platform) and not parsed.query and not parsed.port)
                except (TypeError, ValueError):
                    safe = False
                if not safe:
                    status, url = 'NEEDS_ACTION', None
            else:
                url = None
            platforms[platform] = {'report_status': status, 'remote_id': remote, 'permalink': url}
            if blocked and status != 'VERIFIED':
                platforms[platform]['error_code'] = 'OWNER_APPROVAL_REVOKED_OR_BLOCKED'
        statuses = [row['report_status'] for row in platforms.values()]
        health = ('NEEDS_ACTION' if blocked or any(s in {'FAILED', 'NEEDS_ACTION'} for s in statuses)
                  else 'VERIFIED' if statuses and all(s == 'VERIFIED' for s in statuses) else 'PROCESSING')
        return emit_job_event(self.ledger, job, 'SOCIAL_RECOVERY_STATUS', {
            'health': health, 'status': 'APPROVAL_BLOCKED' if blocked else health,
            'platforms': platforms,
        })

    def run(self, job, *, enabled=False):
        """One bounded pass; call again when due, never a background thread.

        Also resumes Controller.dispatch partial/unknown results without resetting
        its approval or clearing any uncertain platform receipt.
        """
        if enabled is not True:
            raise PermissionError('Explicit recovery activation required')
        if not math.isfinite(self.clock()):
            raise ValueError('Finite clock required')
        with lock(self.controller.root / 'social.lock'):
            state, binding = self._binding(job)
            if not self._authorized(job, state, binding):
                result = self._report(job, binding, blocked=True)
                self._notify(job, result, blocked=True)
                return result
            self._validate_adapters(binding['targets'])
            state['phase'] = 'DISPATCHING'
            self.controller._save(state)
            for platform in binding['targets']:
                # Revocation may arrive during a previous provider operation.
                if not self._authorized(job, state, binding):
                    break
                self._step(job, platform, binding)
            blocked = not self._authorized(job, state, binding)
            result = self._report(job, binding, blocked=blocked)
            state.update(phase='DISPATCHED', result=result)
            self.controller._save(state)
            self._notify(job, result, blocked=blocked)
            return result

    def due(self, *, enabled=False, limit=20):
        """Bounded caller-driven recovery sweep; no cron/service activation."""
        if enabled is not True or type(limit) is not int or not 1 <= limit <= 100:
            raise PermissionError('Explicit bounded sweep required')
        results = {}
        for saved in sorted(self.ledger.jobs(), key=lambda row: row['job_id']):
            if len(results) >= limit:
                break
            job = saved['job_id']
            if saved['state'] == 'REVOKED' or self.ledger.submission_blocked(job):
                continue
            try:
                binding = json.loads(saved['receipt']).get('binding', {})
                targets = binding.get('targets', [])
                pending = [self.ledger.op(job, p) for p in targets
                           if report_status(self.ledger.get(job, p)) == 'PROCESSING']
                if not any(op and op['next_at'] <= self.clock() and op['checks'] < self.max_checks for op in pending):
                    continue
                results[job] = self.run(job, enabled=True)
            except Exception:
                results[job] = {'error': 'RECOVERY_BLOCKED'}
        return results
