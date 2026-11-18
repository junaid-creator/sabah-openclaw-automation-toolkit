# Authenticated product management (portable subset)

This is original implementation code informed by original scoped product engines,
not copied WooCommerce code. Protocol reference: [official Woo REST API](https://woocommerce.github.io/woocommerce-rest-api-docs/).
The adapter uses Woo REST v3 and WordPress REST v2 over configured HTTPS origins.

## What runs

- Create simple or variable **DRAFT** products with explicit unique SKUs, literal
  prices, local attributes, reviewed category IDs, allowlisted metadata and existing
  verified WordPress image attachment IDs. New products are hidden/out of stock;
  creating children with Woo's publish status does not publish the draft parent.
- Edit existing parent text/categories/media/metadata and simple regular prices;
  edit exact existing variation IDs, prices, image IDs and metadata. No variant
  deletion, implicit family remapping or product-type conversion.
- A **separate publish plan** changes only an existing unchanged draft's status.
  Publication preserves catalog visibility and stock; it does not imply saleability.
- Complete explicit-status parent/variation inventory including trash prevents
  name/SKU duplicates and conservatively blocks possible model-family collisions.
  Unsupported status inventory or pagination over 100 pages fails closed.
- 30-minute immutable plans, five-minute delivered-review challenges, signed direct
  owner confirmation, site/account isolation, durable SQLite FULL checkpoints,
  protected before-state snapshot, one unresolved job per site, no write retries,
  scoped readback and read-only uncertain-outcome reconciliation.

All network and writes are OFF by default. No installation modifies a channel,
website, service or scheduler. No credentials or production identity are shipped.

## Configuration and real integration boundary

Start from [product-sites.json](../examples/product-sites.json). Place private state
outside the checkout in an operator-owned 0700 directory. State contains private
catalog copy, approval evidence and metadata; do not publish it. Keep configuration
operator-owned and not group/world writable. Supply independent signing key (at
least 32 bytes), WordPress username and application password through the named
process environment variables. A configured user ID is checked via users/me before
planning and each mutation. Credentials must have the necessary Woo and media
permissions on that exact site. There is no fallback to another site/account.

The host must authenticate the actual channel transport, enforce direct owner
routes, and sign canonical Bridge events with HMAC-SHA256. Do not give the model,
customer, or raw chat processing path access to this key or to arbitrary executable
commands. Event text is a single exact command; quoted JSON/prose and
owner_verified booleans do not grant authority. Routes marked customer, group
messages, altered signatures and wrong site owners are rejected. **A trusted host
can forge any event by design; provisioning that trust boundary is your job.**

The supplied callable contract is toolkit.product_commands.dispatch(engine,
envelope), with Products and Woo constructors for dependency injection. An
executable stdin boundary is also available:


Executable entrypoint:

~~~sh
python -m toolkit.product_commands --config /operator/product-sites.json --state /operator/private-products
~~~

Pass a JSON envelope on stdin containing event and signature. --network enables
reads; --writes additionally enables mutations, but cannot bypass bound approval.
Never put signing keys or passwords in command arguments. This entrypoint installs
**no native OpenClaw ingress, delivery sender or plugin**. An optional source package now exists at [product-owner-bridge](../plugins/product-owner-bridge/README.md), with mocked native-hook tests but no live activation. A native trusted host must
invoke it and deliver the full exact review. A working mocked callback is not proof
of a fresh site's deployment, authorization, network access, REST behavior or UI.

Before enabling writes, disable other product writers for the maintenance scope
and explicitly set exclusive_writer_confirmed=true. REST does not provide an
atomic compare-and-swap or cross-process server lock. The local lock, immediate
fingerprints and readbacks detect drift, but cannot prevent an unrelated remote
writer racing between the final read and POST. Do not use this engine on an
uncontrolled multi-writer storefront. Confirm a site-level database backup and
restoration procedure separately before live adoption.

## Exact command lifecycle

1. PRODUCT PLAN followed by a JSON object matching
   [product-request.json](../examples/product-request.json). Supported operation
   values: create, edit, publish. This is planning only, not approval.
2. The host delivers the complete returned plan (all steps, exact fields, before
   state, dependencies, origin, operation and digest), not merely a summary.
3. PRODUCT REVIEW JOB_ID, attested by the host, is paired out-of-band with
   review_receipt: delivered=true, message_id, binding_digest=fingerprint(binding),
   and channel/account/peer matching the owner route. This receipt must originate
   from the trusted host's real delivery result, never extracted from user/model
   text. The CLI assumes its stdin is accessible only to that trusted host.
4. Return the exact CONFIRM CHALLENGE_ID challenge text to that owner. Their signed
   exact response binds approval; other text is not accepted. Challenge expires in
   at most five minutes, and the entire plan in 30 minutes.
5. PRODUCT EXECUTE JOB_ID executes at most once, only with writes enabled and fresh
   before fingerprints/dependencies. Each outgoing POST has its own durable
   WRITE_STARTED record before transport. An acknowledgment alone is not success.
6. PRODUCT STATUS JOB_ID returns recorded state (not fresh verification).
   PRODUCT RECONCILE JOB_ID rechecks existing writes without mutation. PRODUCT
   REVOKE JOB_ID prevents future writes; it never erases already-recorded writes
   or clears uncertain reservations. Revocation commits independently of the long
   execution lock in a dedicated SQLite table. Each write admission checks it in a
   short transaction and again immediately before transport. An already admitted
   in-flight request cannot be undone; its remote ID is still persisted, then the
   workflow stops in NEEDS_REVIEW without admitting another step. Cancellation
   during backup prevents all product mutations. A stale receipt save cannot erase
   the durable revocation fence.

Example edit request:

~~~json
{"site":"demo","operation":"edit","product_id":10,"fields":{"description":"Exact reviewed copy"},"variations":[{"id":11,"fields":{"regular_price":"25"}}]}
~~~

The parent must actually own variation 11; a simple product rejects this request.
For a variation-only edit, include an unchanged reviewed parent description.
Example separate publish: {"site":"demo","operation":"publish","product_id":10}.

Supported fields are allowlisted in product_plan.py. Existing stock, SKU, type,
attributes, sale prices and sale dates cannot be changed. Regular-price changes
with current/scheduled discounts are blocked rather than overwriting promotions.
Unknown server fields are protected by exact readback; plugin-derived changes can
therefore intentionally leave NEEDS_REVIEW. Variable parent price is accepted only
when equal to the minimum of its published children's exact effective prices.
Media/category lists are explicit replacement lists: include every retained ID.
Metadata merges only operator-allowlisted string keys, preserving unrelated keys.

## Media, backup, verification and recovery

Only existing image attachment IDs are accepted. The adapter reads authenticated
attachment identity, MIME, title, alt, dimensions and source URL as frozen evidence.
It **does not fetch source_url** and never downloads arbitrary URLs. ID identity
is not a semantic photo/content review: the owner must inspect the reviewed image.
Local-file upload, generation, binary hashing, cropping and image optimization are
not included. Pre-upload with a separately authorized tool, then review the ID.

Before a mutation, the engine writes a 0600 immutable JSON plan/before snapshot,
fsyncs file and directory, and checks exact bytes and SHA256. This is a scoped REST
snapshot, **not a full database backup or proof of tested restore**. Existing
private engines' SQL export/gzip integrity workflow is not portable here.

VERIFIED means exact authenticated Woo readback, not public frontend verification.
public_verified is always false. No browser, cart, checkout, selector rendering,
robots, structured data, CDN invalidation or public share URL is verified.

On exception, timeout, malformed response, partial variation creation or drift,
state remains NEEDS_REVIEW (a hard crash can leave WRITE_STARTED). Never reset the
ledger, delete receipts or approve again to retry the POST. Reconciliation locates
new products using a job marker plus exact SKU/fields, checks child count and each
marker, and verifies existing products against the before-state plus approved
patch. It may recognize a completed lost-response write, but cannot finish partial
writes. A missing/ambiguous result does not authorize recreation. Unresolved jobs
keep the site reserved; revocation alone cannot release a partial job. For partial
or uncertain writes, export private evidence and establish remote outcomes with a
separately reviewed operator procedure.

### Separately reviewed scoped restoration

A new PRODUCT PLAN request with operation=restore, site and source_job creates a
new exact review of a previously VERIFIED existing-product edit. Example:

~~~json
{"site":"demo","operation":"restore","source_job":"product-RECORDED_JOB_ID"}
~~~

It verifies the protected before-snapshot hash, owner/site, original plan digest
and exact recorded after-state against current REST readback. Only fields changed
by that original edit are restored; unrelated current fields remain protected.
The restoration is a new plan/challenge/owner confirmation, with the same backup,
expiry, revocation and no-replay safeguards. Current-after fingerprints are checked
again before execution. Created products/children are never deleted. Publication
rollback, partial/uncertain-source restoration, recursively undoing a restore,
restoring newly added metadata keys (would require deletion), and unsupported old
field values are refused. This is not database disaster recovery.

## Deliberate gaps versus the private originals

Not ported: private SKU/ID aliases or hardcoded family mappings; Google Sheets
A:H source parsing and formula snapshots; row-preserving I:N tracking and blank
SKU writeback; SQL/PHP mutation and atomic server-side duplicate checks; protected
SQL database export/restore; source-coupled promotion text substitutions; legacy
product consolidation; public frontend selector and structured-price validation;
automatic recovery workers, scheduled sync, native channel ingress and owner
notifications. This module never touches Sheets, so cannot overwrite rows/formulas,
but does **not** implement original Sheet-coupled reconciliation. Category creation,
taxonomy attribute creation, deletion, stock/discount management and local file
media upload are also out of scope. No claim of complete original-engine parity.

## Offline tests

~~~sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_product_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests
~~~

The product suite injects an in-memory HTTP opener through the actual Woo/WP
transport adapter and denies real socket connections. It covers forged/group/
customer/cross-site admission, replay, expiry, revocation, protected fields,
all-status duplicates, backup failures, failed/lost responses after mutation,
partial children, sibling drift, exact variable edits, attachments, category/media
drift and separate publication. Passing synthetic tests is not a live-site proof.

## Read-only installed-source compatibility evidence

Reviewed isolated WooCommerce **11.2.0** source without loading WordPress, making
HTTP requests or invoking its database. v3 product controller inherits v2
get_collection_params; that method explicitly admits future and trash alongside
get_post_statuses(). v3 variations inherits v2 products' collection parameters and
sets post_status from the requested status. Thus explicit future/trash collection
queries match this installed source; these are collection enums, not writable
product-status enums. Older versions and site plugins remain deployment checks:
unsupported collection queries fail closed rather than silently omit duplicates.

Source review also found that variable parent get_children() includes only publish
and private statuses. The adapter now compares the parent's child-ID list to those
statuses while still separately inventorying draft/pending/future/trash children
for collision detection. v3 variation readback exposes parent_id. No upstream
source was copied into the toolkit.

Evidence hashes (upstream files read, not release artifacts):
- Version2/class-wc-rest-products-v2-controller.php:
  6087fcf7d3e4f14419f51b1b745a79066e39e78d8ce0b1587c3c9edf62954936
- Version3/class-wc-rest-product-variations-controller.php:
  687aa3b7e57a36abee8bf260a89c635d4ff3829a1fc6a2acadbdbd58160a7c90

This is source-level compatibility evidence, not an isolated live REST acceptance
test. Exact readback still intentionally blocks unmodeled plugin/server changes.
