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
