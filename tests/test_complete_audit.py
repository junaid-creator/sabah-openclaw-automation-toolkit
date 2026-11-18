import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class CompleteAuditTests(unittest.TestCase):
    def setUp(self):self.audit=json.loads((ROOT/'docs/complete-capability-audit.json').read_text())
    def test_all_old_records_preserved_once(self):
        rows=self.audit['legacy_record_assignments'];self.assertEqual(len(rows),460);self.assertEqual({r['record'] for r in rows},set(range(460)))
        groups={g['id'] for g in self.audit['capabilities']};self.assertTrue(all(r['capability'] in groups for r in rows))
    def test_strict_status_and_required_evidence_fields(self):
        fields={'purpose','agents','trigger','authentication','source_paths_and_hashes','dependencies_and_native_tools','original_execution_mechanism','schedules_or_events','accounts_and_permissions','public_implementation_paths','configuration_and_installation','test_evidence','missing_functionality_or_restrictions','status'}
        for group in self.audit['capabilities']:
            self.assertTrue(fields<=set(group));self.assertIn(group['status'],self.audit['allowed_statuses'])
    def test_every_claimed_implementation_exists(self):
        for group in self.audit['capabilities']:
            for path in group['public_implementation_paths']:self.assertTrue((ROOT/path).is_file(),path)
    def test_fresh_sources_and_hashes_accounted(self):
        groups={g['id'] for g in self.audit['capabilities']}
        for source in self.audit['source_register']:
            self.assertNotIn('physical_path_private',source);self.assertTrue(source['capabilities']);self.assertTrue(set(source['capabilities'])<=groups)
            if source.get('sha256'):self.assertRegex(source['sha256'],r'^[a-f0-9]{64}$')
    def test_no_exhaustive_or_live_claim(self):
        summary=self.audit['summary'];self.assertFalse(summary['audit_is_exhaustive']);self.assertEqual(summary['fresh_live_external_workflows_accepted'],0)
        originals=[g for g in self.audit['capabilities'] if g['category'] in ('A','B','C')];self.assertEqual(len(originals),summary['bounded_original_capability_groups'])
        self.assertEqual(summary['original_skill_packages_present'],22)
if __name__=='__main__':unittest.main()
