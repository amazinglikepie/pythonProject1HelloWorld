#!/usr/bin/env python3
"""Stage 7 — cross-check the LiteLLM catalog history against the two other sources, and measure its date lag.

Reference A: Qiu tracker api_pricing rows (official-page snapshots, hand-curated; dates are curation dates).
Reference B: modelpricewatch own-captured change events (event in price_change/price_drop/price_increase, dated
             2026-06-25 or later; these carry the site's "verified" label and precede Qiu's curation dates).
Subject    : LiteLLM catalog timelines rebuilt from data/raw/litellm/litellm_price_events.csv.

Matching (judgment call): names normalised (lower-case, provider prefix and parentheticals removed, non-alphanumerics
stripped, DeepSeek date suffixes 0731/0813 stripped); exact match on the normalised string, plus a short alias table
printed below.  Unmatched products are listed, not silently dropped.

Outputs: data/verification/crosscheck_litellm_vs_qiu.csv      (one row per Qiu snapshot row with a LiteLLM match)
         data/verification/crosscheck_litellm_lag.csv         (one row per reference change event: nearest LiteLLM change, lag in days)
         printed summary
"""
import csv, re, collections, datetime as dt
ALIASES = {"gpt56sol": "gpt56sol", "claudeopus5": "claudeopus5"}
def norm(s):
    s = s.lower(); s = re.sub(r"\(.*?\)", "", s); s = s.split("/", 1)[1] if "/" in s and not s.startswith("ft:") else s
    s = re.sub(r"[^a-z0-9]+", "", s); return s.replace("0813", "").replace("0731", "")
def f(x):
    try: return None if x in ("", "None", None) else float(x)
    except ValueError: return None
# --- rebuild LiteLLM timelines: key -> list of (day, input, output)
ev = list(csv.DictReader(open("data/raw/litellm/litellm_price_events.csv")))
tl = collections.defaultdict(list); prov = {}
for e in sorted(ev, key=lambda e: (e["key"], e["day"])):
    k = e["key"]
    if e["litellm_provider"] not in ("", "None"): prov[k] = e["litellm_provider"]
    if e["event"] in ("added", "changed"): tl[k].append((e["day"], f(e["new_input_usd_per_mtok"]), f(e["new_output_usd_per_mtok"])))
    elif e["event"] == "removed": tl[k].append((e["day"], None, None))
bloc = {r["litellm_provider"]: r["bloc"] for r in csv.DictReader(open("data/reference/litellm_provider_bloc_map.csv"))}
# Model-family rule (judgment call): a key counts as the vendor's own price only if the model family belongs to that
# provider, e.g. dashscope/qwen-* yes, dashscope/deepseek-* no (Alibaba reselling DeepSeek).
FAMILY = {"deepseek": ("deepseek",), "dashscope": ("qwen", "qwq", "qvq"), "qwencloud": ("qwen", "qwq", "qvq"), "qwen_ai_platform": ("qwen", "qwq", "qvq"),
          "moonshot": ("moonshot", "kimi"), "zai": ("glm",), "minimax": ("minimax", "abab"), "volcengine": ("doubao",),
          "openai": ("gpt", "o1", "o3", "o4", "chatgpt", "codex", "davinci", "babbage", "ft:", "azure/o"), "anthropic": ("claude",),
          "gemini": ("gemini", "gemma", "learnlm"), "xai": ("grok",), "perplexity": ("sonar", "pplx", "llama", "mistral", "mixtral", "codellama")}
def own_family(k):
    p = prov.get(k, ""); b = k.split("/", 1)[1] if "/" in k and not k.startswith("ft:") else k
    return any(b.lower().startswith(x) for x in FAMILY.get(p, ()))
vendor_keys = [k for k in tl if bloc.get(prov.get(k, ""), "") in ("CN", "US") and own_family(k)]
by_norm = collections.defaultdict(list)
for k in vendor_keys: by_norm[norm(k)].append(k)
def price_on(k, day):
    best = None
    for d, i, o in tl[k]:
        if d <= day: best = (d, i, o)
    return best
def change_days(k):
    out, prev = [], None
    for d, i, o in tl[k]:
        if prev is not None and (i, o) != prev and i is not None: out.append((d, prev, (i, o)))
        if i is not None: prev = (i, o)
    return out
# --- A: Qiu snapshot rows
qiu = list(csv.DictReader(open("data/raw/qiu_tracker/tracker_api_pricing_all_commits.csv")))
rowsA, unmatched = [], set()
for r in qiu:
    if r["input_value"] in ("", "None"): continue
    cands = by_norm.get(norm(r["product"]), [])
    if not cands: unmatched.add((r["vendor"], r["product"])); continue
    for k in cands:
        p = price_on(k, r["commit_date"])
        if not p or p[1] is None: rowsA.append(dict(date=r["commit_date"], qiu_vendor=r["vendor"], qiu_product=r["product"], litellm_key=k, litellm_provider=prov.get(k), qiu_input=r["input_value"], qiu_output=r["output_value"], litellm_input="", litellm_output="", litellm_point_day=(p[0] if p else ""), result="NO_LITELLM_PRICE_YET")); continue
        agree = abs(float(r["input_value"]) - p[1]) < 1e-9 and abs(float(r["output_value"]) - p[2]) < 1e-9
        rowsA.append(dict(date=r["commit_date"], qiu_vendor=r["vendor"], qiu_product=r["product"], litellm_key=k, litellm_provider=prov.get(k), qiu_input=r["input_value"], qiu_output=r["output_value"], litellm_input=p[1], litellm_output=p[2], litellm_point_day=p[0], result="AGREE" if agree else "DISAGREE"))
with open("data/verification/crosscheck_litellm_vs_qiu.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rowsA[0].keys())); w.writeheader(); w.writerows(rowsA)
c = collections.Counter(r["result"] for r in rowsA)
print("A. LiteLLM vs Qiu, all snapshot rows with a name match:", dict(c))
print("   distinct Qiu products matched:", len({(r['qiu_vendor'], r['qiu_product']) for r in rowsA}), "| unmatched Qiu products:", len(unmatched))
for u in sorted(unmatched): print("     unmatched:", u)
dis = collections.Counter((r["qiu_vendor"], r["qiu_product"], r["litellm_key"], r["qiu_input"], r["qiu_output"], r["litellm_input"], r["litellm_output"]) for r in rowsA if r["result"] == "DISAGREE")
print("   DISAGREE patterns (vendor, product, key, qiu in/out, litellm in/out): n_days")
for k, n in dis.most_common(): print("    ", k, n)
# --- lag: reference change events -> nearest LiteLLM change for the same model
lag_rows = []
# A-ref: Qiu product-level changes (consecutive snapshots differ)
qby = collections.defaultdict(list)
for r in sorted(qiu, key=lambda r: r["commit_date"]): qby[(r["vendor"], r["product"])].append(r)
refs = []
for (v, p), rs in qby.items():
    prev = None
    for r in rs:
        cur = (r["input_value"], r["output_value"])
        if prev is not None and cur != prev: refs.append(dict(ref_source="qiu_curation", ref_model=p, ref_day=r["commit_date"], ref_old=prev, ref_new=cur, nkey=norm(p)))
        prev = cur
# B-ref: modelpricewatch own-captured changes
mpw = list(csv.DictReader(open("data/raw/modelpricewatch/price_history_points.csv")))
mpw_by = collections.defaultdict(list)
for r in mpw: mpw_by[r["model_id"]].append(r)
mbloc = {r["vendor_string"]: r["bloc"] for r in csv.DictReader(open("data/reference/bloc_map.csv"))}
for mid, rs in mpw_by.items():
    if mbloc.get(rs[0]["provider"], "") not in ("CN", "US"): continue
    prev = None
    for r in sorted(rs, key=lambda r: r["date"]):
        cur = (r["input_per_mtok"], r["output_per_mtok"])
        if r["event"] in ("price_change", "price_drop", "price_increase") and r["date"] >= "2026-06-25" and prev is not None and cur != prev:
            refs.append(dict(ref_source="modelpricewatch_verified", ref_model=rs[0]["model"], ref_day=r["date"], ref_old=prev, ref_new=cur, nkey=norm(rs[0]["model"])))
        prev = cur
for ref in refs:
    cands = by_norm.get(ref["nkey"], [])
    best = None
    for k in cands:
        for d, old, new in change_days(k):
            lag = (dt.date.fromisoformat(d) - dt.date.fromisoformat(ref["ref_day"])).days
            if best is None or abs(lag) < abs(best[0]): best = (lag, k, d, old, new)
    lag_rows.append(dict(ref_source=ref["ref_source"], ref_model=ref["ref_model"], ref_day=ref["ref_day"], ref_old=str(ref["ref_old"]), ref_new=str(ref["ref_new"]),
                         litellm_key=(best[1] if best else ""), litellm_change_day=(best[2] if best else ""), litellm_old=(str(best[3]) if best else ""), litellm_new=(str(best[4]) if best else ""),
                         lag_days_litellm_minus_ref=(best[0] if best else ""), matched=int(bool(cands)), litellm_has_any_change=int(bool(best))))
with open("data/verification/crosscheck_litellm_lag.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(lag_rows[0].keys())); w.writeheader(); w.writerows(lag_rows)
print("\nB. Date lag of LiteLLM change vs reference change events (positive = catalog later than reference):")
for src in ("qiu_curation", "modelpricewatch_verified"):
    rs = [r for r in lag_rows if r["ref_source"] == src]
    lags = [r["lag_days_litellm_minus_ref"] for r in rs if r["lag_days_litellm_minus_ref"] != ""]
    print(f"   {src}: reference events {len(rs)}, name-matched {sum(r['matched'] for r in rs)}, with a LiteLLM change found {len(lags)}, lags(days) = {sorted(lags)}")
    for r in rs: print(f"     {r['ref_day']} {r['ref_model'][:32]:<32} {r['ref_old']}->{r['ref_new']}  | litellm {r['litellm_key'][:30]:<30} {r['litellm_change_day']} {r['litellm_old']}->{r['litellm_new']} lag={r['lag_days_litellm_minus_ref']}")
