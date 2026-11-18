# Validation record — 2026-11-18

Validation host: Linux x86_64, Python 3.14.4. Python 3.10+ is the source compatibility target, not a tested version matrix.

## VERIFIED locally

- 25/25 offline unit tests passed, including a repeat in a fresh isolated venv with pinned requirements installed. An initial run found one missing-head validation defect; the staged implementation was fixed and the full suite rerun.
- Tests deny socket creation, connection helpers, subprocess launches and os.system; fixtures and state live in temporary directories. No live publishing, messaging, collection, paid Actor or customer-response operation was executed.
- Python AST, JSON, skill frontmatter, metadata JSON, local Markdown links, disallowed artifact/symlink and deployment-identity checks passed. YAML parsed successfully, including the CI workflow and skill frontmatter.
- Gitleaks 8.30.1 directory scan reported no leaks. The scanner archive was obtained from the official gitleaks/gitleaks GitHub release and its SHA256 matched the published release checksum (551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb). Scanner binaries/reports stay outside this repository.
- Manual allowlist review covers the eight adapted sources, fixtures, guides, skill, tests and workflow. No production Git history is imported. No private state/media/binary artifact is included. Every included source is mapped in PROVENANCE.json; dependency code is not vendored.
- 245 production/source/service files matched the recorded SHA256 and permission baselines after staging. This is a bounded source check, not a claim that live runtime data stopped changing.

## PARTIAL / NOT TESTED

- Full production capability portability is incomplete. The release contains eight source-derived modules and one newly packaged coordinating skill, not all discovered workflows.
- Ownership review relies on the owner's authorization of local original implementations plus source inspection. It is not forensic authorship proof. Unresolved derivative procedural skill text is excluded rather than assigned MIT.
- No fresh OpenClaw agent installation, Windows/macOS deployment, live CMS/API adapter or remote browser/credential setup was executed. Skill install commands were checked against 2026.9.8 docs, not installed into production.
- CI YAML was reviewed for read-only permissions, pinned checkout, no stored checkout credentials, finite timeout, no pull_request_target and no deployment. Remote GitHub Actions execution is not established by local testing.
- Gitleaks and targeted checks are not an exhaustive security guarantee. Transitive dependency vulnerability status must also be reviewed in GitHub and before deployment.
- No automatic schedules are installed. Knowledge snapshots retain a documented first-page-only limit. The original production engines remain ADAPT in the inventory.

## Public readback and CI correction

Anonymous GitHub API readback verified public ownership and all 45 file paths, with an exact Git tree match to the reviewed candidate. A fresh public clone passed all 25 tests and the upstream skill frontmatter validator. The first GitHub CI run also passed all 25 tests, but the supplemental gate mistakenly included its installed virtual environment. The gate now excludes the local .venv while explicitly rejecting any tracked .venv content. This is a test-environment boundary correction, not an exclusion for release source. Git is required for that check. The corrected remote run must be inspected before claiming CI success.

## Continuation batch 0.2

75 offline/mocked tests passed after adding seven source-derived operations modules. A mock identity regression was corrected to supply the now-explicit Instagram username. Syntax/JSON/links and Gitleaks directory scans passed. Tests include actual source-derived FB/IG/Sheets behavior, no duplicate publication after timeout, immutable approvals/revocation, exact destination receipts, independent six-position rotation, clock/credit expiry and watchdog state transitions. Live provider functionality and installed schedules remain NOT TESTED.

Preservation qualification: two source files differed from the earlier release baseline during this continuation. No release operation wrote either file; their changes were recorded and left untouched. A new read-only preservation snapshot was retained privately. This report does not attribute those changes or claim the old entire-source baseline remained identical.
