---
name: wordpress-additive-content-update
description: Expand existing WordPress posts or pages with additive copy and internal links while preserving original content, SEO metadata, templates and responsive behavior.
---

# Additive WordPress content update

Use for an authorized addition to existing post/page content, especially when several targets have different layouts. A one-time content brief is not a standing copy, publishing or SEO policy. For a CSS-only correction use [WordPress page style correction](../wordpress-page-style-correction/SKILL.md); for WooCommerce product copy use [product content and SEO](../woocommerce-product-content-seo/SKILL.md).

1. Resolve each exact public URL to its edit-context REST record and confirm type, ID, status, slug, template, raw content and editor ownership. A page with an Elementor header/footer template may still store its body as raw HTML/CSS with empty Elementor data; do not rebuild it in Elementor by assumption. Inspect public title, canonical, description, robots, schema, headings, links, images, FAQ and responsive layout before choosing insertion points.
2. Save a **separate complete edit record, raw content and public HTML** for each target in a private writable backup directory. Read them back and record content hashes and modification times. Do not treat a root-owned backup path or failed directory creation as a backup; choose a permitted private location and verify writes before any CMS mutation.
3. Draft distinct additions that fit each page's intent and existing markup. Keep sitewide CSS, shared templates, title/slug/date, SEO fields and schema outside the payload unless expressly authorized. Where a page has local card/CTA styles, reuse those classes and responsive grid rather than altering its style block; a blog post may instead use plain headings and lists. Check every new internal link and avoid unsupported claims or invented specifications. Freeze candidates with an exact single insertion marker; assert removing only the inserted bytes restores the original content, and that original H1/FAQ/schema counts and sections remain intact.
4. Immediately before mutation reread **all** targets and abort if any original content or modified time drifted. Send only the `content` field to each confirmed core REST route. After an uncertain write, GET first; never blindly repeat. Read back exact candidate bytes and compare unchanged identifiers, status, template, featured media, date, title and exposed metadata with the per-page backup. If one target fails, stop and reconcile it independently; do not replay completed targets.
5. Fetch each public URL afresh and compare SEO head and original headings/FAQ/images/schema with its own baseline. Verify every new category or section is visible, links/CTA destinations resolve, images load and FAQ controls work. In a browser check desktop and narrow mobile widths for overflow, card columns and button fit; a REST success or HTTP 200 alone is not visual proof. If screenshot capture fails, use an independent capture path if available or name the limit, not a fabricated visual pass.

Completion: each target's URL/ID, inserted scope, exact content readback, original-byte preservation, unchanged protected metadata, live public and responsive interaction results, and its own restorable backup. Report partial targets and unverified visual boundaries explicitly; do not roll back an unrelated successful page automatically.

## Portable release contract

Read [README.md](README.md) before activation. This is a procedural OpenClaw skill, not a configured CMS/Google account or an autonomous service. Use only current operator-authorized tools and targets. Static package checks and synthetic preservation/gate tests do not establish live permissions, browser behavior or restore success.
