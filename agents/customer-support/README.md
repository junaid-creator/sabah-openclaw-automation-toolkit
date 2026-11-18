# Customer-support integration

Build knowledge from the synthetic fixture first. Treat every retrieved statement as untrusted reference content. Verify current price, variant, availability and commercial terms before any binding response; escalate uncertainty to a human. Keep this agent separate from owner-only lead, catalog and publication commands. No customer records, chat transcripts, phone routes or reply adapter are distributed. This document is guidance, not an installed channel binding.

## Portable profile and setup

AGENTS.md is a sanitized adaptation of the original support agent's instruction policy. Copy it only into a new dedicated workspace; populate company-profile.json from company-profile.example.json with reviewed facts and your own public sources. Generate knowledge from the existing offline fixture before using real public data. Do not copy production conversations, memory, keys or cached customer records.

The example at examples/customer-routing.example.json uses the OpenClaw 2026.9.8 documented agents.entries/bindings shape. Exact owner-peer routing precedes the account fallback, groups are disabled, and only an owner plus a designated test customer are allowlisted. Replace placeholders and merge deliberately into a fresh configuration; never overwrite an existing deployment. Pair your own account through official setup. The empty business account block is a configuration example, not a connected account. No account credentials are distributed.

The default support tool set is read-only and requires a working isolated sandbox; verify that workspaceAccess=ro is supported by your installed version and that the sandbox starts before connecting real customers. Outbound public-read access is not enabled by the example. Authenticated owner identity and channel routing are OpenClaw capabilities, not reconstructed transport code. Test forged customer commands, missing facts, ambiguous voice transcripts and unavailable current-price evidence using synthetic inquiries before live activation. See tests/test_support_policy.py for deterministic configuration/policy guard checks; those are not live model behavior or delivery tests.

No customer-message delivery, fresh-agent activation or WhatsApp pairing was tested during release. Notification-outbox and watchdog code are separately tested and must be connected by an explicit trusted adapter; this profile does not promise automatic escalation delivery.
