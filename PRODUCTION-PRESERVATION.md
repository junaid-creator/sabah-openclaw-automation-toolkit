> Recovery update: [2026-11-19 release](docs/recovery-release.md) and [current evidence](docs/recovery-acceptance.json) supersede older test counts and native-install claims below. Coverage remains partial.

# Final bounded production preservation

This final readback supersedes any interpretation of earlier successful source
checks as proof that every production source stayed unchanged for the whole task.

- Earlier comparison: 248/248 source/config/service files matched that snapshot.
- Final expanded comparison: **391/393 matched; two source files drifted**.
- Drifted sources: tools/sabah_social_render_catalog.py and
  assets/smgc/templates/catalog.css (logical main-workspace paths).
- Before/after hashes are in docs/production-preservation.json. Attribution is
  **UNVERIFIED**. Neither file was restored or overwritten to hide the drift.
- The release is based on the recorded source versions; later production changes
  were not silently incorporated or claimed to be reproduced.
- This release task performed no production source/config/service writes,
  Gateway/agent restarts, credential/OAuth changes, scheduling changes, live
  business posts, customer messages or paid API starts. Its writes were isolated
  release/test artifacts and approved source-upload staging.
- Gateway process/start evidence was unchanged during the bounded readback.
  Business state and other concurrent activity were not frozen.

The seven read-access limits in the capability audit remain distinct: four
historical files and three system deployment unit/drop-in files could not be
read. The complete master task remains PARTIALLY PORTED, not an exhaustive or
unchanged-production certification.


## Continuation comparison

The continuation rehashed 388 registered source/configuration files and compared
Gateway PID/start/restart metadata. See [current bounded evidence](docs/final-production-preservation.json).
The two prior source drifts match a separately recorded Template 5 deployment;
this release neither edited nor reverted them. Business runtime state was not frozen.
