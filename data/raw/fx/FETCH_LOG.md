# Fetch log — exchange-rate data

| File | Fetched from | Fetched by | When | How it reached this repo |
|---|---|---|---|---|
| `DEXCHUS.csv` (uploaded as `DEXCHUS (1).csv`) | https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXCHUS (FRED series DEXCHUS: China / U.S. Foreign Exchange Rate, Chinese yuan per U.S. dollar, daily, not seasonally adjusted; source Board of Governors of the Federal Reserve System, H.10 release) | the project owner, on their own machine, by opening the link in a browser | download 2026-09-13 (local time); uploaded via the GitHub web interface in commit `2c0ead300fcd29d2585ccd89f94749a91ae3afd9` at 2026-09-13T00:09:18-07:00 | renamed and moved by `git mv` in the next commit; contents unchanged (byte-identical to the uploaded file) |

FRED marks days with no observation (US holidays) as ".". Those rows are kept as-is in the raw file and are
handled explicitly downstream (never interpolated silently).
