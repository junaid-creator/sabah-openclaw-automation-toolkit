#!/usr/bin/env python3
"""Reconstructed local reliability primitives; no network or publication capability."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

ROOT = Path(os.environ.get('TOOLKIT_STATE_DIR', str(Path.home() / '.local/state/automation-toolkit')))
STATE = ROOT / 'runs'

@contextlib.contextmanager
def lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another local blog operation holds the lock') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.checkpoint-')
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def state_path(run_id, root=STATE):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,180}', run_id):
        raise ValueError('Invalid run ID')
    return Path(root) / (run_id + '.json')

class Run:
    """Hold for the ENTIRE orchestration. Global lock covers all local run IDs.
    A crashed sending operation is unresolved, never implicitly retried.
    """
    def __init__(self, run_id, plan, root=STATE):
        self.path = state_path(run_id, root)
        self.guard = lock(Path(root) / 'workflow.lock')
        self.run_id, self.plan = run_id, plan
    def __enter__(self):
        self.guard.__enter__()
        try:
            if self.path.exists():
                self.data = json.loads(self.path.read_text())
                if self.data['plan_hash'] != identity(self.plan):
                    raise RuntimeError('Run ID already bound to a different plan')
            else:
                self.data = dict(run_id=self.run_id, plan_hash=identity(self.plan),
                                 plan=self.plan, operations={})
                atomic_json(self.path, self.data)
            return self
        except BaseException:
            self.guard.__exit__(None, None, None)
            raise
    def __exit__(self, *args):
        return self.guard.__exit__(*args)
    def checkpoint(self, operation, state, **evidence):
        self.data['operations'][operation] = dict(state=state, **evidence)
        atomic_json(self.path, self.data)
    def write(self, operation, write, reconcile, sleep=time.sleep):
        """reconcile -> ('matched', evidence), ('absent', evidence), or ('unknown', evidence).
        'absent' must be authoritative, not an empty eventually-consistent search.
        No match or authoritative absence = stop. Two writes max across restarts.
        """
        previous = self.data['operations'].get(operation, {})
        if previous.get('state') == 'verified':
            return previous.get('evidence')
        if previous.get('state') == 'review_required':
            raise RuntimeError('Review latch set; explicit operator reconciliation required')
        attempts = previous.get('attempts', 0)
        while True:
            status, evidence = reconcile()
            if status == 'matched':
                self.checkpoint(operation, 'verified', attempts=attempts, evidence=evidence)
                return evidence
            if status != 'absent' or attempts >= 2:
                self.checkpoint(operation, 'review_required', attempts=attempts, evidence=evidence)
                raise RuntimeError('Uncertain result or retry budget exhausted; reconcile manually')
            if attempts:
                sleep(2 ** attempts)
            attempts += 1
            self.checkpoint(operation, 'sending', attempts=attempts)
            try:
                write()
            except Exception:
                # Do not persist provider error text/secrets. Next step is always a read.
                self.checkpoint(operation, 'unknown', attempts=attempts)
