# woocommerce-price-display-audit

Purpose: the exact workflow and approval boundaries are defined in SKILL.md. This is a procedural skill, not an executable service adapter.

Prerequisites: your own supported OpenClaw installation and operator-authorized integration. WordPress/WooCommerce skills require read access and browser capability for visual checks; writes need separate scope. Google readiness requires an already-authorized gog CLI on its configured host. No credentials are provided.

Installation from checkout: openclaw skills install ./skills/woocommerce-price-display-audit --agent YOUR_AGENT_ID. Inspect CLI help first. Install linked sibling skills when following their branches, or retain the checkout as a reference library. No gateway/configuration change is performed here.

Configuration: supply your own target URL/IDs, scope, private backup directory and integration. Read-only audit is the default; do not activate mutations, schedules, payments or restoration from an audit request.

Activation/sample: ask the agent to audit one explicitly identified target in read-only mode. Expected output: target-bound evidence distinguishing VERIFIED, UNVERIFIED and BLOCKED, never a fabricated successful write.

Testing: python -m unittest discover -s tests -v and python tests/release_gate.py. Content-review tests exercise original-byte preservation, style-only boundaries, protected-field unions and negative text/link/price changes. Platform tests exercise saved robots/template admission. Every skill's frontmatter/resource links are checked. The complete procedure has NOT been run against a fresh live site/account in this release. Module examples are in docs/operations-modules.md and docs/platform-adapters.md at the checkout root.

Troubleshooting: missing tools, account access, trustworthy snapshots or rollback capability are blockers, not permission to install tools or widen authority. Reconcile uncertain writes before retrying.

Limitations: browser behavior, plugin versions, scopes and restore capability vary. Linux/Python 3.14 and GitHub CI are tested for helper code. Skill install syntax is checked against OpenClaw 2026.9.8 docs; fresh-agent execution and live writes are NOT TESTED.
