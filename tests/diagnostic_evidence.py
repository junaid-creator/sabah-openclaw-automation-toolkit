"""Pure synthetic acceptance-record checks, NOT runtime probes or authority."""

def routing(e):
    required = ('global_primary', 'agent_primary', 'session_model', 'utility_model',
                'subagent_model', 'owner', 'installed_version', 'fallback_semantics')
    compared = all(k in e for k in required) and bool(e.get('owner')) and bool(e.get('installed_version')) and bool(e.get('fallback_semantics'))
    selected = e.get('agent_primary') or e.get('global_primary')
    diagnosis = compared and e.get('observed_management_model') == selected
    applied = e.get('authorized') is True and e.get('backup_private') is True and e.get('change') == 'remove_agent_override' and e.get('applied') is True
    preserved = e.get('global_preserved') is True and e.get('auth_preserved') is True
    reload_ok = applied and preserved and e.get('effective_agent_primary') is None and e.get('effective_management_model') == e.get('global_primary') and e.get('reload_observed') is True
    consult = reload_ok and e.get('harmless_consult_success') is True and e.get('consult_model') == e.get('global_primary')
    return {'diagnosis': bool(diagnosis), 'configuration': bool(applied and preserved), 'hot_reload': bool(reload_ok), 'inference': bool(consult)}

def pairing(e):
    private = all(e.get(k) is True for k in ('gateway_identity_locked','loopback','serve_targets_gateway','tailscale_running','service_stable','ssh_preserved')) and e.get('funnel') is False
    https = private and e.get('tls_valid') is True and e.get('https_status') == 200
    wss = https and e.get('http_version') == '1.1' and e.get('upgrade_valid') is True and e.get('wss_status') == 101
    qr = e.get('qr_url') == e.get('intended_url') and str(e.get('intended_url','')).startswith('wss://') and e.get('qr_auth') == 'token' and e.get('qr_access') == 'full' and e.get('qr_downgraded') is False
    request = e.get('pending_id')
    approval = bool(request) and request == e.get('relisted_id') == e.get('approved_id') and e.get('approval_authorized') is True
    phone = wss and qr and approval and all(e.get(k) is True for k in ('phone_reachable','qr_displayed_privately','phone_connected','no_auth_failure','named_channels_preserved'))
    return {'private_listener': bool(private), 'host_https': bool(https), 'host_wss': bool(wss), 'qr_metadata': bool(qr), 'approval': bool(approval), 'phone': bool(phone)}
