# code/

Scripts are numbered in execution order. Every script writes only under `data/` and prints what it did.

| Script | Stage | Inputs | Outputs |
|---|---|---|---|
| `00_probe_sources.sh` | 0 — reachability | none (network) | `data/verification/reachability_log.tsv` |
| `02_extract_modelpricewatch.py --repo <clone>` | 2 — raw extraction | local clone of https://github.com/romanshumy/llm-prices-data | `data/raw/modelpricewatch/*`, `data/verification/modelpricewatch_commits.tsv`, `data/verification/modelpricewatch_per_model.csv`, `data/verification/modelpricewatch_inventory.md` |
| `03_crosscheck_qiu_vs_modelpricewatch.py` | 3 — cross-check | outputs of stages 1 and 2 | `data/verification/crosscheck_qiu_vs_modelpricewatch.csv` |
| `01_extract_qiu_tracker.py --repo <clone>` | 1 — raw extraction | local clone of https://github.com/JoshuaQSH/joshuaqsh.github.io | `data/raw/qiu_tracker/*.csv`, `data/raw/qiu_tracker/llm_pricing_latest.json`, `data/verification/qiu_tracker_commits.tsv`, `data/verification/qiu_tracker_inventory.md` |

Clone used for stage 1 (shallow, then `git fetch --depth=1000 origin master`):

    GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/JoshuaQSH/joshuaqsh.github.io <clone>
    git -C <clone> fetch --depth=1000 origin master

Python 3.11; stage 1 uses only the standard library.
