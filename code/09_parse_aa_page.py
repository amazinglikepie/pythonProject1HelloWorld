#!/usr/bin/env python3
"""Stage 9 — extract model data from a saved copy of https://artificialanalysis.ai/models

The saved page carries THREE structures with different coverage.  All three are extracted; none is mixed:

  A. `initialModels` — the models the page had selected when it was saved (the "26 of 646" selector).
     Full records: intelligenceIndex, price1mInputTokens/price1mOutputTokens, release date, creator (with country),
     per-benchmark scores, speed.
  B. JSON-LD `Dataset` blocks — one per chart, each holding that chart's plotted points (top-N only).
     The "Artificial Analysis Intelligence Index" block gives label + intelligenceIndex + detailsUrl.
  C. `models` — a registry of every model the page knows (646), but only slug, name, creator, releaseDate,
     deprecated, isReasoning, effort.  NO scores and NO prices.

Usage: python3 code/09_parse_aa_page.py --html <file> --captured YYYY-MM-DD --fetched-by "<name>"
Outputs (data/raw/artificial_analysis/):
  aa_full_records.csv    from A: every field needed downstream, one row per model
  aa_jsonld_points.csv   from B: one row per (dataset, label) point
  aa_model_registry.csv  from C: the 646-model registry
  FETCH_LOG.md           file hash/size, capture date, fetcher, counts per structure
"""
import argparse, csv, hashlib, html as html_lib, json, pathlib, re

def decode_embedded(text, marker):
    i = text.find(marker)
    if i == -1: raise ValueError(f"marker not found: {marker!r}")
    start = text.find("[", i)
    payload, _ = json.JSONDecoder().raw_decode(text[start:].replace('\\"', '"'))
    if not isinstance(payload, list): raise ValueError("payload is not a list")
    return payload

def g(d, *path, default=None):
    for k in path:
        if not isinstance(d, dict): return default
        d = d.get(k)
    return d if d is not None else default

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True); ap.add_argument("--captured", required=True)
    ap.add_argument("--fetched-by", default="project owner"); ap.add_argument("--out", default="data/raw/artificial_analysis")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    raw = pathlib.Path(a.html).read_bytes(); text = raw.decode("utf-8", errors="replace")
    notes = []

    # ---------- A. initialModels ----------
    full = []
    try:
        for m in decode_embedded(text, '\\"initialModels\\":[{'):
            full.append(dict(
                slug=m.get("slug"), name=m.get("name"), short_name=m.get("shortName"),
                creator=g(m, "creator", "name"), creator_country=g(m, "creator", "country"), creator_slug=g(m, "creator", "slug"),
                release_slug=g(m, "release", "slug"), release_name=g(m, "release", "name"),
                release_date=m.get("releaseDate"), deprecated=m.get("deprecated"),
                is_reasoning=m.get("isReasoning"), effort=g(m, "effort", "slug"),
                is_open_weights=m.get("isOpenWeights"), size_class=m.get("sizeClass"),
                context_window_tokens=m.get("contextWindowTokens"),
                intelligence_index=m.get("intelligenceIndex"), intelligence_is_estimated=m.get("intelligenceIndexIsEstimated"),
                input_usd_per_mtok=m.get("price1mInputTokens"), output_usd_per_mtok=m.get("price1mOutputTokens"),
                cache_hit_price=m.get("cacheHitPrice"), blended_3to1=m.get("price1mBlended0To3To1"),
                median_output_speed=g(m, "timescaleData", "medianOutputSpeed"),
                host_model_count=m.get("hostModelCount"),
                perf_source_type=g(m, "performanceDataSource", "type"), perf_source_provider=g(m, "performanceDataSource", "providerName")))
    except Exception as e:
        notes.append(f"initialModels: {e}")

    # ---------- B. JSON-LD datasets ----------
    pts, ld_meta = [], []
    for blk in re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', text, re.DOTALL):
        try: p = json.loads(html_lib.unescape(blk))
        except (json.JSONDecodeError, TypeError): continue
        if not (isinstance(p, dict) and p.get("@type") == "Dataset" and isinstance(p.get("data"), list)): continue
        ds = p.get("name", ""); ld_meta.append((ds, len(p["data"]), str(p.get("description") or "")[:400]))
        for it in p["data"]:
            if not isinstance(it, dict): continue
            row = dict(dataset=ds, label=it.get("label"), details_url=it.get("detailsUrl"), value="", sub_metric="")
            if "intelligenceIndex" in it: pts.append({**row, "sub_metric": "intelligenceIndex", "value": it["intelligenceIndex"]})
            if isinstance(it.get("pricing"), list):
                for v in it["pricing"]:
                    if isinstance(v, dict): pts.append({**row, "sub_metric": v.get("name"), "value": v.get("value")})
            for k in ("medianOutputSpeed", "outputSpeed", "contextWindowTokens", "elo", "costPerTask", "value"):
                if k in it: pts.append({**row, "sub_metric": k, "value": it[k]})
            if isinstance(it.get("passiveParams"), (int, float)) or isinstance(it.get("activeParams"), (int, float)):
                pts.append({**row, "sub_metric": "passiveParams", "value": it.get("passiveParams")})
                pts.append({**row, "sub_metric": "activeParams", "value": it.get("activeParams")})

    # ---------- C. registry ----------
    reg = []
    try:
        for m in decode_embedded(text, '\\"models\\":[{'):
            reg.append(dict(slug=m.get("slug"), name=m.get("name"), creator=g(m, "creator", "name"),
                            release_slug=g(m, "release", "slug"), release_name=g(m, "release", "name"),
                            release_date=m.get("releaseDate"), deprecated=m.get("deprecated"),
                            is_reasoning=m.get("isReasoning"), effort=g(m, "effort", "slug")))
    except Exception as e:
        notes.append(f"models registry: {e}")

    for name, rows in (("aa_full_records.csv", full), ("aa_jsonld_points.csv", pts), ("aa_model_registry.csv", reg)):
        if not rows: continue
        with open(out / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    scored_ld = {p["details_url"] for p in pts if p["sub_metric"] == "intelligenceIndex"}
    scored_full = {r["slug"] for r in full if r["intelligence_index"] is not None}
    log = ["# Fetch log — Artificial Analysis models page", "",
           "- Source URL: https://artificialanalysis.ai/models",
           f"- Saved file: `{pathlib.Path(a.html).name}` ({len(raw):,} bytes, sha256 `{hashlib.sha256(raw).hexdigest()}`)",
           f"- Captured: {a.captured} by {a.fetched_by} (browser 'Save page as'); upload commit time is the authoritative timestamp",
           "", "## What the page contains", "",
           f"- **A. `initialModels`** (the selected models when saved): **{len(full)}** records, {len(scored_full)} with an Intelligence Index and a price.",
           f"- **B. JSON-LD chart datasets**: {len(ld_meta)} datasets, {len(pts)} plotted points; the Intelligence Index chart holds {len(scored_ld)} models (chart top-N, not the full catalog).",
           f"- **C. `models` registry**: **{len(reg)}** models, with slug / name / creator / release date only — **no scores, no prices**.",
           f"- Union of models with an Intelligence Index anywhere in this page: **{len(scored_full | {u.rsplit('/',1)[-1] for u in scored_ld if u})}**.",
           "", "## JSON-LD datasets present", ""]
    for ds, n, desc in ld_meta: log.append(f"- `{ds}` — {n} points. {desc[:200]}")
    if notes: log += ["", "## Parse notes", ""] + [f"- {x}" for x in notes]
    (out / "FETCH_LOG.md").write_text("\n".join(log) + "\n")
    print("\n".join(log))

if __name__ == "__main__":
    main()
