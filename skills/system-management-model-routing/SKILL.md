---
name: system-management-model-routing
description: Diagnose OpenClaw system-management inference failures when ordinary chat works, especially stale agent model overrides and fallback behavior that differs from the current session.
---

# System-management model routing

Use when a management consult reports provider auth, billing or availability failure despite a working chat or global default. This is a routing diagnosis, not proof that provider funding or new credentials are necessary.

1. Gather the selection layers together using scoped config reads and status: global `agents.defaults.model`, requester `agents.entries.<id>.model`, current session override, utility/subagent overrides and resolved system-agent owner. Inspect relevant cron payload models only if that execution surface is failing. Record selected model versus configured primary separately; do not print auth values. A global-default status display alone can conceal an overriding agent primary.
2. Read installed model/system-agent documentation before changing routing. A delegated system consult can retain the requesting agent as owner and use its configured route rather than the caller session's model override. Utility/title routing is a separate purpose; do not set a utility model assuming it repairs the management route.
3. If the advertised fallback does not run, inspect the installed management admission call and its inference-fallback implementation. The observed implementation without route-policy expansion enumerated configured agent routes, not that agent's `model.fallbacks` list. With one agent pinned to the failed provider, another provider working in a session did not rescue the consult. Verify this against the current version; do not generalize it to ordinary chat fallback or assume every configured provider is a candidate.
4. If a stale agent override is proven and the owner authorizes global inheritance, request removal of only that override through the supported management tool. Preserve global primary/fallback choices and auth; back up affected config privately and inspect the exact schema reload requirement. Removing a stale pin avoids replacing it with another workflow-specific provider dependency. Do not add unverified fallbacks or require a second provider merely for this repair.
5. If the management tool fails before starting and exposes no usable model override, distinguish a bootstrap limitation from an application dependency. Do not edit Gateway config through shell or direct RPC as a workaround. After reconciling that no change applied, provide one documented operator action for the proven key, such as `openclaw config unset agents.entries.<id>.model`, under the correct runtime user/profile. Do not ask for credits on the wrong route or repeatedly invoke the same failed consult while waiting for an unchanged prerequisite.
6. After the authorized change, read back effective selection, validate config and perform a harmless management consult. Schema `reloadKind: hot` supports a no-restart expectation, not proof that reload occurred. Record routing diagnosis, configuration application, hot reload and successful management inference as separate results. A backup or suggested command is not a completed recovery.

Completion evidence: global/agent/session route comparison, installed fallback semantics, exact applied change or bootstrap blocker, private backup metadata, and a successful harmless consult on the intended route. This procedure does not establish that application schedulers, publication workers or notification delivery are model-independent; inspect those adapters separately with the separately installed automation-adapter-verification skill (not included in this batch).

## Portable release contract

Read [README.md](README.md) for installation, synthetic evidence checks and limits. This procedure grants no configuration or device-approval authority. Live deployment, pairing and management inference are NOT TESTED in this release.
