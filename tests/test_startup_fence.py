import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from toolkit.startup_fence import check


class StartupFenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name); self.calls = []
        for n in ('home', 'state'): (self.root/n).mkdir(mode=0o700)
        for n in ('entry.mjs', 'config.json', 'guard.mjs'):
            (self.root/n).write_text('{}'); (self.root/n).chmod(0o600)
        self.db = self.root/'guard.sqlite'
        with sqlite3.connect(self.db) as db: db.execute('CREATE TABLE modes(customer TEXT, mode TEXT)')
        self.db.chmod(0o600)
        source = str(self.root/'guard.mjs')
        self.cfg = {'runtime': {'node': str(Path(sys.executable).resolve()),
                    'entry': str(self.root/'entry.mjs'), 'config': str(self.root/'config.json'),
                    'home': str(self.root/'home'), 'state': str(self.root/'state')},
                    'integrity': {'sha256': {source: hashlib.sha256(b'{}').hexdigest()},
                     'plugins': [{'id': 'guard', 'source': source}],
                     'databases': [{'path': str(self.db), 'tables': {'modes': ['customer', 'mode']}}]}}
        self.rows = [{'id': 'guard', 'source': source, 'enabled': True, 'status': 'loaded'}]
    def runner(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, json.dumps({'plugins': self.rows}).encode(), b'')
    def test_native_metadata_to_database_fence(self):
        before = self.db.read_bytes()
        self.assertTrue(check(self.cfg, runner=self.runner)['verified'])
        self.assertEqual(before, self.db.read_bytes())
        argv, opts = self.calls[0]
        self.assertEqual(argv[-3:], ['plugins', 'list', '--json'])
        self.assertEqual(opts['timeout'], 30)
        self.assertNotIn('shell', opts)
        self.assertNotIn('OPENAI_API_KEY', opts['env'])
    def test_disabled_plugin_not_attested(self):
        self.rows[0]['enabled'] = False
        with self.assertRaises(PermissionError): check(self.cfg, runner=self.runner)
    def test_errored_plugin_not_attested(self):
        self.rows[0]['status'] = 'error'
        with self.assertRaises(PermissionError): check(self.cfg, runner=self.runner)
    def test_ambiguous_plugin_denied(self):
        self.rows *= 2
        with self.assertRaises(PermissionError): check(self.cfg, runner=self.runner)
    def test_wrong_source_denied(self):
        self.rows[0]['source'] += '.different'
        with self.assertRaises(PermissionError): check(self.cfg, runner=self.runner)
    def test_timeout_never_accepts(self):
        def timeout(*a, **k): raise subprocess.TimeoutExpired(a[0], 30)
        with self.assertRaises(subprocess.TimeoutExpired): check(self.cfg, runner=timeout)
    def test_failed_cli_never_accepts(self):
        def failed(*a, **k): return subprocess.CompletedProcess(a[0], 1, b'{}', b'private error')
        with self.assertRaises(PermissionError): check(self.cfg, runner=failed)
    def test_shared_state_denied_before_cli(self):
        (self.root/'state').chmod(0o755)
        with self.assertRaises(PermissionError): check(self.cfg, runner=self.runner)
        self.assertFalse(self.calls)
    def test_missing_source_denied(self):
        (self.root/'guard.mjs').unlink()
        with self.assertRaises(PermissionError): check(self.cfg, runner=self.runner)
    def test_cli_failure_has_explicit_exit(self):
        config = self.root/'fence.json'; config.write_text('{}'); config.chmod(0o600)
        result = subprocess.run([sys.executable, '-m', 'toolkit.startup_fence', '--config', str(config)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 78)
        self.assertFalse(json.loads(result.stdout)['verified'])
