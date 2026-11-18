---
name: supplied-image-intake
description: Diagnose rejected owner-supplied SMGC images and recover canonical draft intake while preserving originals, import hashes and existing request identity.
---

# Supplied image intake

## Portable installation boundary

Read [README.md](README.md) before executing this procedure. The authored
reference workflow below describes diagnostic evidence and safety gates.
Reference script names, table names, job prefixes and state paths are schema
examples, NOT commands shipped or activated by installing this skill. Map them
to the configured deployment first. Missing adapters are blockers; do not invent
commands or bypass authorization. This package is a procedural skill, not the
complete underlying engine.


Use for an actual attached image rejected before draft preparation, or resuming its saved import after transient staging cleanup. This is distinct from generated-image task recovery and post-publication reconciliation. Inspection does not authorize expanding trusted roots, uploading private media or publishing.

1. Recover the genuine attachment path and request identity from trusted inbound metadata using bounded session APIs. Inspect the current importer and canonical controller before creating a job. Compare the resolved path, runtime UID, ownership/mode, size, detected MIME and decoded dimensions together. In the verified reference-workflow recovery, the attachment was readable and private but lived under `<configured-inbound-root>/openclaw-staged-<UUID>/input-<filename>`; the importer accepted only `<configured-media-root>/`. A path mismatch is not a permissions or credential failure. Do not copy the file into an allowed root to evade the boundary.
2. If a scoped importer repair is authorized, back up the affected source and admit only the evidenced staging shape, retaining the legacy root. Reject symlink/traversal paths, arbitrary workspace files, wrong-owner or group/world-writable files, nonregular files and empty/oversized input. Bound reads and detect source changes during copying; retain MIME, decode and dimension validation. Path eligibility is not owner authorization: independently verify the authenticated owner and the attachment association at the inbound boundary. A staging filename alone cannot grant publishing rights. Test outside paths, symlinks, wrong shape and invalid file properties before real intake.
3. Deduplicate against saved requests and the live queue using inbound request identity before calling `tools/sabah_whatsapp_draft.py REQUEST_JSON`. Use `media_mode=USE_IMAGE` with the genuine path, preserve the request file/ID on every retry, and inspect saved state after failure before acting again. For any existing approval/attempt or uncertain remote outcome, switch to [publication recovery](../multi-platform-publication-recovery/SKILL.md); local absence alone does not establish remote absence.
4. Preserve the original bytes under the job’s durable asset directory. Create only the required compatible derivative; do not regenerate, crop or redesign supplied artwork. Save source path, original/source SHA256, derivative SHA256, dimensions, MIME and conversion details. Persist the import hash/provenance in controller state, not only a temporary file. Visually inspect original and derivative before recording hash-bound supplied-image review. In the verified controller, missing `supplied-review.json` stopped reporting after the job, asset upload and content were already saved; writing the actual inspection evidence and rerunning the same request resumed that job rather than creating another.
5. Make source-cleanup recovery depend on the saved import proof: while the inbound source exists, compare it to the durable original. Once it is gone, require the original to match the hash persisted at import, then apply the unchanged derivative and semantic-review checks. Missing import proof, changed hash or stale review remains blocked. Test with a copied state pointing to a nonexistent source, then a wrong digest; do not delete the real attachment to test recovery. These checks prove local durable recovery, not future channel admission.
6. Complete preview delivery through [automation adapter verification](../automation-adapter-verification/SKILL.md): claim the exact invocation, call the actual messaging tool, record its raw receipt and validate the binding. Keep independent channel claims. A prepared image URL is not a social post URL, and a successful account preflight is not complete media compatibility or publishing proof. Preserve existing exact-reviewed-content approval controls; do not manufacture approval from the import or request ID.

Completion: one canonical request/job, unchanged durable original, verified derivative and supplied review, restart-safe import proof, actual preview receipts or a precise delivery blocker. Report real channel ingestion separately from synthetic staging-path tests. Roll back source files only; preserve live request state, assets and delivery/publication ledgers.
