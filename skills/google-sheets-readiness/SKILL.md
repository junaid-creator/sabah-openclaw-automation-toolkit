---
name: google-sheets-readiness
description: Verify Google Sheets read access, worksheet names and edit-permission evidence through an existing GOG integration, including when the Drive API is unavailable.
---

# Google Sheets readiness

1. Read the relevant installed integration skill. Use its configured execution host and existing GOG account; do not substitute credentials or bypass an execution denial. For a read-only test, do not run synchronization or health helpers until their effects are understood.
2. Prefer a spreadsheet ID already supplied by the user or explicitly defined in the integration helper. Read only the relevant identifier from the documented helper source; do not inspect credential files or environment dumps. This avoids a separate Drive title-search dependency.
3. Run `gog sheets metadata <spreadsheetId> --json --no-input`. Confirm the returned spreadsheet title matches the requested target and report worksheet names from `sheets[].properties.title`. Check each requested spreadsheet independently.
4. If Drive search reports that the Drive API is disabled, this does not establish that Sheets is inaccessible. Use the known ID with Sheets metadata instead; this recovery has succeeded with the existing GOG account. Do not enable APIs, reauthorize, or change configuration merely to perform title discovery. If no ID is available from the documented integration, request the spreadsheet URL or ID.
5. When edit readiness is requested, inspect `gog auth list --json --no-input` for the existing account’s scopes, then request file-specific evidence with `gog drive get <spreadsheetId> --fields='id,name,capabilities(canEdit)' --json --no-input`. A Sheets write scope establishes OAuth scope only, not the account’s edit role on this file. A returned `canEdit` establishes permission evidence, not a successful Sheets write. If Drive is disabled, keep the successful Sheets read result and mark file-specific edit permission unverified; do not reauthorize or enable an API for this read-only audit. This failure has been observed alongside successful Sheets reads and an existing write scope.
6. Report read access, edit-permission evidence and actual write/readback testing separately. For a read-only request, do not write test rows, update logs, or trigger production workflows. If operational write verification is required later, propose an explicitly authorized write/readback/restore test in a designated unused cell; do not perform it as part of permission discovery. Metadata, scopes and permission evidence alone do not establish full automation readiness.

## Portable release contract

Read [README.md](README.md) before activation. This is a procedural OpenClaw skill, not a configured CMS/Google account or an autonomous service. Use only current operator-authorized tools and targets. Static package checks and synthetic preservation/gate tests do not establish live permissions, browser behavior or restore success.
