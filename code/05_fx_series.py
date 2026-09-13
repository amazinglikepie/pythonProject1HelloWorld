#!/usr/bin/env python3
"""Stage 5 — exchange-rate series preparation (measurement 2 of the brief).

Input : data/raw/fx/DEXCHUS.csv  (FRED DEXCHUS, Chinese yuan per US dollar, daily; "." = no observation)
Output: data/fx/dexchus_daily.csv        every FRED row in the window, with an explicit is_missing flag
        data/fx/dexchus_monthly.csv      month-end value and monthly mean (observed days only)
        data/fx/dexchus_summary.md       total move, extremes, largest 30/60/90-day moves (both directions)
        data/fx/dexchus_rolling_changes.csv  for every observed day: % change vs 30/60/90 calendar days earlier
                                          (this is the reference distribution for the lead-lag test)

Conventions (judgment calls, flagged in METHOD.md):
  * A "move" is the percentage change in CNY per USD: positive = yuan weaker (more yuan per dollar).
  * Missing FRED days are NOT interpolated.  For "value k days earlier" the last observed value on or before that
    calendar date is used (carry-back to the previous trading day), and the number of days carried is recorded.
  * Window: --start and --end (inclusive).  Rolling changes need data from 90 days before --start, which is read
    from the same file.
"""
import argparse, csv, datetime as dt, pathlib, statistics

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--start", required=True); ap.add_argument("--end", required=True)
    ap.add_argument("--infile", default="data/raw/fx/DEXCHUS.csv"); ap.add_argument("--out", default="data/fx"); a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.reader(open(a.infile, encoding="utf-8-sig")))[1:]
    series = [(dt.date.fromisoformat(r[0]), (None if r[1] in (".", "", "NA") else float(r[1]))) for r in rows if r]
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    obs = [(d, v) for d, v in series if v is not None]
    obs_by_date = dict(obs)
    def value_on_or_before(d):
        # last observed value on or before calendar date d
        best = None
        for dd, v in obs:
            if dd <= d: best = (dd, v)
            else: break
        return best
    with open(out / "dexchus_daily.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "cny_per_usd", "is_missing"])
        for d, v in series:
            if start <= d <= end: w.writerow([d.isoformat(), "" if v is None else v, int(v is None)])
    win = [(d, v) for d, v in obs if start <= d <= end]
    if not win: raise SystemExit("no observations in window")
    months = {}
    for d, v in win: months.setdefault(d.strftime("%Y-%m"), []).append((d, v))
    with open(out / "dexchus_monthly.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["month", "month_end_date", "month_end_value", "monthly_mean", "n_obs"])
        for m, vals in sorted(months.items()):
            w.writerow([m, vals[-1][0].isoformat(), vals[-1][1], round(statistics.mean(v for _, v in vals), 6), len(vals)])
    with open(out / "dexchus_rolling_changes.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "cny_per_usd", "chg_30d_pct", "ref_date_30d", "chg_60d_pct", "ref_date_60d", "chg_90d_pct", "ref_date_90d"])
        roll = {30: [], 60: [], 90: []}
        for d, v in win:
            rec = [d.isoformat(), v]
            for k in (30, 60, 90):
                ref = value_on_or_before(d - dt.timedelta(days=k))
                if ref: pct = (v / ref[1] - 1) * 100; roll[k].append((pct, d)); rec += [round(pct, 6), ref[0].isoformat()]
                else: rec += ["", ""]
            w.writerow(rec)
    (d0, v0), (d1, v1) = win[0], win[-1]
    hi = max(win, key=lambda x: x[1]); lo = min(win, key=lambda x: x[1])
    L = [f"# USD/CNY (FRED DEXCHUS) over {start} to {end}", "",
         f"- First observation in window: {d0} = {v0} CNY per USD; last: {d1} = {v1}",
         f"- Total move: {(v1/v0-1)*100:+.3f}% ({'yuan weaker' if v1 > v0 else 'yuan stronger'}); arithmetic: ({v1} / {v0} - 1) x 100",
         f"- Highest: {hi[1]} on {hi[0]}; lowest: {lo[1]} on {lo[0]}; high-to-low range {(hi[1]/lo[1]-1)*100:.3f}%",
         f"- Observed days: {len(win)}; missing FRED days in window: {sum(1 for d, v in series if start <= d <= end and v is None)}", ""]
    for k in (30, 60, 90):
        vals = [p for p, _ in roll[k]]
        mx = max(roll[k]); mn = min(roll[k])
        L.append(f"- {k}-day changes (n={len(vals)}): mean {statistics.mean(vals):+.3f}%, sd {statistics.pstdev(vals):.3f}%, largest weakening {mx[0]:+.3f}% ending {mx[1]}, largest strengthening {mn[0]:+.3f}% ending {mn[1]}")
    (out / "dexchus_summary.md").write_text("\n".join(L) + "\n"); print("\n".join(L))

if __name__ == "__main__":
    main()
