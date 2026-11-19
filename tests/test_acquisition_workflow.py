"""Offline assembly acceptance; sockets/process creation are denied."""
import copy
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from toolkit.acquisition_workflow import (ApifySource, OvertureSource, billing_evidence_status,
    monitor_billing, weekly_leads, claim_report, report_receipt)
from toolkit.apify_client import ApifyClient
from toolkit.google_sheets import GogSheets, TABS
from toolkit.lead_qualification import HEADERS
from toolkit.report_outbox import Outbox


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime.now(timezone.utc)
        self.evidence = self.root / 'billing.json'
        self.evidence.write_text(json.dumps(dict(
            policy_verified_at=(self.now-timedelta(days=1)).isoformat(),
            credit_verified_at=(self.now-timedelta(hours=1)).isoformat(),
            cycle_start=(self.now-timedelta(days=2)).isoformat(),
            cycle_end=(self.now+timedelta(days=20)).isoformat(), remaining_usd=2,
            monthly_limit_usd=5, free_plan_verified=True, no_overage_verified=True)))
        for target in ('socket.socket', 'subprocess.Popen'):
            guard = patch(target, side_effect=AssertionError('No live transports'))
            guard.start()
            self.addCleanup(guard.stop)
        self.profile = dict(geographic_targets=dict(area='Fixture', latitude_min=0,
            latitude_max=1, longitude_min=0, longitude_max=1),
            industry_keywords=dict(direct=['contracting'], adjacent=['maintenance']))
        self.features = [self.feature(), self.feature(), self.feature('duplicate-id')]
        self.download_calls = []
        executable = self.root / 'fixture-overture'
        executable.write_text('fixture only')
        output = self.root / 'features.json'
        def downloader(command, **kwargs):
            self.assertEqual(kwargs['timeout'], 180)
            self.download_calls.append(command)
            output.write_text(json.dumps({'features': self.features}))
            return SimpleNamespace(returncode=0)
        self.source = OvertureSource(executable, (0, 0, 1, 1), output,
                                     allow_download=True, runner=downloader)
        self.rows = {tab: [HEADERS.copy()] for tab in TABS}
        self.writes = []
        self.write_mode = 'success'
        self.fail_read = False
        def sheets_runner(command, **kwargs):
            self.assertEqual(kwargs['timeout'], 45)
            tab = command[4].split("'")[1]
            if command[2] == 'get':
                if self.fail_read:
                    raise subprocess.TimeoutExpired(command, 45)
                return SimpleNamespace(returncode=0, stdout=json.dumps({'values': self.rows[tab]}))
            target = json.loads(next(x.split('=', 1)[1] for x in command if x.startswith('--values-json=')))
            self.writes.append(tab)
            if self.write_mode != 'unknown':
                self.rows[tab] = target
            if self.write_mode in {'unknown', 'committed_timeout'}:
                raise subprocess.TimeoutExpired(command, 45)
            return SimpleNamespace(returncode=0, stdout='{}')
        self.sheets = GogSheets('fixture@example.test', 'fixture', runner=sheets_runner,
                               env={}, allow_reads=True, allow_writes=True)
        self.outbox = Outbox(self.root / 'outbox.json', account='fixture', recipient='owner')

    def feature(self, id='one'):
        return dict(id=id, geometry=dict(type='Point', coordinates=[0.5, 0.5]),
            properties=dict(names=dict(primary='Example Contracting'), taxonomy=dict(primary='contractor'),
                            phones=['+10000000000'], websites=['https://example.test']))

    def tick(self, **kwargs):
        args = dict(root=self.root / 'runs', source=self.source, profile=self.profile,
                    today='2026-11-19', sheets=self.sheets, sheet_id='fixture-sheet', outbox=self.outbox)
        args.update(kwargs)
        return weekly_leads('2026-W47', **args)

    def approve(self):
        result = self.tick()
        self.assertEqual(result['status'], 'WAITING_APPROVAL')
        return result, {p['tab']: p['digest'] for p in result['plans']}

    def apify(self, *, authorize=True, mode='success', count=1):
        calls = []
        item = dict(name='Example Contracting', tags={'office': 'company'}, latitude=0.5,
                    longitude=0.5, website='https://example.test', phone='+10000000000',
                    osmUrl='https://www.openstreetmap.org/node/1', osmType='node', osmId=1)
        def transport(method, path, payload):
            calls.append((method, path))
            if method == 'POST':
                if mode == 'start_timeout':
                    raise TimeoutError('private detail')
                return dict(id='fixture-run', defaultDatasetId='fixture-data',
                    options=dict(maxTotalChargeUsd=0.2, isMaxTotalChargeUsdSetByUser=True))
            if path == 'acts/fixture~actor':
                return dict(id='fixture-id', pricingInfos=[dict(pricingModel='PAY_PER_EVENT')])
            if path.startswith('actor-runs?'):
                return dict(items=[], total=0, count=0, offset=0, limit=100, desc=False)
            if path.startswith('actor-runs/'):
                return dict(status={'processing': 'RUNNING', 'failed': 'FAILED'}.get(mode, 'SUCCEEDED'), usageTotalUsd=0.1)
            if path.startswith('datasets/'):
                return [copy.deepcopy(item) for _ in range(count)]
            raise AssertionError(path)
        client = ApifyClient('fixture~actor', 'fixture-id', lambda: 'not-used', transport=transport)
        self.source = ApifySource(client, {'fixture': True}, state_path=self.root / 'apify.json',
            evidence_path=self.evidence, authorize=lambda digest: authorize)
        return calls

    def test_overture_full_assembly_and_no_replay(self):
        result, approval = self.approve()
        self.assertEqual((result['collected'], result['matching'], result['new']), (3, 1, 1))
        self.assertEqual(self.writes, [])
        result = self.tick(approved_digests=approval)
        self.assertEqual(result['status'], 'REPORT_PREPARED')
        self.assertEqual(self.writes, list(TABS[:2]))
        self.assertEqual(self.tick()['report_key'], result['report_key'])
        self.assertEqual(len(self.download_calls), 1)
        self.assertEqual(len(self.writes), 2)
        self.assertEqual(self.rows[TABS[2]], [HEADERS])
        row = claim_report(self.outbox, result['report_key'])
        self.assertEqual(row['payload']['counts']['matching'], 1)
        report_receipt(self.outbox, result['report_key'], 'fixture-message')
        with self.assertRaises(RuntimeError):
            claim_report(self.outbox, result['report_key'])

    def test_report_timeout_and_crash_fenced(self):
        _, approval = self.approve()
        result = self.tick(approved_digests=approval)
        claim_report(self.outbox, result['report_key'])
        with self.assertRaises(RuntimeError):
            claim_report(self.outbox, result['report_key'])
        report_receipt(self.outbox, result['report_key'])
        with self.assertRaises(RuntimeError):
            claim_report(self.outbox, result['report_key'])
        self.tick()
        self.assertEqual(len(self.writes), 2)

    def test_report_destination_mismatch(self):
        _, approval = self.approve()
        result = self.tick(approved_digests=approval)
        other = Outbox(self.outbox.path, account='fixture', recipient='other')
        with self.assertRaises(ValueError):
            claim_report(other, result['report_key'])

    def test_unknown_sheet_write_never_replayed(self):
        result, approval = self.approve()
        self.write_mode = 'unknown'
        self.assertEqual(self.tick(approved_digests=approval)['status'], 'NEEDS_ACTION')
        self.assertEqual(self.tick(approved_digests=approval)['status'], 'NEEDS_ACTION')
        self.assertEqual(self.writes, [TABS[0]])
        self.rows[TABS[0]] = result['plans'][0]['target']
        self.write_mode = 'success'
        self.assertEqual(self.tick(approved_digests=approval)['status'], 'REPORT_PREPARED')
        self.assertEqual(self.writes, list(TABS[:2]))

    def test_committed_timeout_readback_verified(self):
        _, approval = self.approve()
        self.write_mode = 'committed_timeout'
        self.assertEqual(self.tick(approved_digests=approval)['status'], 'REPORT_PREPARED')
        self.assertEqual(len(self.writes), 2)

    def test_remote_drift_blocks_writes(self):
        _, approval = self.approve()
        self.rows[TABS[0]].append(['different'] * 19)
        self.assertEqual(self.tick(approved_digests=approval)['status'], 'NEEDS_ACTION')
        self.assertEqual(self.writes, [])

    def test_plan_read_timeout_retry_only_reads(self):
        self.fail_read = True
        self.assertEqual(self.tick()['status'], 'NEEDS_ACTION')
        self.fail_read = False
        self.assertEqual(self.tick()['status'], 'WAITING_APPROVAL')
        self.assertEqual(len(self.download_calls), 1)
        self.assertEqual(self.writes, [])

    def test_changed_run_binding_rejected(self):
        self.approve()
        with self.assertRaises(RuntimeError):
            self.tick(min_score=71)

    def test_review_history_preserved_cross_source_dedup(self):
        old = [''] * 19
        old[0], old[1], old[5] = 'old-source', 'Other name', 'https://example.test'
        old[14], old[16], old[17], old[18] = '2025-01-01', 'REVIEWED', 'CONTACTED', 'Owner note'
        self.rows[TABS[0]].append(old)
        result, approval = self.approve()
        self.assertEqual(result['new'], 0)
        self.tick(approved_digests=approval)
        new = self.rows[TABS[0]][1]
        self.assertEqual([new[i] for i in (0, 14, 16, 17)], [old[i] for i in (0, 14, 16, 17)])
        self.assertIn('Owner note', new[18])

    def test_zero_matches_do_not_lower_threshold(self):
        result = self.tick(min_score=100)
        self.assertEqual((result['matching'], result['new']), (0, 0))
        self.assertEqual(result['sheet_url'], 'https://docs.google.com/spreadsheets/d/fixture-sheet/edit')

    def test_download_timeout_is_latched(self):
        self.source.runner = lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired('fixture', 180))
        self.assertEqual(self.tick()['status'], 'NEEDS_ACTION')
        with patch.object(self.source, 'acquire', side_effect=AssertionError('must not retry')):
            self.assertEqual(self.tick()['status'], 'NEEDS_ACTION')

    def test_apify_full_assembly_dedup(self):
        calls = self.apify(count=2)
        result, approval = self.approve()
        self.assertEqual((result['collected'], result['matching']), (2, 1))
        self.assertEqual(self.tick(approved_digests=approval)['status'], 'REPORT_PREPARED')
        self.assertEqual(sum(m == 'POST' for m, p in calls), 1)

    def test_apify_explicit_consent_required(self):
        calls = self.apify(authorize=False)
        self.assertEqual(self.tick()['status'], 'NEEDS_ACTION')
        self.assertEqual(calls, [])

    def test_apify_start_timeout_no_second_post(self):
        calls = self.apify(mode='start_timeout')
        self.assertEqual(self.tick()['status'], 'NEEDS_ACTION')
        self.assertEqual(self.tick()['status'], 'NEEDS_ACTION')
        self.assertEqual(sum(m == 'POST' for m, p in calls), 1)

    def test_apify_processing_bounded_tick(self):
        calls = self.apify(mode='processing')
        self.assertEqual(self.tick()['status'], 'PROCESSING')
        self.assertEqual(self.tick()['status'], 'PROCESSING')
        self.assertEqual(sum(m == 'POST' for m, p in calls), 1)
        self.assertEqual(sum(p == 'actor-runs/fixture-run' for m, p in calls), 2)

    def test_apify_failed_run_blocked(self):
        self.apify(mode='failed')
        self.assertEqual(self.tick()['status'], 'NEEDS_ACTION')
        self.assertEqual(self.writes, [])

    def test_apify_truncation_not_claimed_complete(self):
        self.apify(count=100)
        result = self.tick()
        self.assertEqual(result['status'], 'NEEDS_ACTION')
        self.assertIn('TRUNCATED', result['blocker'])

    def test_billing_status_transition_change_dedup(self):
        state = self.root / 'monitor.json'
        first = monitor_billing(self.evidence, state_path=state, now=self.now)
        self.assertEqual(first['status'], 'VALID')
        self.assertTrue(first['changed'])
        self.assertFalse(monitor_billing(self.evidence, state_path=state, now=self.now)['changed'])
        self.assertEqual(billing_evidence_status(self.evidence, now=self.now+timedelta(days=6))['status'], 'EXPIRING')
        self.assertEqual(billing_evidence_status(self.evidence, now=self.now+timedelta(days=8))['status'], 'BLOCKED')

    def test_crashed_sheet_claim_read_only_recovery(self):
        result, approval = self.approve()
        path = self.root / 'runs' / '2026-W47.json'
        checkpoint = json.loads(path.read_text())
        checkpoint['operations']['sheet:' + TABS[0]] = {'state': 'WRITING'}
        path.write_text(json.dumps(checkpoint))
        self.assertEqual(self.tick(approved_digests=approval)['status'], 'NEEDS_ACTION')
        self.assertEqual(self.writes, [])
        self.rows[TABS[0]] = result['plans'][0]['target']
        self.assertEqual(self.tick(approved_digests=approval)['status'], 'REPORT_PREPARED')
        self.assertEqual(self.writes, [TABS[1]])

    def test_report_prepare_failure_does_not_repeat_sheet_writes(self):
        _, approval = self.approve()
        with patch.object(self.outbox, 'prepare', side_effect=OSError('fixture')):
            self.assertEqual(self.tick(approved_digests=approval)['status'], 'NEEDS_ACTION')
        self.assertEqual(len(self.writes), 2)
        self.assertEqual(self.tick()['status'], 'REPORT_PREPARED')
        self.assertEqual(len(self.writes), 2)

    def test_billing_cycle_policy_and_reserve_rejected(self):
        original = json.loads(self.evidence.read_text())
        for change in (
            {'cycle_end': self.now.isoformat()},
            {'policy_verified_at': (self.now-timedelta(days=31)).isoformat()},
            {'remaining_usd': 0.49},
            {'credit_verified_at': (self.now+timedelta(days=1)).isoformat()},
        ):
            self.evidence.write_text(json.dumps({**original, **change}))
            self.assertEqual(billing_evidence_status(self.evidence, now=self.now)['status'], 'BLOCKED')
        self.evidence.write_text('null')
        self.assertEqual(billing_evidence_status(self.evidence, now=self.now)['status'], 'BLOCKED')

    def test_billing_malformed_missing(self):
        self.evidence.write_text('broken')
        self.assertEqual(billing_evidence_status(self.evidence, now=self.now)['status'], 'BLOCKED')
        self.evidence.unlink()
        self.assertEqual(billing_evidence_status(self.evidence, now=self.now)['status'], 'BLOCKED')

    def test_no_approval_no_write(self):
        self.approve()
        self.assertEqual(self.tick(approved_digests={TABS[0]: 'wrong'})['status'], 'WAITING_APPROVAL')
        self.assertEqual(self.writes, [])


if __name__ == '__main__':
    unittest.main()
