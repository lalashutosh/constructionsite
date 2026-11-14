# evaluator handoff

Status: evalkit built (mostly already present from a prior cycle; this pass filled the missing
`tests/test_eval*.py` and made `evalkit/build_localized.py:build()` testable without side effects),
all gates green.

## How to run

```
.venv/bin/python -m pytest tests -q -k eval        # evalkit's own tests (29)
.venv/bin/python -m pytest -q                      # whole repo (94)
make eval-stub                                      # stub baseline, all 7990 Qs, < 1 s
.venv/bin/python -m evalkit.run --engine prior --split dev
.venv/bin/python -m evalkit.run --engine pipeline --split dev [--no-siblings] [--hard]
.venv/bin/python -m evalkit.build_localized         # rebuild intents_localized.yaml + intent_labels.jsonl
.venv/bin/python -m evalkit.audit --run latest --wrong-only --n 20
.venv/bin/python -m evalkit.compare <run_a> <run_b>
```
Output: `evalkit/out/<ts>-<tag>/{results.jsonl,report.md,report.json,claims.json}`, symlink `evalkit/out/latest`.

## Intent list
12 cubicasa5k count intents (windows, floors, toilets, sinks, showers_baths, doors, saunas, kitchens,
bedrooms, wc_rooms, bathrooms, balconies) + swiss_dwellings (apartments, doors, windows, toilets,
washbasins, bathtubs, showers, room_labelled, room_area_labelled, total_net_area, apartment_net_area,
room_area) + ifc_models (room_net_area, total_net_area_storey, walls_side_area_storey,
walls_length_storey, walls_volume_storey, slabs_volume_storey, doors_on_storey, count_on_storey,
count_in_model) + opening_design (door_schedule_total/_by_type/_by_material/_by_frame/_by_note/_by_width,
door_schedule_total_rooms, room_schedule_area) + ifc_bench (text_freeform catch-all). Defined in
`evalkit/intents.yaml`; localized (fi/de/et/da/sv/fr/it) templates mapped 1:1 to the English intent of
their paired row, stored in `evalkit/intents_localized.yaml`.

## Measured numbers (this pass, repo HEAD 79d8dc3, DATASET_ROOT=preview set, 7990 questions)
- Split sizes (dev/holdout): cubicasa5k 3546/724 · swiss_dwellings 1622/736 · ifc_models 995/54 ·
  ifc_bench 83/166 · opening_design 41/23. Total dev 6287 / holdout 1703 (sums to 7990 — matches AGENTS.md).
- Pairing (EN -> other-language template pairing, `build_localized`): **3838/3838 = 100.0%** covered,
  108 localized template -> intent mappings written.
- **Stub engine** (always value=0, amber), split=all: headline dev 6.9% [6.3,7.6], holdout 5.7%
  [4.7,7.0], overall 6.7% [6.1,7.3] (n=7725 quantitative; text n=265 scored 0% and excluded from
  headline). Full run on all 7990 questions finishes in **0.87 s** (well under the 60 s `make eval-stub`
  gate).
- **Prior engine** (per-intent DEV median, built only from DEV): dev headline **37.3% [36.1,38.5]**
  (n=6192) — the honest floor every real engine route must beat per-intent (report section 3 puts it
  next to each intent's accuracy).
- `evalkit/out/latest/claims.json` present with all required keys (`headline_acc_holdout`, `green_acc`,
  `green_coverage`, `amber_acc`, `grey_share`, `mean_ms`, `tokens_total`, `usd_total`, `llm_calls`,
  `n_questions`, `n_drawings`, `split_sizes`, `engine`, `commit`, `hard_acc_dev/holdout`,
  `planner_calls`, `llm_mode`, `cpu_per_drawing_s`); `merge_claims_dir` fails loudly on key clashes
  from `docs/claims/*.json` (none exist yet — nothing for raster/integrator to clash with).

## What this pass added (my ownership: `evalkit/`, `tests/test_eval*.py`)
- `tests/test_eval_score.py` — count/area/text scoring rules, Wilson CI against the textbook 8/10 ≈
  [0.49, 0.94] value and boundary checks.
- `tests/test_eval_data.py` — split determinism/stability, loader on a synthetic tmp_path dataset,
  missing-file error.
- `tests/test_eval_intents.py` — classification of 5 real question templates across cubicasa5k /
  swiss_dwellings / ifc_models, unknown fallback, param extraction, language guess, and pairing
  verification on synthetic rows (see below).
- `tests/test_eval_run.py` — stub engine on 30 synthetic rows: no crashes, < 10 s, full report
  sections present, full CLI run via `--root` writes all four output files + updates `latest`.
- `tests/test_eval_hard.py` — unverified hard-set rows are never scored by default, `verified_only`
  toggle, missing `verified` key treated as unverified, and a check that the 10 shipped seed rows in
  `evalkit/hard_questions.jsonl` are still `verified: false` (0 scored) until a human checks them.
- Minor refactor to `evalkit/build_localized.py`: `build()` now takes optional `rows=None` (reads the
  real dataset only when not given) and `write=True` (skip touching
  `intents_localized.yaml`/`out/intent_labels.jsonl`), so pairing logic is unit-testable without
  clobbering the real generated files. CLI behaviour (`python -m evalkit.build_localized`) unchanged;
  reran it to confirm (100.0% pairing, same as before the refactor).

## Known gaps / what's next for other agents
- `engine.api.get_engine("pipeline")` is still unbuilt (raises until the integrator ships
  `engine/pipeline.py`); `--engine pipeline` runs will fail until then — expected at this stage.
- No `docs/claims/*.json` files exist yet from raster/integrator, so `clean_acc` / `router_lolo` are not
  yet in `claims.json`; `merge_claims_dir` will pick them up automatically once written.
- Hard set (`evalkit/hard_questions.jsonl`) has only the 10 unverified seed rows (format demo); humans
  still need to write + verify ~50 dev / ~20 holdout rows per RUNBOOK section 8.
- Tier calibration / cost sections are currently trivial (stub/prior never set tier=green or spend
  tokens); they'll become meaningful once a real engine with 2 independent voters exists.
