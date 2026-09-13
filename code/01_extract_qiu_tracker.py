#!/usr/bin/env python3
"""Stage 1 — extract every dated observation from the Shenghao Qiu LLM pricing tracker.

Source: the tracker's own GitHub Pages repository (JoshuaQSH/joshuaqsh.github.io),
file data/llm_pricing.json, which a GitHub Actions job rewrites daily and commits only
when content changed.  Every commit touching that file is therefore a dated snapshot.

Usage (from repo root):
    python3 code/01_extract_qiu_tracker.py --repo /home/user/joshuaqsh/joshuaqsh.github.io

Outputs (all under data/):
    raw/qiu_tracker/llm_pricing_latest.json                 byte copy of HEAD version
    raw/qiu_tracker/tracker_api_pricing_all_commits.csv     api_pricing rows x commits
    raw/qiu_tracker/tracker_history_points_all_commits.csv  history_series points x commits
    raw/qiu_tracker/tracker_benchmark_snapshot_all_commits.csv  AA top-10 by Intelligence Index x commits
    raw/qiu_tracker/tracker_frontier_rows_all_commits.csv   scale_price_frontier rows x commits
    raw/qiu_tracker/tracker_provider_leaderboard_all_commits.csv  AA provider leaderboard x commits
    verification/qiu_tracker_commits.tsv                    provenance: hash + commit time per snapshot
    verification/qiu_tracker_inventory.md                   machine-generated counts used in CHECKPOINT_1.md

Nothing is interpolated, filtered, or de-duplicated here; this is the raw stage.
"""
from __future__ import annotations
import argparse, collections, csv, datetime as dt, json, pathlib, shutil, subprocess

def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout

def flat(v):
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", default="data")
    a = ap.parse_args()
    out = pathlib.Path(a.out); raw = out / "raw" / "qiu_tracker"; ver = out / "verification"
    raw.mkdir(parents=True, exist_ok=True); ver.mkdir(parents=True, exist_ok=True)

    head = git(a.repo, "rev-parse", "HEAD").strip()
    shutil.copyfile(pathlib.Path(a.repo) / "data" / "llm_pricing.json", raw / "llm_pricing_latest.json")

    # One line per snapshot commit: hash, commit time, author, subject.  Author distinguishes the daily
    # GitHub Actions bot (re-fetches Artificial Analysis only) from the tracker author's hand edits, which are
    # the only commits that change vendor list-price rows.
    log = git(a.repo, "log", "--format=%H%x09%cI%x09%an%x09%s", "--", "data/llm_pricing.json").splitlines()
    meta = [l.split("\t", 3) for l in log if l.strip()]
    commits = [(m[0], m[1]) for m in meta]
    with open(ver / "qiu_tracker_commits.tsv", "w") as f:
        f.write("commit\tcommit_time_iso\tauthor\tsubject\n")
        for m in meta: f.write("\t".join(m) + "\n")
    n_manual = sum(1 for m in meta if "github-actions" not in m[2])

    api, hist, bench, front, lead = [], [], [], [], []
    for h, ts in commits:
        d = json.loads(git(a.repo, "show", f"{h}:data/llm_pricing.json"))
        gen = d.get("generated_at") or ts[:10]
        base = dict(commit=h[:7], commit_date=ts[:10], generated_at=gen)
        for r in d.get("api_pricing", []):
            api.append({**base, **{k: flat(r.get(k)) for k in ("vendor","product","unit","input_value","output_value","cached_input_value","official_link","source_label","notes")}})
        for key, ser in (d.get("history_series") or {}).items():
            for p in ser.get("points", []):
                hist.append({**base, "series": key, "label": ser.get("label"), "currency": ser.get("currency"), **{k: flat(v) for k, v in p.items()}})
        for m in (d.get("benchmark_snapshot") or {}).get("models", []):
            bench.append({**base, **{k: flat(v) for k, v in m.items() if k != "color"}})
        for metric, mm in ((d.get("scale_price_frontier") or {}).get("metrics") or {}).items():
            for r in mm.get("rows", []):
                front.append({**base, "metric": metric, **{k: flat(v) for k, v in r.items() if k != "color"}})
        for metric, mm in ((d.get("provider_leaderboard") or {}).get("metrics") or {}).items():
            for r in mm.get("rows", []):
                lead.append({**base, "metric": metric, **{k: flat(v) for k, v in r.items() if k != "color"}})

    def dump(name, rows):
        keys = list(collections.OrderedDict((k, 1) for r in rows for k in r))
        with open(raw / f"{name}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
        return len(rows)
    n_api = dump("tracker_api_pricing_all_commits", api)
    n_hist = dump("tracker_history_points_all_commits", hist)
    n_bench = dump("tracker_benchmark_snapshot_all_commits", bench)
    n_front = dump("tracker_frontier_rows_all_commits", front)
    n_lead = dump("tracker_provider_leaderboard_all_commits", lead)

    # ---- inventory counts (no analysis; these feed the gate decision) ----
    bloc = {r["vendor_string"]: r["bloc"] for r in csv.DictReader(open(out / "reference" / "bloc_map.csv"))}
    dates = sorted({r["commit_date"] for r in api})
    d0, d1 = dt.date.fromisoformat(dates[0]), dt.date.fromisoformat(dates[-1])
    by = collections.defaultdict(list)
    for r in sorted(api, key=lambda r: r["commit_date"]):
        by[(r["vendor"], r["product"])].append(r)
    changes = []
    spans = {}
    for (v, p), rs in by.items():
        prev = None
        for r in rs:
            cur = (r["input_value"], r["output_value"])
            if prev is not None and cur != prev:
                changes.append((r["commit_date"], v, p, prev, cur))
            prev = cur
        spans[(v, p)] = (dt.date.fromisoformat(rs[-1]["commit_date"]) - dt.date.fromisoformat(rs[0]["commit_date"])).days
    prods_cn = [k for k in by if bloc.get(k[0]) == "CN"]
    prods_us = [k for k in by if bloc.get(k[0]) == "US"]
    prods_other = [k for k in by if bloc.get(k[0]) not in ("CN", "US")]
    hist_pts = {tuple((k, v) for k, v in r.items() if k not in ("commit", "commit_date", "generated_at")) for r in hist}
    hist_dates = sorted({dict(p).get("date") for p in hist_pts if dict(p).get("date")})
    bench_models = collections.Counter((r["vendor"], r["model"]) for r in bench)
    bench_cn = [k for k in bench_models if bloc.get(k[0]) == "CN"]
    bench_us = [k for k in bench_models if bloc.get(k[0]) == "US"]
    lines = [
        "# Qiu tracker inventory (machine-generated by code/01_extract_qiu_tracker.py)", "",
        f"- Source repo HEAD: `{head}`",
        f"- Snapshot commits touching data/llm_pricing.json: **{len(commits)}** ({n_manual} hand edits by the author, {len(commits)-n_manual} by the daily bot)",
        f"- Author hand-edit dates: {sorted({m[1][:10] for m in meta if 'github-actions' not in m[2]})}",
        f"- Snapshot date window: **{dates[0]} to {dates[-1]}** = **{(d1-d0).days} days** ({(d1-d0).days/365.25:.2f} years)",
        f"- Rows written: api_pricing {n_api}; history_points {n_hist}; benchmark_snapshot {n_bench}; frontier {n_front}; provider_leaderboard {n_lead}", "",
        "## api_pricing (official-page list prices, one row per product per snapshot)",
        f"- Distinct (vendor, product) rows ever present: **{len(by)}** — CN bloc {len(prods_cn)}, US bloc {len(prods_us)}, other/neither {len(prods_other)}",
        f"- Longest per-product observation span: **{max(spans.values())} days**; products with >= 365 days: **{sum(1 for s in spans.values() if s >= 365)}**",
        f"- Dated price-CHANGE events (same product, consecutive snapshots differ): **{len(changes)}**",
    ]
    for c in changes: lines.append(f"    - {c[0]}  {c[1]} / {c[2]}: (in,out) {c[3]} -> {c[4]}")
    lines += ["", "## history_series (curated flagship lines)",
        f"- Distinct points (union over all commits): **{len(hist_pts)}**; distinct point dates: {len(hist_dates)} -> {hist_dates}",
        "", "## benchmark_snapshot (Artificial Analysis Intelligence Index, top-10 per day)",
        f"- Distinct models ever in the daily top-10: **{len(bench_models)}** — CN bloc {len(bench_cn)}, US bloc {len(bench_us)}",
        f"- Days with a snapshot: {len({r['commit_date'] for r in bench})}",
        "", "## bloc classification", "- From data/reference/bloc_map.csv (a logged judgment call; Together-hosted GLM is excluded from CN pricing)."]
    (ver / "qiu_tracker_inventory.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
