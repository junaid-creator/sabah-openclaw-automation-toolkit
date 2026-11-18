"""Explicit allowlist recovery snapshots; never restores over live state.

Implements the original outage-readiness procedure. Snapshot data may be secret:
keep it private, outside Git. No scheduler, Gateway boot or remote backup exists.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
from .image_intake import read_attachment


def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def safe_name(name):
    p=Path(name)
    if not name or p.is_absolute() or '..' in p.parts or str(p)!=name or name in ('manifest.json',):
        raise ValueError('Unique relative logical name required')
    return p


def private_parent(path):
    path=Path(path).absolute()
    if path != path.resolve(strict=True) or not path.is_dir() or path.stat().st_uid!=os.geteuid() or path.stat().st_mode & 0o077:
        raise ValueError('Private runtime-owned parent directory required')
    return path


def empty_destination(path):
    path=Path(path).absolute()
    private_parent(path.parent)
    if path.exists() or path.is_symlink():raise ValueError('Destination must not exist')
    return path


def check_database(path):
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    try:
        if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:
            raise ValueError('SQLite integrity check failed')
    finally:db.close()


def snapshot(entries, destination):
    """entries: explicit [{name, source, kind: file|sqlite}]. No auto discovery."""
    destination=empty_destination(destination)
    if not isinstance(entries,list) or not entries or len(entries)>1000:
        raise ValueError('Bounded explicit source allowlist required')
    names=[str(safe_name(e['name'])) for e in entries]
    if len(set(names))!=len(names):raise ValueError('Duplicate logical name')
    records=[]
    with tempfile.TemporaryDirectory(prefix='.snapshot-',dir=destination.parent) as temporary:
        stage=Path(temporary)/'snapshot';stage.mkdir(mode=0o700)
        for entry in entries:
            if set(entry)!={'name','source','kind'} or entry['kind'] not in ('file','sqlite'):
                raise ValueError('Explicit supported source schema required')
            source=Path(entry['source']).absolute()
            before=source.lstat()
            if (source!=source.resolve(strict=True) or not stat.S_ISREG(before.st_mode)
                    or before.st_uid!=os.geteuid() or before.st_mode & 0o022):
                raise ValueError('Unsafe source identity, type or mode')
            target=stage/safe_name(entry['name']);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if entry['kind']=='sqlite':
                original=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
                copied=sqlite3.connect(target)
                try:
                    original.backup(copied)
                    copied.execute('PRAGMA journal_mode=DELETE')
                finally:copied.close();original.close()
                check_database(target)
            else:
                raw=read_attachment(source,[source.parent],max_bytes=100*1024*1024)
                target.write_bytes(raw)
            target.chmod(0o600)
            with target.open('rb') as handle:os.fsync(handle.fileno())
            records.append({'name':entry['name'],'kind':entry['kind'],'sha256':sha(target),
                            'bytes':target.stat().st_size,'source_mode':before.st_mode & 0o777})
        manifest={'schema':1,'files':records,'cross_file_transaction_consistency':False,
                  'isolated_gateway_boot_tested':False,'off_server_backup':False}
        path=stage/'manifest.json';path.write_text(json.dumps(manifest,sort_keys=True,indent=2));path.chmod(0o600)
        with path.open('rb') as handle:os.fsync(handle.fileno())
        fd=os.open(stage,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        os.rename(stage,destination)
        fd=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    return manifest


def restore_copy(snapshot_root, destination):
    """Restore only to a fresh isolated directory; verify all bytes and databases."""
    root=private_parent(snapshot_root)
    destination=empty_destination(destination)
    manifest=json.loads(read_attachment(root/'manifest.json',[root],max_bytes=1_000_000))
    if manifest.get('schema')!=1 or not isinstance(manifest.get('files'),list) or not manifest['files']:
        raise ValueError('Invalid manifest')
    names=[str(safe_name(e['name'])) for e in manifest['files']]
    if len(names)!=len(set(names)):raise ValueError('Duplicate manifest entry')
    with tempfile.TemporaryDirectory(prefix='.restore-',dir=destination.parent) as temporary:
        stage=Path(temporary)/'restore';stage.mkdir(mode=0o700)
        for entry in manifest['files']:
            source=root/safe_name(entry['name'])
            raw=read_attachment(source,[root],max_bytes=100*1024*1024)
            if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
                raise ValueError('Snapshot byte/hash mismatch')
            target=stage/entry['name'];target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            target.write_bytes(raw);target.chmod(0o600)
            if entry['kind']=='sqlite':check_database(target)
            elif entry['kind']!='file':raise ValueError('Unknown snapshot kind')
        os.rename(stage,destination)
    return {'verified_files':len(names),'scope':'isolated restore-copy and SQLite integrity only',
            'gateway_boot_tested':False,'live_restore':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('snapshot');a.add_argument('--allowlist',required=True);a.add_argument('--destination',required=True)
    b=sub.add_parser('restore-copy');b.add_argument('--snapshot',required=True);b.add_argument('--destination',required=True)
    a=p.parse_args()
    result=snapshot(json.loads(Path(a.allowlist).read_text()),a.destination) if a.command=='snapshot' else restore_copy(a.snapshot,a.destination)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
