# Product media and source reconciliation

Executable Python integrations; not automatically installed channel commands. Use the supported Python and pinned requirements in DEPENDENCIES.md.

## Reviewed upload

Construct `Media(products, private_asset_directory)` with the existing Products engine and signed owner bridge. Directory 0700, files 0600 WebP, maximum 8 MB/24 million pixels. Require exact SHA-256 and explicit owned/licensed rights evidence. No URL fetching or credential discovery.

Trusted host command sequence (WhatsApp, Telegram or Gateway adapter):
1. `MEDIA PLAN {"site":"demo","file":"owned.webp","sha256":"<exact hash>","rights":"owned","rights_reference":"operator evidence"}`
2. Deliver binding and capture real owner receipt.
3. `MEDIA REVIEW media-<id>` calls challenge with trusted receipt.
4. Returned `CONFIRM <challenge>` calls bridge.confirm.
5. `MEDIA EXECUTE media-<id>` calls execute.

Plan/review never write remotely. Execute requires engine activation, network/write opt-in, expected WP identity, bound approval and unchanged bytes. WP needs upload_files and attachment read permission. Returned unattached media ID requires a separately approved product plan before assignment.

Signed `MEDIA REVOKE media-<id>` blocks future admission, not already in-flight requests. Lost response/crash/renamed file/wrong readback is fenced: never POST again. Reconciliation needs trusted read-only remote-byte SHA verification, not chat evidence. Verifier must allowlist media origin, refuse redirects and bound bytes. No automatic attachment deletion. Restore references through separately approved existing scoped product restore.

## Source and Sheet

`snapshot` binds stable row IDs and separate formula view. `row_request` maps explicit columns into product requests. Call `revalidate` immediately before executing an approved plan under exclusive source writer control. Drift requires new approval. This is not an atomic cross-provider transaction.

`mirror_once` persists intent and exact before/after binding before injected Sheet mutation. Lost responses reconcile by readback, never blind replay. Adapter must enforce authorization and explicit account/spreadsheet/range, using RAW writes. SQL restoration cannot safely be represented by Woo REST; use tested host-owned database recovery tooling.

## Tests and limits

`python -m unittest discover -s tests -p test_product_extensions.py -v`

Ten focused tests: signed approvals, revocation, synthetic WebP, mocked WP HTTP, durable no-replay recovery and formula drift. No real account acceptance. The existing native product plugin dispatches MEDIA PLAN/REVIEW/EXECUTE only when engine config explicitly supplies media_root. CONFIRM resolves the persisted media challenge. Read-only media reconciliation remains a trusted operator adapter, never customer-supplied evidence.
