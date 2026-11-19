# Native control and watchdog recovery (2026-11-19)

## Scope and checkpoint

Bounded staged implementation, based on the saved `docs/complete-capability-audit.json`
records `customer-support-control` and `watchdog`. No production config,
plugin installation, messaging, API call, scheduler, commit or push was performed.
Existing unrelated uncommitted changes were preserved.

Implemented exported paths:

- `plugins/support-guards/index.mjs` uses the real
  `openclaw/plugin-sdk/plugin-entry` export `definePluginEntry`.
- `native.mjs:registerNative` registers `/supportctl`, a
  `message_sending` cancellation hook and, when explicitly configured, a
  lifecycle-owned `api.agent.events.registerAgentEventSubscription`.
- `guards.mjs:applyControl/getMode` supply private SQLite revision/CAS and
  retained command-replay receipts. Existing guard functions remain available.
- `toolkit.watchdog.ingest_runtime` and the `ingest-runtime` CLI ingest
  bounded SDK metadata into the existing watchdog database. The plugin invokes
  the actual Python module, not an operator-provided generic callback.

## Inspected host contract

Read-only reference was OpenClaw **2026.11.5**. Relevant shipped declarations:

- `dist/config-contracts-DRtc9ppD.d.ts`:
  `AgentEventPayload` (runId, seq, ts, stream, sessionKey, sessionId, agentId),
  `PluginCommandContext`, `OpenClawPluginCommandDefinition`,
  `PluginHookMessageContext`, `PluginHookMessageSendingResult`,
  `PluginAgentEventSubscriptionRegistration` and `OpenClawPluginAgentEventsApi`.
- `dist/plugin-command-execution-BG0eMxYe.mjs` and
  `dist/command-registry-state-C89NQ2zC.mjs`: nonempty `requiredScopes`
  both enforce core owner/admin scope admission and expose `senderIsOwner`;
  admitted owner contexts receive an invocation-bound `assertOwnerCurrent`.
  No nonexistent `ownerOnly` registration flag is used.
- `dist/runtime-D4KVL32s.mjs`: metadata subscriptions clone routing fields
  and primitive data fields; subscriptions belong to host plugin lifecycle.
- `dist/agent-run-terminal-outcome-CurjWZiA.mjs`: lifecycle end is terminal;
  generic attempt errors can precede fallback; `executionSettled` and
  `fallbackExhaustedFailure` identify settled failures.
- `docs/plugins/hooks.md` and `docs/plugins/sdk-channel-inbound.md`:
  `message_sending` can cancel native sends, but not every legacy adapter
  promises every hook; in-flight sends and custom direct transports are distinct.
- `docs/plugins/sdk-runtime/state-and-system.md` documents transactional
  `api.runtime.config.mutateConfigFile`; it DOES exist. We do not claim that
  config mutation is absent.

## Authenticated support control

Explicit operator configuration is required. Every owner route binds channel,
account, sender, raw from/to, owner agent and **exact private session key**.
Populate these from verified host routing, not message content. No wildcard,
normalization guess, inferred owner or default account is supported. The operator
must verify that each configured owner session is a private/direct conversation.
Threads are refused. One account cannot serve both owner control and support.

Core registration requests `requireAuth: true` and
`requiredScopes: ["operator.admin"]`. The handler independently requires
`isAuthorizedSender === true`, `senderIsOwner === true`, a native
`assertOwnerCurrent` function and all configured route facts. It calls the
assertion immediately before synchronous local state work. An administrator who
is not the configured owner is refused. Support-agent IDs are independently
excluded even if another identity check is accidentally permissive. Neither a
customer nor a model tool can submit a control envelope through this plugin.

Commands (customer is an operator-defined alias, not arbitrary destination text):

```text
/supportctl STATUS customer-one
/supportctl HUMAN customer-one 0 unique-request-0001
/supportctl AUTO customer-one 1 unique-request-0002
/supportctl RESUME customer-one 2 unique-request-0003
```

Use the actual revision returned by STATUS, not these illustrative numbers.
HUMAN/AUTO/RESUME require a unique 16–64 character request ID and an exact current
revision. RESUME is AUTO admission only: it does not replay any queued reply.
Reusing an ID with changed content fails; exact replay returns the original
receipt plus the current mode and never re-applies an old AUTO after a later HUMAN.
Local legacy `setMode` changes also advance the mode-event revision.

The registered send hook recognizes configured support accounts, support-agent
sessions and configured support destinations. It requires an exact
channel/account/recipient/session tuple, and an explicit AUTO state. HUMAN,
missing mode, missing route facts and state read failures cancel. Unrelated
fully identified routes are left alone. Unknown destinations on support accounts
are blocked, not automatically enrolled. It is not a send implementation, cannot
undo admitted/in-flight sends and does not attest delivery.

### Config merge limitation, not an invented API

The inspected `session.sendPolicy.rules[].match` schema only has
`channel`, `chatType`, `keyPrefix` and `rawKeyPrefix`. It has no exact
session-key match, account-ID predicate or plugin-owned rule ID. Blindly adding a
raw prefix and later deleting it could affect sibling sessions or remove an
operator's identical deny rule. Therefore this bounded port uses an exact native
send hook and **does not implement the historical global config-patch workflow**.
It preserves all pre-existing native send-policy configuration and never removes
another deny; AUTO only removes this plugin's local HUMAN restriction. Exact
config-policy parity remains engineering work if that historical behavior is
required. A protected deployed hook and transport-path acceptance are still
required; disabling this plugin removes its guard.

## Watchdog ingestion

Optional watchdog configuration pins an absolute Python executable, checkout and
private database plus explicit allowed agent IDs. Support IDs cannot be added to
this owner-workflow watcher. It subscribes to lifecycle and tool metadata, ignores
all tool phases except end, and strips messages, tool arguments/results and raw
error text before spawning Python (no shell, fixed module/arguments, minimal
environment, five-second timeout, 64-KiB process-output cap, 16-KiB input cap).

Python validates agent/session agreement, run ID, session incarnation, sequence,
producer timestamp and event age. Native start/activity/terminal updates and
receipt insertion share one immediate SQLite transaction. Retained `(runId,seq)`
receipts deduplicate replay and reject changed identities. Run tombstones,
sequence/time checks, and current-execution matching prevent an old terminal
from finishing a newer execution. A newer start supersedes monitoring of the
prior run; it never retries the prior business operation. Unknown/missing start
and expired events do not fabricate tasks. Existing state is additive.

An unsettled generic error is activity, not whole-task failure. Settled error or
fallback exhaustion fails the run. Tool completion never completes the run.
Lifecycle end marks runtime execution completed, explicitly **not verified
business success or message delivery**. Events/alerts use RUNTIME_STARTED,
RUNTIME_ACTIVITY, RUNTIME_ENDED, RUNTIME_FAILED and RUNTIME_SUPERSEDED semantics.
No arbitrary result-watcher or external alert delivery daemon is supplied here.

The SDK subscription is live, not a durable event-log replay API. Events before
plugin activation or during ingestion failure are not backfilled. Failed child
execution is logged without a blind retry; operator reconciliation is required.
A runtime crash can leave a task running until the existing stall scan. Session
reset without a subsequent observed new start cannot be independently inferred
from these lifecycle events; the host's current-generation event admission remains
part of the trust boundary. Missing sessionId is rejected, not guessed. Typed
provider quota/rate-limit classification beyond inspected lifecycle facts remains
outside this bounded implementation.

## Offline acceptance and what it does not prove

Exact suites:

```sh
python3 -m unittest tests.test_watchdog tests.test_watchdog_ingestion -v
node --test tests/test_support_guards.mjs
OPENCLAW_NATIVE_SDK=/absolute/path/to/openclaw-2026.11.5 python3 -m unittest tests.test_support_control -v
```

20 Python watchdog tests, 21 Node guard/assembled tests and one actual SDK-entry
smoke passed on the final checkpoint; all exit 0 with no timeouts. The native
smoke copies the staged plugin into a disposable directory, imports the real SDK
through a read-only package link, registers on an assembled API, and exercises
owner controls and cancellation against real SQLite. The assembled subscription
test invokes the real Python CLI and verifies durable duplicate and terminal
outcomes. Neither test activates a Gateway or exercises real chat traffic.

Private command/stdout/stderr/exit/timeout receipts are in the adjacent
`recovery-native/` directory, not published here. Final receipts and source
hashes are recorded separately after the final rerun. Live scope/route mapping,
hook behavior for each deployed transport and alert delivery remain **LIVE
ACCEPTANCE REQUIRED**. Do not relabel these capabilities universally verified.
