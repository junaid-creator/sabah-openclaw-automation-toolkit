# Native owner social bridge

Original source adapter for the installed OpenClaw `before_dispatch` and `message_sent` hook contract, matching the existing product bridge. Requires the sibling product-owner-bridge directory because it shares its audited process/identity/receipt implementation. Do not copy this folder alone. No production installation or activation performed by this release.

Use an independently installed official OpenClaw version whose SDK exports plugin-entry and whose hook contract matches the product bridge reference. Python >=3.12, Node 24, pinned render requirements and local Chromium/fonts/authorized branding are required. Follow the product bridge config schema for python/checkout/engineConfig/engineState/stateDir/signingKeyEnv/environmentKeys/routes. Configure distinct private state directories for product and social bridges. The engine module is fixed to toolkit.social_commands; arbitrary module names are rejected.

Engine config must be owner-only 0600 JSON containing bridge_key_env, trusted routes, brand/fonts/atlas (poster renderer schema), and media_url_prefix. The latter must be an owned HTTPS static mapping to engineState/renders. Provision and verify that mapping independently; the executable does not upload, create a web server or claim remote media availability. Set allowWrites only for authorized local draft/approval state. No publish client is included in this command executable. Secrets enter via separately configured environment references, never request text.

Owner examples (same commands on configured WhatsApp or Telegram):
- `SOCIAL CREATE {"template":1,"content":{...},"targets":["facebook","instagram","tiktok"],"captions":{...}}`
- `SOCIAL STATUS SM-<id>`
- `SOCIAL REVISE SM-<id> {"expected":"<current etag>","campaign":{...}}`
- `SOCIAL REVIEW SM-<id>`, after real delivery of the returned exact binding and media URL.
- Returned `CONFIRM <challenge>` records exact-content approval only.
- `SOCIAL REVOKE SM-<id>` persists local revocation; no remote deletion.

Untrusted sender claims, groups, changed account/chat metadata, quoted commands and missing/dry-run/ambiguous receipts are rejected. Revision receipts replace the local review pointer; the controller still rejects stale binding hashes, so a delayed old receipt cannot approve revised content. A lost pointer requires review, never forged delivery. The host process/key must remain inaccessible to model/customer tools. Native callbacks are not exposed as model-callable APIs.

Publication stays NOT_DISPATCHED until the separately configured existing exact-approval worker is invoked. The social controller publisher adapters remain available, but native publication routing, Sheets syncing and owned hosting must pass their own deployment acceptance. Short natural-language campaign parsing and automatic image generation remain unimplemented here; structured owner commands are executable, not an assertion of production feature parity.

Tests: five Python command lifecycle tests plus native hook isolation/revision receipt tests, all simulated transports. Fresh live Gateway/channel acceptance remains required. Rollback by disabling only this newly installed plugin in the target deployment, retaining private receipt/approval ledgers; never clear uncertain work or touch existing accounts.
