# Executable startup integrity fence

`toolkit.startup_fence` composes the recovered hash/plugin/database gate with
OpenClaw 2026.11.5 `plugins list --json`. It uses an absolute Node executable and
entry point, an allowlisted environment, explicit HOME/state/config paths, a
30-second CLI timeout, and no shell. Only enabled, loaded discovery records with
exact hashed source paths satisfy the attestation. Disabled/error/duplicate
records, changed bytes, missing/private-invalid databases and schema mismatches
fail closed. CLI errors are not converted into success.

Run on a separately authorized target:

```sh
python -m toolkit.startup_fence --config /absolute/private/fence.json
```

The private JSON has exactly `runtime` and `integrity`. Runtime fields are `node`,
`entry`, `home`, `state`, `config`, all absolute paths; HOME/state must be private
owned directories. Integrity fields are `sha256` (absolute path to SHA-256 map),
`plugins` (`id`, `source` records), and `databases` (`path`, `tables`, where each
table maps to required column names). Configuration must be mode 0600. Build the
manifest from independently reviewed release artifacts, not from an untrusted
current installation. Include all coupled guard files, not just the entry point.

Exit 0 means these bounded checks passed; failure exits nonzero (normally 78).
An operator can use the command as an `ExecStartPre` in a reviewed service drop-in.
This release does not install that drop-in, restart/stop anything, or replace
existing service configuration. Native CLI discovery can maintain its own local
cache; the fence does not edit the configuration or the checked application DBs.

Tests exercise actual temporary SQLite schemas, subprocess CLI failure, source
changes, native-metadata mismatches, disabled records, timeout and private-state
negatives. The disposable runtime discovers the existing owner bridges disabled;
it is deliberately not represented as successful active-guard acceptance. A
loaded CLI record also does not prove that a running Gateway invoked the hook.
Native service prestart/stop-policy acceptance remains separate target work.
