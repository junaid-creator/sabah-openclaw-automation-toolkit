---
name: seo-marketing-pro
description: SEO and digital marketing execution for keyword research, content planning, on-page SEO, technical SEO, off-page link building, social/email marketing, analytics review, and browser-assisted landing page work with Elementor AI. Use when the user asks to grow organic traffic, improve rankings, plan content, optimize pages, update metadata, build campaigns, audit SEO issues, or create landing pages with browser automation support.
---

# SEO Marketing Pro

Execute SEO and digital marketing work in clear phases. Keep the work practical, evidence-driven, and easy to resume.

## Rules

- Start with the smallest useful audit before making recommendations.
- Prefer public data, existing site content, and first-party analytics over guesswork.
- Treat browser automation as higher risk than read-only analysis.
- Ask before external posting, email sending, account connection, or destructive CMS changes.
- When using Elementor AI or browser automation, verify each important step before publishing.
- Document assumptions, target keywords, URLs, and page intent as you work.

## Phase 1: Keyword Research

1. Define the business goal, target geography, audience, and page type.
2. Group keywords by intent:
   - transactional
   - commercial investigation
   - informational
   - navigational
3. Separate primary keywords from secondary/supporting terms.
4. Evaluate each cluster for:
   - relevance
   - search intent fit
   - difficulty signals
   - content opportunity
   - local modifiers if relevant
5. Build a keyword map that ties each cluster to one target URL or planned page.
6. Avoid cannibalization by assigning one primary keyword per page.

### Use bundled scripts

- Run `scripts/keyword_research.py` to normalize seed keywords, expand variants, and output a simple keyword plan.
- Save exported results before moving into content planning.

## Phase 2: Content Planning

1. Turn keyword clusters into a content calendar or page roadmap.
2. For each page/article define:
   - target URL slug
   - primary keyword
   - secondary keywords
   - search intent
   - page format
   - call to action
3. Prioritize pages by revenue potential, ranking opportunity, and internal-link value.
4. Create outlines that match search intent instead of stuffing terms.
5. Include FAQ, comparison, trust, and local sections when they improve usefulness.

### Use bundled scripts

- Run `scripts/content_brief_generator.py` to turn keyword maps into structured content briefs.

## Phase 3: On-Page SEO

For each target page:

1. Review title tag.
2. Review meta description.
3. Confirm one clear H1.
4. Improve heading hierarchy.
5. Tighten URL slug if needed.
6. Improve keyword placement in:
   - title
   - intro
   - H1/H2s where natural
   - image alt text
   - anchor text
7. Add internal links to relevant money and support pages.
8. Improve CTA clarity and conversion alignment.
9. Remove thin, duplicate, or filler sections.

### Meta tag workflow

1. Export or collect current page metadata.
2. Prepare replacement values in CSV or JSON.
3. Run `scripts/update_meta_tags.py` in dry-run mode first.
4. Review output carefully.
5. Apply changes only after confirmation.

## Phase 4: Technical SEO

Audit the site for:

- crawlability
- indexability
- canonical usage
- robots directives
- XML sitemap coverage
- redirect hygiene
- broken links
- page speed issues
- mobile layout issues
- Core Web Vitals risks
- schema markup gaps
- duplicate metadata

Execution order:

1. Fix blocking indexation or canonical problems first.
2. Fix major internal-link and redirect issues second.
3. Fix speed, image, and render issues third.
4. Add structured data where it materially helps.

## Phase 5: Off-Page and Link Building

1. Identify pages that deserve links before outreach.
2. Build prospect lists by relevance, not volume.
3. Prioritize:
   - local citations
   - niche directories
   - partner links
   - guest content opportunities
   - digital PR angles
4. Avoid spammy bulk link tactics.
5. Track outreach status and acquired links in a simple sheet or JSON file.
6. Focus anchor text diversity and destination relevance.

## Phase 6: Social and Email Marketing

Use SEO insights to amplify distribution.

### Social

1. Adapt page/article value props into short hooks.
2. Create multiple angle variants:
   - problem/solution
   - myth busting
   - checklist
   - local angle
   - proof/result
3. Match format to channel.
4. Link back to the most relevant landing page or article.

### Email

1. Segment by audience or funnel stage.
2. Write one clear outcome-focused subject line.
3. Keep one main CTA per message.
4. Reuse high-intent SEO content in nurture or promo campaigns.
5. Track opens, clicks, and downstream conversions.

## Phase 7: Analytics and Reporting

Review performance with focus on decisions, not vanity metrics.

Track:

- rankings by page cluster
- organic sessions
- CTR
- conversions/leads
- bounce/engagement signals
- indexed page growth
- internal-link impact
- top landing pages
- technical issue counts

Use a simple report structure:

1. what changed
2. what improved
3. what dropped
4. likely cause
5. next action

## Phase 8: Browser Automation and Elementor AI Landing Pages

Use this phase only when browser interaction is actually needed. The bundled wrapper ONLY GENERATES A PLAN; it never logs in, clicks, saves or publishes. Use an authorized native browser tool separately, following current snapshots.

1. Confirm the target URL, site access method, and exact page goal.
2. Use a safer read-first pass before making changes.
3. If Elementor AI is used:
   - define offer
   - define audience
   - define CTA
   - define section order
   - define proof/testimonial needs
4. Build landing pages in this order:
   - hero
   - benefits
   - proof
   - objection handling
   - CTA block
   - FAQ
5. After AI generation, manually improve:
   - headlines
   - trust language
   - CTA copy
   - spacing and section order
   - metadata
6. Verify mobile layout and forms before publish.
7. Save screenshots or notes of major page versions.

### Safe wrapper using agent-browser-clawdbot

Use `scripts/elementor_agent_wrapper.py` as the plan-only browser wrapper when asked to perform WordPress or Elementor work.

Supported command styles inside this skill:

- `/create-landing-page`
- `/open-elementor`
- `/wp-login`
- `/elementor-ai-draft`
- `/elementor-review-checklist`

Treat these as workflow shorthands, not literal chat-platform commands.

### Wrapper rules

- Use `agent-browser-clawdbot` for deterministic browser automation.
- Default to `--dry-run` planning mode first.
- Never auto-publish.
- Never store WordPress credentials in skill files.
- Prefer loading an existing browser auth state if the user already has one.
- Re-snapshot after each important UI action.
- Stop and ask before destructive actions, publishing, deleting, or mass edits.

### Wrapper workflow

1. Run `/wp-login` to open the WordPress login page or restore a saved auth state.
2. Run `/open-elementor` to open the target page or create a new landing-page draft.
3. Run `/elementor-ai-draft` with a structured brief including:
   - audience
   - offer
   - primary keyword
   - CTA
   - sections needed
4. Review generated sections in Elementor.
5. Run `/elementor-review-checklist` before any final save.
6. Save draft only unless the user explicitly asks to publish.

### Example wrapper usage

```bash
python3 skills/seo-marketing-pro/scripts/elementor_agent_wrapper.py \
  /create-landing-page \
  --site-url https://example.com \
  --admin-path /wp-admin/ \
  --page-title "Dubai SEO Landing Page" \
  --brief-file ./landing-brief.json \
  --session seo-admin \
  --dry-run
```

### Browser automation guidance

- Prefer deterministic browser skills for repeatable changes.
- Re-snapshot after each major UI action.
- Never assume Elementor AI output is publish-ready.
- Verify page title, meta description, open graph fields, and index settings before publish.
- If Elementor UI labels differ from the expected brief, inspect the live snapshot and adapt instead of guessing.

## Deliverables

When finishing a task, aim to leave behind one or more of:

- keyword map
- content brief
- metadata update file
- technical audit checklist
- link prospect list
- social/email campaign draft
- landing page outline
- analytics summary with next actions

## Bundled Resources

- `scripts/keyword_research.py` for seed cleanup, clustering, and keyword plan generation
- `scripts/content_brief_generator.py` for turning keyword plans into content briefs
- `scripts/update_meta_tags.py` for local HTML meta-tag updates with dry-run support
- `scripts/elementor_agent_wrapper.py` for gated browser automation planning and command generation using `agent-browser`
- `references/elementor-landing-page-checklist.md` for landing-page build and review guidance

## Workflow Notes

- Use scripts for repeatable local work.
- Keep SKILL.md focused on operating procedure.
- Read the Elementor checklist reference before browser-based landing page work.

## Portable package boundary

Read README.md. Browser shorthands are planning labels, not registered commands. External analytics, browser execution, live accounts and fresh-agent integration are NOT TESTED. Helpers require the repository checkout and its dependencies.
