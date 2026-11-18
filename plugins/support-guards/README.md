# Support admission guards — callable library, not an installed plugin

Requires Node 24 and its built-in node:sqlite. No npm dependencies or channel
registration. Source-derived from the original extensionless-state-directory
rate-limit and delivery guard modules omitted by the prior source scan.

- customerKey(channel, account, peer) creates an account-bound stable key from
  **trusted host metadata**, never customer-provided identity text.
- acceptInbound(privateDatabase, key, eventDigest, time, options) transactionally
  allows ten distinct messages per minute by default. Exact replay retains its
  original decision without consuming another slot. Reused event identity for a
  different customer and clock regression fail closed. Limits are configurable.
- setMode(database, key, HUMAN|AUTO) is an owner-only local integration API. It is
  NOT an authenticated command by itself: expose it only behind verified owner
  routing and exact scoped confirmation, never as a customer/model tool.
- authorizeAndHandoff(database, key, trustedTransportCallback) serializes the mode
  check with callback invocation. Missing/invalid/HUMAN modes block. The callback
  needs its own durable no-replay delivery ledger and permitted native sender.

A callback invocation is not delivery confirmation. Async handoff can finish
after HUMAN is set; mode changes cannot undo an already admitted in-flight send.
If a callback throws after sending, do not call it again merely because this guard
rolled back: reconcile the transport's durable receipt first. This module does
not supply the original complete customer inquiry/result/reply-recovery engine.

Both parent directory and database must be private/operator-owned. No production
paths, account IDs, customer messages or histories are included. Unlike the
reference seven-day deletion, the port keeps event tombstones indefinitely to
avoid re-admitting an old event; plan retention only with an independently safe
anti-replay horizon. Missing mode now fails closed rather than implicit AUTO.

Ten actual disposable-SQLite Node tests cover limits/replay, account isolation,
mode admission, callback exceptions, clocks and private state. No native channel,
customer send, policy config mutation or Gateway activation was performed. The
reference privileged support-control/config-patch service remains a separate
unported capability, not replaced by these callable admission functions.
