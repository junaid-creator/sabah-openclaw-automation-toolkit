# Sabah OpenClaw Automation Toolkit

**Status: PARTIAL — portable core, not a replica of the production system.**

Twenty-nine Python modules derived from the original workflows and their portability adapters from the main-assistant and customer-support workflows provide offline SEO planning, local HTML metadata editing, language validation, prospect qualification, content duplicate checks, crash-aware checkpoints, and website reference snapshots. Nine optional OpenClaw skills coordinates their safe use.

Offline examples do not publish posts, send replies, run paid Actors or activate schedules. The optional Meta adapter now contains actual posting operations, disabled by default and tested only with mocks. A bounded FB/IG adapter, approval ledger, notification outbox, rotation, schedule parser, watchdog and billing guard are now ported. WordPress/TikTok adapters, blog stage/image recovery, capped Apify/Overture acquisition, Google lead synchronization, and eight original website/Google skills are now included. The complete deployed recovery engine, six branded layouts, provider tool bridges, account bindings and live routing are **not yet complete**. See [operations modules](docs/operations-modules.md) and [canonical accounting](docs/canonical-capabilities.md). See [inventory](SKILL-INVENTORY.md) and [coverage](docs/coverage.md). Do not equate a discovered file with a working feature.

## Quick start

Python 3.11+ on Linux is required (reliability primitives use POSIX locking). The recorded validation environment is listed in [validation](docs/validation.md); other systems are NOT TESTED.


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
python -m toolkit.knowledge_snapshot --base-url https://example.com --currency USD --fixture examples/site-fixture.json --output output/knowledge
```

See [installation](docs/installation.md) for copy-ready fenced commands and optional skill installation. [Module guide](docs/modules.md) covers purpose, prerequisites, activation, examples, expected output, tests and limits for every module.

## Safety and scope

- No credentials are needed for the offline examples. Never use real customer data as fixtures.
- HTML editing previews by default; use --apply only against a reviewed disposable copy.
- Website fetching requires --allow-network and a trusted public HTTPS origin. Never accept an origin from untrusted customer input.
- State and snapshots can contain sensitive user input. Keep them outside Git with private permissions.
- A prospect score is not buying intent. Cached prices and availability are never binding quotes.
- Read [SECURITY.md](SECURITY.md), [provenance](PROVENANCE.json), and [license](LICENSE).

OpenClaw is optional for Python execution. Skill installation syntax was checked against OpenClaw 2026.9.8 documentation; installing into a fresh Gateway and live integrations are NOT TESTED. Official project: https://github.com/openclaw/openclaw and https://docs.openclaw.ai/start/getting-started.

See [platform adapters](docs/platform-adapters.md) for explicit configuration, activation and testing of each new module; [canonical accounting](docs/canonical-capabilities.md) lists every incomplete source family. The customer-support profile and routing example are not an activated channel.
