# Installation

## Standalone (offline example execution after dependency installation)


```bash
git clone https://github.com/junaid-creator/sabah-openclaw-automation-toolkit.git
cd sabah-openclaw-automation-toolkit
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
mkdir -p output
python -m toolkit.keyword_research --input examples/seeds.txt --output output/keywords.json
python -m toolkit.content_brief_generator --input output/keywords.json --output output/briefs.json
```

All module commands run from the checkout root. This is a source checkout, not a globally installed Python package. Use an absolute checkout path or cd there first. Installation downloads requests and its dependencies; actual tests and fixtures make no network calls.

## OpenClaw (optional)

Install OpenClaw following https://docs.openclaw.ai/start/getting-started for your OS. Do not pipe an unreviewed installer into a privileged shell. Configure your own provider through the official onboarding flow. No existing deployment or account is inherited.

With the intended agent selected, inspect help first; the local install syntax below is documented in 2026.9.8:


```bash
openclaw skills install --help
openclaw skills install ./skills/offline-automation-review --agent YOUR_AGENT_ID
openclaw skills check --agent YOUR_AGENT_ID
```

For optional publisher/ledger/rotation/outbox/watchdog/billing modules, read [operations-modules.md](operations-modules.md). They do not activate services or schedules.

The skill requires this checkout and its Python environment; record your absolute checkout location in that agent's local tool notes. It does not copy or install the library itself. Do not replace a skill of the same name without inspecting it.

## Update / uninstall

Review release changes, back up user-created local state outside Git, then pull fast-forward only in a clean checkout and rerun tests. Never force-reset a dirty checkout. Remove only this skill from the agent workspace after checking its path; uninstalling does not delete user state or credentials. Delete the isolated checkout/venv only after preserving data you need. No service or schedule needs disabling because none is installed.
