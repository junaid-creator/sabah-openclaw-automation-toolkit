# Isolated implementations for four formerly missing groups

These are executable, offline-tested **partial ports**, not fresh live acceptance.
No production scripts/configuration are imported. No service, account, model,
message, publication, callback listener or schedule is enabled by installation.
Use the repository Python environment/requirements (Pillow for existing renderer
and local-voice imports). Python >=3.11 on POSIX (>=3.12 for optional Playwright rendering); flock requires a local filesystem.
No additional dependency was introduced. Existing stdlib, reliability, trusted
bridge, image intake, approval ledger, six-template renderer, Meta publisher,
TikTok state machine and local voice adapters were reused instead of new stacks.

## Badge audit

Fixture expected JSON is a map: {"123":"Save 20%", "456":"Special offer"}.

~~~sh
python -m toolkit.badge_audit --fixture product.html --expected expected.json --product-id 123
python -m toolkit.badge_audit --url https://shop.example/products/tool/ --allow-host shop.example --expected expected.json --product-id 123
~~~

Only the second command performs one bounded unauthenticated GET. HTTPS and
operator allowlisting are mandatory; redirects, credentials, private resolved
addresses and proxies are refused. Use trusted hosts plus egress restrictions:
DNS prevalidation is not a complete DNS-rebinding defense. No retries or crawling.
Exit 0 means exact own badge once, all encountered product badges match expected,
and no generic Sale! badge; exit 1 means mismatch. Exceptions are errors.
Attribute defaults to data-smgc-product and is configurable. HTMLParser handles
attribute order, nested markup and entities. This audits server HTML, **not CSS
visibility, computed price, JavaScript, carts, checkout or mobile screenshots**.
The fixture mode never fetches URLs contained in HTML.

## TikTok OAuth (independent Login Kit WEB implementation)

Official documentation read on 2026-11-18:

- https://developers.tiktok.com/docs/en/login-kit-web
- https://developers.tiktok.com/docs/en/oauth-get-a-user-access-token
- https://developers.tiktok.com/docs/en/oauth-refresh-a-user-access-token
- https://developers.tiktok.com/docs/en/oauth-user-access-token-management

Contracts: authorize at https://www.tiktok.com/v2/auth/authorize/; exchange and
refresh POST form-encoded bodies to https://open.tiktokapis.com/v2/oauth/token/.
Exchange fields: client_key, client_secret, code, grant_type=authorization_code,
exact redirect_uri. Refresh fields: client_key, client_secret,
grant_type=refresh_token, refresh_token. Lifetimes come from response fields,
not documentation examples (the current docs contain inconsistent examples).
Web-only: mobile/desktop PKCE flows are deliberately not implemented.

Create a fresh owner-only directory (0700), supply credentials explicitly from
an operator secret manager, and instantiate:

~~~python
from toolkit.tiktok_oauth import OAuth, OfficialTransport
# No default credential files or environment discovery.
auth = OAuth(isolated_root, client_key=key, client_secret=secret,
             redirect_uri="https://app.example/callback",
             scopes=["user.info.basic", "video.list"],
             transport=safe_fixture_transport)  # (endpoint, form) -> dict
url = auth.start(authenticated_browser_session_id)
# The HTTPS web adapter verifies its secure session cookie before calling finish.
status = auth.finish(full_callback_url, authenticated_browser_session_id)
status = auth.refresh()  # bounded single attempt, only near expiry
~~~

A separately authorized deployment can explicitly inject
OfficialTransport(enabled=True); default transport is disabled. Do not put
secrets/callback codes in command lines, logs, documentation or chat. The caller
must host its own authenticated HTTPS callback endpoint and secure session cookie;
this module does not establish browser identity. One state/store per application
and account. State uses CSPRNG, hash-at-rest, session binding, expiry, duplicate
parameter rejection, exact callback comparison and durable consumption before
exchange. Token schema, scopes and stable open_id are checked. Rotation saves
both new tokens atomically (0600) under a single cross-process lock. status()
never returns tokens. access_token() is an explicit secret accessor.

Timeout/malformed response/process death is UNKNOWN/EXCHANGING/REFRESHING and
**never automatically retried**, even if old tokens remain on disk. Reconcile
with the provider; if recovery cannot prove the valid rotation, reauthorize into
a new isolated store after reviewing the old attempt. No reset/replay CLI exists.
No token revocation adapter, scheduler, encrypted secret vault or live OAuth test.

**This is NOT TikTok Business API OAuth.** The original helper used
/tt_user/oauth2/token/ and /tt_user/oauth2/refresh_token/ with different fields.
Do not wire these Login Kit tokens into toolkit.tiktok_publisher's Business API
client. Use the separately named BusinessOAuth below. No original credentials
or account configuration were read.

### Business Accounts OAuth v1.3 (original API family)

The separate toolkit.tiktok_business_oauth.BusinessOAuth implements exchange,
refresh and token-info validation with independent client_id/client_secret,
pinned expected_open_id, scope checks and business-oauth.json/private lock.
It shares the tested state/session/replay/atomic-rotation machinery, NOT the
Login Kit token transport. Its token_provider(force=False) directly satisfies
existing tiktok_publisher.Client's explicit callback interface.

~~~python
from toolkit.tiktok_business_oauth import BusinessOAuth
business = BusinessOAuth(isolated_root, client_id=app_id, client_secret=secret,
    redirect_uri="https://app.example/callback", expected_open_id=account_id,
    scopes=["video.list", "video.publish"], transport=safe_business_transport)
request = business.start(authenticated_browser_session_id)
# Trusted web adapter puts request['state'] into its reviewed Business consent URL.
business.finish(full_callback_url, authenticated_browser_session_id)
# Supply business.token_provider to a separately configured Business publisher.
~~~

Official indexed docs verified on 2026-11-18:
- https://business-api.tiktok.com/portal/docs/accounts-api-authentication/v1.3
- https://business-api.tiktok.com/portal/docs/renew-a-short-term-access-token/v1.3
- https://business-api.tiktok.com/portal/docs/obtain-the-authorized-creator-permissions/v1.3

Contract: JSON POST client_id/client_secret/grant_type=authorization_code/
auth_code/redirect_uri to /open_api/v1.3/tt_user/oauth2/token/; JSON POST
client_id/client_secret/grant_type=refresh_token/refresh_token to
/open_api/v1.3/tt_user/oauth2/refresh_token/. Token-info POST uses app_id and
access_token at /open_api/v1.3/tt_user/token_info/get/; code=0/data envelope,
app_id, creator_id and scope must match before promotion. The fixed host is
business-api.tiktok.com. BusinessTransport is disabled unless enabled=True.
The original source's code/auth_code callback aliases are supported, but an
ambiguous pair or duplicate is rejected. Both OAuth families can coexist without
reading or overwriting each other's token files.

Precise remaining verification limit: direct unauthenticated web_fetch of both
Business portal pages returned HTTP 200 but only 53/57-byte title shells (JS
content unavailable); official indexed search supplied the endpoint/parameter
contracts above. The public official SDK AuthenticationApi docs describe the
DIFFERENT advertiser /oauth2/access_token/ (app_id/secret) API; a guessed
BusinessAccountApi.md URL returned 404 and was not used as evidence. No browser
or login was authorized. Business consent-URL generation is therefore explicitly
OPERATOR_REVIEW_REQUIRED rather than silently using Login Kit's URL. start()
returns state, client_id, scopes and redirect_uri for the reviewed web adapter.
Refresh expiry is optional: a present refresh_token_expires_in is validated;
absent expiry is unknown, not an invented one-year value. Initial/refresh app,
account and scope are checked via the verified token-info endpoint. Original
username/profile/owned-media proof and provider-specific revocation are not
implemented by this auth module; use the existing publisher identity preflight
before any separately authorized posting. No live OAuth acceptance claimed.

## Durable social draft/revision/review/approval dispatch

Use toolkit.social_review.Controller with a private local root, the existing
trusted_bridge.Bridge, approval_ledger.Ledger, renderer and sender callbacks.
The authenticated host must sign transport-verified events using Bridge's exact
schema; raw text/claimed sender IDs never create authority. Do not expose its key
to models or customers. All invocations below are Python API calls:

1. create(event, signature, campaign): stable event/route-derived job ID;
   exact same request resumes without re-rendering. No delivery or approval.
2. review(job): exact frozen binding to the configured owner via sender.
   sender(owner_route, binding) must return delivered=True, message_id,
   binding_digest, channel, account, peer; queued/dryRun/uncertain is not receipt.
3. challenge(job, event, signature): binds the delivered review to the existing
   trusted bridge, returns its short confirmation challenge.
4. approve(job, confirmation_event, signature): requires the bridge's exact
   CONFIRM challenge text; stores an authenticated exact-content Ledger receipt.
5. dispatch(job, publisher=adapter, enabled=True): one explicitly enabled
   adapter handoff, never automatic creation-time publication.

campaign schema: template (integer 1–6), content (poster_render.normalized schema),
targets (nonempty unique subset of facebook/instagram/tiktok), captions (exact
final text per target, including any hashtags). Language defaults to ENGLISH;
ARABIC/BILINGUAL require their existing exact-copy pairs. No inferred promises,
prices, image generation or copy-generation service is added.

LocalRenderer invokes existing poster_render.render for all six templates,
using explicit brand/fonts/atlas/output_root and host(path,sha256,revision_key).
Place its output_root under the controller private root. Rendering remains local
and network-blocked; hosting is an injected deployment adapter, never bundled.
Geometry proof is not semantic review/QR verification. The owner must review the
exact media and captions. Template assets/models/fonts are not redistributed.

revise(job,event,signature,campaign,expected=etag) preserves history and same job,
advances revision, clears current review/challenge, and requires fresh delivery
and approval. status(job) provides the CAS etag. Any existing publication receipt
or attempt blocks revision; revoke/reconcile through the existing owner ledger
before creating independently reviewed replacement work. No approval reassociation.

PublisherAdapters bridges MetaPublisher.run_job and tiktok_publisher.advance with
the SAME ledger. Explicit operator adapters must provide exact frozen Sheet rows,
blank per-platform override URLs or identical master URL, and final caption text
with empty separate hashtag fields. It checks the initial Sheet snapshot; the
Meta publisher must use social_publish_gate.BoundApprovalGate(controller, sheets,
SheetPublicationGate(sheets)); this wrapper rechecks the frozen rows, bridge and
ledger on every platform action and rejects changed override media/captions.

The TikTok engine.checked must validate the exact bound approval/account, and its
caption method must preserve the supplied final caption. Clients must enforce
media immutability/account identity and provider contracts. The controller checks
local media hashes before review/approval/dispatch, not hosted-media bytes.

No Sheet creation/revision adapter is automatically activated. No native
WhatsApp/Telegram transport is installed. Production language inference,
one-line intent parsing, paid media generation, automatic topic/template selection,
short production approval aliases, scheduled recovery and turnkey cloud wiring
remain outside this partial port. Returned PROCESSING is not publication success;
VERIFIED requires matching durable PUBLISHED receipt and public URL.

Process death/uncertain render, host, delivery or dispatch is latched before the
side effect. No blind retry exists. Cooperating controller calls share one lock;
external workers must not mutate the same drafts or approval state concurrently.
DISPATCHED means the adapter returned, not that all platforms published. A
PROCESSING TikTok task needs a separately controlled read-only reconciliation
path using the existing ledger/task ID; this controller never resubmits it.

## Opt-in isolated voice control

~~~sh
python -m toolkit.voice_control --root /absolute/private/test-voice status
python -m toolkit.voice_control --root /absolute/private/test-voice --enable-isolated-write apply --patch patch.json --expected ETAG_FROM_STATUS
python -m toolkit.voice_control --root /absolute/private/test-voice --enable-isolated-write rollback --generation 0 --expected CURRENT_ETAG
~~~

Directory must already exist with owner-only permissions. Writes only voice.json
and voice.lock beneath that explicit root; never openclaw.json, systemd, account
configuration, services or shell rc. Example patch: {"mode":"off","profile":"male"}.
Allowed top-level settings: mode (off/inbound), profile (female/male), local_voice,
routes. Recursive dictionaries merge; explicit arrays/scalars replace; unrelated
stored fields survive. Every mutation requires CAS over the full previous state.
Previous settings and hash are recorded in the same atomic document. Rollback is
a new generation, requires current CAS and validates archived settings.

Inbound mode requires model_license_reviewed=true, exact direct routes
(channel/account/peer), and trusted existing local_voice executable/model paths
(ffmpeg, asr, encoder, decoder, tokens, piper, voices[profile][language]).
VoiceControl.local_config(route) returns (config, profile) for existing
local_voice.transcribe/synthesize. It neither runs them nor sends audio. Assets
are not downloaded or bundled. Native binary/model licensing, ASR comparisons,
latency/quality, Gateway installation and live channel integration are untested.
Same-UID hostile writers are outside the private-directory boundary. flock/CAS
coordinates participating processes, not unrelated editors.

## Verification

Run: python -m unittest discover -s tests -p 'test_missing_implementations.py' -v

Offline tests cover negative schemas/URLs, CSRF/session/replay/expiry, rotation,
private-store permissions, uncertain and crash latches, concurrent claims/CAS,
all six template dispatches (renderer mocked; no browser run), real existing
TikTok state-machine invocation with a fixture client, existing MetaPublisher
dry-run with no transport calls, review invalidation and public-receipt gating.
No live provider, account, publication, messages, browser or native model executed.
