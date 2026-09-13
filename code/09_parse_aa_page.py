#!/usr/bin/env python3
"""Stage 9 — read Intelligence Index scores from a saved copy of https://artificialanalysis.ai/models

The page embeds its full model table in the HTML (a Next.js payload with escaped JSON, and separately JSON-LD
"Dataset" blocks).  The Shenghao Qiu tracker's refresh script parses exactly these two structures; this parser
follows the same two routes, embedded payload first, JSON-LD as fallback, and records which route was used.

Usage:  python3 code/09_parse_aa_page.py --html <saved page.html> --captured YYYY-MM-DD --fetched-by "<name>"
Outputs: data/raw/artificial_analysis/aa_models_index.csv   one row per model: name, vendor, slug, intelligence index,
                                                            input/output USD per 1M tokens, release date, flags
         data/raw/artificial_analysis/FETCH_LOG.md          file hash, size, capture date, fetcher, parse route, counts
Nothing is filtered here.
"""
import argparse, csv, hashlib, html as html_lib, json, pathlib, re

MARKERS = ('\\"models\\":[{\\"additional_text\\"', '\\"defaultData\\":[{\\"additional_text\\"', '\\"models\\":[{', '\\"defaultData\\":[{')

def decode_embedded_array(text: str, marker: str):
    i = text.find(marker)
    if i == -1: raise ValueError(f"marker not found: {marker!r}")
    start = text.find("[", i)
    decoded = text[start:].replace('\\"', '"')
    payload, _ = json.JSONDecoder().raw_decode(decoded)
    if not isinstance(payload, list): raise ValueError("payload is not a list")
    return payload

def rows_from_embedded(models):
    out = []
    for m in models:
        if not isinstance(m, dict): continue
        creators = m.get("model_creators") or {}
        out.append(dict(name=m.get("name"), short_name=m.get("short_name"), vendor=(creators.get("name") if isinstance(creators, dict) else None),
            slug=str(m.get("model_url") or m.get("slug") or "").removeprefix("/models/"), intelligence_index=m.get("intelligence_index"),
            input_usd_per_mtok=m.get("price_1m_input_tokens"), output_usd_per_mtok=m.get("price_1m_output_tokens"),
            blended_usd_per_mtok=m.get("price_1m_blended_3_to_1", m.get("price_1m_blended_0_3_1")),
            release_date=m.get("release_date"), is_open_weights=m.get("is_open_weights"), deprecated=m.get("deprecated"), deleted=m.get("deleted"),
            median_output_speed=(m.get("timescaleData") or {}).get("median_output_speed") if isinstance(m.get("timescaleData"), dict) else None))
    return out

def rows_from_json_ld(text: str):
    datasets = {}
    for raw in re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', text, re.DOTALL):
        try: payload = json.loads(html_lib.unescape(raw))
        except (json.JSONDecodeError, TypeError): continue
        if isinstance(payload, dict) and payload.get("@type") == "Dataset" and isinstance(payload.get("data"), list):
            datasets[payload.get("name", "")] = payload["data"]
    intel = datasets.get("Artificial Analysis Intelligence Index", [])
    if not intel: raise ValueError("no JSON-LD Intelligence Index dataset found")
    merged = {}
    for it in intel:
        if it.get("detailsUrl"):
            merged[it["detailsUrl"]] = dict(name=it.get("label"), short_name=it.get("label"), vendor=None, slug=str(it["detailsUrl"]).rsplit("/models/", 1)[-1],
                intelligence_index=it.get("intelligenceIndex"), input_usd_per_mtok=None, output_usd_per_mtok=None, blended_usd_per_mtok=None,
                release_date=None, is_open_weights=None, deprecated=None, deleted=None, median_output_speed=None)
    for it in datasets.get("Pricing: Cache Hit, Input, and Output", []):
        row = merged.get(it.get("detailsUrl"))
        if row is None: continue
        pricing = {v.get("name"): v.get("value") for v in it.get("pricing", []) if isinstance(v, dict)}
        row["input_usd_per_mtok"] = pricing.get("inputPrice"); row["output_usd_per_mtok"] = pricing.get("outputPrice")
    return list(merged.values())

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--html", required=True); ap.add_argument("--captured", required=True)
    ap.add_argument("--fetched-by", default="project owner"); ap.add_argument("--out", default="data/raw/artificial_analysis"); a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    raw = pathlib.Path(a.html).read_bytes(); text = raw.decode("utf-8", errors="replace")
    route, rows, errors = None, [], []
    for mk in MARKERS:
        try: rows = rows_from_embedded(decode_embedded_array(text, mk)); route = f"embedded payload ({mk[:20]}...)"; break
        except Exception as e: errors.append(f"{mk[:24]}: {e}")
    if not rows:
        try: rows = rows_from_json_ld(text); route = "JSON-LD Dataset blocks"
        except Exception as e: errors.append(f"json-ld: {e}")
    if not rows: raise SystemExit("could not find model data in the saved page: " + "; ".join(errors))
    cols = ["name", "short_name", "vendor", "slug", "intelligence_index", "input_usd_per_mtok", "output_usd_per_mtok", "blended_usd_per_mtok", "release_date", "is_open_weights", "deprecated", "deleted", "median_output_speed"]
    with open(out / "aa_models_index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    scored = [r for r in rows if r["intelligence_index"] not in (None, "")]
    log = ["# Fetch log — Artificial Analysis models page", "",
           f"- Source URL: https://artificialanalysis.ai/models", f"- Saved page file: `{pathlib.Path(a.html).name}` ({len(raw)} bytes, sha256 {hashlib.sha256(raw).hexdigest()})",
           f"- Captured on: {a.captured}, by: {a.fetched_by} (browser 'Save page as')", f"- Parse route: {route}",
           f"- Models found: {len(rows)}; with an Intelligence Index value: {len(scored)}; with a price: {sum(1 for r in rows if r['input_usd_per_mtok'] not in (None, ''))}",
           f"- Parse attempts that failed before the successful route: {errors or 'none'}"]
    (out / "FETCH_LOG.md").write_text("\n".join(log) + "\n"); print("\n".join(log))

if __name__ == "__main__":
    main()
