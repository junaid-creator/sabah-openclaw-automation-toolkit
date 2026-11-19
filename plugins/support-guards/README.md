# Support admission guards and native controls

Node 24 built-in SQLite; Python 3 standard library for optional watchdog ingestion.
No npm dependency, sender implementation, automatic installation or activation.
The exported plugin entry is pinned/tested against OpenClaw **2026.11.5**.

## Native integration

`index.mjs` exports a real SDK plugin. `native.mjs:registerNative` registers:

- `/supportctl STATUS customer-alias` and revision-bound
  `HUMAN|AUTO|RESUME customer-alias revision request-id` commands;
- `message_sending` cancellation for configured support routes unless AUTO;
- optional `api.agent.events.registerAgentEventSubscription` feeding the real
  `toolkit.watchdog ingest-runtime` CLI with bounded metadata.

Native owner authorization, account/channel/from/to/agent/session matching and
independent support exclusion are required. No model tool is registered. A
customer alias only selects an existing operator-configured route. Missing mode
or incomplete support route metadata blocks sending. RESUME never replays replies.
A stale command cannot undo a later mode change. Read STATUS for the actual
revision; each write needs a unique 16–64 character request ID.

See [native-control-recovery](../../docs/native-control-recovery.md) for inspected
SDK declarations, tests, limits and deployment acceptance requirements. Historical
global send-policy config mutation is NOT implemented: the SDK offers only prefix
rules, not exact account/session matching. Existing operator policy is untouched.
The exact send hook is a bounded alternative, not universal config-policy parity.

Example plugin configuration (all routes/paths are illustrative and must be
replaced using verified native metadata; create a private 0700 state directory):

```json
{
  "database": "/private/toolkit/support.sqlite3",
  "supportAgentIds": ["support"],
  "owners": [{
    "channel": "telegram", "account": "owner-account",
    "sender": "OWNER_ID", "from": "OWNER_ID", "to": "BOT_ID",
    "agent": "main",
    "sessionKey": "agent:main:telegram:owner-account:direct:OWNER_ID"
  }],
  "customers": [{
    "name": "customer-one", "channel": "telegram", "account": "support-account",
    "peer": "CUSTOMER_ID", "agent": "support",
    "sessionKey": "agent:support:telegram:support-account:direct:CUSTOMER_ID"
  }],
  "watchdog": {
    "python": "/usr/bin/python3", "checkout": "/opt/automation-toolkit",
    "database": "/private/toolkit/watchdog.sqlite3", "allowedAgentIds": ["main"]
  }
}
```

Do not guess the session-key syntax from this example. The owner command requires
an actual private owner session, native owner assertion and exact raw route values.
Owner/support accounts must be distinct. Unconfigured destinations on a support
account are denied, so enrollment and exact route acceptance precede activation.
Omit `watchdog` to disable ingestion. All tables are additive; nothing prunes
receipt tombstones automatically.

## Callable library retained

- `customerKey(channel, account, peer)` binds trusted route metadata.
- `acceptInbound(database, key, eventDigest, time, options)` retains its
  transactional ten-distinct-messages-per-minute default and replay decision.
  Reused event identity for another customer and clock regression fail closed.
  This rate limiter is a library, not a newly registered native ingress hook.
- `setMode(database, key, HUMAN|AUTO)` remains a privileged **local** API,
  not authenticated by itself. Never expose it as a customer/model tool.
- `getMode` returns current mode and revision; `applyControl` performs
  revision-checked control and durable command deduplication behind native auth.
- `authorizeAndHandoff(database, key, trustedTransportCallback)` remains a
  local admission helper. Its callback needs its own durable delivery ledger.

Parent directory and database must be private and operator-owned. Callback or
native-hook admission is not delivery confirmation. In-flight sends cannot be
recalled by HUMAN. Unknown transport outcome must be reconciled, never retried
because a guard callback threw. Native transports that bypass the inspected send
hook are not protected; disabling this plugin removes its admission boundary.
No customer inquiry/result/reply-recovery engine or external alert dispatcher is
claimed by this package.
