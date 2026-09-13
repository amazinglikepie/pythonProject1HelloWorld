#!/usr/bin/env python3
"""Stage 3 — cross-check the two obtained price sources on overlapping models.

Qiu tracker  : official-page snapshots, hand-curated (data/raw/qiu_tracker/tracker_api_pricing_all_commits.csv)
modelpricewatch: daily captures + LiteLLM-reconstructed backfill (data/raw/modelpricewatch/price_history_points.csv)

Matching rule (judgment call): product names are normalised (lower-case, parentheticals removed, non-alphanumerics
stripped, the DeepSeek date suffixes 0731/0813 stripped) and matched exactly.  Every modelpricewatch row whose provider
is a US host (Together, Fireworks, DeepInfra, Groq) is kept in the table but flagged, because a host's resale price is
not the model vendor's own list price and is expected to differ.

For each Qiu product, the comparison date is the LAST Qiu snapshot that carried that product; the modelpricewatch price
is the latest point on or before that date (carry-forward, which is how the site itself defines its daily snapshots).

Outputs: data/verification/crosscheck_qiu_vs_modelpricewatch.csv and a printed summary.
"""
import csv, re, collections
def norm(s):
    s = s.lower(); s = re.sub(r"\(.*?\)", "", s); s = re.sub(r"[^a-z0-9]+", "", s)
    return s.replace("0813", "").replace("0731", "")
bloc = {r["vendor_string"]: r["bloc"] for r in csv.DictReader(open("data/reference/bloc_map.csv"))}
mpw = list(csv.DictReader(open("data/raw/modelpricewatch/price_history_points.csv")))
mpw_by = collections.defaultdict(list)
for r in mpw: mpw_by[r["model_id"]].append(r)
qiu = list(csv.DictReader(open("data/raw/qiu_tracker/tracker_api_pricing_all_commits.csv")))
qiu_by = collections.defaultdict(list)
for r in qiu: qiu_by[(r["vendor"], r["product"])].append(r)
out = []
for (v, p), rs in sorted(qiu_by.items()):
    rs = sorted(rs, key=lambda r: r["commit_date"]); last = rs[-1]
    cands = [mid for mid, pts in mpw_by.items() if norm(pts[0]["model"]) == norm(p)]
    if not cands:
        out.append(dict(qiu_vendor=v, qiu_product=p, date=last["commit_date"], qiu_input=last["input_value"], qiu_output=last["output_value"],
                        mpw_model_id="", mpw_provider="", mpw_provider_bloc="", mpw_input="", mpw_output="", mpw_point_date="", mpw_event="", mpw_source="", result="NO_MATCH"))
        continue
    for mid in cands:
        pts = [r for r in mpw_by[mid] if r["date"] <= last["commit_date"]]
        if not pts:
            out.append(dict(qiu_vendor=v, qiu_product=p, date=last["commit_date"], qiu_input=last["input_value"], qiu_output=last["output_value"],
                            mpw_model_id=mid, mpw_provider=mpw_by[mid][0]["provider"], mpw_provider_bloc=bloc.get(mpw_by[mid][0]["provider"], ""),
                            mpw_input="", mpw_output="", mpw_point_date="", mpw_event="", mpw_source="", result="NO_MPW_POINT_YET")); continue
        m = pts[-1]
        try: agree = abs(float(last["input_value"]) - float(m["input_per_mtok"])) < 1e-9 and abs(float(last["output_value"]) - float(m["output_per_mtok"])) < 1e-9
        except (TypeError, ValueError): agree = False
        pb = bloc.get(m["provider"], "")
        res = ("AGREE" if agree else "DISAGREE") + ("_HOST_RESALE" if pb == "HOST_US" else "")
        out.append(dict(qiu_vendor=v, qiu_product=p, date=last["commit_date"], qiu_input=last["input_value"], qiu_output=last["output_value"],
                        mpw_model_id=mid, mpw_provider=m["provider"], mpw_provider_bloc=pb, mpw_input=m["input_per_mtok"], mpw_output=m["output_per_mtok"],
                        mpw_point_date=m["date"], mpw_event=m["event"], mpw_source=m["source"], result=res))
with open("data/verification/crosscheck_qiu_vs_modelpricewatch.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
c = collections.Counter(r["result"] for r in out)
print("cross-check results:", dict(c))
print("\nDISAGREE on a vendor's own price (not host resale):")
for r in out:
    if r["result"] == "DISAGREE":
        print(f"  {r['date']} {r['qiu_vendor']} / {r['qiu_product']}: Qiu=({r['qiu_input']},{r['qiu_output']}) vs MPW {r['mpw_model_id']}=({r['mpw_input']},{r['mpw_output']}) [{r['mpw_event']} {r['mpw_point_date']}]")
