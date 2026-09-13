# Sources

All access attempts on 2026-09-13 (UTC). Per-URL timestamps: `data/verification/reachability_log.tsv`.
"Blocked" = HTTP 403 at the session's egress proxy (organisation network policy), confirmed on two transport
paths (curl through the proxy, and the WebFetch tool). Nothing blocked was retried or routed around.

## Named primary sources

| Source | URL | Status | What was obtained |
|---|---|---|---|
| Gradually LLM Price Index | https://www.gradually.ai/en/llm-price-index/ | Blocked | nothing |
| pricepertoken pricing history | https://pricepertoken.com/pricing-history | Blocked | nothing |
| Shenghao Qiu, LLM Pricing Tracker (page) | https://joshuaqsh.github.io/posts/llm-pricing-tracker/ | Blocked | nothing from the page |
| Shenghao Qiu, LLM Pricing Tracker (repository) | https://github.com/JoshuaQSH/joshuaqsh.github.io | **Obtained** via anonymous git clone, 2026-09-13 ~06:25 UTC; HEAD `c29093f407b7607a0c025718dc75d0913212d6a6` | `data/llm_pricing.json` at 94 commits (2026-03-19 to 2026-09-12); see `data/raw/qiu_tracker/` |
| `llm-price-tracker` (PyPI) | https://pypi.org/project/llm-price-tracker/ (repo: https://github.com/chigwell/llm-price-tracker) | **Obtained** via `pip download`, version 2026.6.121355 | code only; no data |
| Artificial Analysis API | https://artificialanalysis.ai/api/v2/data/llms/models | Blocked | nothing directly; Intelligence Index values for the daily top-10 models arrive second-hand inside the Qiu tracker snapshots |
| Kaggle mirror (LLM Price-Performance Tracker) | https://www.kaggle.com | Blocked | nothing |
| FRED DEXCHUS | https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXCHUS | Blocked | nothing |
| Bank of Canada Valet | https://www.bankofcanada.ca/valet/observations/FXUSDCAD/csv?recent=5 | Blocked | nothing |
| Federal Reserve H.10 (primary publisher of DEXCHUS) | https://www.federalreserve.gov/releases/h10/hist/dat00_ch.htm | Blocked | nothing |

## Upstream pages cited inside the obtained tracker data (not fetched by me; blocked here)

These are the `source` / `official_link` URLs recorded in the tracker's JSON. They are the tracker author's
citations, reproduced so each price row can be traced one step further back.

- https://openai.com/api/pricing/ and https://developers.openai.com/api/docs/pricing
- https://ai.google.dev/gemini-api/docs/pricing
- https://docs.anthropic.com/en/docs/about-claude/models/all-models , https://www.anthropic.com/pricing , https://claude.com/pricing , https://platform.claude.com/docs/en/about-claude/models/overview
- https://api-docs.deepseek.com/quick_start/pricing/
- https://www.alibabacloud.com/help/en/model-studio/model-pricing
- https://platform.kimi.ai/docs/pricing/chat-k26.md , https://platform.kimi.ai/docs/pricing/chat-k27-code.md , https://platform.kimi.ai/
- https://platform.minimax.io/subscribe/token-plan?tab=api-enterprise
- https://platform.xiaomimimo.com/static/docs/pricing.md , https://platform.xiaomimimo.com/static/docs/price/pay-as-you-go.md
- https://x.ai/api , https://docs.x.ai/docs/models/grok-4.3 , https://docs.x.ai/developers/models/grok-4-5 , https://docs.x.ai/developers/grok-4-6
- https://www.together.ai/models/glm-5 , https://www.together.ai/models/glm-52
- https://artificialanalysis.ai/models and https://artificialanalysis.ai/leaderboards/providers (the only pages the tracker's script fetches automatically)

## Pages the PyPI package scrapes at run time (all blocked here)

https://developers.openai.com/api/docs/pricing ; https://docs.anthropic.com/en/docs/about-claude/pricing ;
https://ai.google.dev/gemini-api/docs/pricing ; https://platform.kimi.ai/docs/pricing/chat.md (and chat-v1, chat-k25, chat-k26, chat-k27-code) ;
https://platform.minimax.io/docs/guides/pricing-paygo.md ; https://www.alibabacloud.com/help/en/model-studio/models

## Web searches run (search API reachable; results were used only to identify the tracker's repository)

- "JoshuaQSH llm-pricing-tracker github repository Shenghao Qiu" (2026-09-13 ~06:23 UTC)
- "JoshuaQSH github llm pricing tracker repo snapshots CSV JSON" (2026-09-13 ~06:24 UTC)

Candidate substitute datasets that appeared in those results and were **not accessed**:
https://github.com/simonw/llm-prices , https://github.com/pydantic/genai-prices , https://github.com/tekacs/llm-pricing ,
https://github.com/latitude-dev/llm-pricing , https://github.com/wordenneapolitan768/llm-pricing

## Added at checkpoint 2 (2026-09-13)

| Source | URL | Status | What was obtained |
|---|---|---|---|
| modelpricewatch.com API (proposed by the user) | https://modelpricewatch.com/api/v1/models.json , https://modelpricewatch.com/api/v1/price-history.json , docs https://modelpricewatch.com/api/ | Blocked (proxy 403 on curl and WebFetch, ~07:00 UTC) | nothing directly |
| modelpricewatch.com data repository | https://github.com/romanshumy/llm-prices-data | **Obtained** via anonymous git clone ~07:01 UTC; HEAD `9ec36197e7ad13cbef4754eb6373cb55f9234702`; licence CC-BY-4.0 (attribution: modelpricewatch.com) | `price-history.json`, `models.json`, `providers.json`, `CHANGELOG.md`, `llm-price-index.csv`; see `data/raw/modelpricewatch/` |
| LiteLLM price catalog at a cited commit (verification test only) | https://raw.githubusercontent.com/BerriAI/litellm/41436fefa0/model_prices_and_context_window.json | **Obtained** (HTTP 200) | one file, used to verify one reconstructed point; not used as data |
| Artificial Analysis chart exports | https://artificialanalysis.ai/models | Paywalled (reported by the user) | nothing |
| Gradually, pricepertoken | (as above) | No export exists (reported by the user) | nothing |

Web searches run: "modelpricewatch.com API v1 LLM model pricing history endpoints documentation" and
"modelpricewatch price-history.json github romanshumy llm-prices-data" (~07:00 UTC), used to locate the API file
names and the data repository.
