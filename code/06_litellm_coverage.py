#!/usr/bin/env python3
"""Stage 6 — per-model price timelines and coverage by bloc from the LiteLLM event log.

Input : data/raw/litellm/litellm_price_events.csv (stage 4), data/reference/litellm_provider_bloc_map.csv
Output: data/litellm/litellm_model_timelines.csv   one row per (provider, key): first/last day, span, prices, change dates
        data/litellm/litellm_price_changes_vendor_own.csv  every dated input/output price change for vendor-own CN and US chat models
        data/verification/litellm_coverage.md    machine-generated counts for the gate

Rules (judgment calls):
  * Only vendor-own providers (bloc CN or US in the map) count toward the gate; hosts and aggregators are excluded.
  * Only entries whose mode is chat / completion / responses are kept (embeddings, images, audio, rerank excluded).
  * Span = first 'added' day to the 'removed' day, or to the last sampled day if never removed.
  * A price change = a 'changed' event where input or output USD per 1M tokens differs (cache-only changes ignored).
  * Keys are kept as they appear in the catalog (e.g. both 'deepseek-chat' and 'deepseek/deepseek-chat' may exist);
    de-duplication into one row per model happens at the pair-building stage, not here.
"""
import csv, collections, datetime as dt, pathlib
LAST_DAY = None
ev = list(csv.DictReader(open("data/raw/litellm/litellm_price_events.csv")))
LAST_DAY = max(e["day"] for e in ev)
bloc = {r["litellm_provider"]: r["bloc"] for r in csv.DictReader(open("data/reference/litellm_provider_bloc_map.csv"))}
CHAT = {"chat", "completion", "responses"}
def f(x):
    try: return None if x in ("", "None", None) else float(x)
    except ValueError: return None
tl = collections.OrderedDict()
# Group by catalog key only: a key's litellm_provider label can be edited between versions (26 keys were added with
# provider None and labelled later), so grouping by (provider, key) would split one timeline in two.  The latest
# provider label and mode are carried.
for e in sorted(ev, key=lambda e: (e["key"], e["day"])):
    k = e["key"]
    t = tl.setdefault(k, dict(provider=e["litellm_provider"], key=e["key"], mode=e["mode"], first_day=None, removed_day=None, points=[], changes=[]))
    if e["litellm_provider"] not in ("", "None", None): t["provider"] = e["litellm_provider"]
    if e["mode"] not in ("", "None", None): t["mode"] = e["mode"]
    if e["event"] == "added":
        if t["first_day"] is None: t["first_day"] = e["day"]
        t["removed_day"] = None
        t["points"].append((e["day"], f(e["new_input_usd_per_mtok"]), f(e["new_output_usd_per_mtok"])))
    elif e["event"] == "changed":
        oi, oo = f(e["old_input_per_token"]), f(e["old_output_per_token"]); ni, no = f(e["new_input_usd_per_mtok"]), f(e["new_output_usd_per_mtok"])
        oi = None if oi is None else oi * 1e6; oo = None if oo is None else oo * 1e6
        if (oi, oo) != (ni, no):
            t["changes"].append(dict(day=e["day"], commit=e["commit"], old_input=oi, old_output=oo, new_input=ni, new_output=no))
            t["points"].append((e["day"], ni, no))
    elif e["event"] == "removed":
        t["removed_day"] = e["day"]
# Model-family rule (judgment call): a key is the vendor's own price only if the model family belongs to that provider
# (dashscope/qwen-* yes; dashscope/deepseek-* is Alibaba reselling DeepSeek -> bloc RESALE_UNDER_VENDOR).
FAMILY = {"deepseek": ("deepseek",), "dashscope": ("qwen", "qwq", "qvq"), "qwencloud": ("qwen", "qwq", "qvq"), "qwen_ai_platform": ("qwen", "qwq", "qvq"),
          "moonshot": ("moonshot", "kimi"), "zai": ("glm",), "minimax": ("minimax", "abab"), "volcengine": ("doubao",),
          "openai": ("gpt", "o1", "o3", "o4", "chatgpt", "codex", "davinci", "babbage", "ft:", "azure/o"), "anthropic": ("claude",),
          "gemini": ("gemini", "gemma", "learnlm"), "xai": ("grok",), "perplexity": ("sonar", "pplx", "llama", "mistral", "mixtral", "codellama")}
def own_family(p, k):
    b = k.split("/", 1)[1] if "/" in k and not k.startswith("ft:") else k
    return any(b.lower().startswith(x) for x in FAMILY.get(p, ()))
rows, changes_out = [], []
for k, t in tl.items():
    p = t["provider"]; b = bloc.get(p, "OTHER")
    if b in ("CN", "US") and not own_family(p, k): b = "RESALE_UNDER_VENDOR"
    last = t["removed_day"] or LAST_DAY
    span = (dt.date.fromisoformat(last) - dt.date.fromisoformat(t["first_day"])).days
    fp, lp = t["points"][0], t["points"][-1]
    rows.append(dict(bloc=b, provider=p, key=k, mode=t["mode"], first_day=t["first_day"], last_day=last, removed=int(bool(t["removed_day"])), span_days=span,
                     first_input=fp[1], first_output=fp[2], last_input=lp[1], last_output=lp[2], n_price_changes=len(t["changes"]),
                     change_days=";".join(c["day"] for c in t["changes"]), is_chat=int((t["mode"] or "") in CHAT)))
    if b in ("CN", "US") and (t["mode"] or "") in CHAT:
        for c in t["changes"]:
            changes_out.append(dict(bloc=b, provider=p, key=k, **c, direction=("cut" if (c["new_output"] or 0) < (c["old_output"] or 0) or (c["new_input"] or 0) < (c["old_input"] or 0) else "increase_or_mixed")))
pathlib.Path("data/litellm").mkdir(exist_ok=True)
with open("data/litellm/litellm_model_timelines.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
with open("data/litellm/litellm_price_changes_vendor_own.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(changes_out[0].keys())); w.writeheader(); w.writerows(sorted(changes_out, key=lambda r: r["day"]))
L = ["# LiteLLM coverage by bloc (machine-generated by code/06_litellm_coverage.py)", "", f"- Last sampled day: {LAST_DAY}", ""]
for b in ("CN", "US", "RESALE_UNDER_VENDOR", "HOST_US", "HOST", "NEITHER", "OTHER"):
    rs = [r for r in rows if r["bloc"] == b and r["is_chat"]]
    if not rs: continue
    L.append(f"- **{b}** chat-mode entries: {len(rs)}; span >= 365 d: {sum(1 for r in rs if r['span_days']>=365)}; span >= 365 and >= 1 price change: {sum(1 for r in rs if r['span_days']>=365 and r['n_price_changes']>=1)}; still listed (not removed) with span >= 365: {sum(1 for r in rs if r['span_days']>=365 and not r['removed'])}; total price-change events: {sum(r['n_price_changes'] for r in rs)}; earliest first_day: {min(r['first_day'] for r in rs)}")
for b in ("CN", "US"):
    L += ["", f"## {b} vendor-own chat entries with >= 365 days (provider | key | first..last | first price in/out -> last price in/out | changes)"]
    for r in sorted([r for r in rows if r["bloc"] == b and r["is_chat"] and r["span_days"] >= 365], key=lambda r: (r["provider"], r["first_day"], r["key"])):
        L.append(f"- {r['provider']} | {r['key']} | {r['first_day']}..{r['last_day']}{' (removed)' if r['removed'] else ''} | {r['first_input']}/{r['first_output']} -> {r['last_input']}/{r['last_output']} | {r['n_price_changes']}: {r['change_days']}")
L += ["", "## Dated price-change events for vendor-own chat models, by bloc and year"]
c = collections.Counter((r["bloc"], r["day"][:4], r["direction"]) for r in changes_out)
for k in sorted(c): L.append(f"- {k[0]} {k[1]} {k[2]}: {c[k]}")
L += ["", "## Providers seen but not in the bloc map (treated as OTHER)", f"- {sorted({r['provider'] for r in rows if r['bloc']=='OTHER'})}"]
pathlib.Path("data/verification/litellm_coverage.md").write_text("\n".join(L) + "\n"); print("\n".join(L))
