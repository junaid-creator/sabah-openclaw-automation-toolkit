# Architecture

main assistant -> offline keyword/brief/metadata/language/lead/ledger modules

customer support -> website snapshot -> untrusted reference files -> human/live verification

reliability.Run -> private JSON checkpoints + process-local host filesystem lock -> caller-supplied reconcile/write functions

The reusable core is separate from credentials, browser sessions, service timers, publication engines and owner routes. Run.write records attempts before invoking a callback; uncertain outcomes latch for review instead of blind retry. It allows at most two writes after authoritative absence checks, not globally exactly-once delivery.

Source mappings and hashes are in PROVENANCE.json. The inventory includes discovered but excluded deployment components; it does not include their private source or settings.
