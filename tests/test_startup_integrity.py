import copy, hashlib, os, sqlite3, tempfile, unittest
from pathlib import Path
from toolkit.gateway_monitor import startup_integrity

class StartupIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'guard.mjs';self.source.write_text('// fixture')
        self.db=self.root/'guard.sqlite'
        with sqlite3.connect(self.db) as db:db.execute('CREATE TABLE modes(customer TEXT, mode TEXT)')
        self.db.chmod(0o600)
        self.config={'sha256':{str(self.source):hashlib.sha256(self.source.read_bytes()).hexdigest()},
                     'plugins':[{'id':'guard','source':str(self.source)}],
                     'databases':[{'path':str(self.db),'tables':{'modes':['customer','mode']}}]}
    def run_gate(self):return startup_integrity(self.config,plugin_source_reader=lambda _:str(self.source))
    def test_exact_contract_passes_without_mutation(self):
        before=self.db.read_bytes();self.assertTrue(self.run_gate()['verified']);self.assertEqual(before,self.db.read_bytes())
    def test_changed_source_fails(self):
        self.source.write_text('// changed')
        with self.assertRaises(PermissionError):self.run_gate()
    def test_wrong_active_plugin_fails(self):
        with self.assertRaises(PermissionError):startup_integrity(self.config,plugin_source_reader=lambda _:'/different/source')
    def test_missing_database_not_created(self):
        self.db.unlink()
        with self.assertRaises(ValueError):self.run_gate()
        self.assertFalse(self.db.exists())
    def test_schema_mismatch_fails(self):
        self.config['databases'][0]['tables']['modes'].append('missing')
        with self.assertRaises(PermissionError):self.run_gate()
    def test_unsafe_identifier_fails(self):
        self.config['databases'][0]['tables']={'modes; DROP TABLE modes':['mode']}
        with self.assertRaises(ValueError):self.run_gate()
    def test_shared_database_fails(self):
        self.db.chmod(0o644)
        with self.assertRaises(PermissionError):self.run_gate()
    def test_symlink_source_fails(self):
        real=self.root/'real';self.source.rename(real);self.source.symlink_to(real)
        with self.assertRaises(PermissionError):self.run_gate()
    def test_empty_attestation_fails(self):
        self.config['plugins']=[]
        with self.assertRaises(ValueError):self.run_gate()
    def test_corrupt_database_fails(self):
        self.db.write_bytes(b'not a database')
        with self.assertRaises(sqlite3.DatabaseError):self.run_gate()
