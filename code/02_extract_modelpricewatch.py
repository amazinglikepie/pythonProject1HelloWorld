#!/usr/bin/env python3
"""Stage 2 — extract and inventory the modelpricewatch.com dataset.

Source: the site's own public data repository https://github.com/romanshumy/llm-prices-data
(README: "maintained by modelpricewatch.com"; data licence CC-BY-4.0; the same files are served
without a key at https://modelpricewatch.com/api/v1/price-history.json and .../models.json).

Usage:  python3 code/02_extract_modelpricewatch.py --repo /home/user/romanshumy/llm-prices-data
Outputs (under data/):
    raw/modelpricewatch/price_history_points.csv   one row per dated point, all JSON fields flattened
    raw/modelpricewatch/models.csv                 models.json flattened (key fields)
    raw/modelpricewatch/providers.csv              providers.json flattened
    raw/modelpricewatch/price-history.json, models.json, providers.json, price-history.csv, CHANGELOG.md  byte copies
    verification/modelpricewatch_commits.tsv       repo commit provenance
    verification/modelpricewatch_per_model.csv     per-model coverage: span, points, own vs reconstructed, change events
    verification/modelpricewatch_inventory.md      machine-generated counts

Definitions used here (judgment calls, see METHOD.md):
  * "own" point      = event != 'backfill' and source != 'litellm-archive'  (the site's own captures)
  * "reconstructed"  = event == 'backfill' or source == 'litellm-archive'   (rebuilt from LiteLLM git history)
  * price-change event = a point whose (input, output) differs from the model's previous point in date order,
    excluding points whose event is 'correction' (the site fixing its own earlier error, not a market move).
Nothing is filtered or interpolated here.
"""
from __future__ import annotations
import argparse, collections, csv, datetime as dt, json, pathlib, shutil, subprocess

def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, check=True).stdout

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--repo", required=True); ap.add_argument("--out", default="data")
    a = ap.parse_args(); repo = pathlib.Path(a.repo); out = pathlib.Path(a.out)
    raw = out / "raw" / "modelpricewatch"; ver = out / "verification"; raw.mkdir(parents=True, exist_ok=True); ver.mkdir(parents=True, exist_ok=True)
    head = git(a.repo, "rev-parse", "HEAD").strip()
    for f in ("price-history.json", "models.json", "providers.json", "price-history.csv", "CHANGELOG.md", "llm-price-index.csv", "README.md", "LICENSE-DATA.md"):
        shutil.copyfile(repo / f, raw / f)
    with open(ver / "modelpricewatch_commits.tsv", "w") as f:
        f.write("commit\tcommit_time_iso\tauthor\tsubject\n")
        for l in git(a.repo, "log", "--format=%H%x09%cI%x09%an%x09%s").splitlines(): f.write(l + "\n")

    hist = json.load(open(repo / "price-history.json"))
    pts = []
    for mid, rec in hist.items():
        for p in rec["history"]:
            pts.append(dict(model_id=mid, model=rec["model"], provider=rec["provider"], date=p.get("date"), event=p.get("event"),
                source=p.get("source"), confidence=p.get("confidence"), evidence_url=p.get("evidence_url"), captured_at=p.get("captured_at"),
                sha=p.get("sha"), input_per_mtok=p.get("input_per_mtok"), output_per_mtok=p.get("output_per_mtok"),
                cached_input_per_mtok=p.get("cached_input_per_mtok"), context_window=p.get("context_window"),
                changes=json.dumps(p.get("changes"), ensure_ascii=False)))
    pts.sort(key=lambda r: (r["model_id"], r["date"]))
    with open(raw / "price_history_points.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pts[0].keys())); w.writeheader(); w.writerows(pts)

    models = json.load(open(repo / "models.json"))
    mkeys = ["id","provider","model","category","status","released","released_source","retired_on","input_per_mtok","output_per_mtok","cached_input_per_mtok","context_window","open_source","parameters","pricing_url","source","last_updated","promo","promo_until","native_price","price_note","tags"]
    with open(raw / "models.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=mkeys); w.writeheader()
        for m in models: w.writerow({k: (json.dumps(m.get(k), ensure_ascii=False) if isinstance(m.get(k), (list, dict)) else m.get(k)) for k in mkeys})
    provs = json.load(open(repo / "providers.json"))
    with open(raw / "providers.csv", "w", newline="") as f:
        pk = ["id","name","type","url","pricing_url","founded"]; w = csv.DictWriter(f, fieldnames=pk); w.writeheader()
        for p in provs: w.writerow({k: p.get(k) for k in pk})

    bloc = {r["vendor_string"]: r["bloc"] for r in csv.DictReader(open(out / "reference" / "bloc_map.csv"))}
    minfo = {m["id"]: m for m in models}
    per = []
    by = collections.defaultdict(list)
    for r in pts: by[r["model_id"]].append(r)
    for mid, rs in by.items():
        own = [r for r in rs if r["event"] != "backfill" and r["source"] != "litellm-archive"]
        rec = [r for r in rs if not (r["event"] != "backfill" and r["source"] != "litellm-archive")]
        prev = None; changes = []
        for r in rs:
            cur = (r["input_per_mtok"], r["output_per_mtok"])
            if prev is not None and cur != prev and r["event"] != "correction": changes.append(r["date"])
            prev = cur
        d0, d1 = dt.date.fromisoformat(rs[0]["date"]), dt.date.fromisoformat(rs[-1]["date"])
        m = minfo.get(mid, {})
        per.append(dict(model_id=mid, model=rs[0]["model"], provider=rs[0]["provider"], bloc=bloc.get(rs[0]["provider"], "UNMAPPED"),
            status=m.get("status"), released=m.get("released"), category=m.get("category"),
            first_date=rs[0]["date"], last_date=rs[-1]["date"], span_days=(d1 - d0).days, n_points=len(rs),
            n_own_points=len(own), n_reconstructed_points=len(rec), first_own_date=(own[0]["date"] if own else ""),
            n_price_changes=len(changes), price_change_dates=";".join(changes),
            n_changes_before_first_own=sum(1 for c in changes if own and c < own[0]["date"])))
    per.sort(key=lambda r: (r["bloc"], r["provider"], r["model"]))
    with open(ver / "modelpricewatch_per_model.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per[0].keys())); w.writeheader(); w.writerows(per)

    dates = sorted({r["date"] for r in pts}); own_dates = sorted({r["date"] for r in pts if r["event"] != "backfill" and r["source"] != "litellm-archive"})
    L = ["# modelpricewatch inventory (machine-generated by code/02_extract_modelpricewatch.py)", "",
         f"- Source repo HEAD: `{head}`; repo commits: {len(git(a.repo,'rev-list','--count','HEAD').split())and git(a.repo,'rev-list','--count','HEAD').strip()}; first repo commit: {git(a.repo,'log','--reverse','--format=%cI').splitlines()[0][:10]}",
         f"- Points: **{len(pts)}** across **{len(by)}** model ids, **{len({r['provider'] for r in pts})}** providers; dates {dates[0]} to {dates[-1]} ({len(dates)} distinct dates)",
         f"- Own-captured points: {sum(1 for r in pts if r['event']!='backfill' and r['source']!='litellm-archive')} (dates {own_dates[0]} to {own_dates[-1]}); reconstructed (LiteLLM archive) points: {sum(1 for r in pts if r['event']=='backfill' or r['source']=='litellm-archive')}",
         f"- Event types: {dict(collections.Counter(r['event'] for r in pts))}",
         f"- Source labels: {dict(collections.Counter(r['source'] or '(blank)' for r in pts))}", "",
         "## Coverage by bloc (models = distinct model ids in the history file)"]
    for b in ("CN", "US", "HOST_US", "NEITHER", "UNMAPPED"):
        rows = [r for r in per if r["bloc"] == b]
        if not rows: continue
        L.append(f"- **{b}**: {len(rows)} models; with span >= 365 days: {sum(1 for r in rows if r['span_days']>=365)}; with span >= 365 AND >= 1 price change: {sum(1 for r in rows if r['span_days']>=365 and r['n_price_changes']>=1)}; total price-change events: {sum(r['n_price_changes'] for r in rows)}; own-capture span >= 365 days: {sum(1 for r in rows if r['first_own_date'] and (dt.date.fromisoformat(r['last_date'])-dt.date.fromisoformat(r['first_own_date'])).days>=365)}")
    L += ["", "## Models with >= 365 days of history (CN and US), first/last date, own-capture start, price changes"]
    for r in per:
        if r["bloc"] in ("CN", "US") and r["span_days"] >= 365:
            L.append(f"- {r['bloc']} | {r['provider']} | {r['model']} | {r['first_date']} to {r['last_date']} ({r['span_days']} d) | own from {r['first_own_date'] or 'never'} | changes {r['n_price_changes']}: {r['price_change_dates']}")
    L += ["", "## Span distribution (days from first to last point, per model)"]
    buckets = [(0, 90), (90, 180), (180, 270), (270, 365), (365, 10**6)]
    for b in ("CN", "US", "HOST_US"):
        rows = [r for r in per if r["bloc"] == b]
        counts = [sum(1 for r in rows if lo <= r["span_days"] < hi) for lo, hi in buckets]
        L.append(f"- **{b}** (n={len(rows)}): <90 d: {counts[0]}; 90-179: {counts[1]}; 180-269: {counts[2]}; 270-364: {counts[3]}; >=365: {counts[4]}; earliest first_date: {min(r['first_date'] for r in rows)}")
    L += ["", "## CN models with >= 180 days of history"]
    for r in per:
        if r["bloc"] == "CN" and r["span_days"] >= 180:
            L.append(f"- {r['provider']} | {r['model']} | {r['first_date']} to {r['last_date']} ({r['span_days']} d) | own from {r['first_own_date'] or 'never'} | reconstructed points {r['n_reconstructed_points']} | changes {r['n_price_changes']}: {r['price_change_dates']}")
    L += ["", "## Unmapped providers (need a bloc decision)", f"- {sorted({r['provider'] for r in per if r['bloc']=='UNMAPPED'})}"]
    (ver / "modelpricewatch_inventory.md").write_text("\n".join(L) + "\n"); print("\n".join(L))

if __name__ == "__main__":
    main()
