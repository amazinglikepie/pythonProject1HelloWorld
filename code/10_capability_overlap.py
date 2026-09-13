#!/usr/bin/env python3
"""Stage 10 — capability-score coverage, and the identity-stability audit of the candidate set.

Part 1: how many of the 68 price-history candidates have an Intelligence Index anywhere in the data obtained?
Part 2: does the Artificial Analysis 646-model registry list them at all (i.e. could a score be obtained)?
Part 3: is each candidate a FIXED model or a ROLLING API alias?  A rolling alias keeps one billing name while the
        model behind it is replaced; its price series is continuous but its capability is not, so it cannot be
        capability-matched to a fixed US snapshot.  Detected from the LiteLLM event log: a key is classed ROLLING
        if its advertised context window changes, or if its name carries no date/version stamp while its price
        changes more than once.  Hand-checked exceptions are listed in ROLLING_OVERRIDE.

Matching: normalised names plus an explicit alias table (LiteLLM API keys use SKU ids like
`gpt-4o-2024-11-20`; the Artificial Analysis registry uses display names like "GPT-4o (Nov '24)").
Every unmatched candidate is reported, never silently dropped.

Outputs: data/pairs/capability_join.csv, data/verification/capability_overlap.md
"""
import csv, re, collections, pathlib

MONTH = {"01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "June", "07": "July",
         "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}

def strip_quals(s):
    s = re.sub(r"\((?:max|high|xhigh|low|medium|reasoning|non-reasoning|adaptive[^)]*|with fallback|[^)]*effort[^)]*|[^)]*fallback[^)]*)\)", " ", s, flags=re.I)
    return s

def norm(s):
    s = (s or "").lower()
    s = strip_quals(s)
    s = re.sub(r"\(.*?\)", " ", s)
    s = s.split("/", 1)[1] if "/" in s and not s.startswith("ft:") else s
    return re.sub(r"[^a-z0-9]+", "", s)

def variants(base):
    """Candidate API key -> the display-name spellings Artificial Analysis might use."""
    out = {norm(base)}
    b = base.lower()
    m = re.search(r"(.*?)-(20\d{2})-?(\d{2})-?(\d{2})$", b)            # gpt-4o-2024-11-20 / claude-3-5-sonnet-20241022
    if m:
        stem, y, mo, _ = m.groups()
        out.add(norm(stem))
        out.add(norm(f"{stem} ({MONTH[mo]} '{y[2:]})"))
        out.add(norm(f"{stem} {MONTH[mo]} {y}"))
    m2 = re.search(r"(.*?)-(\d{3})$", b)                                 # gemini-1.5-pro-002
    if m2: out.add(norm(m2.group(1)))
    out.add(norm(b.replace("-", " ")))
    return {v for v in out if v}

cand = list(csv.DictReader(open("data/pairs/candidates_for_capability_lookup.csv")))
full = list(csv.DictReader(open("data/raw/artificial_analysis/aa_full_records.csv")))
pts  = list(csv.DictReader(open("data/raw/artificial_analysis/aa_jsonld_points.csv")))
reg  = list(csv.DictReader(open("data/raw/artificial_analysis/aa_model_registry.csv")))
qiu  = list(csv.DictReader(open("data/raw/qiu_tracker/tracker_benchmark_snapshot_all_commits.csv")))
ev   = list(csv.DictReader(open("data/raw/litellm/litellm_price_events.csv")))

scored = {}
for r in full:
    if r["intelligence_index"]:
        for k in (norm(r["name"]), norm(r["release_name"])):
            scored.setdefault(k, ("aa_page_full", r["name"], float(r["intelligence_index"])))
for p in pts:
    if p["sub_metric"] == "intelligenceIndex" and p["value"]:
        scored.setdefault(norm(p["label"]), ("aa_page_chart", p["label"], float(p["value"])))
qiu_scored = {}
for r in qiu:
    if r.get("intelligence"):
        for k in (norm(r["model"]), norm(r.get("short_label"))):
            qiu_scored.setdefault(k, (r["model"], float(r["intelligence"])))
registry = {}
for r in reg:
    for k in (norm(r["name"]), norm(r["release_name"])):
        if k: registry.setdefault(k, r)

# identity stability from the event log
evk = collections.defaultdict(list)
for e in ev: evk[e["key"]].append(e)
ROLLING_OVERRIDE = {  # hand-checked; reason recorded in the output
    "moonshot-v1-128k": ("FIXED", "context-tier SKU of a versioned family; context window constant at 131072"),
    "kimi-latest-128k": ("ROLLING", "'latest' alias by construction"),
    "kimi-latest": ("ROLLING", "'latest' alias by construction"),
    "chatgpt-4o-latest": ("ROLLING", "'latest' alias by construction"),
    "codex-mini-latest": ("ROLLING", "'latest' alias by construction"),
}
DATED = re.compile(r"(20\d{2}-?\d{2}-?\d{2}|-\d{3,4}$|\d\.\d)")
def identity(key, base):
    if base in ROLLING_OVERRIDE: return ROLLING_OVERRIDE[base]
    rows = [e for e in evk.get(key, []) if e["event"] in ("added", "changed")]
    ctxs = {e["max_input_tokens"] for e in rows if e["max_input_tokens"] not in ("", "None")}
    if len(ctxs) > 1: return ("ROLLING", f"advertised context window changed: {sorted(ctxs)}")
    if base.endswith("-latest"): return ("ROLLING", "'latest' alias by construction")
    if not DATED.search(base) and len(rows) > 2: return ("ROLLING", f"undated name with {len(rows)} price revisions")
    return ("FIXED", "dated or versioned name, context window constant")

rows = []
for c in cand:
    vs = variants(c["base_name"])
    s = next((scored[v] for v in vs if v in scored), None)
    q = next((qiu_scored[v] for v in vs if v in qiu_scored), None)
    g = next((registry[v] for v in vs if v in registry), None)
    ident, why = identity(c["key"], c["base_name"])
    rows.append(dict(bloc=c["bloc"], provider=c["provider"], key=c["key"], base_name=c["base_name"],
                     first_day=c["first_day"], last_day=c["last_day"], span_days=c["span_days"],
                     last_input=c["last_input"], last_output=c["last_output"], n_price_changes=c["n_price_changes"],
                     identity=ident, identity_reason=why,
                     aa_scored=int(bool(s)), aa_label=(s[1] if s else ""), aa_index=(s[2] if s else ""),
                     qiu_scored=int(bool(q)), qiu_index=(q[1] if q else ""),
                     in_aa_registry=int(bool(g)), registry_name=(g["name"] if g else ""), registry_slug=(g["slug"] if g else ""),
                     registry_release_date=(g["release_date"] if g else ""), registry_deprecated=(g["deprecated"] if g else "")))
with open("data/pairs/capability_join.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

def c_(b, **kw): return sum(1 for r in rows if r["bloc"] == b and all(r[k] == v for k, v in kw.items()))
L = ["# Capability-score coverage and identity audit of the price-history candidates", "",
     "Machine-generated by `code/10_capability_overlap.py`. Access date 2026-09-13.", "",
     "## 1. Do the candidates have a capability score?", "",
     "| Bloc | Candidates (>= 365 d price history) | Scored in the saved AA page | Scored in the Qiu daily top-10 | Listed in the AA 646-model registry (score obtainable) | Not listed at all |",
     "|---|---|---|---|---|---|"]
for b in ("CN", "US"):
    n = sum(1 for r in rows if r["bloc"] == b)
    L.append(f"| {b} | {n} | **{c_(b, aa_scored=1)}** | **{c_(b, qiu_scored=1)}** | {c_(b, in_aa_registry=1)} | {c_(b, in_aa_registry=0)} |")
L += ["", "The saved page embeds scores only for the models selected in its chart (the \"26 of 646\" control) plus the",
      "chart top-20: **25 distinct models, 24 of them released in 2026**. None of the 68 candidates is among them.", "",
      "## 2. Fixed model or rolling API alias?", "",
      "A rolling alias keeps one billing name while the model behind it is replaced. Its price series is continuous;",
      "its capability is not. Pairing a rolling Chinese alias against a frozen US snapshot compares a moving target",
      "to a fixed one, so identity is reported before any pairing is attempted.", "",
      "| Bloc | Candidates | FIXED identity | ROLLING alias |", "|---|---|---|---|"]
for b in ("CN", "US"):
    L.append(f"| {b} | {sum(1 for r in rows if r['bloc']==b)} | {c_(b, identity='FIXED')} | **{c_(b, identity='ROLLING')}** |")
L += ["", "### Chinese candidates in detail", "",
      "| Model (catalog key) | Provider | Priced | Span (d) | Price changes | Identity | Why | In AA registry |", "|---|---|---|---|---|---|---|---|"]
for r in [r for r in rows if r["bloc"] == "CN"]:
    L.append(f"| `{r['base_name']}` | {r['provider']} | {r['first_day']} to {r['last_day']} | {r['span_days']} | {r['n_price_changes']} | **{r['identity']}** | {r['identity_reason']} | {r['registry_name'] or 'not listed'} |")
L += ["", "### US candidates, summary by identity", ""]
for ident in ("FIXED", "ROLLING"):
    ks = [r["base_name"] for r in rows if r["bloc"] == "US" and r["identity"] == ident]
    L.append(f"- **{ident}** ({len(ks)}): {', '.join('`'+k+'`' for k in ks)}")
L += ["", "## 3. The 25 scored models in the saved page, and their dated price history", "",
      "| Model | Creator | Index | Released | Longest dated price history in the LiteLLM catalog |", "|---|---|---|---|---|"]
tl = list(csv.DictReader(open("data/litellm/litellm_model_timelines.csv")))
tlb = collections.defaultdict(list)
for t in tl: tlb[norm(t["key"])].append(int(t["span_days"]))
for r in sorted(full, key=lambda r: -(float(r["intelligence_index"]) if r["intelligence_index"] else 0)):
    if not r["intelligence_index"]: continue
    sp = max((max(tlb[v]) for v in variants(r["name"]) | variants(r["release_name"] or "") if v in tlb), default=None)
    L.append(f"| {r['name']} | {r['creator']} ({r['creator_country']}) | {float(r['intelligence_index']):.2f} | {r['release_date']} | {str(sp) + ' d' if sp is not None else 'not matched in catalog'} |")
pathlib.Path("data/verification/capability_overlap.md").write_text("\n".join(L) + "\n")
print("\n".join(L[:60]))
