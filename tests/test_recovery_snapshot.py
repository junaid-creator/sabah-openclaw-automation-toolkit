import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from toolkit.recovery_snapshot import snapshot,restore_copy

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir(mode=0o700)
        self.config=self.source/'config.txt';self.config.write_text('synthetic configuration');self.config.chmod(0o600)
        self.database=self.source/'ledger.sqlite3'
        self.db=sqlite3.connect(self.database);self.addCleanup(self.db.close)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('CREATE TABLE events(id INTEGER PRIMARY KEY,value TEXT)');self.db.execute("INSERT INTO events(value) VALUES('fixture')");self.db.commit();self.database.chmod(0o600)
        self.entries=[{'name':'configuration.txt','source':str(self.config),'kind':'file'},{'name':'data/ledger.sqlite3','source':str(self.database),'kind':'sqlite'}]
    def test_wal_backup_and_isolated_restore(self):
        before=self.config.read_bytes();manifest=snapshot(self.entries,self.root/'backup')
        self.assertEqual(len(manifest['files']),2)
        self.assertFalse(manifest['cross_file_transaction_consistency'])
        self.assertEqual(restore_copy(self.root/'backup',self.root/'restore')['verified_files'],2)
        restored=sqlite3.connect(self.root/'restore/data/ledger.sqlite3')
        try:self.assertEqual(restored.execute('SELECT value FROM events').fetchall(),[('fixture',)])
        finally:restored.close()
        self.assertEqual(self.config.read_bytes(),before)
        self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
    def test_existing_destination_refused(self):
        with self.assertRaises(ValueError):snapshot(self.entries,self.source)
        snapshot(self.entries,self.root/'backup')
        with self.assertRaises(ValueError):restore_copy(self.root/'backup',self.source)
    def test_corruption_refused(self):
        snapshot(self.entries,self.root/'backup')
        (self.root/'backup/configuration.txt').write_text('changed')
        with self.assertRaises(ValueError):restore_copy(self.root/'backup',self.root/'restore')
        self.assertFalse((self.root/'restore').exists())
    def test_symlink_and_traversal_refused(self):
        alias=self.source/'alias';alias.symlink_to(self.config)
        with self.assertRaises(ValueError):snapshot([{'name':'x','source':str(alias),'kind':'file'}],self.root/'backup')
        for name in ['../escape','/absolute','manifest.json']:
            with self.assertRaises(ValueError):snapshot([dict(self.entries[0],name=name)],self.root/'backup')
    def test_bad_database_refused(self):
        with self.assertRaises(sqlite3.DatabaseError):snapshot([dict(self.entries[0],kind='sqlite')],self.root/'backup')
        self.assertFalse((self.root/'backup').exists())
    def test_private_permissions_and_no_source_paths(self):
        manifest=snapshot(self.entries,self.root/'backup')
        self.assertNotIn(str(self.source),json.dumps(manifest))
        for p in (self.root/'backup').rglob('*'):
            if p.is_file():self.assertEqual(p.stat().st_mode & 0o777,0o600)
    def test_duplicate_names_refused(self):
        with self.assertRaises(ValueError):snapshot([self.entries[0],self.entries[0]],self.root/'backup')
    def test_manifest_path_tamper_refused(self):
        snapshot(self.entries,self.root/'backup')
        p=self.root/'backup/manifest.json';value=json.loads(p.read_text());value['files'][0]['name']='../escape';p.write_text(json.dumps(value))
        with self.assertRaises(ValueError):restore_copy(self.root/'backup',self.root/'restore')

if __name__=='__main__':unittest.main()
