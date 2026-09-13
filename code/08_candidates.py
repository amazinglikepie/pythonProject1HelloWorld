#!/usr/bin/env python3
"""Stage 8 — candidate models for capability-matched pairing (before any capability score is known).

Input : data/litellm/litellm_model_timelines.csv (stage 6)
Rule  : vendor-own (bloc CN or US), chat mode, span >= 365 days, a non-zero USD price at the end of the timeline.
De-duplication (judgment calls, every exclusion logged with a reason in data/pairs/candidate_exclusions.csv):
  * strip the 'provider/' prefix to get the base name;
  * drop dated variants ('-2025-04-14', '-20250514', '-0430', '-0709', '-1212' ...) and '-latest'/'-beta' aliases when an
    undated base name is also a candidate; otherwise keep the variant (its base may not exist in the catalog);
  * drop fine-tuning ('ft:'), audio / realtime / tts / vision-preview / search-preview / deep-research / thinking-preview
    variants, experimental ('exp') and open-weight-free entries (Gemma, $0 prices), and codellama/llama resales;
  * keep both the with-prefix and without-prefix DeepSeek keys only once (the longer one).
Output: data/pairs/candidates_for_capability_lookup.csv, data/pairs/candidate_exclusions.csv,
        data/pairs/CAPABILITY_LOOKUP_REQUEST.md (the list the project owner reads Intelligence Index values for)
"""
import csv, re, collections
rows = list(csv.DictReader(open("data/litellm/litellm_model_timelines.csv")))
def f(x):
    try: return None if x in ("", "None") else float(x)
    except ValueError: return None
FAMILY = {"deepseek": ("deepseek",), "dashscope": ("qwen", "qwq", "qvq"), "qwencloud": ("qwen", "qwq", "qvq"), "qwen_ai_platform": ("qwen", "qwq", "qvq"),
          "moonshot": ("moonshot", "kimi"), "zai": ("glm",), "minimax": ("minimax", "abab"), "volcengine": ("doubao",),
          "openai": ("gpt", "o1", "o3", "o4", "chatgpt", "codex", "davinci", "babbage"), "anthropic": ("claude",),
          "gemini": ("gemini",), "xai": ("grok",), "perplexity": ("sonar",)}
def own_family(r):
    b = r["key"].split("/", 1)[1] if "/" in r["key"] and not r["key"].startswith("ft:") else r["key"]
    return any(b.lower().startswith(x) for x in FAMILY.get(r["provider"], ()))
pool = [r for r in rows if r["bloc"] in ("CN", "US") and r["is_chat"] == "1" and int(r["span_days"]) >= 365 and own_family(r)]
# context-length tiers of one model (Moonshot) and duplicate spellings of one SKU (Anthropic): keep the first, log the rest
TIER_OR_DUP = {"moonshot-v1-8k": "moonshot-v1-128k", "moonshot-v1-32k": "moonshot-v1-128k", "moonshot-v1-auto": "moonshot-v1-128k",
               "kimi-latest-8k": "kimi-latest-128k", "kimi-latest-32k": "kimi-latest-128k", "kimi-latest": "kimi-latest-128k",
               "claude-4-opus-20250514": "claude-opus-4-20250514", "claude-4-sonnet-20250514": "claude-sonnet-4-20250514",
               "gemini-2.0-flash-001": "gemini-2.0-flash", "gemini-1.5-pro-001": "gemini-1.5-pro", "gemini-1.5-pro-002": "gemini-1.5-pro",
               "gemini-1.5-flash-001": "gemini-1.5-flash-latest", "gemini-1.5-flash-002": "gemini-1.5-flash-latest",
               "gemini-2.0-flash-lite-preview-02-05": "gemini-2.0-flash-lite", "gemini-2.5-flash-lite-preview-06-17": "gemini-2.5-flash-lite",
               "gpt-4-1106-preview": "gpt-4-turbo", "gpt-4-0125-preview": "gpt-4-turbo", "gpt-4-turbo-preview": "gpt-4-turbo",
               "chatgpt-4o-latest": "gpt-4o", "gpt-3.5-turbo-16k-0613": "gpt-3.5-turbo", "gpt-4-32k": "gpt-4-0314", "grok-vision-beta": "grok-beta", "grok-2-vision": "grok-2"}
excl, keep = [], []
def base(k): return k.split("/", 1)[1] if "/" in k and not k.startswith("ft:") else k
names = {base(r["key"]) for r in pool}
DATED = re.compile(r"[-@](20\d{2}-\d{2}-\d{2}|20\d{6}|\d{4})$")
BAD = re.compile(r"(^ft:|audio|realtime|tts|vision-preview|search-preview|deep-research|thinking-preview|-exp|exp-\d|gemma|learnlm|codellama|llama|mixtral|mistral-7b|pplx-|sonar-(small|medium)|instant|preview-tts|coder)", re.I)
for r in pool:
    k = r["key"]; b = base(k); li, lo = f(r["last_input"]), f(r["last_output"])
    reason = None
    if li is None or lo is None: reason = "no price in catalog at end of timeline"
    elif li == 0 and lo == 0: reason = "free/experimental ($0) entry, not a list price"
    elif BAD.search(b): reason = "variant excluded by rule (fine-tune/audio/realtime/vision/search/research/experimental/open-weight-free/resold model)"
    elif DATED.search(b) and DATED.sub("", b) in names: reason = f"dated variant of '{DATED.sub('', b)}'"
    elif b.endswith("-latest") and b[:-7] in names: reason = f"'-latest' alias of '{b[:-7]}'"
    elif b.endswith("-beta") and b[:-5] in names: reason = f"'-beta' alias of '{b[:-5]}'"
    elif b.endswith("-fast-latest") or b.endswith("-fast-beta") or b.endswith("-fast"): reason = "xAI 'fast' tier (same model, higher price tier)"
    elif b.endswith("-0430") or b.endswith("-0709") or b.endswith("-1212"): reason = "dated variant"
    elif b in TIER_OR_DUP: reason = f"context-length tier or duplicate spelling of '{TIER_OR_DUP[b]}'"
    if reason: excl.append(dict(bloc=r["bloc"], provider=r["provider"], key=k, reason=reason)); continue
    keep.append(r)
# collapse with/without provider prefix duplicates (e.g. 'deepseek-chat' and 'deepseek/deepseek-chat')
byb = collections.defaultdict(list)
for r in keep: byb[(r["provider"], base(r["key"]))].append(r)
final = []
for (p, b), rs in byb.items():
    rs.sort(key=lambda r: -int(r["span_days"]))
    final.append(rs[0])
    for r in rs[1:]: excl.append(dict(bloc=r["bloc"], provider=r["provider"], key=r["key"], reason=f"same model as '{rs[0]['key']}' (shorter timeline)"))
final.sort(key=lambda r: (r["bloc"], r["provider"], r["first_day"]))
with open("data/pairs/candidates_for_capability_lookup.csv", "w", newline="") as fh:
    cols = ["bloc", "provider", "key", "base_name", "first_day", "last_day", "removed", "span_days", "first_input", "first_output", "last_input", "last_output", "n_price_changes", "change_days"]
    w = csv.DictWriter(fh, fieldnames=cols + ["aa_intelligence_index", "aa_index_version", "aa_page_url", "lookup_date"]); w.writeheader()
    for r in final: w.writerow({**{c: (base(r["key"]) if c == "base_name" else r[c]) for c in cols}, "aa_intelligence_index": "", "aa_index_version": "", "aa_page_url": "", "lookup_date": ""})
with open("data/pairs/candidate_exclusions.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["bloc", "provider", "key", "reason"]); w.writeheader(); w.writerows(excl)
cn = [r for r in final if r["bloc"] == "CN"]; us = [r for r in final if r["bloc"] == "US"]
L = ["# Capability lookup request", "",
     f"Candidates with >= 365 days of dated catalog price history: **{len(cn)} Chinese-vendor models** and **{len(us)} US-vendor models** "
     f"(from {len(pool)} raw entries; {len(excl)} excluded as aliases, dated variants, non-list or non-chat entries, see candidate_exclusions.csv).", "",
     "For each model below, open its page on https://artificialanalysis.ai/models (search the model name), and write down the",
     "**Intelligence Index** number shown, the index version if shown (e.g. v4), the page URL, and the date. Models that no",
     "longer appear on the site get 'not listed' — that is a valid answer and is recorded as such.", ""]
for b, rs in (("Chinese vendors", cn), ("US vendors", us)):
    L += [f"## {b}", "", "| # | Provider | Model (catalog key) | Priced since | Current price in / out (USD per 1M) | Intelligence Index | Index version | Page URL |", "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rs, 1): L.append(f"| {i} | {r['provider']} | `{base(r['key'])}` | {r['first_day']} | {r['last_input']} / {r['last_output']} |  |  |  |")
    L.append("")
open("data/pairs/CAPABILITY_LOOKUP_REQUEST.md", "w").write("\n".join(L) + "\n")
print(f"candidates: CN {len(cn)}, US {len(us)}; excluded {len(excl)}")
for r in final: print(f"  {r['bloc']} {r['provider']:<10} {base(r['key']):<40} {r['first_day']}..{r['last_day']} {r['last_input']}/{r['last_output']} changes={r['n_price_changes']}")
