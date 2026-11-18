"""Synthetic records cannot establish live management inference or phone pairing."""
import unittest
from unittest.mock import patch
from pathlib import Path
from diagnostic_evidence import routing, pairing

class DiagnosticSkills(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket', 'socket.create_connection', 'subprocess.Popen', 'os.system'):
            p = patch(target, side_effect=AssertionError('offline test attempted egress'))
            p.start(); self.addCleanup(p.stop)
        self.route = dict(global_primary='provider-a/model', agent_primary='provider-b/model', session_model='provider-a/model', utility_model=None, subagent_model=None, owner='demo', installed_version='synthetic-v1', fallback_semantics='configured agent routes only', observed_management_model='provider-b/model', authorized=True, backup_private=True, change='remove_agent_override', applied=True, global_preserved=True, auth_preserved=True, effective_agent_primary=None, effective_management_model='provider-a/model', reload_observed=True, harmless_consult_success=True, consult_model='provider-a/model')
        self.phone = {k: True for k in ('gateway_identity_locked','loopback','serve_targets_gateway','tailscale_running','service_stable','ssh_preserved','tls_valid','upgrade_valid','approval_authorized','phone_reachable','qr_displayed_privately','phone_connected','no_auth_failure','named_channels_preserved')}
        self.phone.update(funnel=False, https_status=200, http_version='1.1', wss_status=101, qr_url='wss://gateway.example.ts.net', intended_url='wss://gateway.example.ts.net', qr_auth='token', qr_access='full', qr_downgraded=False, pending_id='synthetic-request', relisted_id='synthetic-request', approved_id='synthetic-request')

    def test_complete_synthetic_routing_record(self):
        self.assertTrue(all(routing(self.route).values()))

    def test_chat_route_not_management_route(self):
        self.route['observed_management_model'] = self.route['session_model']
        self.assertFalse(routing(self.route)['diagnosis'])

    def test_missing_version_or_fallback_is_unknown(self):
        for key in ('installed_version', 'fallback_semantics', 'owner'):
            with self.subTest(key=key):
                self.assertFalse(routing({**self.route,key:None})['diagnosis'])

    def test_change_requires_scope_backup_and_preservation(self):
        for key in ('authorized','backup_private','applied','global_preserved','auth_preserved'):
            with self.subTest(key=key):
                result=routing({**self.route,key:False})
                self.assertFalse(result['configuration']); self.assertFalse(result['inference'])

    def test_saved_config_is_not_reload_or_inference(self):
        result=routing({**self.route,'reload_observed':False})
        self.assertTrue(result['configuration']); self.assertFalse(result['hot_reload']); self.assertFalse(result['inference'])

    def test_wrong_or_failed_consult_not_recovery(self):
        self.assertFalse(routing({**self.route,'consult_model':'wrong/model'})['inference'])
        self.assertFalse(routing({**self.route,'harmless_consult_success':False})['inference'])

    def test_complete_synthetic_pairing_record(self):
        self.assertTrue(all(pairing(self.phone).values()))

    def test_public_or_unstable_listener_rejected(self):
        for key,value in [('funnel',True),('loopback',False),('service_stable',False),('serve_targets_gateway',False),('ssh_preserved',False)]:
            with self.subTest(key=key): self.assertFalse(pairing({**self.phone,key:value})['phone'])

    def test_http200_and_http2_are_not_wss(self):
        for changes in ({'wss_status':200},{'http_version':'2'},{'upgrade_valid':False},{'tls_valid':False}):
            self.assertFalse(pairing({**self.phone,**changes})['host_wss'])

    def test_host_success_does_not_prove_phone(self):
        result=pairing({**self.phone,'phone_reachable':False})
        self.assertTrue(result['host_wss']); self.assertFalse(result['phone'])

    def test_qr_metadata_downgrade_wrong_target_and_no_display(self):
        for changes in ({'qr_access':'limited'},{'qr_downgraded':True},{'qr_url':'wss://wrong.example'},{'qr_displayed_privately':False}):
            self.assertFalse(pairing({**self.phone,**changes})['phone'])

    def test_exact_fresh_approval_not_latest(self):
        for changes in ({'pending_id':None},{'approved_id':'latest'},{'relisted_id':'another-request'},{'approval_authorized':False}):
            self.assertFalse(pairing({**self.phone,**changes})['approval'])

    def test_connection_and_channels_must_remain_verified(self):
        for key in ('phone_connected','no_auth_failure','named_channels_preserved'):
            self.assertFalse(pairing({**self.phone,key:False})['phone'])

    def test_empty_evidence_fails_closed(self):
        self.assertFalse(any(routing({}).values())); self.assertFalse(any(pairing({}).values()))

    def test_packaged_procedures_retain_critical_boundaries(self):
        root=Path(__file__).resolve().parents[1]/'skills'
        for name, phrases in {
            'system-management-model-routing': ('fallback','bootstrap','hot','Do not edit Gateway config through shell or direct RPC'),
            'private-mobile-gateway-pairing': ('never Funnel','101 Switching Protocols','Re-list immediately','never chat')}.items():
            body=(root/name/'SKILL.md').read_text()
            for phrase in phrases: self.assertIn(phrase,body)
            self.assertIn('NOT TESTED',(root/name/'README.md').read_text())
