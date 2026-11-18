# Platform and workflow adapters — batch 2

## Common setup and safety

Use Python 3.11+ (Pillow 13 requires it); Linux/Python 3.14 is locally tested. Install requirements.txt in an isolated venv, then run python -m unittest discover -s tests -v. All release tests use temporary state, synthetic identities and mocked network/process adapters. No live provider behavior, account scope, paid start, customer reply or schedule activation is claimed. API contracts can change; review official provider documentation before enabling an integration.

These are callable libraries, not auto-installed OpenClaw tools. Keep credentials in your own secret manager and construct clients only in an explicitly authorized adapter. Do not put tokens in example files. Most usage examples below are exercised fully in the named test files; using a mock is not live authorization.

## WordPress REST client

Purpose: bounded authenticated REST reads and explicit writes with no redirects. Construct wordpress.WP(base_url, username, application_password, allow_network=False, allow_write=False). The HTTPS origin is explicit; no private host, user ID or deployment helper is assumed. Only /wp-json/ paths are accepted; responses are bounded and errors do not return raw provider bodies. Network/write flags default off. An injected opener allows complete offline tests.

Installation: standard library. Configure your own WordPress application password, minimum role, exposed REST fields and canonical public origin. Activate allow_network=True only for an authorized read. allow_write=True additionally permits POSTs and must be confined by your application's approval boundary. This low-level client does not itself authenticate a chat owner. Sample: with the default flags, request('/wp-json/wp/v2/posts') raises Network disabled without making a call. tests/test_platform_adapters.py includes a fake opener and read/write denial examples.

Expected output: parsed JSON or a safe exception. Inventory pagination is bounded to 100 pages. Troubleshooting: confirm route/auth separately; redirect refusal requires configuring the canonical origin, not relaxing TLS. Custom SEO/plugin namespaces are intentionally not guessed or shipped. Fresh live sites are NOT TESTED.

## Blog publication and saved-state gates

Purpose: publish one already-reviewed existing draft, with immutable fingerprint, fresh per-gate evidence, owner/account/WP-user identity checks, local-date reservation, readback and no second POST after an uncertain result. The implementation is adapted from the actual publication adapter, not a simulated publisher.

Call blog_publication.publish_existing with wp, plan, approval, evidence and an independent public_check callback. Required configuration includes expected_owner, expected_account, expected_wp_user, explicit allow_publish=True, private root/ledger paths and an IANA timezone. approval must contain owner_verified, explicit_activation, explicit_publish, exact owner/account/source_message_id, run_id, post_id, local_date and post_hash. These fields must come from a trusted authenticated adapter, never customer text. No former standing daily approval is inherited.

GATES enumerates every required content/taxonomy/media/SEO/robots/template/browser/ledger/notification check. Each proof must bind the same post/hash, have an artifact reference, passed=True and an aware timestamp no older than 30 minutes. This library validates supplied evidence; it does not fabricate research, visual review or transport receipts. The complete synthetic plan/ledger schema is in tests/test_platform_adapters.py, including a simulated POST that succeeds remotely but times out locally.

Expected output: verified saved/public result, or a durable review-required state. Never clear a checkpoint merely to retry. A missing post ID, stale evidence, changed content or wrong owner blocks. One publication per configured local day is enforced independently by local reservation, ledger and current CMS inventory. Locks do not coordinate multiple servers. CMS success is not proof of visual rendering; public_check must provide that independent evidence.

blog_gates.snapshot_robots validates saved indexing inheritance. snapshot_template(snapshot, expected_template_id) checks the configured template and competing single-template conditions. Both consume supplied snapshots, make no CMS call and fail closed when metadata is absent. They do not assume a production template ID or private WP-CLI grant.

## Blog orchestration, assets and report receipts

blog_controller.Controller(run_id, root, account=..., recipient=..., asset_root=..., timezone_name='UTC') implements the original inventory → research → article → images → plan → draft → validation → report state machine. Stable run IDs use blog-daily-YYYY-MM-DD. Supply actual authorized adapters to run(), or use begin/record_image_task/finish for asynchronous tools. Queued images and empty evidence are not completion. A failed/interrupted stage is latched; a repeat never blindly regenerates or repeats the callback.

record_image_task binds one provider task ID; image_task_status never authorizes resubmission. recover_image_assets requires the same completed receipt and three distinct, hash-bound WebPs under that run's asset directory. blog_assets fully decodes bounded still WebP bytes with Pillow and rejects path escape/hash drift. No provider-generation API is imitated. Native OpenClaw image/browser/message tools must be supplied through a trusted tool-aware integration, which remains an explicit deployment dependency.

draft_primitives.create_once persists intent before a creation callback and preserves the returned ID before readback; unknown creation never gets a second call. update_known rereads before a bounded idempotent update. It is suitable only for confirmed idempotent setters, not create/post/send operations. report_outbox.Outbox requires explicit account/recipient, freezes payloads, claims once and records exact receipts. Missing/uncertain delivery cannot be reclaimed automatically. Controller.finish_report checks the saved destination and message receipt; for publication reports, pass the explicit publication run ID. No sender is installed.

Tests: test_blog_controller.py exercises stage ordering/replay, task identity, timeout/no-resubmit, actual temporary WebP recovery, hash drift, create-once uncertainty, and wrong-recipient rejection. Limitations: complete model research/image generation, custom SEO route, tracker synchronization and channel binding are not implemented by these primitives. The orchestration API is working, but a fully configured daily blog deployment remains INCOMPLETE.

## TikTok Business photo adapter

Purpose: original Accounts/Business API photo preparation, submission, status polling and owned-post share-URL verification. Construct tiktok_publisher.Client with a config dict containing client_id, client_secret, expected_open_id and approved_media_hosts; supply a token_provider(force=False) callback returning the current access_token/open_id for that account. OAuth storage/refresh is your separately authorized upstream integration; the private installed helper and app ID are not copied.

The default HTTP transport uses the Business API origin and refuses redirects. prepare performs live READ/preflight calls when you explicitly invoke it: video.publish and video.list, identity, verified URL property and public-photo settings must all pass. submit is blocked unless live_enabled=True and a trusted authorize(payload) callback returns True for the exact reviewed payload/account. A task/share ID is not a publication receipt. public_post/verify_public_post require an owned-post lookup and actual share URL. Inbox outcomes require human action. API version/capabilities must be revalidated for your own app before deployment.

advance(engine, job, content) retains the source's durable operation phases. The injected engine must provide ledger, tiktok client, clock(), caption(content, platform) and checked(job), with checked enforcing fresh exact approval/revocation. In-flight unknown submissions never blindly retry. reconcile_existing is read-only. Tests mock provider responses, verify scopes/account/host constraints, and block default submission. They do not establish current app permissions or live photo acceptance. Pillow is required for bounded JPEG/WebP validation.

## Apify paid-run client

Purpose: source-derived capped Actor admission and single-step collection without notifications or Sheet writes. Construct ApifyClient(actor_slug, expected_actor_id, token_provider, allow_network=False), or inject a fake transport for tests. start requires a stable run key, payload, private state_path, trusted billing evidence_path, authorize(input_digest), cap, reserve and monthly workflow limit. Defaults are $0.20 cap, $0.30 reserve and $1 reserved-cap monthly limit, matching the original conservative design; no money is spent by examples.

Independent guards: fresh Free-plan/no-overage policy and current-cycle credit; expected Actor ID; PAY_PER_EVENT pricing with a compatible minimum; no active/uncertain local run; account run inventory; monthly reserved caps; durable STARTING record before POST; and provider confirmation of maxTotalChargeUsd. Missing cap proof retains the run ID and blocks new paid work. Unknown start is UNCERTAIN_START and is never resubmitted. collect performs only reads on the saved run/dataset; cost evidence is checked and no paid retry occurs.

Limitations: evidence is a trusted external input, not automatically authenticated billing truth. The account inventory now checks up to 2,000 runs using 100-row ascending pages, validates pagination fields and terminal states, rejects duplicate IDs/changing totals, and rereads the first page before admission. Larger histories or incomplete/unknown evidence fail closed. This is not an atomic account-wide lock: another client can start after the final read. Only one authorized workflow controller should initiate paid runs; independent billing and cap checks remain mandatory. The dataset read is limited to 100 rows and reports possible truncation rather than claiming a complete dataset. Monthly accounting conservatively reserves the entire cap for every admitted run; it does not promise billing reconciliation across unrelated workflows. Pricing/API/billing behavior is NOT live-tested.

## Overture acquisition

Purpose: use the official externally installed Overture downloader with an explicit bounding box and fresh output, convert point features, retain coordinates for geographic qualification and deduplicate construction-sector prospects. Install the upstream tool from https://docs.overturemaps.org/; no downloader source is redistributed.

Call download(absolute_executable, (west,south,east,north), output, allow_download=False). It is off by default and executes a fixed argv without a shell only when explicitly enabled. Tests inject a runner that writes synthetic GeoJSON. qualify_features(geojson, profile, date) is entirely offline and uses the existing qualification rules. The profile schema is in examples/lead-profile.json. Returned rows are prospects, not confirmed buyers; data licensing and contact-use obligations remain with the operator. No outreach or Sheet sync occurs.

## Content-review and Google-evidence helpers

content_review implements the original procedural byte-preservation checks: one insertion marker, exact reversal of only the addition, style-body-only changes, protected-field comparison across the union of keys, and narrowly scoped inter-tag whitespace comparison. No CSS/HTML input is safe merely because these checks pass; visual review and HTML sanitization are separate.

google_readiness.assess takes supplied spreadsheet metadata, expected title, optional file-specific Drive evidence and scopes. It separates read success, OAuth write scope, canEdit and an unperformed write test. It never treats a Drive failure as a failed Sheets read and never writes a test cell. The eight packaged website/Google skills retain the original procedural safeguards and their resource links. Their artifacts/helper scenarios are validated; live skill execution against a new account/site is NOT TESTED.

## Google Sheets lead synchronization

lead_sheet_merge retains original identity/domain/phone/name deduplication and preserves first-seen, review, contact and notes fields. Blank/duplicate existing IDs and malformed incoming rows block rather than silently collapse data. google_sheets.GogSheets wraps the installed upstream GOG CLI with explicit account/client, a narrow environment and read/write opt-ins. It never reads a private runtime.env, searches for credentials, or exposes CLI stderr.

Configure your own existing GOG OAuth/keyring setup. GogSheets(account, client, allow_reads=True) supports preview reads; plan(sheet_id, tab, HEADERS, incoming) freezes source and exact intended RAW values plus a digest. apply(plan, approved_digest=...) requires write opt-in and the same explicitly reviewed digest, rereads source before mutation and reads back exact values after normal or uncertain writes. Replaying an already-landed target performs zero updates. Tabs are the declared All Leads, Qualified Leads and Reviewed / Contacted schema, not arbitrary worksheet access. Store plans privately: they contain prospect data.

Tests/test_google_sheets.py provides a full fake CLI runner, preserved metadata, wrong-digest/concurrent-edit rejection and timeout-after-success readback/replay. No Google account was accessed. A local lock or frozen plan cannot prevent a remote human edit between final read and update; this residual cross-service race remains. No automatic append/send/retry or scheduler is installed.
