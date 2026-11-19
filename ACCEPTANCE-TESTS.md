> Recovery update: [2026-11-19 release](docs/recovery-release.md) and [current evidence](docs/recovery-acceptance.json) supersede older test counts and native-install claims below. Coverage remains partial.

# Acceptance tests and evidence boundaries

## Executed offline acceptance

Run from the checkout:

~~~bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tests/release_gate.py
.venv/bin/python -m pip check
~~~

The reproducibility batch adds 22 tests in tests/test_trusted_bridge.py (179 total with the follow-up acquisition batch). Tests deny socket and subprocess creation in the new boundary scenarios. Cases cover invalid signatures, tampering, stale/future events, unknown peers, customer-owner separation, exact single confirmation, expiry, revocation, exact review receipt, content binding, policy denial, tool/destination injection, disabled sending, exact receipt, replay prevention, ambiguous send, wrong-recipient receipt, crash reservation, event collision, duplicate route and safe scaffold creation.

Earlier tests cover actual local WebP validation, SEO/local content operations, publication/paid acquisition mocks, Google merge/readback, outboxes and procedural evidence contracts. These are not real provider E2E tests. See [validation history](docs/validation.md).

## Acquisition pagination follow-up

Eleven tests in tests/test_apify_pagination.py cover >30 runs, empty history, all nonterminal/unknown statuses, page bounds, changing totals, duplicate IDs, malformed metadata, missing pages, head changes and invalid bounds. A full start-admission fixture proves an active run blocks before any paid POST or local reservation. API contract checked against the [official Actor-runs endpoint](https://docs.apify.com/api/v2/actor-runs-get); no live authenticated call or Actor start was performed.

## Mandatory authorized real-world acceptance (NOT PERFORMED)

1. Install into a disposable fresh OpenClaw profile/VPS; validate agent schema and each chosen model.
2. Try forbidden cross-workspace reads, owner commands from customers, group messages and forged sender text. All must fail before a business adapter call.
3. Run one authorized provider READ for each integration; check identity, scopes and exact origin. Do not expose response secrets in reports.
4. WordPress: disposable draft + image upload/readback + independent browser/meta validation; then one exact authorized publication only if separately requested.
5. Social: licensed asset render/review, exact approval binding, one allowed test publication/platform, official owned-post lookup and share URL. Six-template parity remains unavailable.
6. Messaging: test contact only; confirmed real message receipt, injected timeout/unknown result, no duplicate send, staff intervention path.
7. Leads: bounded free dataset, qualification and disposable Sheet preview/write/readback. Paid Actor start requires a separate explicit spend authorization and fresh billing evidence.
8. Restart during each side-effect boundary; preserve remote IDs and reconcile read-only. No blind retries or ledger resets.
9. Validate private backup restore and independent monitor delivery, then explicitly approve schedule activation if the full workflow is ready.

No test here grants real publication, customer contact, paid start or production activation authority. CI success and mock counts cannot close missing native integrations.

## Expanded reconciliation release — 2026-11-18

315 Python unit tests and 20 Node tests passed; optional real local Chromium rendered
all six original layout structures in three language modes (18/18), with four
retry/drift/overflow checks. New clean dependency environment and pip check passed.
315 is not a count of live capabilities. No fresh live external workflow accepted.
Product revocation was independently corrected and tested during in-flight writes;
scoped restoration always requires a new exact review. Original sources remain
unchanged within bounded recorded checks. Full master-task status: PARTIALLY PORTED.
See the complete audit and docs/complete-release-acceptance.json. Render fixtures,
fonts, prior failures and scope are detailed in docs/poster-render-acceptance.json.
