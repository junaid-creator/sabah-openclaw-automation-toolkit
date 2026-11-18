import argparse
import contextlib
import io
import json
import unittest
from unittest.mock import patch
from toolkit import elementor_plan as p

class PlanTests(unittest.TestCase):
    def args(self, **kw):
        value=dict(command='/create-landing-page',site_url='https://example.com',admin_path='/wp-admin/',page_title='Example',session='test-session')
        value.update(kw)
        return argparse.Namespace(**value)
    def test_all_shorthands_plan_only(self):
        for command in p.SUPPORTED_COMMANDS:
            steps=p.build_plan(self.args(command=command),{'audience':'Example'})
            self.assertEqual(steps[0]['step'],'open_admin')
            self.assertTrue(all('publish' not in s['command'] for s in steps))
    def test_trusted_origin(self):
        for origin in ['http://example.com','https://u:p@example.com','https://example.com/path','https://example.com?x=y','file:///etc/passwd']:
            with self.assertRaises(ValueError):p.build_plan(self.args(site_url=origin),{})
    def test_admin_path_guard(self):
        for path in ['wp-admin/','/../admin/','/admin/?key=value','/admin/#x']:
            with self.assertRaises(ValueError):p.build_plan(self.args(admin_path=path),{})
    def test_cli_never_implies_execution(self):
        stream=io.StringIO()
        with patch('sys.argv',['plan','/wp-login','--site-url','https://example.com']),contextlib.redirect_stdout(stream):p.main()
        result=json.loads(stream.getvalue())
        self.assertTrue(result['dry_run'])
        self.assertFalse(result['executed'])
    def test_unsupported_command_rejected(self):
        with self.assertRaises(ValueError):p.build_plan(self.args(command='/publish'),{})

if __name__=='__main__':unittest.main()
