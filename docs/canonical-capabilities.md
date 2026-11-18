# Canonical capability register

**Complete-library status: INCOMPLETE. Published batches are independently validated within documented offline/mock boundaries.**

{
  "original_inventory_records": 460,
  "supplemental_original_sources": 1,
  "canonical_groups": 174,
  "original_capability_groups": 42,
  "upstream_groups": 128,
  "blocked_derivative_groups": 2,
  "supporting_groups": 2,
  "runtime_modules": 31,
  "packaged_skills": 11,
  "status_counts": {
    "UNTESTED OR INCOMPLETE": 28,
    "PUBLISHED AND VALIDATED": 13,
    "DUPLICATE / ALREADY COVERED": 1
  },
  "method": "Source identity before dependency-family grouping; content hashes retain aliases. Categories separate procedures, engines, adapters, supporting aliases and upstream. These are release work groups, not counts of independent end-user products."
}

The original 460 discovery records are all assigned. A targeted read of the support agent policy added one supplemental original source; this is not a repeated environment inventory. Source identity corrected one runtime entry previously treated as local. Original 265 ADAPT records are not 265 packages. See the JSON for source hashes and every record mapping.

| Capability | Category | Status | Published implementation | Remaining reason / evidence limit |
|---|---|---|---|---|
| skill:automation-adapter-verification | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| skill:capped-external-api-pilot | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| skill:gateway-outage-reliability-audit | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| skill:generated-asset-checkpoint-recovery | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| blocked:gog-clean | F | BLOCKED WITH VERIFIED REASON | — | Source explicitly identifies derivative ancestry; upstream redistribution/license chain is unresolved. All six original blocked records remain excluded. |
| skill:google-sheets-readiness | A | PUBLISHED AND VALIDATED | google-sheets-readiness | Original procedural package and resource links validated; applicable synthetic preservation/permission/gate helpers tested. Live skill execution is NOT TESTED and requires operator-configured upstream tools. |
| skill:multi-platform-publication-recovery | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| skill:poster-template-integration | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| skill:private-mobile-gateway-pairing | A | PUBLISHED AND VALIDATED | private-mobile-gateway-pairing | Original portable diagnostic procedure and synthetic evidence-contract tests validated offline. Fresh installation, live deployment, phone pairing, management inference and hot reload are NOT TESTED. No runtime engine completed. |
| skill:sabah-daily-seo-blog | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| skill:seo-marketing-pro | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| skill:smgc-publication-intake-diagnosis | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| skill:smgc-social-media | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| skill:supplied-image-intake | A | UNTESTED OR INCOMPLETE | — | Original operational procedure still references unported adapters/evidence paths or tool capabilities. It has not yet been generalized and independently validated; do not treat engine coverage as skill completion. |
| skill:system-management-model-routing | A | PUBLISHED AND VALIDATED | system-management-model-routing | Original portable diagnostic procedure and synthetic evidence-contract tests validated offline. Fresh installation, live deployment, phone pairing, management inference and hot reload are NOT TESTED. No runtime engine completed. |
| skill:woocommerce-cart-checkout-diagnosis | A | PUBLISHED AND VALIDATED | woocommerce-cart-checkout-diagnosis | Original procedural package and resource links validated; applicable synthetic preservation/permission/gate helpers tested. Live skill execution is NOT TESTED and requires operator-configured upstream tools. |
| skill:woocommerce-catalog-reconciliation | A | PUBLISHED AND VALIDATED | woocommerce-catalog-reconciliation | Original procedural package and resource links validated; applicable synthetic preservation/permission/gate helpers tested. Live skill execution is NOT TESTED and requires operator-configured upstream tools. |
| skill:woocommerce-price-display-audit | A | PUBLISHED AND VALIDATED | woocommerce-price-display-audit | Original procedural package and resource links validated; applicable synthetic preservation/permission/gate helpers tested. Live skill execution is NOT TESTED and requires operator-configured upstream tools. |
| skill:woocommerce-product-content-seo | A | PUBLISHED AND VALIDATED | woocommerce-product-content-seo | Original procedural package and resource links validated; applicable synthetic preservation/permission/gate helpers tested. Live skill execution is NOT TESTED and requires operator-configured upstream tools. |
| skill:wordpress-additive-content-update | A | PUBLISHED AND VALIDATED | wordpress-additive-content-update | Original procedural package and resource links validated; applicable synthetic preservation/permission/gate helpers tested. Live skill execution is NOT TESTED and requires operator-configured upstream tools. |
| skill:wordpress-child-theme-readiness | A | PUBLISHED AND VALIDATED | wordpress-child-theme-readiness | Original procedural package and resource links validated; applicable synthetic preservation/permission/gate helpers tested. Live skill execution is NOT TESTED and requires operator-configured upstream tools. |
| skill:wordpress-page-style-correction | A | PUBLISHED AND VALIDATED | wordpress-page-style-correction | Original procedural package and resource links validated; applicable synthetic preservation/permission/gate helpers tested. Live skill execution is NOT TESTED and requires operator-configured upstream tools. |
| blocked:wordpress-rest-api-clean | F | BLOCKED WITH VERIFIED REASON | — | Source explicitly identifies derivative ancestry; upstream redistribution/license chain is unresolved. All six original blocked records remain excluded. |
| other:woocommerce-verify-badges.py | C | UNTESTED OR INCOMPLETE | — | One-off browser verification script is deployment-scoped; reusable badge/cart checks are retained in procedural skills, but no standalone generic browser harness has been validated. |
| seo-blog-engine | B | UNTESTED OR INCOMPLETE | blog_controller, blog_publication, blog_gates, wordpress, draft_primitives, reliability, content_ledger | Portable stages, create-once, publication gates and uncertain-write recovery are implemented. Native research/image/message tool bridges, site-specific SEO REST registration and full tracker orchestration are not wired as a fresh deployment. |
| social-scheduling | B | UNTESTED OR INCOMPLETE | product_rotation, schedule_core | Explicit date parser, durable outbox and six-position product/template assignment are implemented. Authenticated inbound schedule challenge/confirmation bridge and daemon admission wiring remain unported. |
| deployment-specific-utilities | D | DUPLICATE / ALREADY COVERED | — | Supporting test/package/deployment-utility records, not additional standalone skills; retained in record accounting rather than reimplemented individually. |
| verification-harnesses | D | DUPLICATE / ALREADY COVERED | — | Supporting test/package/deployment-utility records, not additional standalone skills; retained in record accounting rather than reimplemented individually. |
| tiktok-auth | B | UNTESTED OR INCOMPLETE | — | Photo operations accept explicit credentials and token-provider callback. The original OAuth callback/refresh helper is bound to private application setup and is not redistributed or activated; use your own reviewed OAuth integration. |
| social-publishing | B | UNTESTED OR INCOMPLETE | meta_publisher, approval_ledger, tiktok_publisher | FB/IG adapter, TikTok adapter and durable approval/revocation are implemented. The original multi-platform Engine worker, exact visual/asset binding and autonomous recovery dispatcher still require a portable integrated harness. |
| notification-delivery | B | UNTESTED OR INCOMPLETE | notification_outbox, report_outbox | Durable claim/receipt/no-replay logic and owner report outbox are implemented. The original native message-tool/owner-route bridge is not packaged as an authenticated transport; callbacks must use an independently authorized sender. |
| product-catalog | B | UNTESTED OR INCOMPLETE | — | Original WooCommerce mutation adapters use site-specific WP-CLI grants and source-schema mappings. The generic WordPress client and catalog procedural skill do not replace the full isolated Woo setter/backup/derived-field test environment, which is not available in this release. |
| watchdog | B | UNTESTED OR INCOMPLETE | watchdog | Task lifecycle, stalls, endpoint health and inquiry failure reader are implemented. Native runtime-event ingestion and production-specific result watchers/delivery daemon remain outside the standalone adapter. |
| apify-budgeted-acquisition | B | UNTESTED OR INCOMPLETE | apify_budget, apify_client | Capped start/collection and independent policy/credit guards are implemented and mocked. Original scheduled owner evidence-monitor routing is not ported; account history beyond the bounded 30-run window is deliberately blocked pending tested pagination. |
| social-draft-review | B | UNTESTED OR INCOMPLETE | — | Original canonical draft controller writes production Sheets and invokes host-owned image/preview tools. No safely configured standalone creation/revision/delivery entry point has passed isolated adapter tests. |
| poster-generation | B | UNTESTED OR INCOMPLETE | — | Original rendering code depends on supplied branded logo/QR/photo assets, six layout-specific font/QR contracts, Playwright and exact-artifact visual review. These dependencies were inspected; no complete brand-neutral renderer/assets package with independent QA is validated. Rotation alone is not six rendered templates. |
| blog-image-recovery | B | UNTESTED OR INCOMPLETE | blog_assets, blog_controller | Receipt-bound three-image validation/recovery is implemented. Provider-task capture/replay bridge and original marker/crop quality reviewer depend on host-owned task and artifact contracts not ported. |
| lead-acquisition | B | UNTESTED OR INCOMPLETE | lead_qualification, overture_adapter, lead_sheet_merge, google_sheets | Overture acquisition, conversion, qualification, dedup and approved Google lead merge/readback are implemented. Original verified-site/geography-specific enrichment and weekly notification orchestration are not generalized. |
| campaign-language | B | PUBLISHED AND VALIDATED | language | Original language behavior is ported and regression-tested. |
| wordpress-client | B | DUPLICATE / ALREADY COVERED | wordpress | Authenticated REST read/update/media functionality is provided by the portable WordPress client; production-bound shell invocation and credentials are intentionally not copied. Live account integration is NOT TESTED. |
| google-sheets-adapter | B | UNTESTED OR INCOMPLETE | google_sheets, google_readiness | Generic GOG lead synchronization is implemented. The original multi-tab SEO tracker adapter/schema and process-bound coordination remain separate unported integration work. |
| seo-local-tools | B | UNTESTED OR INCOMPLETE | keyword_research, content_brief_generator, local_metadata, content_review | Keyword/brief/local metadata/content-review helpers are implemented. The original Elementor command-plan wrapper is not an executable browser integration; external agent-browser dependency and live Elementor flow remain unvalidated. |
| customer-knowledge | B | PUBLISHED AND VALIDATED | knowledge_snapshot | Original public knowledge refresher is generalized, fixture-tested and documented with its first-page-only limit. Its production timer/account deployment is not activated. |
| gateway-monitor | B | UNTESTED OR INCOMPLETE | — | A generic watchdog is available. Independent Gateway alert service has deployment-specific Telegram credentials, process bindings and recovery handover; no portable unattended alert service is validated. |
| deployment-adapters | C | UNTESTED OR INCOMPLETE | — | Original service/timer definitions contain host-specific executables, identities and environment bindings. They remain excluded from automatic installation; no production schedules are activated. |
| customer-support-policy | C | PUBLISHED AND VALIDATED | — | Targeted supplemental discovery: original support language/inquiry/privacy/tool policy generalized with test-only allowlisted routing. Static guard checks pass; fresh-agent/model behavior and actual customer delivery are NOT TESTED. |

Categories: A original procedural skills; B engines/scripts; C configuration/integration adapters; D supporting duplicates or covered records; E upstream; F independently identified release blocker. Published artifact validation never implies live account/model/transport acceptance.

Full machine-readable register: [canonical-capabilities.json](canonical-capabilities.json).

## Reproducibility batch

Current detailed paths, sources, tools, configuration, priorities and unchanged gaps are in [feature matrix](../FEATURE-REPLICATION-MATRIX.md). Added trusted_bridge and setup_scaffold; no original group is upgraded to fully reproduced. The JSON register holds updated module links.
