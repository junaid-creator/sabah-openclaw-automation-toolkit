---
name: gateway-outage-reliability-audit
description: Audit an OpenClaw Gateway outage and handover readiness; for separately authorized backup and independent alert changes, verify restore and notification boundaries without altering business workflows.
---

# Gateway outage reliability audit

## Portable installation boundary

Read [README.md](README.md) before executing this procedure. The authored
reference workflow below describes diagnostic evidence and safety gates.
Reference script names, table names, job prefixes and state paths are schema
examples, NOT commands shipped or activated by installing this skill. Map them
to the configured deployment first. Missing adapters are blockers; do not invent
commands or bypass authorization. This package is a procedural skill, not the
complete underlying engine.


Use for a requested Gateway outage postmortem or round-the-clock handover audit. Audit alone does not authorize restart, replay, notification drain, timer changes or production restore. When the owner separately authorizes a recovery snapshot or independent outage alert, read [authorized readiness changes](authorized-readiness-changes.md) before implementation. For application approval/transport wiring use [automation adapter verification](../automation-adapter-verification/SKILL.md); for platform publication uncertainty use [publication recovery](../multi-platform-publication-recovery/SKILL.md).

1. Establish UTC audit time, host/user and bounded outage interval. Inspect systemctl --user show and cat for the actual Gateway unit and drop-ins, plus user lingering, local listener, openclaw gateway status --deep, openclaw config validate and named-channel probes. Check current service start time against the outage window. Read openclaw doctor --lint, not mutating doctor variants; report security findings separately from outage causality. Never display environment files or credentials.
2. Read bounded user/system journals around the first stop and next start. Distinguish explicit systemd Stopping/SIGTERM from crash, OOM and restart-loop evidence. Restart=always does **not** restart a unit after an explicit systemd stop; an enabled unit and lingering user likewise do not prove unattended recovery. Quantify downtime from the journal, then check drain timeout, unfinished work and memory-pressure diagnostics without promoting temporal correlation to cause. The stop initiator remains unknown unless caller-attributed audit/sudo/service-management records identify it; lack of access to system-level logs is an evidence limit, not a guess about the caller. A guard-watch unit with a stop branch is not the cause when its contemporaneous run reported integrity OK.
3. Compare scheduled time, enabled job definition, scheduler **run receipts**, observer records and downstream result for each missed interval. A later catch-up run is not the on-time run. A scheduler ok or terminal success can mean the agent correctly stopped at a business validation blocker; verify the actual WordPress/public result, append-only ledger and relevant Sheet rows independently before saying content was published. Preserve date and approval gates; never trigger a historical content run merely to test availability.
4. For owner summaries and application notices, join the event key to per-channel claims, attempts and stored messaging receipts. Distinguish queued/pending, failed, sent-with-message-ID and unknown; a connected channel now does not establish delivery during an outage. A watchdog may detect Gateway unavailability yet be unable to notify through that same Gateway. Do not resend failed or uncertain notices during diagnosis; reconcile transport ownership and stale-event policy first. For lifecycle/digest-specific repair read [lifecycle notification repair](../automation-adapter-verification/lifecycle-notifications.md).
5. Inspect relevant user **and** system timers and their actual ExecStart/selectors; active timers do not prove a missing cron trigger ran or that business work succeeded. For backup readiness, identify the named backup job/repository and its latest dated receipt, scope, integrity check and isolated restore proof. Local component snapshots or package-manager backups are not a restorable Gateway/workspace backup. If the reported failed attempt cannot be matched to a log/receipt, say so rather than inventing its error. Keep an undeployed candidate or on-disk hash separate from running plugin generation and observed inbound behavior.

For a read-only audit, report current health, cause versus unknown initiator, exact downtime, per-date scheduled versus business result, per-channel notice state, backup/restore proof and remaining readiness gates separately. Prove the current state with the smallest read-only probe; state that no repair, replay, migration or test send was performed. Independent outage alerts and any restart design require separate authorization and must preserve deliberate maintenance/integrity stops.
