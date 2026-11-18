# Complete capability audit — PARTIALLY PORTED

**This report does not declare the master task complete.** The requested scope is exhaustive; this evidence is bounded and the deeper trace is unfinished. Existing public content/history is preserved.

## Counts and meaning

~~~json
{
  "previous_discovery_records": 460,
  "previous_original_groups": 42,
  "initial_fresh_scan_entries": 394,
  "targeted_renderer_source_additions": 5,
  "fresh_source_entries": 399,
  "new_hashed_source_entries": 147,
  "new_local_original_candidate_sources": 52,
  "bounded_original_capability_groups": 51,
  "additional_original_groups": 9,
  "original_publishable_skill_packages": 22,
  "original_skill_packages_present": 22,
  "total_repository_skill_packages": 24,
  "python_runtime_modules": 45,
  "original_group_status_counts": {
    "PARTIALLY PORTED": 42,
    "MISSING IMPLEMENTATION": 4,
    "VERIFIED AND PORTABLE": 5
  },
  "original_non_skill_groups_with_executable_release_paths": 25,
  "fresh_live_external_workflows_accepted": 0,
  "audit_is_exhaustive": false,
  "access_denied_paths": 7,
  "system_service_access_denials": 3,
  "status": "PARTIALLY PORTED",
  "evidence_limit": "Bounded fresh scan plus preserved 460 mappings. Deep tracing timed out; three system service definitions/drop-ins and four historical copies were access-denied; deeper native/dynamic traces and fresh-host integration remain unverified. Files/groups are different units."
}
~~~

The old 460 records were discovery rows, not 460 capabilities. All mappings remain in the machine register. The fresh scan adds source identities, including PHP, extensionless executables, native state-directory guards, plugin manifests and system-level triggers. Nine new original behavior/procedure groups are separated without counting their tests/resources as capabilities.

## Previously omitted behaviors

- **skill:public-toolkit-release**: Source audit, provenance, isolated packaging, CI/security and exact public-tree reconciliation. Native tools and GitHub account required; procedural package, fresh-host execution NOT TESTED.
- **local-speech-recognition**: Bounded local FFmpeg to sherpa-onnx transcription. Executable adapter and synthetic subprocess tests; actual model/license/accuracy/native attachment acceptance NOT TESTED.
- **local-voice-synthesis**: Explicit profile/script Piper speech synthesis. No model or voice redistributed. Actual model quality/licensing, native voice reply and audio/text priority NOT TESTED.
- **voice-runtime-control**: Persist voice mode, configure native audio/TTS, compare model variants. Original scripts mutate Gateway/account/runtime configuration and depend on separately installed model/binary assets. No portable validated control/deployment adapter; no configuration changes authorized by this release.
- **customer-support-control**: Per-customer handoff mode and scoped native send-policy control. Local mode state is executable. Original authenticated owner command/config-patch integration and exact native send-policy merge are not ported or fresh-host validated.
- **integrity-guard**: Hash/package-source/database guard before Gateway startup. Generic manifest checks exist. Native plugin source attestation, exact DB schemas, startup fencing and deliberate stop-policy service adapter remain unported; no stop/restart behavior added.
- **native-rate-limit**: Durable account-scoped ten-per-minute admission and replay decisions. Actual disposable SQLite tests pass. Callable library only, not activated native interception. Retains tombstones rather than original seven-day deletion.
- **native-delivery-guard**: Serialize HUMAN/AUTO mode check with transport invocation. Callable admission guard verified with SQLite; no delivery guarantee or native transport activation. Missing mode fails closed; callback needs its own durable receipt ledger.
- **customer-reply-runtime-recovery**: Durable inbound turn, timeout, final-result lookup and reply reconciliation. Existing portable outboxes/attestation do not port the native final-result/transcript lookup and per-inquiry runtime recovery. Native source coupling and privacy boundary require separate adaptation and tests.

## Product-management finding

The original workflow was not a generic WordPress client. Its authenticated command hook called a durable row/source-bound engine, exact plan approval, WP-CLI/Woo setters, protected SQL backup, formula/source guards, mirror reconciliation and readback. The new executable port supports two configurable independent sites, draft/edit/separate publish/scoped restore, variations, existing media IDs, duplicate guards, native signed command source and uncertain-write/revocation controls. It remains PARTIALLY PORTED: no binary media upload, original Sheet/formula integration, SQL restore, private family mapping or live storefront/native-channel acceptance. See [product guide](docs/product-management.md) and [native adapter](plugins/product-owner-bridge/README.md).

## Release classifications

| Capability | Responsible subsystem | Strict status | Public implementation | Remaining gap / validation boundary |
|---|---|---|---|---|
| skill:automation-adapter-verification | main | PARTIALLY PORTED | skills/automation-adapter-verification/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:capped-external-api-pilot | main | PARTIALLY PORTED | skills/capped-external-api-pilot/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:gateway-outage-reliability-audit | main | PARTIALLY PORTED | skills/gateway-outage-reliability-audit/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:generated-asset-checkpoint-recovery | main | PARTIALLY PORTED | skills/generated-asset-checkpoint-recovery/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:google-sheets-readiness | main | PARTIALLY PORTED | skills/google-sheets-readiness/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:multi-platform-publication-recovery | main | PARTIALLY PORTED | skills/multi-platform-publication-recovery/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:poster-template-integration | main | PARTIALLY PORTED | skills/poster-template-integration/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:private-mobile-gateway-pairing | main | PARTIALLY PORTED | skills/private-mobile-gateway-pairing/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:sabah-daily-seo-blog | main | PARTIALLY PORTED | skills/sabah-daily-seo-blog/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:seo-marketing-pro | main | PARTIALLY PORTED | skills/seo-marketing-pro/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:smgc-publication-intake-diagnosis | main | PARTIALLY PORTED | skills/smgc-publication-intake-diagnosis/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:smgc-social-media | main | PARTIALLY PORTED | skills/smgc-social-media/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:supplied-image-intake | main | PARTIALLY PORTED | skills/supplied-image-intake/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:system-management-model-routing | main | PARTIALLY PORTED | skills/system-management-model-routing/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:woocommerce-cart-checkout-diagnosis | main | PARTIALLY PORTED | skills/woocommerce-cart-checkout-diagnosis/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:woocommerce-catalog-reconciliation | main | PARTIALLY PORTED | skills/woocommerce-catalog-reconciliation/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:woocommerce-price-display-audit | main | PARTIALLY PORTED | skills/woocommerce-price-display-audit/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:woocommerce-product-content-seo | main | PARTIALLY PORTED | skills/woocommerce-product-content-seo/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:wordpress-additive-content-update | main | PARTIALLY PORTED | skills/wordpress-additive-content-update/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:wordpress-child-theme-readiness | main | PARTIALLY PORTED | skills/wordpress-child-theme-readiness/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| skill:wordpress-page-style-correction | main | PARTIALLY PORTED | skills/wordpress-page-style-correction/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| other:woocommerce-verify-badges.py | main | MISSING IMPLEMENTATION | — | One-off browser verification script is deployment-scoped; reusable badge/cart checks are retained in procedural skills, but no standalone generic browser harness has been validated. |
| seo-blog-engine | main, shared | PARTIALLY PORTED | toolkit/blog_controller.py, toolkit/blog_gates.py, toolkit/blog_publication.py, toolkit/content_ledger.py, toolkit/draft_primitives.py, toolkit/reliability.py, toolkit/wordpress.py | Portable stages, create-once, publication gates and uncertain-write recovery are implemented. Native research/image/message tool bridges, site-specific SEO REST registration and full tracker orchestration are not wired as a fresh deployment. |
| social-scheduling | main, main/support (see private snapshot), shared | PARTIALLY PORTED | toolkit/product_rotation.py, toolkit/schedule_core.py | Explicit date parser, durable outbox and six-position product/template assignment are implemented. Authenticated inbound schedule challenge/confirmation bridge and daemon admission wiring remain unported. |
| tiktok-auth | main | MISSING IMPLEMENTATION | — | Photo operations accept explicit credentials and token-provider callback. The original OAuth callback/refresh helper is bound to private application setup and is not redistributed or activated; use your own reviewed OAuth integration. |
| social-publishing | main | PARTIALLY PORTED | toolkit/approval_ledger.py, toolkit/meta_publisher.py, toolkit/tiktok_publisher.py | FB/IG adapter, TikTok adapter and durable approval/revocation are implemented. The original multi-platform Engine worker, exact visual/asset binding and autonomous recovery dispatcher still require a portable integrated harness. |
| notification-delivery | main | PARTIALLY PORTED | plugins/product-owner-bridge/bridge.mjs, toolkit/notification_outbox.py, toolkit/report_outbox.py, toolkit/trusted_bridge.py | Outbox primitives and native product review-receipt capture source are supplied. Full multi-workflow native sender/recovery routing and live delivery remain NOT TESTED. |
| product-catalog | main, shared | PARTIALLY PORTED | plugins/product-owner-bridge/index.mjs, toolkit/product_api.py, toolkit/product_commands.py, toolkit/product_plan.py, toolkit/product_recovery.py, toolkit/product_workflow.py | Actual configurable Woo draft/edit/publish/scoped-restore engine, signed native hook source, before snapshots, independent revocation and no-replay reconciliation are tested offline. No full SQL backup/restore, Sheet/formula source bridge, binary media upload, promotion-copy substitutions, private family aliases, storefront/cart or live native-channel acceptance. |
| watchdog | main | PARTIALLY PORTED | toolkit/watchdog.py | Task lifecycle, stalls, endpoint health and inquiry failure reader are implemented. Native runtime-event ingestion and production-specific result watchers/delivery daemon remain outside the standalone adapter. |
| apify-budgeted-acquisition | main | PARTIALLY PORTED | toolkit/apify_budget.py, toolkit/apify_client.py | Capped start/collection and independent policy/credit guards are implemented and mocked. Complete account inventory now uses bounded pagination (100 rows/page, 20 pages), validates metadata and run states, and rechecks the head before admission. Histories exceeding 2,000 runs, changing/unknown inventory and active runs fail closed. Scheduled owner billing-evidence monitoring and native routing remain unported; concurrent starts by other clients cannot be atomically excluded. |
| social-draft-review | main | MISSING IMPLEMENTATION | — | Original canonical draft controller writes production Sheets and invokes host-owned image/preview tools. No safely configured standalone creation/revision/delivery entry point has passed isolated adapter tests. |
| poster-generation | main | PARTIALLY PORTED | poster_templates/catalog.css, poster_templates/reference.css, poster_templates/template6.css, toolkit/image_intake.py, toolkit/poster_catalog.py, toolkit/poster_cobrand.py, toolkit/poster_reference.py, toolkit/poster_render.py | Original six layout structures and crop/brand geometry are adapted with replaceable synthetic assets and operator fonts; build tests and local Chromium render evidence are supplied separately. Native image generation, genuine QR validation, independent exact-artifact semantic review and integrated draft pipeline remain incomplete. |
| blog-image-recovery | main | PARTIALLY PORTED | toolkit/blog_assets.py, toolkit/blog_controller.py | Receipt-bound three-image validation/recovery is implemented. Provider-task capture/replay bridge and original marker/crop quality reviewer depend on host-owned task and artifact contracts not ported. |
| lead-acquisition | main | PARTIALLY PORTED | toolkit/google_sheets.py, toolkit/lead_qualification.py, toolkit/lead_sheet_merge.py, toolkit/overture_adapter.py | Overture acquisition, conversion, qualification, dedup and approved Google lead merge/readback are implemented. Original verified-site/geography-specific enrichment and weekly notification orchestration are not generalized. |
| campaign-language | main | VERIFIED AND PORTABLE | toolkit/language.py | Original local language-selection/validation behavior ported and regression-tested. |
| wordpress-client | main | PARTIALLY PORTED | toolkit/wordpress.py | Authenticated REST read/update/media functionality is provided by the portable WordPress client; production-bound shell invocation and credentials are intentionally not copied. Live account integration is NOT TESTED. |
| google-sheets-adapter | main | PARTIALLY PORTED | toolkit/google_readiness.py, toolkit/google_sheets.py | Generic GOG lead synchronization is implemented. The original multi-tab SEO tracker adapter/schema and process-bound coordination remain separate unported integration work. |
| seo-local-tools | main | VERIFIED AND PORTABLE | toolkit/content_brief_generator.py, toolkit/content_review.py, toolkit/elementor_plan.py, toolkit/keyword_research.py, toolkit/local_metadata.py | Original local SEO helpers and inert Elementor command-plan generation reproduced; the original wrapper did not execute Elementor. Real browser/analytics operations remain upstream/account dependencies. |
| customer-knowledge | shared, smgc-customer-support | VERIFIED AND PORTABLE | toolkit/knowledge_snapshot.py | Original bounded public knowledge snapshot behavior generalized and fixture-tested; original first-page-only limitation remains explicit. Fresh live account/scheduler acceptance not claimed. |
| gateway-monitor | shared | PARTIALLY PORTED | examples/services/toolkit-monitor.service, examples/services/toolkit-monitor.timer, toolkit/gateway_monitor.py | Independent alert-only HTTP probe, durable incident/unknown-send fencing and optional configured Telegram transport plus inert service templates are executable. Actual natural service invocation and owner delivery NOT TESTED; no Gateway control. |
| deployment-adapters | shared | PARTIALLY PORTED | toolkit/setup_scaffold.py | Original service/timer definitions contain host-specific executables, identities and environment bindings. They remain excluded from automatic installation; no production schedules are activated. Inert two-workspace scaffolder implemented and tested; no fresh Gateway or service installation acceptance. |
| customer-support-policy | smgc-customer-support | PARTIALLY PORTED | toolkit/trusted_bridge.py | Targeted supplemental discovery: original support language/inquiry/privacy/tool policy generalized with test-only allowlisted routing. Static guard checks pass; fresh-agent/model behavior and actual customer delivery are NOT TESTED. Signed routing, denied sensitive actions, opt-in send reservation and exact receipt validation are now executable and offline tested. Independent semantic policy callback and native ingress/sender still required. |
| skill:public-toolkit-release | main | PARTIALLY PORTED | skills/public-toolkit-release/SKILL.md | Original procedural skill package and resources are published; native tools/accounts and associated engine integration must be configured. Static/helper tests are not full fresh-agent workflow acceptance. |
| local-speech-recognition | main/support | PARTIALLY PORTED | toolkit/local_voice.py | Executable adapter and synthetic subprocess tests; actual model/license/accuracy/native attachment acceptance NOT TESTED. |
| local-voice-synthesis | main/support | PARTIALLY PORTED | toolkit/local_voice.py | No model or voice redistributed. Actual model quality/licensing, native voice reply and audio/text priority NOT TESTED. |
| voice-runtime-control | main/shared | MISSING IMPLEMENTATION | — | Original scripts mutate Gateway/account/runtime configuration and depend on separately installed model/binary assets. No portable validated control/deployment adapter; no configuration changes authorized by this release. |
| customer-support-control | main/shared | PARTIALLY PORTED | plugins/support-guards/guards.mjs | Local mode state is executable. Original authenticated owner command/config-patch integration and exact native send-policy merge are not ported or fresh-host validated. |
| integrity-guard | shared | PARTIALLY PORTED | toolkit/gateway_monitor.py | Generic manifest checks exist. Native plugin source attestation, exact DB schemas, startup fencing and deliberate stop-policy service adapter remain unported; no stop/restart behavior added. |
| native-rate-limit | customer-support | VERIFIED AND PORTABLE | plugins/support-guards/guards.mjs | Actual disposable SQLite tests pass. Callable library only, not activated native interception. Retains tombstones rather than original seven-day deletion. |
| native-delivery-guard | customer-support | VERIFIED AND PORTABLE | plugins/support-guards/guards.mjs | Callable admission guard verified with SQLite; no delivery guarantee or native transport activation. Missing mode fails closed; callback needs its own durable receipt ledger. |
| customer-reply-runtime-recovery | customer-support | PARTIALLY PORTED | toolkit/notification_outbox.py, toolkit/trusted_bridge.py | Existing portable outboxes/attestation do not port the native final-result/transcript lookup and per-inquiry runtime recovery. Native source coupling and privacy boundary require separate adaptation and tests. |

## Security, licensing and native dependencies

Two legacy derivative skill families (gog-clean and wordpress-rest-api-clean) remain excluded pending provenance/license-chain resolution. Patched native WhatsApp bundles are separately blocked from redistribution; use the official supported distribution. No production images, logos, QR/contact assets, fonts, voice models, credentials, session data or customer records are copied. Original reusable code is adapted under the repository license; upstream software retains its own licenses.

All 22 identified publishable original procedural packages are present. That does NOT mean every underlying workflow installs and runs end-to-end: procedures may require unported engines or configured native tools. New wrapper/reference packages are counted separately. No model-generated mock receipt proves actual delivery.

## Reproduction and acceptance

Start with [setup](COMPLETE-SETUP-GUIDE.md), [configuration](CONFIGURATION-REFERENCE.md), [dependencies](DEPENDENCIES.md), [acceptance](ACCEPTANCE-TESTS.md) and the deployment checklist. Install standalone libraries, configure separate accounts/state, install only appropriate owner skills, then prove each integration in an isolated target before activation. Customer-support never receives administrative tools by copying the main-agent package list.

**Full fresh-install external workflows accepted: zero.** Actual local SQLite/file/image utility tests are distinct from mocked providers, native hook fixtures, live accounts, a booted fresh Gateway or an exact recreation of production.

The [machine-readable register](docs/complete-capability-audit.json) records purpose, agent, trigger, authentication, source paths/hashes, dependencies, execution, schedules, accounts, implementation paths, setup, validation boundaries, gaps and strict classification for every grouped record. Logical paths replace private host roots. Old sources that could not be freshly matched retain their previous hashes with explicit limits.

The audit itself remains unfinished: untraced native recovery/control branches and bounded discovery limits are not silently classified as complete. Preserve this register and the public release checkpoint for continuation.
