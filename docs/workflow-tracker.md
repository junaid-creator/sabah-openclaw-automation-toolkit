# Durable multi-tab workflow tracker

`workflow_tracker.Tracker` uses the already supported GOG command contract through an explicitly configured `GogSheets` instance. No credentials or schema are discovered. Configure account/client, spreadsheet ID, private state root, allowed tab names, exact headers/key column, bounded row limit and exclusive_writer=True. Reads/writes remain independently disabled by default on GogSheets.

Tracker owns dedicated formula-free tabs only. It reads VALUE and FORMULA views, rejects formulas/header drift/duplicate keys/incomplete inventories, preserves all existing identities, and writes literal RAW values. Never point it at editable source/formula sheets. Use the separate source_reconciliation read-only snapshots there. GOG access needs authorized Sheets read/write scope for this new target; grant least privilege.

`plan(updates_by_tab)` produces exact before/after ranges and digest. `apply(stable_operation_id, plan, approved_digest=...)` requires a trusted host-approved exact plan. The digest is content binding, not authentication: do not expose this API or signing/approval decisions directly to customer/model tools. Multi-tab writes are not an atomic provider transaction. All tabs are preflighted before first write, each write has durable intent, and lost responses reconcile by exact readback. Unknown outcomes never resend. Repeated calls retain the original frozen plan.

Workflow integration:
- `sync_social_draft(controller, job_id, queue_tab=..., content_tab=..., enabled=True)` reads the actual controller binding and creates only manual WAITING_APPROVAL rows with blank scheduling. No Sheet value grants publication approval. Dedicated tracker schemas are explicit in social_draft_plan; these are not silently substituted for a deployed publisher Sheet schema.
- `SEO.draft(validate=..., tracker=tracker, tracker_tabs={"draft_tab":"Drafts","topic_tab":"Topics","run_tab":"Runs"})` completes all three tracker tabs before preparing the owner report. Choose this configuration from the first execution; changing tracking after a frozen owner report requires review, not rewriting that report.

The three example schemas are executable in tests/test_workflow_tracker.py. Owner row/source approval and exclusive writer setup are deployment prerequisites. Existing private spreadsheets are never migrated by installation. No new third-party package: the operator installs official GOG separately and verifies its version/account.

Nine focused tests plus one complete SEO/tracker/outbox integration test cover exact three-tab sync, response loss, partial-stop replay protection, preflight drift, formula rejection, frozen plan reuse and manual-only social tracking. All use the actual GOG argv adapter with a simulated process transport, not live Google.

Rollback: stop only the new target tracker worker, preserve plan and per-tab intent files, revert code. Reconcile partial writes by reading exact existing rows. Do not delete checkpoints, blindly clear ranges, restore an entire Sheet or recreate an uncertain operation under another ID. Live Google/native delivery acceptance remains separately required.
