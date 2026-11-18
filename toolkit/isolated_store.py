"""Explicit private, caller-owned isolated stores. No implicit home/config paths.

POSIX flock coordinates cooperating processes. Same-UID malicious writers are
outside this boundary; hardlinks/symlinks and permissive state are refused.
"""
import json
import os
import stat
from pathlib import Path
from .reliability import atomic_json, lock

class Store:
    def __init__(self, root, namespace):
        self.root = Path(root).absolute()
        if self.root != self.root.resolve(strict=True) or not self.root.is_dir():
            raise ValueError('Existing nonsymlink isolated directory required')
        s=self.root.stat()
        if s.st_uid != os.geteuid() or s.st_mode & 0o077:
            raise PermissionError('Private owner-only directory required')
        if namespace not in {'oauth','business-oauth','voice'}: raise ValueError('Invalid namespace')
        self.path=self.root/(namespace+'.json'); self.lockpath=self.root/(namespace+'.lock')
        self.check(self.path); self.check(self.lockpath)
    @staticmethod
    def check(path):
        if path.is_symlink(): raise PermissionError('Symlink refused')
        if path.exists():
            s=path.stat()
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=os.geteuid() or s.st_mode & 0o077:
                raise PermissionError('Private regular owner file required')
    def guard(self):
        self.check(self.lockpath)
        # Ensure reliability.lock opens an already-private file.
        fd=os.open(self.lockpath,os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600);os.close(fd)
        return lock(self.lockpath)
    def read(self):
        self.check(self.path)
        if not self.path.exists(): return {}
        if self.path.stat().st_size > 4*1024*1024: raise ValueError('State exceeds bound')
        return json.loads(self.path.read_text())
    def save(self,value):
        self.check(self.path);atomic_json(self.path,value)
