# Private recovery snapshots

Executable implementation of the original outage-readiness snapshot procedure.
No automatic discovery, scheduler, live restore, Gateway boot or SaaS backup.
Never commit snapshots: they can contain credentials and private application data.

Create a private destination parent and an explicit reviewed allowlist using
examples/recovery-allowlist.json. Each source must be an owned non-writable-by-
others regular file; symlink/traversal inputs are rejected. Use source kind sqlite
for active SQLite databases so the online backup API includes committed WAL data.
Do not copy an active SQLite file as kind=file. The isolated database copy uses
DELETE journal mode; the source journal mode is not changed.

    python -m toolkit.recovery_snapshot snapshot --allowlist /private/allowlist.json --destination /private/new-snapshot
    python -m toolkit.recovery_snapshot restore-copy --snapshot /private/new-snapshot --destination /private/new-restore-rehearsal

Both destinations must not exist; no path is restored over live state. Every
snapshot file is private, hash/size-bound and recorded under a logical name.
Manifest records original modes for review but restore-copy stays mode 0600.
Copy validation checks every hash and SQLite integrity. Regular files and restored
snapshot objects are bounded to 100 MiB; larger database restores need a separately
reviewed streaming implementation. Missing/inaccessible files abort the entire
candidate rather than silently declaring a complete backup.

Eight synthetic tests cover active WAL, actual restored SQL query, hashes,
permissions, corruption, invalid database, path tampering and destination refusal.
These are safe fresh temporary-directory acceptance for THIS utility only.
Cross-file transaction consistency, an isolated Gateway boot, off-host restoration,
encryption/key custody and disaster recovery are NOT TESTED. Snapshot scope must
include separately reviewed uploads, config, source, state and service definitions;
remote accounts are not recreated from a local file backup.
