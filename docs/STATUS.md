# STATUS — gate numbers (all from commands, no hand-typed results)

<!-- gate:w1 -->
Dataset: `/home/ashutosh/Downloads/junction-dataset-preview` (from `dataset_root()`), 7990 rows, 320 drawings (eval report). Commit at gate: `5bfd71c`.
`make test`: **94 passed** in 1.28 s (logs/gate_w1_test.log).

## G1 (wave 1) — gated 2026-11-14
| agent | gate command | number | GO/NO-GO |
|---|---|---|---|
| evaluator | `make eval-stub`; `python -m evalkit.run --engine prior --split dev` | stub dev 6.9% [6.3,7.6] (n=6192), holdout 5.7%, 7990 Qs; prior dev **37.3% [36.1,38.5]**; report has tier table (sec. 4); 29 eval tests | GO ([handoff](handoff/evaluator.md)) |
| raster-extractor | `python -m engine.count.devcheck --n 150` (handoff); cold-timing script, cache disabled, 20 smoke images (logs/gate_w1_raster_cold.log) | DEV150 61.3% vs prior 47.3%; beats prior on **8/12** intents (windows, floors, toilets, doors, saunas, bedrooms, wc_rooms, balconies), ties 3 (prior fallback), loses sinks 46.2 vs 53.8; CLEAN 63.0% n=27; cold **median 2.21 s/image** (first 4.34 s incl. model load), cached 0.00 s | GO, conditional ([handoff](handoff/raster.md)) |
| takeoff | `pytest tests/takeoff`; `python -m engine.takeoff.demo contracts/fixtures/sample_facts.json --vibe standard` | 44 tests; demo ProofObject validates: tier green, 20.0 m2 | GO ([handoff](handoff/takeoff.md)) |
| ui-builder | `npm run typecheck`; `npm run build` | both clean (build 315 ms, 252 kB js); 18 PNGs in docs/shots/ui (handoff says 19; gate needs 8) | GO ([handoff](handoff/ui-builder.md)) |

Conditions and caveats (not blockers):
- raster: 8/12 is exactly the threshold and in-sample (fixes picked on the same 150 rows; 123/150 images are in the CNN's training set). Cold speed 2.21 s misses the 2 s target by 10%; W2 budget is 5 s/drawing (prompts/25 step 7), so tracked there, not a fix prompt.
- raster: showers_baths, kitchens, bathrooms are prior fallbacks, recorded in `facts.extras["count_defaults"]`; must surface as `Tag.defaulted` (docs/decisions/count-defaults-tag.md).
- takeoff: `engine.decide.quote(facts, ...)` and facts-driven `rank` not built; `engine/reconcile/` is a stub.
- ui: live POSTs (scale, decide, ask) not wired; fixture-driven only.
- docs/handoff/raster-extractor.md is stale (says the run was blocked); docs/handoff/raster.md is the current one.
- No contract change requests (`docs/decisions/contract-*.md`: none).

## G2 (wave 2)
| agent | gate command | number | GO/NO-GO |
|---|---|---|---|
| vector | | | |
| skeptic | | | |
| integrator | | | |
| integration (DEV) | | | |

## Verdicts
- G1: **GO** (4/4; raster conditional on speed and in-sample caveat). W2 may start.
- G2: pending
