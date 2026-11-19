"""Assembled signed review -> real adapters -> simulated provider recovery.
No inherited TestCase methods; no business network is reachable.
"""
import copy
import hashlib
import hmac
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from toolkit import meta_publisher as meta
from toolkit import tiktok_publisher as tiktok
from toolkit.approval_ledger import Ledger, digest
from toolkit.social_review import Controller, ReviewError
from toolkit.social_recovery import Recovery
from toolkit.social_publish_gate import BoundApprovalGate
from toolkit.trusted_bridge import Bridge, canonical


class Sheets:
    def __init__(self, binding):
        self.queue = dict.fromkeys(meta.QUEUE_FIELDS, '')
        self.queue.update(job_id=binding['job_id'], enabled='TRUE', action='PUBLISH',
                          approval_mode='MANUAL', status='APPROVED')
        self.queue.update({p: 'TRUE' for p in binding['targets']})
        self.content = dict.fromkeys(meta.OUTPUT_FIELDS, '')
        self.content.update(job_id=binding['job_id'], selected_concept='1',
                            final_master_asset_url=binding['url'])
        self.content.update({p + '_caption': c for p, c in binding['captions'].items()})
        self.logs = []
        self.fail_log = False
    def read_queue_job(self, job): return copy.deepcopy(self.queue)
    def read_content_job(self, job): return copy.deepcopy(self.content)
    def upsert_post_log(self, row):
        if self.fail_log: raise TimeoutError('private provider failure')
        self.logs.append(row)
    def update_queue_status(self, *args): raise AssertionError('Aggregate status must not replace approval')


class Secrets:
    def get_facebook_page_access_token(self): return 'fixture-only'
    def get_instagram_access_token(self): return 'fixture-only'


class Media:
    def verify_public_jpeg(self, url): pass


class Providers:
    def __init__(self):
        self.calls = []
        self.fb_error = None
        self.ig_error = None
        self.tt_error = None
        self.tt_read_error = None
        self.link_error = False
        self.indexed = True
        self.status = 'PUBLISH_COMPLETE'
        self.on_post = lambda endpoint: None
    def meta(self, method, url, **kw):
        endpoint = urlsplit(url).path.split('/')[-1]
        self.calls.append(('meta', method, endpoint))
        if method == 'POST': self.on_post(endpoint)
        if endpoint == 'photos':
            if self.fb_error: raise self.fb_error
            return meta.HttpResponse(200, {'id': '101', 'post_id': '101'})
        if endpoint == 'media': return meta.HttpResponse(200, {'id': 'container1'})
        if endpoint == 'media_publish':
            if self.ig_error: raise self.ig_error
            return meta.HttpResponse(200, {'id': '202'})
        if self.link_error: raise TimeoutError()
        return meta.HttpResponse(200, {'id': endpoint, 'permalink_url': 'https://facebook.com/posts/101',
                                       'permalink': 'https://instagram.com/p/202/'})
    def tt(self, method, endpoint, **kw):
        self.calls.append(('tt', method, endpoint))
        if endpoint == 'tt_user/token_info/get/':
            return {'app_id': 'app', 'creator_id': 'owner', 'scope': 'video.publish,video.list'}
        if endpoint == 'business/property/list/':
            return {'url_property_info_list': [{'property_status': 1, 'property_type': 1, 'url': 'media.example'}]}
        if endpoint == 'business/video/settings/': return {'privacy_level_options': ['PUBLIC_TO_EVERYONE']}
        if endpoint == 'business/photo/publish/':
            if self.tt_error: raise self.tt_error
            return {'share_id': 'accepted-task'}
        if endpoint == 'business/publish/status/':
            if self.tt_read_error: raise self.tt_read_error
            return {'status': self.status, 'post_ids': ['303'] if self.status == 'PUBLISH_COMPLETE' else []}
        if endpoint == 'business/video/list/':
            return {'videos': [{'item_id': '303', 'share_url': 'https://tiktok.com/@fixture/video/303'}] if self.indexed else []}
        raise AssertionError(endpoint)
    def posts(self):
        return [c for c in self.calls if c[1] == 'POST' and c[2] in {'photos', 'media', 'media_publish', 'business/photo/publish/'}]


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.now = 1000; self.key = b'f' * 32
        self.route = {'channel': 'fixture', 'account': 'test', 'peer': 'owner', 'role': 'owner'}
        self.bridge = Bridge(self.root / 'bridge.sqlite', self.key, [self.route], clock=lambda: self.now)
        self.ledger = Ledger(self.root / 'publish.sqlite')
        self.photo = b'synthetic-reviewed-photo'
        def renderer(campaign, key):
            path = self.root / (key + '.jpg'); path.write_bytes(self.photo); path.chmod(0o600)
            return {'path': str(path), 'sha256': hashlib.sha256(self.photo).hexdigest(),
                    'url': 'https://media.example/' + key + '.jpg', 'template': campaign['template'], 'geometry_pass': True}
        def sender(route, binding):
            return dict(route, delivered=True, message_id='delivered-review', binding_digest=digest(binding))
        self.c = Controller(self.root, bridge=self.bridge, ledger=self.ledger, renderer=renderer, sender=sender)
        self.providers = Providers()
        self.addCleanup(patch.stopall)
        patch.object(meta, 'LIVE_ENABLEMENT_APPROVED', True).start()
        patch('socket.socket', side_effect=AssertionError('NETWORK_DENIED')).start()
        patch.object(meta.time, 'sleep', lambda n: None).start()
        self.prepare()
    def event(self, id, text='Draft'):
        e = dict(id=id, channel='fixture', account='test', peer='owner', kind='direct', timestamp=self.now, text=text)
        return e, hmac.new(self.key, canonical(e).encode(), hashlib.sha256).hexdigest()
    def prepare(self, targets=('facebook', 'instagram', 'tiktok'), approved=True, id='create'):
        campaign = {'template': 1, 'content': {'headline': 'Tools', 'subheadline': 'For projects', 'cta': 'Contact',
                    'services': [{'en': 'Tool ' + str(i), 'ar': '', 'icon': 'tool'} for i in range(4)]},
                    'targets': list(targets), 'captions': {p: 'Exact reviewed caption' for p in targets}}
        state = self.c.create(*self.event(id), campaign); self.job = state['job_id']
        if approved:
            self.c.review(self.job)
            ch = self.c.challenge(self.job, *self.event('challenge' + id))
            self.c.approve(self.job, *self.event('confirm' + id, ch['confirmation']))
        self.binding = self.c._binding(self.c._read(self.job))
        self.sheets = Sheets(self.binding)
        gate = BoundApprovalGate(self.c, self.sheets, meta.SheetPublicationGate(self.sheets))
        settings = meta.MetaSettings(api_version='v25.0', instagram_auth_mode=meta.InstagramAuthMode.FACEBOOK_LOGIN,
                    page_id='123456', instagram_user_id='654321', expected_page_name='Fixture',
                    verified_media_hosts=frozenset({'media.example'}), api_contracts_verified=True, live_enablement_approved=True)
        class Transport:
            request = staticmethod(self.providers.meta)
        self.publisher = meta.MetaPublisher(settings=settings, transport=Transport(), secrets=Secrets(),
                        sheets=self.sheets, ledger=self.ledger, media_verifier=Media(), approval_gate=gate, dry_run=False)
        self.client = tiktok.Client({'client_id': 'app', 'client_secret': 'fixture', 'expected_open_id': 'owner',
                        'approved_media_hosts': ['media.example']}, lambda **kw: {'access_token': 'fixture', 'open_id': 'owner'},
                        transport=self.providers.tt, live_enabled=True, authorize=lambda payload: True)
        self.worker = self.reopen()
    def reopen(self):
        return Recovery(self.c, meta_publisher=self.publisher, tiktok_client=self.client,
                        media_digest=lambda url: hashlib.sha256(self.photo).hexdigest(), clock=lambda: self.now)
    def run_job(self): return self.worker.run(self.job, enabled=True)
    def tick(self, n=400): self.now += n; return self.run_job()
    def revoke(self):
        self.ledger.owner_action(self.job, 'OWNER_REJECTED', owner_verified=True, confirmation='cancel', message_id='cancel')
    def test_three_platform_completion_restart_and_duplicate_fence(self):
        first = self.run_job()
        self.assertEqual([first[p]['status'] for p in self.binding['targets']], ['VERIFIED', 'VERIFIED', 'PROCESSING'])
        self.worker = self.reopen(); final = self.tick()
        self.assertTrue(all(r['status'] == 'VERIFIED' for r in final.values()))
        before = self.providers.posts(); self.tick(); self.assertEqual(self.providers.posts(), before)
        self.assertEqual(len(before), 4)
    def test_submission_timeout_does_not_stop_other_platforms_or_replay(self):
        self.providers.fb_error = TimeoutError('sensitive')
        r = self.run_job(); self.assertEqual(r['facebook']['status'], 'NEEDS_ACTION')
        self.assertEqual(r['instagram']['status'], 'VERIFIED')
        self.providers.fb_error = None; self.tick(); self.assertEqual(sum(c[2] == 'photos' for c in self.providers.posts()), 1)
    def test_instagram_unknown_keeps_container_and_never_recreates(self):
        self.providers.ig_error = TimeoutError()
        self.run_job(); self.providers.ig_error = None; self.tick()
        self.assertEqual(self.ledger.get(self.job, 'instagram')['remote_id'], 'container1')
        self.assertEqual(sum(c[2] == 'media' for c in self.providers.posts()), 1)
    def test_tiktok_unknown_submission_never_replayed(self):
        self.providers.tt_error = tiktok.Unknown('TIKTOK_SUBMISSION_OUTCOME_UNKNOWN')
        self.run_job(); self.providers.tt_error = None; r = self.tick()
        self.assertEqual(r['tiktok']['status'], 'NEEDS_ACTION')
        self.assertEqual(sum(c[2] == 'business/photo/publish/' for c in self.providers.posts()), 1)
    def test_tiktok_retry_after_is_durable_and_bounded(self):
        self.providers.tt_error = tiktok.Retry('TIKTOK_RATE_LIMIT', 900)
        self.run_job(); count = len(self.providers.posts()); self.tick(300)
        self.assertEqual(len(self.providers.posts()), count)
        self.providers.tt_error = None; self.tick(601); r = self.tick()
        self.assertEqual(r['tiktok']['status'], 'VERIFIED')
        self.assertEqual(sum(c[2] == 'business/photo/publish/' for c in self.providers.posts()), 2)
    def test_tiktok_read_timeout_and_index_delay_only_poll_existing_task(self):
        self.run_job(); self.providers.tt_read_error = tiktok.Retry('TIKTOK_READ_UNAVAILABLE', 300)
        self.tick(); self.providers.tt_read_error = None; self.providers.indexed = False
        self.assertEqual(self.tick()['tiktok']['status'], 'PROCESSING')
        self.providers.indexed = True; self.assertEqual(self.tick()['tiktok']['status'], 'VERIFIED')
        self.assertEqual(sum(c[2] == 'business/photo/publish/' for c in self.providers.posts()), 1)
    def test_missing_meta_link_readback_never_republishes(self):
        self.providers.link_error = True; self.run_job(); before = self.providers.posts()
        self.providers.link_error = False; r = self.tick()
        self.assertEqual(r['facebook']['status'], 'VERIFIED'); self.assertEqual(r['instagram']['status'], 'VERIFIED')
        self.assertEqual(self.providers.posts(), before)
    def test_revocation_before_dispatch(self):
        self.revoke(); r = self.run_job()
        self.assertFalse(self.providers.calls); self.assertTrue(all(x['status'] == 'NEEDS_ACTION' for x in r.values()))
    def test_bridge_only_revocation_blocks(self):
        state = self.c._read(self.job); cid = state['challenge']
        self.bridge.revoke(*self.event('revoke', 'REVOKE ' + cid), cid)
        self.run_job(); self.assertFalse(self.providers.calls)
    def test_revocation_between_platforms_preserves_success(self):
        self.providers.on_post = lambda ep: self.revoke() if ep == 'photos' else None
        r = self.run_job(); self.assertEqual(r['facebook']['status'], 'VERIFIED')
        self.assertEqual([c[2] for c in self.providers.posts()], ['photos'])
    def test_revocation_after_instagram_container_blocks_publish(self):
        self.providers.on_post = lambda ep: self.revoke() if ep == 'media' else None
        self.run_job(); self.assertNotIn('media_publish', [c[2] for c in self.providers.posts()])
    def test_crash_after_post_marker_restart_fences(self):
        self.providers.fb_error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.run_job()
        self.assertEqual(self.c._read(self.job)['phase'], 'DISPATCHING')
        self.providers.fb_error = None; self.worker = self.reopen(); r = self.tick()
        self.assertEqual(r['facebook']['status'], 'NEEDS_ACTION')
        self.assertEqual(sum(c[2] == 'photos' for c in self.providers.posts()), 1)
    def test_controller_unknown_dispatch_resumes_same_receipt(self):
        receipt = self.ledger.job(self.job)['receipt']
        with self.assertRaises(ReviewError):
            self.c.dispatch(self.job, publisher=lambda *args: (_ for _ in ()).throw(TimeoutError()), enabled=True)
        self.run_job(); self.tick()
        self.assertEqual(self.ledger.job(self.job)['receipt'], receipt)
    def test_local_artifact_tamper_blocks_all_calls(self):
        Path(self.c._read(self.job)['artifact']['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ReviewError, 'MEDIA_CHANGED'): self.run_job()
        self.assertFalse(self.providers.calls)
    def test_hosted_media_tamper_blocks_submissions(self):
        self.worker.media_digest = lambda url: 'wrong'
        self.run_job(); self.assertFalse(self.providers.posts())
    def test_caption_or_targets_tamper_does_not_reapprove(self):
        state = self.c._read(self.job); state['campaign']['captions']['facebook'] = 'changed'; self.c._save(state)
        with self.assertRaises(ReviewError): self.run_job()
        self.assertFalse(self.providers.calls)
    def test_frozen_sheet_mismatch_blocks_meta_not_unrelated_tiktok(self):
        self.sheets.content['facebook_caption'] = 'changed'; self.run_job()
        self.assertEqual([c[2] for c in self.providers.posts()], ['business/photo/publish/'])
    def test_partial_sheet_log_timeout_does_not_republish(self):
        self.sheets.fail_log = True; r = self.run_job()
        self.assertEqual(r['facebook']['status'], 'VERIFIED')
        before = self.providers.posts(); self.sheets.fail_log = False; self.tick()
        self.assertEqual(self.providers.posts(), before)
    def test_unapproved_and_disabled_are_not_admitted(self):
        with self.assertRaises(PermissionError): self.worker.run(self.job)
        self.prepare(approved=False, id='unapproved')
        with self.assertRaises(ReviewError): self.run_job()
        self.assertFalse(self.providers.calls)
    def test_exact_subset_and_due_sweep(self):
        self.revoke()
        self.prepare(targets=('tiktok',), id='subset'); r = self.worker.due(enabled=True, limit=1)
        self.assertIn(self.job, r); self.assertEqual(set(r[self.job]), {'tiktok'})
        self.assertFalse(any(c[0] == 'meta' for c in self.providers.calls))
    def test_concurrent_workers_share_lock(self):
        entered = threading.Event(); release = threading.Event(); errors = []
        def on_post(ep):
            if ep == 'photos': entered.set(); release.wait(3)
        self.providers.on_post = on_post
        def run():
            try: self.run_job()
            except Exception as e: errors.append(e)
        thread = threading.Thread(target=run); thread.start(); self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(RuntimeError): self.reopen().run(self.job, enabled=True)
        finally: release.set(); thread.join(3)
        self.assertFalse(errors); self.assertEqual(sum(c[2] == 'photos' for c in self.providers.posts()), 1)
    def test_permanent_tiktok_failure_and_inbox_need_action(self):
        self.run_job(); self.providers.status = 'SEND_TO_USER_INBOX'
        self.assertEqual(self.tick()['tiktok']['status'], 'NEEDS_ACTION')
        self.assertEqual(sum(c[2] == 'business/photo/publish/' for c in self.providers.posts()), 1)
    def test_permanent_provider_failure_no_retry(self):
        self.run_job(); self.providers.status = 'FAILED'
        self.assertEqual(self.tick()['tiktok']['status'], 'FAILED')
        count = len(self.providers.calls); self.tick(); self.assertEqual(len(self.providers.calls), count)
    def test_tiktok_crash_after_acceptance_recovers_without_submission(self):
        original = self.ledger.update
        def crash(job, platform, state, **kw):
            if platform == 'tiktok' and state == 'CONTAINER_CREATED': raise KeyboardInterrupt()
            return original(job, platform, state, **kw)
        with patch.object(self.ledger, 'update', crash):
            with self.assertRaises(KeyboardInterrupt): self.run_job()
        self.assertEqual(self.ledger.op(self.job, 'tiktok')['container_id'], 'accepted-task')
        self.assertEqual(self.tick()['tiktok']['status'], 'VERIFIED')
        self.assertEqual(sum(c[2] == 'business/photo/publish/' for c in self.providers.posts()), 1)
    def test_meta_retry_rechecks_revocation(self):
        original = self.providers.meta
        calls = []
        def rate_limit(method, url, **kw):
            if url.endswith('/photos'):
                calls.append(url); self.revoke(); return meta.HttpResponse(429, {})
            return original(method, url, **kw)
        self.publisher.transport.request = rate_limit
        self.run_job(); self.assertEqual(len(calls), 1)
    def test_attempt_budget_and_permission_block(self):
        self.providers.tt_error = tiktok.Retry('TIKTOK_RATE_LIMIT', 60)
        self.run_job()
        for _ in range(4): self.tick(1000)
        self.assertEqual(sum(c[2] == 'business/photo/publish/' for c in self.providers.posts()), 4)
        self.assertEqual(self.ledger.get(self.job, 'tiktok')['state'], 'FAILED_FINAL')
    def test_invalid_meta_permalink_is_not_verified(self):
        self.run_job()
        self.ledger.update(self.job, 'facebook', 'PUBLISHED', permalink='https://evil.example/101')
        before = self.providers.posts(); r = self.tick()
        self.assertEqual(r['facebook']['status'], 'NEEDS_ACTION')
        self.assertIsNone(r['facebook']['url']); self.assertEqual(self.providers.posts(), before)
    def test_tiktok_read_budget_stops_processing_forever(self):
        self.worker.max_checks = 3; self.providers.status = 'PROCESSING'
        self.run_job(); r = self.tick()
        self.assertEqual(r['tiktok']['status'], 'NEEDS_ACTION')
        before = len(self.providers.calls); self.tick(); self.assertEqual(len(self.providers.calls), before)
    def events(self):
        with self.ledger._connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM publication_outbox ORDER BY created_at')]
    def drain_mock(self, sender):
        from toolkit import notification_outbox as notifications
        channels = {'whatsapp': 'fixture-wa', 'telegram': 'fixture-tg'}
        targets = {c: {'account': a, 'recipient': 'fixture-owner'} for c, a in channels.items()}
        with patch.object(notifications, 'CHANNELS', channels):
            return notifications.drain(self.ledger, targets, sender=sender, now=self.now)
    @staticmethod
    def sent(channel, account, recipient, message):
        return {'delivered': True, 'messageId': 'fixture-message-' + channel,
                'channel': channel, 'account': account, 'recipient': recipient}
    def test_notification_prepare_then_drain_once_per_target(self):
        from toolkit import notification_outbox as notifications
        with patch.object(notifications, 'drain', side_effect=AssertionError('MUST_NOT_SEND')):
            self.run_job(); self.run_job()
        self.assertEqual(len(self.events()), 1)
        with self.ledger._connect() as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='publication_notification_delivery'").fetchone())
        calls = []
        def sender(*args): calls.append(args); return self.sent(*args)
        result = self.drain_mock(sender)
        self.assertEqual([r['state'] for r in result], ['SENT', 'SENT'])
        self.run_job(); self.assertEqual(self.drain_mock(sender), [])
        self.assertEqual(len(calls), 2)
        self.assertTrue(all('Tiktok: PROCESSING' in call[3] for call in calls))
        self.tick(); self.assertEqual(len(self.events()), 2)
        self.assertEqual(len(self.drain_mock(sender)), 2)
        self.assertEqual(len(calls), 4)
        self.assertTrue(all('Tiktok: VERIFIED' in call[3] for call in calls[2:]))
    def test_notification_retry_counters_do_not_emit_spam(self):
        self.providers.status = 'PROCESSING'; self.run_job()
        before = self.events()[0]['event_id']
        self.tick(); self.tick()
        self.assertGreater(self.ledger.op(self.job, 'tiktok')['checks'], 1)
        self.assertEqual([e['event_id'] for e in self.events()], [before])
        payload = json.loads(self.events()[0]['payload'])
        self.assertEqual(payload['health'], 'PROCESSING')
        self.assertNotIn('next_at', self.events()[0]['payload'])
        self.assertNotIn('checks', self.events()[0]['payload'])
    def test_notification_unknown_send_never_republishes_or_resends(self):
        self.providers.status = 'PROCESSING'; self.run_job(); before = self.providers.posts()
        calls = []
        def sender(*args): calls.append(args); raise TimeoutError('unknown delivery')
        self.assertEqual([r['state'] for r in self.drain_mock(sender)], ['UNKNOWN', 'UNKNOWN'])
        self.tick(); self.assertEqual(self.providers.posts(), before)
        self.assertEqual(self.drain_mock(sender), []); self.assertEqual(len(calls), 2)
        self.assertEqual(len(self.events()), 1); self.assertEqual(self.events()[0]['state'], 'UNKNOWN')
    def test_notification_partial_unknown_and_revoked_accurate(self):
        self.providers.fb_error = TimeoutError(); self.run_job()
        payload = json.loads(self.events()[-1]['payload'])
        self.assertEqual(payload['health'], 'NEEDS_ACTION')
        self.assertEqual(payload['platforms']['facebook']['report_status'], 'NEEDS_ACTION')
        self.assertIsNone(payload['platforms']['facebook']['permalink'])
        self.assertEqual(payload['platforms']['instagram']['report_status'], 'VERIFIED')
        self.revoke(); self.run_job(); self.run_job()
        self.assertEqual(len(self.events()), 2)
        payload = json.loads(self.events()[-1]['payload'])
        self.assertEqual(payload['status'], 'APPROVAL_BLOCKED')
        self.assertEqual(payload['platforms']['instagram']['report_status'], 'VERIFIED')
        self.assertEqual(payload['platforms']['tiktok']['report_status'], 'NEEDS_ACTION')
        self.assertEqual(payload['platforms']['tiktok']['remote_id'], 'accepted-task')
        messages = []
        def sender(*args): messages.append(args[3]); return self.sent(*args)
        self.drain_mock(sender)
        self.assertIn('owner approval revoked or blocked', messages[-1])
    def test_notification_bridge_only_revocation_prepares_without_provider_calls(self):
        cid = self.c._read(self.job)['challenge']
        self.bridge.revoke(*self.event('revoke-notify', 'REVOKE ' + cid), cid)
        self.run_job(); self.assertFalse(self.providers.calls)
        payload = json.loads(self.events()[0]['payload'])
        self.assertEqual(payload['health'], 'NEEDS_ACTION')
        self.assertTrue(all(p['report_status'] == 'NEEDS_ACTION' for p in payload['platforms'].values()))
    def test_notification_payload_redacts_provider_diagnostics_and_unsafe_values(self):
        self.run_job()
        self.ledger.update(self.job, 'facebook', 'PUBLISHED', remote_id='bad id\nsecret',
                           permalink='https://facebook.com/101?access_token=secret', error_code='private raw provider body')
        self.run_job(); payload = self.events()[-1]['payload']
        self.assertNotIn('secret', payload); self.assertNotIn('private raw', payload)
        self.assertNotIn(str(self.root), payload); self.assertNotIn('Exact reviewed caption', payload)
        row = json.loads(payload)['platforms']['facebook']
        self.assertEqual(row, {'report_status': 'NEEDS_ACTION', 'remote_id': None, 'permalink': None})
    def test_notification_failed_platform_keeps_failed_status(self):
        self.run_job(); self.providers.status = 'FAILED'; self.tick()
        payload = json.loads(self.events()[-1]['payload'])
        self.assertEqual(payload['health'], 'NEEDS_ACTION')
        self.assertEqual(payload['platforms']['tiktok']['report_status'], 'FAILED')
        self.assertIsNone(payload['platforms']['tiktok']['permalink'])
    def test_notification_revocation_after_complete_does_not_erase_success(self):
        self.run_job(); self.tick(); before = self.providers.posts()
        self.revoke(); self.run_job(); self.worker = self.reopen(); self.run_job()
        self.assertEqual(len(self.events()), 3)
        payload = json.loads(self.events()[-1]['payload'])
        self.assertEqual(payload['health'], 'NEEDS_ACTION')
        self.assertEqual(payload['status'], 'APPROVAL_BLOCKED')
        self.assertTrue(all(row['report_status'] == 'VERIFIED' for row in payload['platforms'].values()))
        self.assertEqual(self.providers.posts(), before)
    def test_notification_write_failure_retry_does_not_republish(self):
        from toolkit import notification_outbox as notifications
        self.providers.status = 'PROCESSING'
        with patch.object(notifications, 'emit_job_event', side_effect=OSError('outbox unavailable')):
            with self.assertRaises(OSError): self.run_job()
        before = self.providers.posts(); self.run_job()
        self.assertEqual(self.providers.posts(), before); self.assertEqual(len(self.events()), 1)
    def test_preflight_failures_exhaust_read_budget(self):
        self.worker.max_checks = 2; self.worker.media_digest = lambda url: 'wrong'
        self.run_job(); r = self.tick()
        self.assertTrue(all(x['status'] == 'NEEDS_ACTION' for x in r.values()))
        count = len(self.providers.calls); self.tick(); self.assertEqual(len(self.providers.calls), count)


if __name__ == '__main__': unittest.main()
