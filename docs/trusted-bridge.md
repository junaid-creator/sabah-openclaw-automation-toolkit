# Trusted bridge contract

This original application-level module addresses a narrow missing orchestration boundary. It is **not** a native OpenClaw endpoint/plugin and does not authenticate a Telegram webhook or WhatsApp connection by itself.

## Trust and installation

Install the normal toolkit dependencies and import toolkit.trusted_bridge.Bridge. Pass a private SQLite path, at least 32 independent random key bytes, exact routes (channel/account/peer/role), and optionally an injected clock. Store the key outside the model, customer workspace and repository. Keep the database directory private (0700), database permissions restrictive, and use one local host. Rotate a key through your own adapter maintenance process, not by chat request.

A separately implemented, reviewed ingress adapter must verify the actual channel sender/account and direct-chat status, construct a unique transport event ID, timestamp and text, then HMAC-SHA256 the canonical JSON with that key. The event fields are exactly id, channel, account, peer, kind, timestamp, text. Never sign a customer-provided JSON envelope or derive the role from text. The native OpenClaw-to-this-contract adapter remains missing.

## Owner operations

challenge(event, signature, binding, review_receipt=...) requires an owner route and a trusted delivered review matching the immutable binding digest and destination. It returns one CONFIRM challenge. confirm accepts only that exact signed owner confirmation, with a 300-second maximum challenge lifetime. Identical receipt replay is idempotent; another confirmation is rejected. The binding should include operation/job, targets, media byte hashes, captions, schedule and account as appropriate. No operation is executed by confirming.

The downstream executor must call authorized(challenge_id, exact_binding) immediately before side effects, and use its existing durable publication ledger for no-replay behavior. revoke requires an exact owner command and prevents future authorization. There is no atomic transaction spanning revocation and a remote HTTP call: serialize admission in the trusted executor and check revocation again before each phase. Already performed remote operations cannot be undone by local revocation. This library is not a replacement for the integrated social recovery engine.

## Support replies

prepare_reply accepts only a customer route and a proposal with action=reply and bounded text. A mandatory operator-owned semantic policy callback must enforce the supplied support profile. An always-true callback is used only in transport unit fixtures, not a production policy. This module enforces structural boundaries; it cannot guarantee an LLM's truthfulness, pricing, privacy or language behavior.

The destination is derived exclusively from authenticated ingress, never from the proposal. deliver is disabled by default. An authorized sender callback must return delivered=true, nonempty message_id and exact channel/account/peer. Only those safe receipt fields are saved. Missing/wrong receipts or exceptions become UNKNOWN; a process crash retains SENDING. Neither is automatically resent. Inspect independently obtained transport evidence and escalate for manual reconciliation; there is intentionally no unsafe reset/retry API. SENT is durable and duplicate delivery calls never invoke the sender again.

See tests/test_trusted_bridge.py for executable synthetic examples and denied-network tests. No native sender or policy model is installed. This advances notification/support/owner boundary coverage while those overall capabilities remain PARTIAL.
