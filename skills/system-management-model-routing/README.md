# system-management-model-routing

Portable diagnostic procedure, not a service or runtime engine.

## Install and configure

Prerequisites: your own supported OpenClaw installation, current installed CLI/schema documentation, and read access explicitly authorized by the operator. No credential or production configuration is included. From this checkout (inspect installed CLI help first):

~~~bash
openclaw skills install ./skills/system-management-model-routing --agent YOUR_AGENT_ID
~~~

Installation syntax was checked against OpenClaw 2026.9.8 documentation, not a fresh installation in this release. Keep this checkout for references. Configure the request with your own agent/profile, scope and private evidence directory; never put tokens, QR/setup codes, configuration dumps or user identities in Git. Default scope is diagnosis only.

## Example request and evidence

“Read-only: diagnose management inference for agent demo in my specified profile. Compare global primary/fallbacks, agent override, session override, utility/subagent routes and resolved management owner. Do not modify configuration.”

Record redacted model identifiers and the installed version's fallback semantics, not auth values. A working chat model does not prove the management consult used it. If a stale pin is proven, report it; do not demand credits or switch utility routing. A supported operator change example, ONLY after separate authorization and private backup, is `openclaw config unset agents.entries.demo.model`. Verify the actual schema and profile first. A failed management bootstrap is not permission to edit config through shell/RPC.

Expected result: separate diagnosis, applied configuration, hot-reload evidence and harmless-consult result. Saved configuration or hot-reload schema alone cannot establish recovery. A missing fallback implementation/version is UNVERIFIED. Application schedulers and notifications need the separately installed automation-adapter-verification skill; it is not packaged here.

## Offline acceptance and limits

Run `python -m unittest discover -s tests -v` and `python tests/release_gate.py` from the checkout. tests/test_diagnostic_skills.py exercises the bundled pure evidence evaluator against synthetic routing and pairing success/failure cases with socket/subprocess calls denied. These are acceptance-record contract tests, NOT executions of OpenClaw, Tailscale, QR generation or a phone. Live deployment, pairing, management inference, fresh-agent installation and actual hot reload: **NOT TESTED**.

Troubleshooting: a missing tool, permission, version-specific schema or evidence is a blocker. Do not widen permissions, reset accounts, restart services or repeatedly replay a failed consult. Record unknown stages instead of claiming recovery.
