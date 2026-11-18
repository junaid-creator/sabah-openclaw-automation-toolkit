import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SupportTemplateTests(unittest.TestCase):
 def test_least_privilege_and_groups_disabled(self):
  c=json.loads((ROOT/'examples/customer-routing.example.json').read_text());s=c['agents']['entries']['customer-support']
  self.assertEqual(s['tools']['allow'],['read']);self.assertEqual(s['sandbox']['workspaceAccess'],'ro');self.assertEqual(c['channels']['whatsapp']['groupPolicy'],'disabled')
 def test_owner_specific_route_and_test_allowlist(self):
  c=json.loads((ROOT/'examples/customer-routing.example.json').read_text());self.assertEqual(c['bindings'][0]['agentId'],'main-assistant');self.assertEqual(c['bindings'][0]['match']['peer']['kind'],'direct');self.assertEqual(c['channels']['whatsapp']['dmPolicy'],'allowlist')
 def test_no_implicit_business_facts(self):
  p=json.loads((ROOT/'agents/customer-support/company-profile.example.json').read_text());self.assertTrue(p['example_only']);self.assertEqual(p['verified_facts'],[])
