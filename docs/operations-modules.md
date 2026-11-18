# Publication and operations modules — batch 1

These are working source-derived libraries, not installed services. Python 3.11+ and a writable private state directory are required; validated environments are Linux/Python 3.14 and GitHub Ubuntu CI. Live accounts and other platforms remain NOT TESTED. Install the repository requirements and run commands from its root. No import starts a scheduler or sends messages.

## Meta publishing and Google Sheets

Purpose: Facebook Page photos and Instagram two-step media publication with durable per-platform receipts, approval gates, bounded retry and no replay after uncertain outcomes. TikTok is deliberately not routed through this module.

Install: standard library only; optional Google integration requires your separately authorized gspread workbook. Pass that workbook to GspreadSheetsStore(workbook); no OAuth setup or private helper is imported. POST_QUEUE, CONTENT_OUTPUT and POST_LOG fields are declared in the module. Account access and scopes must be established by the operator through the official Google/Meta setup processes.

Configuration: construct MetaSettings with an explicit currently supported Graph API version, Page ID, Instagram user ID, expected Page name/username, application IDs and verified public media-host allowlist. EnvironmentSecrets reads TOOLKIT_META_FACEBOOK_PAGE_ACCESS_TOKEN, TOOLKIT_META_INSTAGRAM_ACCESS_TOKEN, TOOLKIT_META_VALIDATION_ACCESS_TOKEN and TOOLKIT_META_APP_ACCESS_TOKEN. Keep values in your secret manager, not in a command or JSON fixture. The toolkit does not obtain or refresh credentials.

Activation: MetaPublisher requires injected transport, credential store, workbook adapter, local PublishLedger path, media verifier and trusted ApprovalGate. Its default gate denies everything and dry_run defaults true. dry_run reads the configured job but performs no provider/media calls or Sheet writes. validate_token_and_identity is a separate explicit live READ and is not an offline test. See tests/test_meta_publisher.py for a complete runnable synthetic setup.

An operator who independently verifies API contracts and exact-content owner approval can opt in with TOOLKIT_ALLOW_LIVE_META=I_UNDERSTAND before import, settings.live_enablement_approved=True, settings.api_contracts_verified=True and dry_run=False. This is not permission from this repository. SheetPublicationGate is only an operational flag check, NOT authenticated owner approval; do not use it as the sole live gate. Use fingerprint_rows to bind reviewed queue/content/account/version fields in your trusted admission adapter. API versions, token scopes and permission grants must be reviewed against current provider documentation before deployment.

Expected output: DRY_RUN, per-platform confirmed ID/link, or a fail-closed error/uncertain ledger state. Missing permalink never causes a second publication. Troubleshooting: verify schemas, target identity, media host and separate approval; reconcile remote outcomes rather than clearing ledger rows. Limitations: this is the bounded publisher, not the production three-platform recovery daemon; no guarantee of exactly-once delivery across hosts. Media host allowlisting assumes operator-controlled DNS. Redirects are refused. Provider responses and application permissions are mocked in tests, not live-proven.

## Approval ledger

Purpose: approval-bound SQLite jobs, operation phases, authenticated-source metadata, immutable content fingerprints, review references and revocation. Instantiate approval_ledger.Ledger with a private SQLite path. approve(job, receipt) requires source.authenticated=True, source.review_ref and binding.targets; the caller must actually authenticate that source. This boolean is evidence supplied by a trusted adapter, not an authentication implementation. Changed binding or revoked jobs are rejected. owner_action records rejection/deletion claims and blocks future submission; it never deletes remote posts. See tests/test_engines.py for complete synthetic receipts and revocation examples.

Expected output: durable job dictionaries and operation rows. Troubleshooting: conflicting fingerprints require new reviewed content, not resetting an old receipt. Raw error/receipt payloads may contain user data; sanitize before persistence and protect the database. Concurrency is local SQLite; remote reconciliation is not implemented by this ledger alone.

## Schedule core and product rotation

Purpose: schedule_core parses explicit natural-language dates/times in an IANA timezone, rejects past/ambiguous/DST-fold/gap times, and provides durable schedule/outbox tables. Example: parse_schedule('tomorrow 6 pm', '2026-01-15T17:00:00Z', 'UTC'). It returns local, UTC and epoch timestamps. It does not install or activate a schedule.

product_rotation preserves immutable daily product snapshots, independently rotates six template numbers, and records image eligibility/unresolved products. Configure TOOLKIT_SERIES_ID, TOOLKIT_TIMEZONE, TOOLKIT_HOUR, TOOLKIT_MINUTE and TOOLKIT_PRODUCT_HOST before import. Defaults are an example series, UTC, 16:00 and example.com. install_series(path, catalog) initializes only your supplied local SQLite database; reserve(path, day, catalog, now=aware_datetime) allocates a date once. Catalog shape and complete two-product fixtures are in tests/test_engines.py. No product facts, photos or templates are supplied by this module. bind_job expects JOB- followed by at least four digits. Legacy schema field names containing uae_date are retained for compatibility but mean the configured-zone date.

Expected output: the same assignment on repeat calls, independent product/template cursors, explicit conflicts on changed identities. Troubleshooting: use exact storefront IDs and an approved HTTPS host; do not silently replace an ineligible product. Limitations: six-template numbering is implemented, but the actual six branded layouts are not included in this batch. Receipt checks are local admission checks, not permission to post.

## Notification outbox

Purpose: durable, deduplicated per-channel delivery with claim leases, exact-destination receipt checks, bounded retries and UNKNOWN outcomes that cannot be automatically resent. Construct an approval ledger, call schedule_core.outbox, then notification_outbox.drain(ledger, targets, sender=trusted_callback). Targets are explicit channel/account/recipient mappings. Account identifiers default to default and can be set with TOOLKIT_WHATSAPP_ACCOUNT and TOOLKIT_TELEGRAM_ACCOUNT. There is no automatic owner discovery and no CLI sender.

The callback receives channel, account, recipient, message. It returns an exact destination plus delivered=True and messageId only on confirmed delivery; ambiguous=True on timeout/uncertainty; retryable=True only on authoritative non-delivery. In OpenClaw, the adapter must use its authorized messaging tool. Tests use an in-memory callback and never send a customer message. Incorrect receipts are rejected. Expired leases become UNKNOWN. Caller-supplied errors/receipts must not contain credentials.

Expected output: delivery state records. Troubleshooting: missing or mismatched destinations block delivery; UNKNOWN requires read-only reconciliation. This is a delivery state machine, not a configured WhatsApp/Telegram account or customer-response generator.

## Watchdog

Purpose: persist task lifecycle, detect stalls/deadlines, monitor a configured TCP endpoint and deduplicate staff alerts without restarting work or sending messages. TOOLKIT_STATE_DIR isolates local data. TOOLKIT_GATEWAY_HOST is required for real health probes; TOOLKIT_GATEWAY_PORT defaults to 18789. API tests pass connect_fn to avoid any socket access. CLI example: python -m toolkit.watchdog status (local database only). start/progress/complete/fail require explicit task IDs and evidence. scan performs a configured endpoint probe; do not point it at production during tests. scan_customer_failures requires an explicit read-only inquiry-database path.

Expected output: JSON task/health state and queued alerts. Completion evidence is recorded, not independently proven by this component. Gateway recovery never declares a task completed. No daemon/timer is installed. Alerts and inquiry metadata are private runtime data and must never be committed.

## Apify billing evidence guard

Purpose: independently validate Free-plan/no-overage policy evidence (30-day limit) and current-cycle credit evidence (7-day limit), preserving an explicit per-run cap and reserve. Call billing_guard(evidence_path, now=aware_time, cap=0.20, reserve=0.30). Synthetic proof schema is fully shown in tests/test_engines.py. Return is normalized evidence and balance; stale, malformed, insufficient or nonfinite evidence is blocked. No account query or Actor is started. The proof must come from a trusted billing source; this module cannot authenticate a screenshot or establish current credit automatically. Actor submission and billing enforcement at the provider remain separate unfinished adapters.

## Tests and limitations

Run python -m unittest discover -s tests -v. Original Meta/Sheets and watchdog regression cases are retained with generic identities; new tests exercise rotation, budget expiry, schedule ambiguity, immutable approvals, revocation, exact receipts and no replay after timeout. No live posts, Sheets writes, paid APIs, customer replies or installed schedules are used. The complete source register remains explicit about unported orchestration and identity/routing adapters.
