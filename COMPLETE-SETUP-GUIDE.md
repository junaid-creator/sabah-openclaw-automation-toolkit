# Complete setup guide — PARTIAL functional reproduction

This is a complete installation guide for the **published subset**, not a claim that every production capability is ported. See [feature matrix](FEATURE-REPLICATION-MATRIX.md). No fresh OpenClaw/VPS end-to-end acceptance is available. The inert scaffold and standalone libraries are tested locally.

## 1. Install the standalone toolkit

Use a separate unprivileged Linux account or disposable VPS. Python 3.11+ is required; Python 3.14 is the recorded test runtime. Review pinned dependencies before allowing their installation network access.

~~~bash
git clone https://github.com/junaid-creator/sabah-openclaw-automation-toolkit.git
cd sabah-openclaw-automation-toolkit
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tests/release_gate.py
.venv/bin/python -m toolkit.setup_scaffold --destination "$HOME/toolkit-staging"
# Explicit opt-in; destination must not already exist:
.venv/bin/python -m toolkit.setup_scaffold --destination "$HOME/toolkit-staging" --apply
~~~

The scaffold creates two private workspaces, empty knowledge directories, private state, an inactive activation plan and a REVIEW-ONLY routing example. It runs no subprocess/network call, installs no skills, writes no Gateway config and registers no schedules. It refuses existing destinations and .openclaw profile paths. Do not place private state inside this Git checkout.

## 2. Install OpenClaw separately

Follow the [official installation](https://docs.openclaw.ai/start/getting-started). Select a currently supported release. Run its onboarding/configuration UI to select your own provider and model. Never copy another installation's auth directory or customer history. Read [dependencies](DEPENDENCIES.md).

The following is a **manual opt-in on the new installation only**, after reviewing CLI help and authorizing configuration changes. It is not executed by the scaffold:

~~~bash
openclaw agents add --help
openclaw agents add main-assistant --workspace "$HOME/toolkit-staging/main-assistant" --model YOUR_PROVIDER/YOUR_MODEL
openclaw agents add customer-support --workspace "$HOME/toolkit-staging/customer-support" --model YOUR_PROVIDER/YOUR_MODEL
openclaw agents list --bindings
~~~

CLI syntax was checked against installed OpenClaw documentation, not exercised against a new Gateway. Do not assume future versions retain the same config schema. Configure each agent's auth deliberately. Give customer-support only sandboxed read access to its reviewed knowledge; no exec, file writes, other-agent sessions, administrative tools or proactive sender. Test isolation before connecting customers. Prompt policies are not security boundaries.

## 3. Review and install selected original skills

~~~bash
openclaw skills install --help
openclaw skills install ./skills/offline-automation-review --agent main-assistant
openclaw skills check --agent main-assistant
~~~

Repeat only for selected reviewed directories under skills/. Their READMEs list dependencies. Do not install owner administration skills into customer-support. Record this checkout's absolute path and Python executable in main-assistant's local tool notes. Skills do not bundle a model or install toolkit libraries. The two unresolved derivative-license packages are deliberately absent; obtain upstream software through its licensed distribution.

## 4. Configure integrations individually

Use [configuration reference](CONFIGURATION-REFERENCE.md) and the exact callable examples in [platform adapters](docs/platform-adapters.md) / [operations](docs/operations-modules.md). The .env.example is a documentation template, not an auto-loaded credential store.

- Google: install official GOG, authorize your own account and test read-only metadata first. Configure exact account, client, Sheet and tab. Review a frozen merge digest before enabling writes.
- WordPress: configure your canonical HTTPS origin and a least-privilege application password. Verify REST discovery and supported fields read-only. Custom SEO fields require a site plugin/route you supply; none is guessed. Use a disposable draft before any publication approval.
- Meta/TikTok: register and authorize your own apps/accounts, verify scopes and media-host ownership. TikTok OAuth token refresh is external. Keep publication disabled until exact-content review, asset verification and durable approval pass. A mocked adapter is not live acceptance.
- Leads: Overture downloader is separately installed; obey data licensing. Paid Apify starts remain disabled until independently obtained billing/credit evidence, cap and explicit authorization are supplied.
- Images/research: the installed agent's actual available tools must supply research evidence and completed hash-bound image artifacts. No model-provider API or native OpenClaw tool bridge is fabricated here.

## 5. Messaging and support

Use official [Telegram](https://docs.openclaw.ai/channels/telegram) / [WhatsApp](https://docs.openclaw.ai/channels/whatsapp) setup on the new host. Keep groups disabled and DMs allowlisted to owner/test contacts. Review routing.REVIEW-ONLY.json against your installed schema, replace placeholders and merge rather than overwrite config. Verify the exact owner peer/account routes to main-assistant and a distinct test customer routes to customer-support. Do not open a public customer channel before sandbox/routing tests pass.

[Trusted bridge](docs/trusted-bridge.md) supplies executable application-level signature, confirmation and receipt boundaries. It does **not** attach itself to OpenClaw. An operator-owned transport adapter and semantic policy checker are still required; no live sender is included.

## 6. Schedules and activation

There is deliberately no automatic schedule installation. Confirm timezone, durable state, immutable review, revocation, ambiguity handling, reporting and recovery against [acceptance tests](ACCEPTANCE-TESTS.md). Only then use the installed OpenClaw scheduler or a reviewed system service, with explicit operator approval. Do not enable both for the same job. The full recovery dispatcher and native lifecycle ingestion are still incomplete; do not schedule these components as a purported replica.

## 7. Backups, updates and rollback

Back up private state consistently (SQLite online backup or stopped writers), configuration and authorized assets separately from Git; encrypt off-host copies and test restoration. Keep old checkout/venv alongside the candidate. Run tests before changing any deployment path. Roll back code only with compatible state and preserve unknown remote operations for reconciliation. Never clear a ledger to force a repeat.

Finish [deployment checklist](DEPLOYMENT-CHECKLIST.md). A successful offline install does not authorize business actions.
