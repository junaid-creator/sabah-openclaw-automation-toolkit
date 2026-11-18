# Integrated SEO draft workflow

`SEO` composes the existing daily controller, create-once primitives, WordPress client, three-image validation and owner outbox. Draft-only: later publication still requires the separate publication gate.

Construct `Controller(stable_daily_id, private_root, account=..., recipient=..., asset_root=...)`, a WP client with explicit application credentials/network/write permissions, and `SEO(controller, wp, expected_wp_user=..., enabled=True)`. The WP user needs draft/media permissions. No credentials are discovered.

`prepare(research=..., article=..., start_images=..., read_images=...)` persists stages. Article returns exact title/content/excerpt/slug/keyword. Research/copy require qualified source review. Image intent is durable before start; the saved task is polled through the authorized callback. Pending returns WAITING_IMAGES. Missing task identity stops rather than regenerating. Exactly three distinct same-byte WebPs must match the completed task receipt.

`draft(validate=...)` uploads once, saves/verifies media metadata, creates one draft, verifies saved fields, invokes independent plan-bound validation and prepares an owner report. Unknown writes preserve IDs and block replay. Validator must actually perform required checks, not return an invented success flag.

`deliver(sender=..., enabled=True)` reserves the owner outbox before the host messaging callback and requires exact account/recipient/message receipt. Unknown delivery never resends; verified repeats reuse the receipt. No native SDK API is guessed.

Five integration tests exercise actual synthetic WebPs and durable state through a disposable CMS protocol fixture and simulated transport. This is not a booted WordPress server. Three-tab tracker schema, SEO-plugin metadata registration, inline media URL rewriting, semantic review and real account acceptance remain explicit limitations. `source_reconciliation` provides safe exact-range tracker primitives, not an assumed private schema.

Rollback: deactivate only the separately installed new runner, preserve all state and remote IDs, revert code. Never clear uncertainty to recreate objects. Removing drafts/media requires separate operator authorization.

Run `python -m unittest discover -s tests -p test_seo_workflow.py -v`.
