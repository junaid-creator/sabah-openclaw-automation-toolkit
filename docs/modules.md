# Module guide

Every module is adapted from a reviewed local source listed in PROVENANCE.json. Prerequisites for all: Python 3.11+, checkout-root working directory, writable private output directory. Only knowledge_snapshot needs requests. Install requirements as described in installation.md. No module requires credentials for fixture use.

## keyword_research

**Purpose:** Generate heuristic keyword clusters from seeds.

**Configuration / activation:** Explicit CLI invocation below; no service is installed.

```bash
mkdir -p output
python -m toolkit.keyword_research --input examples/seeds.txt --output output/keywords.json
```

**Expected output:** JSON list of clusters with primary/secondary keywords and intent.

**Testing:** python -m unittest discover -s tests -v covers this module with synthetic inputs. See validation.md for actual results.

**Troubleshooting:** validate input shape and local permissions; do not bypass failures or point tests at production.

**Limitations:** No search-volume, ranking or live keyword research. English ASCII normalization.

## content_brief_generator

**Purpose:** Convert a keyword plan into content briefs.

**Configuration / activation:** Explicit CLI invocation below; no service is installed.

```bash
mkdir -p output
python -m toolkit.content_brief_generator --input output/keywords.json --output output/briefs.json
```

**Expected output:** JSON list of titles, outlines and suggested slugs.

**Testing:** python -m unittest discover -s tests -v covers this module with synthetic inputs. See validation.md for actual results.

**Troubleshooting:** validate input shape and local permissions; do not bypass failures or point tests at production.

**Limitations:** Requires keyword_research output; outlines need editorial review.

## local_metadata

**Purpose:** Preview or edit local HTML metadata.

**Configuration / activation:** Explicit CLI invocation below; no service is installed.

```bash
mkdir -p output
python -m toolkit.local_metadata --site-root examples/site --updates examples/meta-updates.json --dry-run
```

**Expected output:** Preview count and update/nochange messages; no write by default.

**Testing:** python -m unittest discover -s tests -v covers this module with synthetic inputs. See validation.md for actual results.

**Troubleshooting:** validate input shape and local permissions; do not bypass failures or point tests at production.

**Limitations:** Add --apply only for reviewed disposable copies. Regex markup matching is limited; no CMS calls.

## lead_qualification

**Purpose:** Score and deduplicate public-listing fixtures.

**Configuration / activation:** Explicit CLI invocation below; no service is installed.

```bash
mkdir -p output
python -m toolkit.lead_qualification --profile examples/lead-profile.json --raw examples/leads.json --output output/leads.json
```

**Expected output:** Headers, all/qualified rows, source count and aggregate summary.

**Testing:** python -m unittest discover -s tests -v covers this module with synthetic inputs. See validation.md for actual results.

**Troubleshooting:** validate input shape and local permissions; do not bypass failures or point tests at production.

**Limitations:** Construction-sector heuristics, not generic sales intelligence. Requires coordinates and valid IDs. No collection, paid Actors, Sheets writes or outreach. Data rights remain your responsibility.

## content_ledger

**Purpose:** Check normalized content duplicates in local JSONL.

**Configuration / activation:** Explicit CLI invocation below; no service is installed.

```bash
mkdir -p output
python -m toolkit.content_ledger check --ledger output/content-ledger.jsonl --title "Example guide"
```

**Expected output:** JSON clear/matches result; exit 0 clear, 2 duplicate, 1 invalid.

**Testing:** python -m unittest discover -s tests -v covers this module with synthetic inputs. See validation.md for actual results.

**Troubleshooting:** validate input shape and local permissions; do not bypass failures or point tests at production.

**Limitations:** Creates a lock file. Requires authenticated CMS inventory and semantic review separately. append needs a complete record; see REQUIRED in source.

## knowledge_snapshot

**Purpose:** Create customer-support reference files from public CMS fixtures.

**Configuration / activation:** Explicit CLI invocation below; no service is installed.

```bash
mkdir -p output
python -m toolkit.knowledge_snapshot --base-url https://example.com --currency USD --fixture examples/site-fixture.json --output output/knowledge
```

**Expected output:** Markdown reference files and products.json with timestamp/source.

**Testing:** python -m unittest discover -s tests -v covers this module with synthetic inputs. See validation.md for actual results.

**Troubleshooting:** validate input shape and local permissions; do not bypass failures or point tests at production.

**Limitations:** First 100 pages/products only; no pagination. Variation requests depend on API shape. Snapshot writes are per-file atomic, not whole-directory transactional. Never trust stale files after a failed refresh; use a fresh output directory. Network requires --allow-network and trusted operator-selected HTTPS origin.

## language

**Purpose:** Select English/Arabic/bilingual and validate copy.

**Configuration / activation:** Import the API explicitly; importing performs no business operation.



**Expected output:** Python functions select_language, select_text, validate_copy.

**Testing:** python -m unittest discover -s tests -v covers this module with synthetic inputs. See validation.md for actual results.

**Troubleshooting:** validate input shape and local permissions; do not bypass failures or point tests at production.

**Limitations:** No CLI, translation or rendered-text verification. Script detection is heuristic, not language understanding. English is default; invalid mode is rejected.

## reliability

**Purpose:** Persist private run checkpoints and bound retries.

**Configuration / activation:** Import the API explicitly; importing performs no business operation.



**Expected output:** Run, lock, atomic_json, identity, state_path APIs.

**Testing:** python -m unittest discover -s tests -v covers this module with synthetic inputs. See validation.md for actual results.

**Troubleshooting:** validate input shape and local permissions; do not bypass failures or point tests at production.

**Limitations:** No CLI or built-in remote adapters. POSIX filesystem locking; no cross-host locking. Unknown outcomes latch; two writes maximum after authoritative absence. Caller callbacks must enforce authorization.

## Reproducibility batch

Added toolkit.trusted_bridge (signed ingress, single confirmation, recipient-bound support receipts) and toolkit.setup_scaffold (inert private workspace setup). See [bridge](trusted-bridge.md) and [setup](../COMPLETE-SETUP-GUIDE.md). These are original application integrations, not native OpenClaw APIs.
