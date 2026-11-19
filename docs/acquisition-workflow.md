# Acquisition workflow: bounded portable assembly

Implemented in `toolkit/acquisition_workflow.py`; offline acceptance in
`tests/test_acquisition_workflow.py`. This is library orchestration, **not an
installed weekly scheduler, live-account acceptance or a messaging API**.

## Billing evidence monitor

`billing_evidence_status(path, now=aware_datetime)` calls the existing
`apify_budget.billing_guard`. Missing, malformed, expired or financially unsafe
evidence returns BLOCKED; safe evidence returns VALID or EXPIRING (default warning:
one day). Deadlines are policy verification +30 days, credit verification +7 days,
and cycle end; the earliest governs. Existing guard boundary semantics are retained
(policy/credit valid exactly at their age limit; cycle invalid at its end).

`monitor_billing(path, state_path=..., now=...)` atomically saves the observation
under a lock and returns a change flag. It never updates evidence, refreshes credit,
starts an Actor, sends an alert or installs a timer. A caller may surface the returned
state through its already-authorized reporting path. A repeated unchanged observation
is not a new alert. The change flag is not a delivery receipt.

## Explicit adapter contracts

- `OvertureSource` delegates to `overture_adapter.download` with a caller-selected
  installed executable, bounding box, fresh output path, download opt-in and optional
  mocked runner. It then uses `qualify_features`. No executable or account discovery.
- `ApifySource` takes an existing `ApifyClient`, exact payload, durable reservation
  path, billing evidence path and **trusted authorization callback**. It calls the
  existing capped `start`/`collect` interfaces with the same workflow run key.
  Authorization is not inferred from enabling the workflow or monitoring billing.
  Processing performs one collect per invocation; no internal polling loop. A
  possible 100-row dataset truncation blocks Sheet writes rather than pretending
  acquisition is complete. OSM-shaped Actor rows use existing `qualify`.
- Sheets use existing `GogSheets.plan/values/apply`; tests inject its subprocess runner.
  Read/write flags, explicit account/client and exact plan digest are still required.
- Reports reuse `report_outbox.Outbox.prepare/claim/receipt`. No CLI/RPC sender is
  introduced. The tool-aware parent must use an authorized messaging tool.

All native timeout bounds are inherited: Overture CLI 180 seconds, GOG 45 seconds,
Apify HTTP 40 seconds per request (Actor runtime cap 300 seconds). Injected transports
must enforce their own deadlines; Python cannot safely cancel arbitrary callbacks.
No background thread is abandoned to continue a possible write after a fake deadline.

## Weekly invocation protocol

1. Choose one stable run ID for the reviewed weekly scope, e.g. `2026-W47`, and an
   explicit private state root. Use the same ID and inputs on resume; never rotate an
   ID to escape an unresolved operation. A single root lock serializes local ticks.
2. Call `weekly_leads` with source, explicit geographic/industry profile, fixed date,
   quantity, minimum score, Sheets adapter/ID and Outbox destination. No timer is made.
3. First invocation acquires, qualifies, deduplicates by ID/domain/phone/name and
   ranks by score then name. It does not lower the threshold to fill a quantity.
   Matching is the deduplicated count above threshold before quantity selection.
4. It returns WAITING_APPROVAL with full frozen plans for All Leads and Qualified
   Leads. Both merge selected above-threshold rows; Reviewed / Contacted is untouched.
   Existing review/contact/first-seen/notes are preserved by `lead_sheet_merge`.
   Historical rows are merged, not deleted or recomputed as a new qualified snapshot.
5. Present those exact plans for approval. Only after real approval, pass a mapping
   `approved_digests={tab: reviewed_digest}` on the next invocation. Do not automatically
   copy returned digests into an approval map in an unattended wrapper. Missing or
   wrong approval means no writes. All outstanding plans must be approved before
   applying any. Remote drift blocks the write.
6. After both exact readbacks, REPORT_PREPARED returns the report key and counts,
   including the full Sheet URL even for zero matches. The `new` count is the planned
   All Leads row increase; before completion it is **not** a confirmed inserted count.
7. `claim_report(outbox, key)` checks the persisted destination and claims once.
   Parent delivers the returned payload using its authorized message tool, then calls
   `report_receipt(outbox, key, actual_message_id)`. A timeout/unknown delivery calls
   it without an ID. Neither sending nor unknown is reclaimable. Never send again
   merely because the workflow continues to return REPORT_PREPARED.

The existing report schema only accepts Published/Draft/Blocked/Failed. A success
report uses Published **solely for verified Sheet merge**, with explicit
`purpose=lead_sheet_merge`; it is not social publishing, confirmed buyers or evidence
of notification delivery. No automatic two-channel dispatch is implemented despite
the legacy Outbox's unused per-channel delivery fields. Use an explicit approved
parent delivery policy; this assembly claims one aggregate delivery.

## Durability and conservative recovery

Run binding includes source payload/identity/paths, profile, date, threshold, quantity,
Sheet/account/client and report destination/path. Changed input under one ID fails.
Raw acquisition, qualification, exact merge plans, per-tab write states and report
key are atomically checkpointed. Keep these private: they contain public business
contact data and existing Sheet review/history. Errors stored in orchestration state
are generic, not credential-bearing transport messages.

ACQUIRING after interruption or acquisition failure/timeout is a manual reconciliation
latch. It does not redownload or restart an Actor. Inspect the existing adapter's
retained IDs/reservations read-only; no reset API is supplied. PROCESSING can resume
through the same paid-run key and still requires the trusted authorization callback.
A qualification failure is similarly latched. Failed planning reads can be repeated
because no write has been attempted and acquired data is already checkpointed.

Before Sheet apply, WRITING is persisted. UNKNOWN or interrupted WRITING only performs
read-only target comparison on later ticks. An exact match marks VERIFIED; every other
result stays NEEDS_ACTION, even authoritative absence. There is no automatic write
replay. A successful first tab is not repeated when the second tab is unresolved.
This is local single-writer fencing, not a remote transactional multi-tab commit.

A crash between Outbox preparation and report checkpoint is recovered by the existing
same-key/same-payload prepare behavior. Already-verified Sheet operations are skipped.
Sending crashes remain claimed; missing delivery receipts never re-trigger acquisition
or Sheet writes. Caller must surface PROCESSING/NEEDS_ACTION and arrange an existing
authorized completion/watch path; this library neither promises nor installs one.

## Explicit remaining gaps

- Original geography-specific enrichment, website crawling/contact discovery and
  location-specific production routing are **not ported**. Existing profile-bound
  qualification only is assembled; no undocumented native provider API is invented.
- No live Apify/Overture/GOG account acceptance, actual downloads, paid spend, customer
  contact, Sheet update, messaging delivery or weekly scheduler was performed here.
- No cross-host lock, account-wide atomic Apify spend reservation, automatic uncertain
  start reconciliation or dataset pagination beyond the existing adapter is added.
- No stale/expired evidence refresh, unattended exact-plan approval, multi-recipient
  outbox extension, failure-alert delivery or operator latch-reset interface is added.
- Threshold applies to retained incoming rows in both written tabs; this is not a
  full raw-source archive or deletion-based qualified-view synchronization.

## Offline verification

`python3 -m unittest discover -s tests -p 'test_acquisition_workflow.py' -v`

Tests deny socket and subprocess creation and inject real adapter transport seams.
They cover both source assemblies, billing expiry/change observations, paid consent,
processing, truncation/failure/start timeout, acquisition timeout, source and Sheet
dedup/history preservation, approval/drift, read failures, committed/uncommitted write
timeouts, read-only recovery and report claim/unknown/receipt fencing.
