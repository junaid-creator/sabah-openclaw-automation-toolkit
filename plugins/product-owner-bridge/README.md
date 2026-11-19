# Native owner product bridge — opt-in, NOT installed

Original source adaptation of the production before_dispatch/product bridge.
The plugin entry registers before_dispatch and message_sent using the installed
OpenClaw SDK contract. It is NOT a model-callable tool. It signs only exact
commands received on an explicitly configured trusted direct-owner route.

This package closes the earlier missing source-level native adapter gap, but its
live registration/channel behavior remains NOT TESTED. Node fixture tests
cover trusted admission, forgery/group/account rejection, HMAC binding, exact real
receipt matching, uncertain/ambiguous delivery, replay, output bounds, fixed argv,
environment isolation and UTF-8 streaming. They do not prove a connected channel.

## Host setup (new isolated Gateway only)

1. Install the toolkit and its Python requirements. Keep a reviewed absolute
   checkout/interpreter path. Keep plugin/engine configuration and state private.
2. Read current official OpenClaw plugin installation and message-hook docs:
   https://docs.openclaw.ai/plugins/hooks/messages and
   https://docs.openclaw.ai/plugins/sdk-setup . Use its supported local-package
   installer/configuration UI; this repository performs no installation/restart.
3. Copy config.example.json into this plugin's entry config. Replace every path,
   route and alias with trusted channel metadata observed on YOUR Gateway. Align
   peer/account/channel tuples with product-sites.json. Gateway webchat can be
   added only when its hook actually supplies authenticated sender/account/direct
   metadata; absent fields fail closed, never synthesize an owner identity.
4. Supply one independent >=32-byte signing key through the named protected host
   environment variable; keep it inaccessible to models/customers. The Python
   engine uses the same key reference. Only explicitly named credential variables
   cross the child boundary; loader overrides are rejected. Do not grant arbitrary
   process invocation to customers. Protect all ancestor directories as well as
   0700 state roots. Use separate state/config/keys for separate trust domains.
5. Leave allowNetwork and allowWrites false until offline tests, owner-route
   verification and an authorized disposable-site acceptance pass. Source import
   or module eligibility is not activation approval.

## Exact flow

PRODUCT PLAN JSON is intercepted before normal model dispatch. Python returns the
entire exact frozen plan/binding. The plugin returns that exact canonical JSON as
one native reply. message_sent must prove matching bytes, route, session and real
outbound ID before a durable review receipt exists. No receipt is fabricated from
an intended reply or from quoted/user-supplied text. More than 12,000 reply
characters is rejected, not truncated into an incomplete review.

PRODUCT REVIEW JOB_ID uses that saved receipt to issue a short-lived CONFIRM
challenge. Only known product challenges are intercepted. After exact confirmed
approval, PRODUCT EXECUTE JOB_ID invokes the durable engine once. STATUS,
RECONCILE and REVOKE retain their engine semantics. There are no automatic sends,
schedules, retries, model calls or approval inference. Native host returns the
reply through its normal route; no shell/RPC messaging fallback is used.

Uncertain subprocess completion requires existing-job inspection. A timeout can
occur after a remote write; killing the local child is not cancellation of the
remote action. Engine receipts own recovery. Engine revocation is durable and
independent of its long execution lock.

## Intentional limits

This is strict-command ingress, not a natural-language product extractor. The
original row commands have become explicit website-independent JSON plans; a
model may propose a plan but cannot sign its own authority. No local media upload,
Google source-row/formula bridge, support-agent tools or provider accounts are
installed. The exact review must fit one inline native reply. Pending reply
correlation is memory-only and expires after five minutes; reload/ambiguous or
uncertain delivery blocks approval. Do not reset receipt files to force replay.
Recover oversized/lost review through a separately reviewed delivery adapter.

Native hook declarations were rechecked read-only on OpenClaw 2026.11.5. Other versions need contract
checks. This release did not load the plugin into the production Gateway, restart
services, connect a fresh customer channel, deliver a real preview or publish.

## Required migration: exact owner session isolation (2026.11.5)

Existing configurations must be migrated before loading this revision. There is
no compatibility fallback: missing policy rejects registration. In BOTH plugin
configs, add an explicit nonempty supportAgentIds array containing every deployed
support-agent ID. Each owner route must add agent (the owner agent ID) and the
exact host-observed sessionKey beginning with agent:<agent>:. Owner agents must
be disjoint from supportAgentIds. Keep the existing channel/account/peer/alias
restrictions. Use config.example.json as a shape only; do not guess session keys.
Preserve private signing keys, engine configuration, receipt state and all
unrelated settings. No receipt migration/reset or live activation is authorized.

The inspected 2026.11.5 before_dispatch contract supplies ctx.sessionKey and
optional event.sessionKey, but no ctx.agentId, senderIsOwner or owner-current
assertion. This bridge requires BOTH sessionKey fields, equal to each other and
the configured exact owner session. Missing/conflicting event session metadata
fails closed; a channel which omits it cannot use this bridge until its trusted
mapping is established. Support-agent sessions are independently rejected even
when sender/account/chat otherwise match. Outbound review correlation also
requires the exact ctx.sessionKey, without an event-only fallback.

This is authenticated host-metadata route isolation, NOT the native owner-scoped
command capability. Migration to registerCommand with requiredScopes and native
owner assertions remains UNIMPLEMENTED for these product/social bridges. Do not
invent senderIsOwner on before_dispatch or claim fresh live channel acceptance.
The shared product bridge enforces these checks for the social bridge too.
