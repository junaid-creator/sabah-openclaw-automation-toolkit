# Reply and schedule integration adapters

## Customer reply lifecycle

`toolkit.reply_recovery.Replies` accepts only signed, configured customer routes. `start(event, signature, submit=...)` durably reserves the inquiry before the host starts inference. Repeated events reuse the original task. A crash before task-ID persistence becomes UNKNOWN_TASK, not permission to rerun inference.

`recover(event_id, result_reader=..., sender=..., enabled=True)` accepts only the exact task/inquiry/route final assistant result. It never reads raw transcript files or guesses a native API. The installed host must supply authorized bounded result lookup and a real messaging transport. Pending results are not completion; wrong inquiry, tool output, non-final content and policy failures are rejected. The operator semantic policy is checked again before send admission.

`ReviewedPolicy` supplies an executable conservative alternative to arbitrary prose approval: exact reviewed phrases bound to locale, intent, reviewer and review age, with an operator-owned classifier. It does not establish arbitrary model semantic correctness. Unknown classification must request human review, not approve a guessed intent. Sensitive prices, availability, payment instructions and guarantees must not be added to the phrasebook without authoritative review. No private company profile or customer messages ship with this release.

Delivery persists uncertainty BEFORE calling the sender. Read-only `reconcile_delivery` requires event ID, recipient/account/channel, message ID and exact text digest; missing proof never authorizes a resend. No proactive recipient changes. Operator storage contains inquiry text: use private encrypted storage, a retention policy and backup controls. Default inactive.

## Schedule admission

`Schedule.plan` parses signed `SCHEDULE today 1 pm` with explicit timezone and frozen content. Deliver exact returned binding, then `SCHEDULE REVIEW schedule-<id>` calls challenge; owner sends returned `CONFIRM <id>` through the existing bridge. Signed `REVOKE <id>` prevents future admission.

An independently configured worker calls `dispatch_due(..., enabled=True)` with trusted exact-content reader and publication dispatcher. It rechecks current approval, unchanged content and due time. Default five-minute grace; missed windows become EXPIRED. Admission is persisted before dispatch; no callback repeats after uncertainty. Callback must use the original exact-content publication ledger; this adapter does not invent fresh publication approvals or treat a task ID as success. Inspect that ledger for real per-platform receipts.

No timer/service is activated. Configure an inert service example only in a new authorized deployment; test with disposable state first. No generic worker can safely infer existing account routing. Rollback: stop only the new deployment worker, preserve ledgers and receipts, revert the adapter version. Never delete uncertain-state records or restart a job under a new identity.

## Acceptance boundary

Seven inquiry lifecycle tests, four phrasebook tests and five schedule tests use disposable state and simulated callbacks. Actual native result lookup, semantic model behavior and WhatsApp/Telegram delivery remain LIVE ACCEPTANCE REQUIRED. These contracts are application interfaces, not claimed OpenClaw SDK methods.
