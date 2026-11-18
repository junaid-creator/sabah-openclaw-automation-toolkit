# Independent alert-only Gateway monitor

This is an executable one-tick service adapter, not a restarted Gateway or an
installed schedule. The source reference is the original independent monitor;
no production bot, recipient, service identifier, or private configuration is copied.

## Offline first

Run tests/test_gateway_monitor.py with unittest. Seventeen tests use disposable
SQLite state and mocked HTTP/transport. No outage, test message or service restart
is required. State keeps incidents, ticks and notice receipts separately.

Copy examples/gateway-monitor.json to a private operator-owned configuration
file and replace ALL placeholders. Configure two explicitly trusted endpoints,
a private state directory, a maintenance marker, expected source hashes, and an
independently verified Telegram owner destination. Supply the bot credential via
the named environment variable in a protected service environment file. Never
put it in command arguments, logs or the repository. The implementation does not
read or modify OpenClaw configuration or reuse Gateway credentials implicitly.

Read-only health tick (explicit opt-in to health network):

    python -m toolkit.gateway_monitor --config /private/monitor.json --enable-network

After separate owner authorization for alerts, add --enable-alerts. The optional
Telegram adapter uses the official Bot API directly to remain independent of the
Gateway. Operators must ensure that this transport is permitted in their hosting
policy; where forbidden, do not activate it. A tool-only host must use its permitted
transport and cannot claim independent outage alerting through the failed Gateway.

## State and safety

Startup grace and repeated failures gate an incident. Healthy resets failures;
maintenance or failed/missing integrity evidence suppresses outage AND recovery
sends. An ended unsent outage becomes STALE. Only a confirmed outage can produce
one recovery notice. SENDING is committed before handoff, UNKNOWN/SENDING is never
automatically resent. API receipt verifies the configured recipient and message ID,
not handset display. New incidents retain old receipts. No restart/stop, queue
replay, business write, credential refresh or service management command exists.

The original optional systemd ActiveState probe is replaced by explicit HTTP
health/readiness endpoints. HTTP 200 object response is availability evidence,
not model/channel/business readiness; configure suitable endpoints. Integrity
hashes must be updated only after a separately reviewed deployment. Health
configuration is trusted operator input, never a customer URL. Limit state access
to the service user; archive historical tick rows under separately authorized
maintenance (no automatic destructive retention is enabled).

## Optional service deployment — NOT performed

Templates in examples/services are inert text. Replace the checkout, interpreter,
config and environment paths; inspect existing user units and merge without
replacing unrelated services. Run systemd-analyze --user verify on staged unit
files; review timer frequency, failure behavior and environment protections.
Copy/enable only with explicit scheduling/notification authorization. Keep the
monitor and integrity stop policy independent. A fresh-host systemd invocation,
real failure/recovery, approved owner test send, reboot and natural timer run are
NOT TESTED in this release. A timer definition is not an execution receipt.

Rollback disables/removes only the explicitly installed monitor timer/service;
retain state and remote receipt evidence. It never changes the Gateway or business
schedulers. Local alert tests do not prove off-server disaster recovery.
