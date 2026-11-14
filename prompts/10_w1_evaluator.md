# W1 · EVALUATOR (agent: evaluator, worktree branch w1/evaluator, budget ~60 min)

Mission: build the measuring stick that every other agent and the final README depend on. If this is wrong, every claim is wrong, so be exact and boring.

Read first: `AGENTS.md`, `contracts/interfaces.py`, `contracts/proof.py` (ProofObject only), `docs/recon.md` (first 150 lines). Dataset row format: `{"path","question","answer","unit","type"}`; `source = path.split("/")[1]`.

You own: `evalkit/`, `tests/test_eval*.py`, the `claims` target in `Makefile` (append only). Do not touch anything else.

## Steps

1. **`evalkit/data.py`**
   - `load_questions(root)` -> list of `Q(path, question, answer, unit, type, source, lang, intent, params)`.
   - `split_of(path)`: `"holdout" if int(sha1(path.encode()).hexdigest(), 16) % 5 == 0 else "dev"`. Split is by PATH so a drawing's questions never straddle splits. Print split sizes by source in the report.
   - `DATASET_ROOT` from env, then `.env` (parse manually, no extra dependency).
2. **`evalkit/intents.py` + `evalkit/intents.yaml`** (others import `classify`!)
   - Public API: `classify(question: str, path: str) -> Intent(name, params: dict, lang: str)`; unknown -> `Intent("unknown", {}, lang)`.
   - English patterns are regexes in YAML with named groups for params. The 12 cubicasa intents are: `windows, floors, toilets, sinks, showers_baths, doors, saunas, kitchens, bedrooms, wc_rooms, bathrooms, balconies`. Mine the rest from `docs/recon.md`: swiss_dwellings (`apartments, doors, windows, toilets, washbasins, bathtubs, total_net_area, apartment_net_area{letter}`), ifc_models (`room_net_area{room,storey}`, `doors_on_storey{storey}`, `walls_length{storey}`, `walls_volume{storey}`, `slabs_volume{storey}`), opening_design (`door_schedule_total`, `door_schedule_by_{type|material|frame|note|width}`), ifc_bench (`text_*`, free-form).
   - Non-English rows: the file lists each question in English then in a second language directly after, with identical `path`, `answer`, `unit`. VERIFY this pairing (print the % of rows that pair cleanly) and use it to give every localized question the intent of its English partner. Store the localized template -> intent mapping in `evalkit/intents_localized.yaml`. Export `evalkit/out/intent_labels.jsonl` (`question, lang, intent, path`) for every preview row. The integrator will use this to test the multilingual router with leave-one-language-out.
   - Language guess: small stopword/character heuristic, return an ISO code (`en fi de et da sv xx`), no external package.
3. **`evalkit/score.py`**
   - count: exact match after `int(round(x))`. area/length/volume: relative error <= 0.02 (if the truth is 0, require exact). text: normalised exact match, reported separately and EXCLUDED from the headline.
   - `wilson(k, n, z=1.96)` confidence interval; use it in every table cell.
4. **`evalkit/run.py`**: `python -m evalkit.run --engine {stub,prior,pipeline} --split {dev,holdout,all} [--no-siblings] [--limit N] [--sources a,b] [--workers N] [--tag name]`
   - Group questions by path; one engine instance per worker (`engine.api.get_engine(mode)`); `prior` engine is built into evalkit: per-intent median answer computed on DEV only (an honest floor).
   - Call `engine.ask(path, question, allow_siblings=not args.no_siblings, benchmark=True)`. Catch every exception per question, record it as an error row (never crash the run). Check `contracts.invariants.check(po)` for each result and count violations.
   - Write `evalkit/out/<timestamp>-<tag>/{results.jsonl, report.md, report.json, claims.json}` and update the symlink `evalkit/out/latest`. Each `results.jsonl` row holds the question fields, `truth`, `correct` (bool), `intent`, `split`, `lang`, and the FULL `ProofObject` dict as `po` (the skeptic trains its calibrator from these rows).
5. **`report.md` sections** (in this order): (1) headline accuracy per split and overall, (2) source x type table with n, k, Wilson CI, (3) per-intent table (n, accuracy, CI, prior baseline accuracy next to it), (4) **tier calibration**: for green/amber/grey the n, share of questions (coverage) and accuracy with CI, plus an accuracy-vs-coverage table at 10 coverage levels, (5) cost: mean/median/p95 ms per question, total tokens, total USD, LLM calls, estimated CPU-seconds per drawing and per 14,000 drawings (computed, labelled "estimate"), (6) failure buckets: group wrong answers by (source, intent, image width bucket, error direction over/under), (7) 20 random wrong examples (path, question, truth, prediction, tier), (8) invariant violations and exceptions count, (9) the exact command line and git commit hash.
6. **`claims.json`**: a flat dict of the only numbers allowed in README/video: `headline_acc_holdout, headline_ci, green_acc, green_coverage, amber_acc, grey_share, mean_ms, tokens_total, usd_total, llm_calls, n_questions, n_drawings, split_sizes, engine, commit`, plus `hard_acc_dev, hard_n_dev, hard_acc_holdout, hard_n_holdout, planner_calls, llm_mode`. `make claims` copies it to `web/public/claims.json` if `web/` exists. Also include `cpu_per_drawing_s` (computed estimate). Merge every flat JSON in `docs/claims/*.json` into it (raster writes `clean_acc`, integrator writes `router_lolo`); a key clash fails loudly.
7. **`evalkit/audit.py`** (`--run latest --intent doors --wrong-only --n 20`) prints path, truth, prediction, tier so extractor agents can inspect failures. **`evalkit/compare.py A B`** prints per-intent accuracy deltas and lists regressions.
8. **Tests** (`tests/test_eval*.py`, build a tiny synthetic dataset in `tmp_path`, no real data): split determinism and stability across runs, Wilson against known values (e.g. 8/10 -> about 0.49 to 0.94), score rules for count/area/text, intent classification of five real templates, pairing verification, and a full `run` with the stub on 30 synthetic rows finishing in under 10 s.
9. **Hard set** (the judges use harder questions than the dataset). `evalkit/hard_questions.jsonl` rows: `{path, question, answer, unit, type, lang, kind_of_hard, verified, author}`, `kind_of_hard` in {filter, group, adjacency, mixed, cross_format, multilingual}. HUMANS write and verify these (RUNBOOK section 8). You ship: the format, a loader, `--hard` in `evalkit.run` (scores only `verified: true` rows, split by the same path hash), report section 10 "Hard set" (per kind_of_hard: n, accuracy, CI), and 10 seed rows marked `verified: false` on IFC and Swiss drawings to show the format. Write `LLM_PROVIDER` into every report header and into `claims.json` as `llm_mode` so planner-on and LLM-off runs are never mixed. Never tune on this file. Also add a test that unverified rows are never scored.

## Gates (run them, paste the last lines of output in your handoff)
```
.venv/bin/python -m pytest tests -q -k eval
make eval-stub          # stub baseline on all questions, < 60 s
.venv/bin/python -m evalkit.run --engine prior --split dev
ls -l evalkit/out/latest/claims.json
```
Report the stub and prior baselines and the pairing percentage.

## Don'ts
No engine imports except `engine.api`. No tuning on holdout. No bare overall accuracy anywhere. Never let a failing question crash the run. Do not hard-code dataset paths.

## Handoff
Write `docs/handoff/evaluator.md`: how to run, the intent list, baselines (stub, prior), pairing %, split sizes, known gaps. Commit as `evalkit: <what>` in small commits.
