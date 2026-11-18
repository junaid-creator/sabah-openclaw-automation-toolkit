# Sabah OpenClaw Automation Toolkit

**PARTIALLY PORTED — not a complete recreation of production.**

The fresh reconciliation identifies **51 bounded original capability groups**,
including **9 additional groups** missed by earlier grouping, and preserves all
**460 original record mappings**. It indexes **399 source entries** (394 fresh
scan + 5 targeted rendering sources), with **147 newly hashed entries** absent
from the old source baseline. File counts are not capability counts. Three system
deployment files and four historical copies were access-denied; deeper tracing
and full-host completeness remain unresolved.

Current source package: **45 Python runtime modules, 24 skill packages** (22
original procedural packages plus two toolkit wrappers), an optional native
product-command plugin and callable Node support guards. **315 Python tests,
20 Node tests, 18 actual local rendering cases and four renderer retry/negative
checks passed** in isolated/synthetic validation. No real business write,
customer send, paid Actor run or production activation was tested.

## What is installable versus callable

| Type | Included | Boundary |
|---|---|---|
| Procedural OpenClaw skills | 22 original packages + review/product wrappers | Require configured tools/accounts; not whole engines |
| Callable Python libraries/CLIs | SEO, leads, WordPress/Google/platform adapters, products, images, voice, snapshots, monitor | Exact configuration and scopes; writes/network opt-in |
| Native plugin source | Trusted owner product commands + actual review receipt capture | Not installed or live-channel accepted |
| Node support libraries | Rate/replay limits and HUMAN/AUTO handoff admission | Not native support routing or semantic policy |
| Six poster layouts | Original source-derived structures/CSS, synthetic replaceable assets | Operator fonts, real QR and semantic review required |
| Full external workflows | Components and partial orchestration | **Zero fresh live end-to-end workflows accepted** |
| Upstream capabilities | Official OpenClaw/software references | Not redistributed or automatically provisioned |

Product management is real configurable workflow code, not just a REST client:
draft/edit/separate publish/scoped restoration, variations, categories, pricing,
metadata, existing media IDs, exact owner approval, before snapshots, revocation
and uncertain-write reconciliation. See [product guide](docs/product-management.md).
Binary media upload, original Sheet/formula coupling, SQL restore, storefront
verification and full native deployment are still missing or NOT TESTED.

Start with [COMPLETE-CAPABILITY-AUDIT.md](COMPLETE-CAPABILITY-AUDIT.md) and its
[machine register](docs/complete-capability-audit.json). Strict classifications
are VERIFIED AND PORTABLE, PARTIALLY PORTED, UPSTREAM DEPENDENCY,
LICENSING / SECURITY BLOCKED, NOT TESTED and MISSING IMPLEMENTATION.
No feature matrix or static skill packaging is treated as full functional parity.

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

Two optional diagnostic skills cover [management routing](skills/system-management-model-routing/README.md) and [private mobile pairing](skills/private-mobile-gateway-pairing/README.md). Synthetic acceptance records do not establish live recovery or pairing.

## Reproducible installation batch

Start with [COMPLETE-SETUP-GUIDE.md](COMPLETE-SETUP-GUIDE.md), [feature matrix](FEATURE-REPLICATION-MATRIX.md), [configuration](CONFIGURATION-REFERENCE.md), [dependencies](DEPENDENCIES.md), [deployment checklist](DEPLOYMENT-CHECKLIST.md) and [acceptance tests](ACCEPTANCE-TESTS.md).

The inert scaffolder and signed application boundary are not automatic deployments.
The latest [complete capability audit](COMPLETE-CAPABILITY-AUDIT.md) supersedes older
coverage counts. Existing features/history are preserved; no full production
replica or fresh external end-to-end acceptance is claimed.

## Implementation continuation

Four previously missing groups now have executable offline-tested partial ports: badge audit, independent TikTok Business/Login Kit OAuth, social draft/revision/review/dispatch and isolated voice control. See [current audit](COMPLETE-CAPABILITY-AUDIT.md) and [installation/limits](docs/missing-implementations.md). No live acceptance is implied.


## Current release acceptance

See [final implementation guide](FINAL-IMPLEMENTATION.md) for executable setup,
61 runtime modules / 24 skills, 402 Python and 25 Node tests, actual local browser
and six-template workflow acceptance, production preservation and exact limitations.
This is a verified public release, not 100% reproduction or live-provider acceptance.


Dedicated [workflow tracking](docs/workflow-tracker.md) is now executable for social
drafts and three-tab SEO reporting through the existing configured GOG adapter.
Exact preflight, frozen plans, per-tab intent/readback and no blind replay are tested.
No existing private Sheet schema is migrated or inferred, and no live Google call occurred.
