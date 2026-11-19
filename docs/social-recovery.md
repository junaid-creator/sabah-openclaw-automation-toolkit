# Portable social recovery harness

`toolkit.social_recovery.Recovery` assembles the existing signed `social_review.Controller`, durable approval/operation ledger, `MetaPublisher`, and TikTok `Client` / `advance` state machine. It is an opt-in Python API, **not an installed worker, scheduler or live acceptance**. It neither approves jobs nor changes their reviewed creative, targets, captions, local asset hash or HTTPS URL. Draft creation still cannot publish.

## Integration

Construct the existing controller with its private persistent root, Bridge and Ledger. Complete the normal delivered review / challenge / confirmation flow. Supply a MetaPublisher sharing that exact ledger and using `BoundApprovalGate(controller, sheets, operational_gate)`. Its Sheets adapter must return the exact frozen targets, captions and asset URL; operational fields must independently permit publication. Existing Meta live-enable and API-contract checks remain mandatory. Supply a configured TikTok Client with its own enabled submission authorization, identity, media-domain ownership and scope checks.

Then call (objects below are operator-configured, not globals provided here):

```python
from toolkit.social_recovery import Recovery

worker = Recovery(
    controller,
    meta_publisher=meta_publisher,
    tiktok_client=tiktok_client,
    media_digest=verified_hosted_jpeg_sha256,
)
result = worker.run(exact_approved_job_id, enabled=True)
# A separately authorized host may invoke bounded recovery passes later:
results = worker.due(enabled=True, limit=20)
```

The mandatory `media_digest(url)` adapter must retrieve bounded hosted JPEG bytes, enforce verified HTTPS host/redirect/SSRF policy, validate the image, and return their SHA256. It is checked against the exact reviewed local artifact before each new platform submission. Immutable/content-addressed hosting is required: no hash check can prevent an origin changing after the check and before the provider fetches the media. Rendering/geometry proof remains the existing controller responsibility; this harness does not rerender media.

Use one shared durable root and SQLite ledger for every worker. The controller lock covers the complete pass; overlapping callers fail closed rather than wait or publish twice. Each operation journals its next admission before the adapter call. Provider adapters must have bounded transport deadlines; Python does not forcibly cancel a hung injected transport. Process death leaves a durable claim. The API does not install a service, run a loop, or sleep between recovery passes. The existing Meta adapter may perform its own small bounded definitive-429 retry.

## Recovery rules

- Exact Bridge approval and durable receipt are rechecked, including during recovery from Controller DISPATCHING / DISPATCH_UNKNOWN / DISPATCHED states.
- One failed platform does not suppress independent authorized targets.
- Confirmed posts are never submitted again. Missing Meta links use GET by the saved confirmed ID; TikTok accepted tasks only poll that same saved task.
- TikTok requires PUBLISH_COMPLETE plus owned-post lookup and a real share URL. Submission/task IDs are PROCESSING, never success. Inbox outcomes need action.
- Definitive retryable responses retain bounded adapter attempt budgets and durable next-at times. TikTok Retry-After is honored. Read checks are bounded.
- An interrupted Meta POST/container, or TikTok submit with no durable accepted task, becomes NEEDS_ACTION. Unknown outcomes are never reset or blindly retried.
- Revocation stops subsequent admission and preserves already-recorded successes; it cannot undo an already in-flight request or delete remote publications.
- Per-platform output uses VERIFIED, PROCESSING, FAILED or NEEDS_ACTION and includes saved remote IDs and actual verified URLs. A job is not wholly verified unless every requested platform is VERIFIED.

## Durable notification preparation (no sending)

Every completed bounded run, including a blocked/revoked approval report, calls
existing `notification_outbox.emit_job_event` with kind
`SOCIAL_RECOVERY_STATUS`. It prepares a consolidated snapshot in the same durable
ledger; it does not invoke channels, configure recipients or drain notifications.
An independently authorized caller can use the existing
`notification_outbox.drain(ledger, explicit_targets, sender=trusted_sender)`.
The unchanged outbox requires exact per-channel/account/recipient receipts and
latches ambiguous sends UNKNOWN instead of resending.

Only stable report statuses, constrained remote IDs and validated public URLs
enter the snapshot. Captions, local paths, raw provider errors, hosted-media
origins, retry timestamps and counters are excluded. URLs with credentials,
query strings, fragments, control characters or nonstandard ports are not
forwarded. A rejected verified link is reported NEEDS_ACTION, not invented.
Identical snapshots produce the same event ID even after retries or restart;
a meaningful status/ID/URL or approval-block transition creates a new event.
Partial successes remain visible; blocked unfinished targets need action and
confirmed publications remain recorded. Approval-blocked aggregate health is
NEEDS_ACTION even if already published targets are verified.

An outbox storage error propagates after durable publication results are saved.
Retry the same `run(job, enabled=True)` to prepare the missing event; never approve
again or clear publication receipts. The due sweep intentionally skips revoked
or already complete jobs, so it is not a substitute for this explicit repair.
Do not also call generic `sync_job_events` for these jobs: that is a separate
snapshot producer and would create another notification stream. Pending status
transitions are not coalesced; the independently configured sender may deliver
the retained chronological snapshots. No automatic delivery is activated.

## Deliberate limits

This is a portable integrated publication/recovery core, not full production parity. Scheduling remains the separate exact-time approval workflow; this harness does not consume schedule approvals or convert them into publication approvals. Native owner-worker wiring, daemon installation, provider contracts, account permissions, real media hosting and live acceptance remain deployment work. Use the existing dedicated native owner commands for review and approval.

The original Meta adapter writes its immediate POST_LOG row; this harness does not rewrite aggregate queue approval status, mirror TikTok to Sheets, or recover uncertain Sheet log writes. Consolidated owner status events are prepared durably, but actual notification transport/targets/draining and live delivery acceptance remain separately configured. Native timer/worker installation and Sheet aggregate reconciliation are explicitly unfinished. A Sheet/report failure never authorizes republishing. Unknown Meta outcomes and revoked accepted TikTok tasks require separate read-only operator reconciliation. No automatic account-discovery or unknown-post matching is added. A caller-supplied trusted adapter remains part of the security boundary.

## Offline verification

```sh
python -m unittest discover -s tests -p "test_social_recovery.py" -v
```

Tests assemble real Controller, Bridge, Ledger, BoundApprovalGate, MetaPublisher and TikTok Client with simulated provider transports and denied socket creation. They cover completion, partial failure, timeout, process-death markers, accepted-task recovery, revocation, changed assets/captions/rows, retry timing/budgets, duplicates and concurrent workers. Synthetic renderer and media fixtures are not live visual, hosting, identity or API acceptance evidence.
