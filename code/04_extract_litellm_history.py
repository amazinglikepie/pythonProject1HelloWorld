#!/usr/bin/env python3
"""Stage 4 — dated price history from the LiteLLM catalog's git history (approved by the owner on 2026-09-13).

Source: https://github.com/BerriAI/litellm, file model_prices_and_context_window.json — a community-maintained
catalog of per-token prices used by the LiteLLM library.  It is NOT an official provider page.  Every price point
here is tied to the git commit (hash + committer date) in which the catalog carried it, and the file content for
each sampled commit is downloaded from raw.githubusercontent.com and verified against the git blob id recorded in
the commit's tree (integrity check), so each number can be re-fetched and re-checked by anyone.

Judgment calls (flagged in METHOD.md):
  * Daily resolution: for each UTC calendar day on which the file changed, the LAST commit of that day is sampled;
    intra-day churn is ignored.  Event dates are therefore "the day the catalog changed", which lags the provider's
    announcement by an unknown amount (days to weeks).  This lag is a known limitation for the lead-lag test.
  * Per-token costs are converted to USD per 1M tokens by multiplying by 1,000,000.  Both are stored.
  * Nothing is filtered by provider here; bloc mapping happens in a later stage.

Usage:  python3 code/04_extract_litellm_history.py --repo /home/user/berriai/litellm --blobs <cache dir> --out data
Outputs:
  data/verification/litellm_price_file_commits.tsv   every commit touching the file (hash, committer date, author, subject)
  data/verification/litellm_sampled_versions.tsv     one row per sampled day: sha, blob id, download/integrity status, entry count
  data/raw/litellm/litellm_price_events.csv          added / changed / removed events per catalog key, with old and new prices
  data/raw/litellm/litellm_latest_snapshot.csv       every entry in the latest sampled version
  data/verification/litellm_inventory.md             machine-generated counts
"""
from __future__ import annotations
import argparse, collections, concurrent.futures as cf, csv, hashlib, json, pathlib, subprocess, urllib.request

FILE = "model_prices_and_context_window.json"
FIELDS = ("litellm_provider", "mode", "input_cost_per_token", "output_cost_per_token", "cache_read_input_token_cost",
          "max_input_tokens", "max_output_tokens", "max_tokens", "deprecation_date")

def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, check=True).stdout

def blob_oid_of_bytes(b: bytes) -> str:
    h = hashlib.sha1(); h.update(f"blob {len(b)}\0".encode()); h.update(b); return h.hexdigest()

def fetch(sha, dest: pathlib.Path):
    if dest.exists(): return "cached"
    url = f"https://raw.githubusercontent.com/BerriAI/litellm/{sha}/{FILE}"
    try:
        with urllib.request.urlopen(url, timeout=120) as r: data = r.read()
        dest.write_bytes(data); return "downloaded"
    except Exception as e:
        return f"error: {e}"

def per_mtok(v):
    try: return None if v is None else round(float(v) * 1_000_000, 10)
    except (TypeError, ValueError): return None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--repo", required=True); ap.add_argument("--blobs", required=True)
    ap.add_argument("--out", default="data"); ap.add_argument("--workers", type=int, default=8); a = ap.parse_args()
    out = pathlib.Path(a.out); raw = out / "raw" / "litellm"; ver = out / "verification"; blobs = pathlib.Path(a.blobs)
    raw.mkdir(parents=True, exist_ok=True); ver.mkdir(parents=True, exist_ok=True); blobs.mkdir(parents=True, exist_ok=True)

    log = git(a.repo, "log", "--format=%H%x09%cI%x09%aI%x09%an%x09%s", "--", FILE).splitlines()
    commits = [l.split("\t", 4) for l in log if l.strip()]          # newest first
    with open(ver / "litellm_price_file_commits.tsv", "w") as f:
        f.write("commit\tcommitter_time_iso\tauthor_time_iso\tauthor\tsubject\n")
        for c in commits: f.write("\t".join(c) + "\n")
    # committer time -> UTC day
    import datetime as dt
    def utc_day(iso): return dt.datetime.fromisoformat(iso).astimezone(dt.timezone.utc).date().isoformat()
    last_of_day = {}
    for c in reversed(commits):                                        # oldest -> newest, so the last write wins
        last_of_day[utc_day(c[1])] = c
    sampled = [(d, c) for d, c in sorted(last_of_day.items())]
    print(f"commits touching {FILE}: {len(commits)}; sampled days: {len(sampled)} ({sampled[0][0]} .. {sampled[-1][0]})")

    oids = {}
    for d, c in sampled:
        oids[c[0]] = git(a.repo, "rev-parse", f"{c[0]}:{FILE}").strip()
    with cf.ThreadPoolExecutor(a.workers) as ex:
        status = dict(zip([c[0] for _, c in sampled], ex.map(lambda sha: fetch(sha, blobs / f"{sha}.json"), [c[0] for _, c in sampled])))

    versions, events, prev, latest_entries = [], [], {}, {}
    for d, c in sampled:
        sha = c[0]; p = blobs / f"{sha}.json"; ok = p.exists()
        integrity = ok and blob_oid_of_bytes(p.read_bytes()) == oids[sha]
        entries = {}
        if ok:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if k == "sample_spec" or not isinstance(v, dict): continue
                    entries[k] = {f: v.get(f) for f in FIELDS}
            except Exception as e:
                ok = False; status[sha] = f"parse error: {e}"
        versions.append(dict(day=d, commit=sha, committer_time_iso=c[1], blob_oid=oids[sha], fetch_status=status.get(sha), integrity_ok=integrity, n_entries=len(entries)))
        if not ok or not integrity: continue
        def key(e): return (e["input_cost_per_token"], e["output_cost_per_token"], e["cache_read_input_token_cost"])
        for k, e in entries.items():
            if k not in prev:
                events.append(dict(day=d, commit=sha, event="added", key=k, litellm_provider=e["litellm_provider"], mode=e["mode"],
                    old_input_per_token=None, old_output_per_token=None, old_cache_read_per_token=None,
                    new_input_per_token=e["input_cost_per_token"], new_output_per_token=e["output_cost_per_token"], new_cache_read_per_token=e["cache_read_input_token_cost"],
                    new_input_usd_per_mtok=per_mtok(e["input_cost_per_token"]), new_output_usd_per_mtok=per_mtok(e["output_cost_per_token"]), new_cache_read_usd_per_mtok=per_mtok(e["cache_read_input_token_cost"]),
                    max_input_tokens=e["max_input_tokens"], deprecation_date=e["deprecation_date"]))
            elif key(prev[k]) != key(e):
                o = prev[k]
                events.append(dict(day=d, commit=sha, event="changed", key=k, litellm_provider=e["litellm_provider"], mode=e["mode"],
                    old_input_per_token=o["input_cost_per_token"], old_output_per_token=o["output_cost_per_token"], old_cache_read_per_token=o["cache_read_input_token_cost"],
                    new_input_per_token=e["input_cost_per_token"], new_output_per_token=e["output_cost_per_token"], new_cache_read_per_token=e["cache_read_input_token_cost"],
                    new_input_usd_per_mtok=per_mtok(e["input_cost_per_token"]), new_output_usd_per_mtok=per_mtok(e["output_cost_per_token"]), new_cache_read_usd_per_mtok=per_mtok(e["cache_read_input_token_cost"]),
                    max_input_tokens=e["max_input_tokens"], deprecation_date=e["deprecation_date"]))
        for k in prev:
            if k not in entries:
                o = prev[k]
                events.append(dict(day=d, commit=sha, event="removed", key=k, litellm_provider=o["litellm_provider"], mode=o["mode"],
                    old_input_per_token=o["input_cost_per_token"], old_output_per_token=o["output_cost_per_token"], old_cache_read_per_token=o["cache_read_input_token_cost"],
                    new_input_per_token=None, new_output_per_token=None, new_cache_read_per_token=None,
                    new_input_usd_per_mtok=None, new_output_usd_per_mtok=None, new_cache_read_usd_per_mtok=None, max_input_tokens=o["max_input_tokens"], deprecation_date=o["deprecation_date"]))
        prev = entries; latest_entries = entries; latest_day, latest_sha = d, sha

    with open(ver / "litellm_sampled_versions.tsv", "w") as f:
        f.write("\t".join(versions[0].keys()) + "\n")
        for v in versions: f.write("\t".join(str(x) for x in v.values()) + "\n")
    with open(raw / "litellm_price_events.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(events[0].keys())); w.writeheader(); w.writerows(events)
    with open(raw / "litellm_latest_snapshot.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["day", "commit", "key"] + list(FIELDS) + ["input_usd_per_mtok", "output_usd_per_mtok", "cache_read_usd_per_mtok"])
        for k, e in sorted(latest_entries.items()):
            w.writerow([latest_day, latest_sha, k] + [e[f] for f in FIELDS] + [per_mtok(e["input_cost_per_token"]), per_mtok(e["output_cost_per_token"]), per_mtok(e["cache_read_input_token_cost"])])

    prov = collections.Counter(e["litellm_provider"] for e in events if e["event"] == "added")
    bad = [v for v in versions if not v["integrity_ok"]]
    L = ["# LiteLLM catalog history inventory (machine-generated by code/04_extract_litellm_history.py)", "",
         f"- Commits touching `{FILE}`: **{len(commits)}**; sampled days (last commit per UTC day): **{len(sampled)}**, {sampled[0][0]} to {sampled[-1][0]}",
         f"- Versions downloaded and integrity-verified against the git blob id: **{len(versions)-len(bad)}** of {len(versions)}; failures: {[(v['day'], v['fetch_status']) for v in bad][:10]}",
         f"- Entries in latest sampled version ({latest_day}, {latest_sha[:10]}): **{len(latest_entries)}**",
         f"- Events: {dict(collections.Counter(e['event'] for e in events))}",
         f"- 'changed' events by year: {dict(sorted(collections.Counter(e['day'][:4] for e in events if e['event']=='changed').items()))}",
         f"- Distinct litellm_provider values among added entries: {len(prov)}", "",
         "## Entries added, by litellm_provider (top 60)"]
    for p, n in prov.most_common(60): L.append(f"- {p}: {n}")
    (ver / "litellm_inventory.md").write_text("\n".join(L) + "\n"); print("\n".join(L))

if __name__ == "__main__":
    main()
