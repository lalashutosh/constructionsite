# Evidence: the evaluation reports behind every number we quote

`evalkit/out/` is not committed (its per-question results are tens of megabytes), so the reports cited in the README,
`llms.txt` and `docs/JUDGES.md` are copied here unchanged: `report.md` (headline, source x type, per-intent accuracy
with 95% confidence intervals, tier calibration, cost) and `claims.json` (the same numbers, machine-readable).

| Run | What it measures |
|---|---|
| `20261115-024003-gate_r9` | CubiCasa5k scanned plans, exact counts, DEV sample n = 400, LLM off: 81.5% |
| `20261115-022504-gate_sw8` | Swiss Dwellings, given file only: counts 91.3% (n = 206) |
| `20261114-154539-w2-dev` | Full DEV split, 6,192 questions, with sibling files: 75.0% |
| `20261114-161203-w2-dev-nosib` | Full DEV split, given file only: 70.4% |

The harder questions on Stoa's full-size sheets are in [`../stress-report-r9.md`](../stress-report-r9.md) (24/25).
Reproduce with `make eval` / `make eval-nosib` (needs the dataset at `DATASET_ROOT`).
