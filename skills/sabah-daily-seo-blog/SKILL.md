---
name: sabah-daily-seo-blog
description: Prepare researched nonduplicate WordPress SEO articles with three licensed images, durable review gates and tracker reconciliation; draft by default.
---

# Portable daily SEO article workflow

**PARTIALLY PORTED.** This is the generalized original procedure, not a configured
daily service. Installing it creates NO standing publication authority, schedule,
WordPress account, Google tracker or messaging route. Read README.md first.

## Required deployment bindings

Configure a website origin and verified application-password identity, supported
post/media/taxonomy APIs, actually exposed SEO metadata routes, content ledger,
tracker/tab schema, private run-state root and trusted owner routes. Use normal
WordPress posts, not Elementor-designed articles. Inspect the site's existing
single-post template: one dynamic featured hero, title/date, one content widget.
Never alter site templates/theme/header/footer/commerce during routine writing.

Use authenticated REST first. A separately authorized local WP-CLI path may fill
a specific REST verification gap, not bypass a denial. Use native browser tools
for optional design inspection. Keep each operation on its configured host; a
remote desktop node is not automatically a server-side execution host. Do not
install credentials or broaden tool grants to make a scheduled context work.

SEO plugins vary. The reference used Rank Math updateMeta and a custom readback
route. Neither is assumed present on another site. Discover permitted routes,
write only reviewed supported fields and independently read them back. Missing
mandatory verification blocks publication; optional FAQ schema may be omitted.

## Topic, content and media

1. A supplied topic preserves owner intent. Otherwise inspect current authorized
   posts (including drafts), the ledger and actual company services; research a
   distinct commercially relevant topic for the configured geography/audience.
2. Check title, slug and primary keyword duplicates with the local ledger AND
   current WordPress inventory. Assess semantic overlap/search intent separately;
   exact hashes do not establish topic uniqueness. Ignore synthetic validation
   records for topic planning, but never discard real attempt history.
3. Use current reputable sources. Distinguish fact from advice. Never invent
   regulations, prices, deadlines, credentials, completed projects or citations.
   Write useful title/introduction, H2/H3 sections, actionable detail, relevant
   internal links, referenced facts, conclusion and an appropriate CTA.
4. Freeze slug, excerpt, category, tags, primary/secondary keywords and supported
   SEO/social metadata. Canonical is the final HTTPS permalink. Do not accidentally
   noindex the article or create conflicting Article/FAQ entities.
5. Supply exactly three distinct topic-relevant licensed images: featured hero
   outside post_content; inline images around 25–35% and 60–75% of useful text.
   Optimize WebP, descriptive filenames/title/alt/caption, responsive inline size
   and lazy-loading. Label generated/stock scenes as illustrative, not customer
   projects. Do not reuse the same bytes as featured and inline imagery.
6. FAQs belong in visible article content: 3–5 meaningful topic-specific semantic
   details/summary pairs using one grouped name and configurable scoped classes.
   Add FAQPage only when it matches visible text and no duplicate schema exists.

## Durable execution and approval

Use repository blog_controller, blog_publication, blog_gates, blog_assets,
draft_primitives, content_ledger and reliability modules according to their
actual callable contracts. They are not a replacement for missing native tool
bridges. Resolve current signatures from code/docs before calling; never invent
a production controller command from the reference deployment.

- Keep one stable run ID and frozen plan across retries. Lock local writers and
  persist intent BEFORE external writes. A local lock does not exclude remote
  writers; use an exclusive window when the API lacks compare-and-swap.
- Create/update draft by default. Manual publication needs verified owner identity
  and an exact current-content review/confirmation. Bare contextual approval is
  valid only with one unambiguous eligible draft and genuine quoted preview
  receipt. Social approvals must not route to blog publication or vice versa.
- A scheduled policy, if independently authorized and installed, may permit at
  most one new same-day run for its configured timezone. Do not infer such policy
  from this skill, replay older drafts, fake time, or create a second scheduler.
- Verify post state, content, taxonomy, media, SEO, canonical and robots. Draft
  REST readiness is not visual/schema/public readiness. An anonymous draft 404
  is expected. Mandatory public gates run independently after actual publication.
- Bound equivalent failures; uncertain creates require stable-ID/run-marker
  reconciliation, never another POST merely because the response was lost.
  Preserve review latches and remote IDs. Rollback restores only reviewed affected
  fields after checking for intervening changes; no automatic deletion/publication.

## Image task and asynchronous recovery

Reconcile saved task identity/status before generation. Exactly one authorized
provider route per frozen image intent; never run native and CLI generators in
parallel or regenerate an uncertain task. Persist genuine task/output binding.
Decode actual atlas dimensions/separators, crop distinct panels, hash actual
outputs and bind exact metadata. Use generated-asset-checkpoint-recovery for
same-job and historical-gate diagnosis. Model/provider generation, semantic
review and asynchronous host dispatch remain external integration requirements.

## Tracking and reports

WordPress is content-state authority; Sheets is a reporting mirror. Preserve
append-only run history and stable Post ID/run ID. Tracker updates read existing
schema/rows, use literal values, preserve formulas/review columns, read back each
tab and append a run log once. A cross-tab failure resumes only the same record
set; never creates/republishes WordPress content. The generic Google adapter does
not yet reproduce the reference three-tab tracker orchestration.

Reports include title, post ID, topic/keyword, Draft/Published/Blocked/Failed,
actual URL, tracker outcome and sanitized blocker. Label draft links nonpublic.
Persist per-route send claim before the native messaging tool, then the actual
receipt. Unknown delivery is not automatically resent and never causes reposting.
No shell/CLI messaging is substituted for required native tool delivery.

## Completion and limits

Report actual gate evidence, not successful helper invocation. Fresh Gateway,
provider generation, native sender, site-specific SEO readback, tracker integration
and end-to-end scheduled publication are NOT TESTED. Preserve original exclusions
through configurable per-site policies; do not transplant private product/post IDs.
