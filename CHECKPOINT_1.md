# Checkpoint 1 — data verification (the hard gate)

**Verdict: the gate is not cleared. No analysis was run.**

Two independent reasons:

1. Four of the five named price/capability sources, and every exchange-rate source, are blocked by this
   session's network egress policy. The block is at the proxy (HTTP 403 on CONNECT), identical on two
   transport paths, and the proxy's own documentation classifies it as an organisation policy denial that
   must not be retried or routed around.
2. The one source that could be obtained (the Shenghao Qiu tracker, via its GitHub repository) covers
   **177 days**, contains **5 dated price-change events**, and has no second source to cross-check against.

Access date for everything in this document: **2026-09-13** (UTC timestamps per URL are in
`data/verification/reachability_log.tsv`). Nothing below is interpolated or estimated.

## 1. Source reachability

| # | Source | URL tried | curl via session proxy | WebFetch tool |
|---|---|---|---|---|
| 1 | Gradually LLM Price Index | https://www.gradually.ai/en/llm-price-index/ | CONNECT 403 (policy) | EGRESS_BLOCKED |
| 2 | pricepertoken pricing history | https://pricepertoken.com/pricing-history | CONNECT 403 (policy) | EGRESS_BLOCKED |
| 3 | Shenghao Qiu tracker (blog page) | https://joshuaqsh.github.io/posts/llm-pricing-tracker/ | CONNECT 403 (policy) | EGRESS_BLOCKED |
| 3b | Qiu tracker (its GitHub repo) | https://github.com/JoshuaQSH/joshuaqsh.github.io | **git clone OK** (anonymous read via session git proxy) | n/a |
| 4 | Artificial Analysis API | https://artificialanalysis.ai/api/v2/data/llms/models | CONNECT 403 (policy) | EGRESS_BLOCKED |
| 4b | Kaggle mirror | https://www.kaggle.com | CONNECT 403 (policy) | not tried |
| 5 | FRED DEXCHUS (CSV) | https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXCHUS | CONNECT 403 (policy) | EGRESS_BLOCKED |
| 5b | Bank of Canada Valet | https://www.bankofcanada.ca/valet/observations/FXUSDCAD/csv?recent=5 | CONNECT 403 (policy) | not tried |
| 5c | Fed H.10 (primary publisher of DEXCHUS) | https://www.federalreserve.gov/releases/h10/hist/dat00_ch.htm | CONNECT 403 (policy) | not tried |
| 6 | llm-price-tracker (PyPI) | https://pypi.org/project/llm-price-tracker/ | **pip download OK** (PyPI bypasses the proxy) | n/a |
| – | Wayback Machine | https://web.archive.org/ | CONNECT 403 (policy) | not tried |
| – | Provider pricing pages (DeepSeek, OpenAI, Anthropic) | see reachability log | CONNECT 403 (policy) | not tried |
| – | raw.githubusercontent.com (control) | https://raw.githubusercontent.com/openai/openai-cookbook/main/README.md | **200** | n/a |

What is reachable from this session: anonymous git reads of public GitHub repositories,
raw.githubusercontent.com, and the PyPI package index. Nothing else that was tested.

## 2. What actually came back

### 2a. Shenghao Qiu tracker — obtained from its own repository

The rendered page is blocked, but it is a GitHub Pages site built from the public repository
`JoshuaQSH/joshuaqsh.github.io`. I cloned that repository (HEAD `c29093f407b7607a0c025718dc75d0913212d6a6`,
committed 2026-09-12T10:48:37Z) and extracted every historical version of `data/llm_pricing.json`, which a
scheduled GitHub Actions job rewrites daily and commits only when the content changed. Each such commit is a
dated snapshot. This is the source you named, read at its origin rather than at the rendered page; I do not
treat it as a substitution. Extraction code: `code/01_extract_qiu_tracker.py`. Raw output:
`data/raw/qiu_tracker/`. Provenance (commit hash and time per snapshot): `data/verification/qiu_tracker_commits.tsv`.

Counts are machine-generated (`data/verification/qiu_tracker_inventory.md`):

| Item | Value |
|---|---|
| Dated snapshots | 94 |
| Snapshot window | 2026-03-19 to 2026-09-12 (177 days, 0.48 years) |
| `api_pricing`: distinct vendor/product rows ever present | 43 (CN bloc 17, US bloc 23, neither 3) |
| `api_pricing`: longest single-product observation span | 177 days |
| `api_pricing`: products with >= 365 days of history | 0 |
| `api_pricing`: dated price-change events (same product, consecutive snapshots differ) | 5, of which 4 dated 2026-08-17 |
| `history_series` (curated flagship lines): distinct points, all commits | 46 across 10 vendor lines |
| `history_series`: distinct point dates | 12; only 3 precede 2026-03-19 and all 3 were later removed by the author |
| `benchmark_snapshot` (Artificial Analysis Intelligence Index): coverage | top-10 models per day only; 54 distinct models over 87 days (CN 18, US 36) |
| `provider_leaderboard`: coverage | 25 host-providers x 4 metrics per day; best endpoint per host, not per model |
| `scale_price_frontier`: output-price rows since 2021 | 13 ("highest public output price by year"; not relevant to the question) |

**How the dates arise (matters for the lead-lag design).** The refresh script fetches only
`artificialanalysis.ai` and `together.ai`. The vendor list-price rows are carried forward from the committed
JSON and change only when the author edits them by hand. The same dates therefore recur across unrelated
vendors (2026-03-19, 2026-05-20, 2026-06-18, 2026-07-04, 2026-08-17 each appear in several vendor lines);
a few points carry what look like release dates (GPT-5.6 Sol 2026-07-09, Grok 4.5 2026-07-08). So the price
dates in this source are mostly curation dates, not provider announcement dates. Even with a longer window
this source could not support a 30/60/90-day lead-lag test.

Verification: the script's only HTTP fetch function is called for `artificialanalysis.ai/models`,
`artificialanalysis.ai/leaderboards/providers` and `together.ai/models/glm-52`. Of the 94 snapshot commits,
13 are hand edits by the author (`data/verification/qiu_tracker_commits.tsv`, `author` column), dated
2026-03-19, 04-01, 04-03, 04-24, 04-29, 05-20, 06-18, 07-04, 07-13 and 08-17; every one of the five
price-change events and nearly every `history_series` point date coincides with one of those edits.

Bloc classification is a judgment call and is logged in `data/reference/bloc_map.csv`. One notable choice:
GLM prices in this source are Together AI's (a US host), not Z.ai's own list price, so they are excluded
from the Chinese-provider price set.

### 2b. `llm-price-tracker` (PyPI) — obtained, but no data

Version 2026.6.121355, 23 kB, pure code, no bundled snapshots. It scrapes official pricing pages at run
time (URL list in `SOURCES.md`); every one of those pages is blocked here. It contributes nothing in this
environment.

### 2c. Gradually, pricepertoken, Artificial Analysis API, FRED, Bank of Canada — not obtained

Blocked on every path tried. No date ranges, model counts, or event counts can be reported for them.

## 3. Gate criteria

| Criterion (from your brief) | Required | Obtained | Cleared? |
|---|---|---|---|
| Each price-history source reachable and exportable | all | 1 of 3 price-history sources (via repo); capability API blocked | No |
| Cross-check overlapping models across >= 2 price sources | yes | impossible with one source | No |
| >= ~8 capability-matched pairs with >= 12 months of price history | >= 8 | 0 (longest span 177 days) | No |
| FX series covering the full window | yes | none obtained | No |
| Capability scores for pair matching | yes | Intelligence Index for the daily top-10 only, 177 days | Partial |

## 4. What I deliberately did not do

- Did not fetch, clone, or read any source you did not name. GitHub-hosted price datasets that surfaced in a
  web search are listed under option C below; none was accessed.
- Did not retry or route around any policy denial.
- Did not interpolate, fill, match pairs, or compute anything beyond the inventory counts above.

## 5. Decision needed before anything else happens

Options, my recommendation first:

**A. You fetch the blocked files on your own machine and commit them to this repository (recommended).**
The session can read anything pushed to GitHub. You would be the fetcher of record, with your own access
date, and nothing is substituted. Suggested paths and exact URLs:

| File to commit | Fetch from | Notes |
|---|---|---|
| `data/raw/fx/DEXCHUS.csv` | https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXCHUS | direct CSV download, full history |
| `data/raw/gradually/...` | https://www.gradually.ai/en/llm-price-index/ | I could not see the page, so I cannot confirm an export exists; if it offers CSV/JSON, commit that, otherwise a saved copy of the page |
| `data/raw/pricepertoken/...` | https://pricepertoken.com/pricing-history | same caveat |
| `data/raw/artificial_analysis/models.json` | https://artificialanalysis.ai/api/v2/data/llms/models | likely needs a free API key per their docs (unverified from here); or the Kaggle "LLM Price-Performance Tracker" CSV |

Risk: these sources may also prove shallow, in which case the gate still fails, but we would know from
primary data.

**B. Have the environment administrator allow the blocked hosts** (www.gradually.ai, pricepertoken.com,
joshuaqsh.github.io, artificialanalysis.ai, fred.stlouisfed.org, plus bankofcanada.ca, federalreserve.gov
and web.archive.org for archived pricing pages), then I re-run `code/00_probe_sources.sh`.

**C. Approve GitHub-hosted substitutes.** Candidates surfaced by search, not accessed, depth unknown:
`simonw/llm-prices`, `pydantic/genai-prices`, `tekacs/llm-pricing`, `latitude-dev/llm-pricing`,
`wordenneapolitan768/llm-pricing`. I would inspect each and report its date range and model coverage
before using any. Provenance is weaker than A.

**D. Stop here.**

For calibration: the one source in hand could at best support a 177-day cross-sectional picture of the
price ratio at roughly six curation dates for a handful of capability-matched pairs. It cannot support the
12-month trend, the decomposition over FX sub-periods, or the lead-lag test as designed.
