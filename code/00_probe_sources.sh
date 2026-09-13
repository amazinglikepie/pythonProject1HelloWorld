#!/usr/bin/env bash
# Stage 0 — reachability probe of every named data source.
# Writes a timestamped TSV (UTC) of HTTP status + bytes per URL.  Run from the repo root:
#   bash code/00_probe_sources.sh > data/verification/reachability_log.tsv
# Notes: curl hides response bodies on failed CONNECTs; a 000 code with
# "CONNECT tunnel failed, response 403" means the egress proxy refused the host
# (organisation network policy), not that the site is down.
set -u
URLS=(
  "https://www.gradually.ai/en/llm-price-index/"
  "https://pricepertoken.com/pricing-history"
  "https://joshuaqsh.github.io/posts/llm-pricing-tracker/"
  "https://artificialanalysis.ai/api/v2/data/llms/models"
  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXCHUS"
  "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/csv?recent=5"
  "https://www.federalreserve.gov/releases/h10/hist/dat00_ch.htm"
  "https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&series=c5d6e0edf324b2fb28d73bcacafaaa02&lastobs=&from=01/01/2022&to=12/31/2026&filetype=csv&label=include&layout=seriescolumn"
  "https://www.kaggle.com"
  "https://api.github.com/repos/openai/openai-cookbook"
  "https://raw.githubusercontent.com/openai/openai-cookbook/main/README.md"
  "https://github.com/openai/openai-cookbook"
  "https://web.archive.org/web/2024/https://api-docs.deepseek.com/quick_start/pricing"
  "https://api-docs.deepseek.com/quick_start/pricing"
  "https://openai.com/api/pricing/"
  "https://www.anthropic.com/pricing"
)
printf 'utc_timestamp\thttp_code\tbytes\turl\tcurl_error\n'
for u in "${URLS[@]}"; do
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  err=$(mktemp)
  r=$(curl -sS -o /dev/null -w "%{http_code}\t%{size_download}" --max-time 25 -L "$u" 2>"$err" || true)
  printf '%s\t%s\t%s\t%s\n' "$ts" "$r" "$u" "$(tr '\n' ' ' <"$err")"
  rm -f "$err"
done
