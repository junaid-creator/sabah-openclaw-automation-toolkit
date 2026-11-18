# private-mobile-gateway-pairing

Portable diagnostic procedure, not a service or runtime engine.

## Install and configure

Prerequisites: your own supported OpenClaw installation, current installed CLI/schema documentation, and read access explicitly authorized by the operator. No credential or production configuration is included. From this checkout (inspect installed CLI help first):

~~~bash
openclaw skills install ./skills/private-mobile-gateway-pairing --agent YOUR_AGENT_ID
~~~

Installation syntax was checked against OpenClaw 2026.9.8 documentation, not a fresh installation in this release. Keep this checkout for references. Configure the request with your own agent/profile, scope and private evidence directory; never put tokens, QR/setup codes, configuration dumps or user identities in Git. Default scope is diagnosis only.

## Example request and evidence

“Read-only: audit my explicitly identified loopback Gateway profile for private mobile access; preserve my SSH tunnel and named channel accounts. Do not enable Serve, install software or approve devices.”

Prerequisites for a later separately authorized setup: operator-managed Tailscale, private tailnet membership/ACLs, native mobile client and installed upstream node-connect skill for client troubleshooting. Use Serve, never Funnel. Confirm service identity and permissions before privileged changes; never treat tool availability as root authority. Read-only examples: `tailscale status --json`, `tailscale serve status --json` and `openclaw channels status --probe`. Keep their identity-bearing results private.

If local DNS fails, a placeholder diagnostic is `curl --resolve gateway.example.ts.net:443:100.64.0.10 https://gateway.example.ts.net/` using your current live name/address, without disabling TLS verification or changing DNS. HTTPS 200 is not WSS: require an HTTP/1.1 Upgrade handshake with a valid key and 101 response. Neither host check proves phone reachability or authenticated connection.

Review only allowlisted QR metadata as described in SKILL.md; keep fresh full-access QR/setup credentials in the private Control UI, never chat or tool-visible output. Re-list pending devices before exact-ID approval; never approve “latest.” Expected report separates Gateway/Serve/HTTPS/WSS, phone reachability, named channels, QR display, exact approval and connected-device evidence. A missing phone peer/request remains UNVERIFIED. Saved config during a draining restart is not activated service state.

## Offline acceptance and limits

Run `python -m unittest discover -s tests -v` and `python tests/release_gate.py` from the checkout. tests/test_diagnostic_skills.py exercises the bundled pure evidence evaluator against synthetic routing and pairing success/failure cases with socket/subprocess calls denied. These are acceptance-record contract tests, NOT executions of OpenClaw, Tailscale, QR generation or a phone. Live deployment, pairing, management inference, fresh-agent installation and actual hot reload: **NOT TESTED**.

Troubleshooting: a missing tool, permission, version-specific schema or evidence is a blocker. Do not widen permissions, reset accounts, restart services or repeatedly replay a failed consult. Record unknown stages instead of claiming recovery.
