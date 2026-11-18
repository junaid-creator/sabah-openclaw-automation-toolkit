import contextlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from toolkit import language, reliability, content_ledger as ledger
from toolkit import keyword_research as keywords, content_brief_generator as briefs
from toolkit import local_metadata as meta, lead_qualification as leads
from toolkit import knowledge_snapshot as kb

ROOT = Path(__file__).resolve().parents[1]

def denied(*args, **kwargs):
    raise AssertionError('External IO denied in offline tests')

class Offline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('socket.socket', denied))
        self.stack.enter_context(patch('socket.create_connection', denied))
        self.stack.enter_context(patch('subprocess.Popen', denied))
        self.stack.enter_context(patch('os.system', denied))
        self.stack.enter_context(patch.dict(os.environ, {'HOME':str(self.root), 'TOOLKIT_STATE_DIR':str(self.root)}))

    def cli(self, module, args):
        with patch.object(sys, 'argv', ['test'] + args), contextlib.redirect_stdout(io.StringIO()):
            return module.main()

    def test_language_default(self):
        self.assertEqual(language.select_language(request_text='draft equipment'), 'ENGLISH')
    def test_language_explicit(self):
        self.assertEqual(language.select_language('ar'), 'ARABIC')
        self.assertEqual(language.select_language(request_text='both languages'), 'BILINGUAL')
    def test_language_invalid(self):
        for fn in [lambda: language.select_language('bad'),lambda: language.validate_copy('text','bad'),lambda:language.select_text('x','y','bad')]:
            with self.assertRaises(ValueError): fn()
    def test_language_copy(self):
        self.assertEqual(language.validate_copy('مرحبا', 'ARABIC'), 'مرحبا')
        with self.assertRaises(ValueError): language.validate_copy('Hello مرحبا', 'ENGLISH')
        language.validate_copy('Hello مرحبا', 'BILINGUAL')
    def test_keyword_brief_pipeline(self):
        output=self.root/'keywords.json'; out2=self.root/'briefs.json'
        self.cli(keywords,['--input',str(ROOT/'examples/seeds.txt'),'--output',str(output)])
        self.cli(briefs,['--input',str(output),'--output',str(out2)])
        self.assertGreater(len(json.loads(out2.read_text())),0)
    def test_keyword_intent(self):
        self.assertEqual(keywords.detect_intent('how to inspect'),'informational')
    def test_metadata_escape(self):
        out=meta.apply_update('<head><title>Old</title></head>','<script>','"unsafe')
        self.assertNotIn('<script>',out); self.assertIn('&quot;unsafe',out)
    def test_metadata_default_dry_run(self):
        site=self.root/'site'; site.mkdir(); page=site/'a.html'; page.write_text('<head><title>Old</title></head>')
        changes=self.root/'updates.json'; changes.write_text(json.dumps([dict(path='a.html',title='New')]))
        self.cli(meta,['--site-root',str(site),'--updates',str(changes)])
        self.assertIn('Old',page.read_text())
        self.cli(meta,['--site-root',str(site),'--updates',str(changes),'--apply'])
        self.assertIn('New',page.read_text())
    def test_metadata_path_traversal(self):
        changes=self.root/'updates.json'; changes.write_text('[{"path":"../escape.html","title":"x"}]')
        with self.assertRaises(ValueError): self.cli(meta,['--site-root',str(self.root/'site'),'--updates',str(changes),'--apply'])
    def test_metadata_missing_head(self):
        with self.assertRaises(ValueError): meta.apply_update('<body>x</body>','Title',None)
    def test_lead_fixtures(self):
        out=self.root/'leads.json'
        self.cli(leads,['--profile',str(ROOT/'examples/lead-profile.json'),'--raw',str(ROOT/'examples/leads.json'),'--output',str(out)])
        self.assertEqual(len(json.loads(out.read_text())['all']),1)
    def test_lead_geo_filter(self):
        profile=json.loads((ROOT/'examples/lead-profile.json').read_text()); item=json.loads((ROOT/'examples/leads.json').read_text())[0]
        item['latitude']=90
        self.assertIsNone(leads.qualify_overture(item,profile,'2026-01-01'))
    def test_lead_dedup(self):
        items=json.loads((ROOT/'examples/leads.json').read_text()); raw=self.root/'raw.json'; raw.write_text(json.dumps(items*2)); out=self.root/'out.json'
        self.cli(leads,['--profile',str(ROOT/'examples/lead-profile.json'),'--raw',str(raw),'--output',str(out)])
        self.assertEqual(len(json.loads(out.read_text())['all']),1)
    def test_ledger_corrupt(self):
        p=self.root/'ledger.jsonl'; p.write_text('{"run_id":"one"}')
        with self.assertRaises(ValueError): ledger.load(p)
    def test_ledger_duplicates(self):
        self.assertFalse(ledger.check([dict(run_id='a',post_id='1',title='A &amp; B')],title='a & b')['clear'])
    def test_ledger_append_replay(self):
        row={k:'' for k in ledger.REQUIRED}; row.update(run_id='one',date='2026-01-01',created_at='2026-01-01T00:00:00Z',status='not-created',secondary_keywords=[])
        p=self.root/'ledger.jsonl'; ledger.append(p,row)
        with self.assertRaises(ValueError): ledger.append(p,row)
    def test_run_identity(self):
        with reliability.Run('a',{'x':1},self.root): pass
        with self.assertRaises(RuntimeError):
            with reliability.Run('a',{'x':2},self.root): pass
    def test_run_id_path_escape(self):
        with self.assertRaises(ValueError): reliability.state_path('../outside',self.root)
    def test_run_reconcile_before_write(self):
        count=[]
        with reliability.Run('b',{},self.root) as run:
            out=run.write('create',lambda:count.append(1),lambda:('matched',{'id':'fixture'}))
        self.assertEqual(count,[]); self.assertEqual(out['id'],'fixture')
    def test_run_unknown_latch(self):
        with reliability.Run('c',{},self.root) as run:
            with self.assertRaises(RuntimeError): run.write('create',denied,lambda:('unknown',{}))
            with self.assertRaises(RuntimeError): run.write('create',denied,lambda:('absent',{}))
    def test_run_retry_budget(self):
        count=[]
        with reliability.Run('d',{},self.root) as run:
            with self.assertRaises(RuntimeError): run.write('create',lambda:count.append(1),lambda:('absent',{}),sleep=lambda _:None)
        self.assertEqual(len(count),2)
    def test_snapshot_fixture(self):
        out=self.root/'kb'
        self.cli(kb,['--base-url','https://example.com','--currency','USD','--fixture',str(ROOT/'examples/site-fixture.json'),'--output',str(out)])
        self.assertEqual(json.loads((out/'products.json').read_text())['products'],[])
        self.assertIn('untrusted',(out/'company-and-policies.md').read_text())
        self.assertEqual((out/'products.json').stat().st_mode & 0o777,0o600)
    def test_snapshot_no_network_default(self):
        with self.assertRaises(ValueError): self.cli(kb,['--base-url','https://example.com','--currency','USD','--output',str(self.root/'none')])
    def test_snapshot_reject_credentials(self):
        with self.assertRaises(ValueError): self.cli(kb,['--base-url','https://user:password@example.com','--currency','USD','--fixture',str(ROOT/'examples/site-fixture.json'),'--output',str(self.root/'none')])
    def test_clean_untrusted_html(self):
        self.assertEqual(kb.clean('<p>Hello</p><script>bad()</script><p>World</p>'),'Hello\nWorld')

if __name__ == '__main__':
    unittest.main()
