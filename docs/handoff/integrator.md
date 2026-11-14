# Handoff: integrator (W2)

## What exists
- `engine/pipeline.py` `PipelineEngine` (via `engine.api.get_engine("pipeline")`; stub still works). Order: route -> sha256 facts cache
  `(sha, allow_siblings)` (`engine/cache.py`, `cache/pipeline/`, never caches failed extractions) -> triage -> sibling resolve ->
  extract -> voters -> tier -> scale/interval/decisions (area, length, volume only) -> finalizers -> calibrators -> `invariants.check`
  (violations downgrade green to amber and are appended to `notes`). Zero plugins: amber 0 with a note.
- Extraction: vector extractor is looked up by duck typing (`engine.vector.plugin.extract` or `engine.vector.extract.extract`, for
  pdf/dxf/ifc/svg), falling back to `engine.raster.extract.extract`. Integration pass must confirm vector's real entry point.
- Plugins written by me (owners had none): `engine/raster/plugin.py` (`detector` count voter; prior-fallback note) and
  `engine/takeoff/plugin.py` (`area_polygons` for area/length/volume, `query_engine` for count intents the detector does not cover;
  it deliberately stays silent on raster cubicasa intents so the same logic is never counted as an independent voter).
- `engine/router.py`: regex (`evalkit.intents.classify`) -> source-aware char n-gram TF-IDF nearest template (threshold 0.55) ->
  optional LLM template classifier (once per distinct normalised template, cached in `cache/templates.json`) -> unknown.
- `engine/query/`: `run(spec, facts, px_per_m)`, `schema.json`, `validate`, named `rules.py`, `fixed.py` (12 cubicasa intents plus swiss,
  ifc specs), `graph.py` (networkx apartments), `planner.py` + `llm.py` (LLM drafts spec only; client reuses scripts/verda.py env,
  auth and ledger). Fixed specs equal the intent path on 25 cached raster sheets x 12 intents and on a synthetic fixture (tests).
- `api/main.py`: `/health`, `/api/analyze` (multipart or `/api/analyze/json`), `/api/facts`, `/api/ask`, `/api/scale`, `/api/decide`
  (501 until `engine.decide.quote` exists), `/api/cost`, `/api/upload`, `/api/ask_async` + `/api/stream/{job}` (SSE: triage, resolve,
  extract, vote, finalize, done). CORS for localhost:5173. Uploads: `cache/uploads/<sha256>.<ext>`, extension allow-list, 60 MB cap.
- `engine/cost.py` process-wide meter behind `/api/cost`.

## Tiers
Value: exact-source voter if any, else median of voters (ties -> smaller TTA spread). Green iff all valued voters agree (count exact,
area/length/volume 2%) and >= 2 are independent; a voter whose note starts "prior fallback" (count_defaults) is not independent and its
value is tagged `Tag.defaulted` via an Assumption. Amber otherwise; grey only for triage refusal or unreadable input in product mode.
Planner answers with a single voter are amber. Benchmark mode with no voter value uses the dev-median prior (`cache/priors.json`).
Known conflict: invariants demand exact equality for green, so area green is effectively exact (docs/decisions/hook-invariants-area-tolerance.md).

## Measured
- Gates: `pytest tests -q` 124 passed; `make api` serves, health ok (probed with `scripts/api_probe.py`, curl needs approval in this sandbox);
  `python -m evalkit.run --engine pipeline --limit 100 --split dev` runs clean (68.0%, n=100, 0 exceptions, 0 invariant violations).
- `--limit 600 --split dev`: 75.7% [72.1, 78.9] (cubicasa count only, 0 exceptions). Every cubicasa intent >= prior; windows 41.9 vs 9.7,
  doors 63.2 vs 5.3, sinks 67.7 = prior. Report `evalkit/out/*integ600*`.
- Stratified smoke (`python -m scripts.pipeline_smoke 6`): no crashes in any source/type; non-cubicasa sources run on the prior
  until vector plugins land (extraction of pdf fails soft, notes say so).
- Router leave-one-language-out (distinct templates, n=423): overall 0.8085 (`docs/claims/integrator.json`); en .871, fr .789,
  it .765, de .667, da .632, fi .417 (n=12), et .286 (n=14), xx 1.0. Weak for fi/et because their templates have few cross-language
  neighbours; the LLM layer (when on) covers these and costs <= one call per distinct template (tested with a fake LLM).

## Known gaps
- Only cubicasa is truly answered; swiss/ifc/opening_design depend on vector/skeptic plugins (`engine.vector.plugin`, `engine.skeptic.plugin`).
- No independent second count voter exists yet, so counts are all amber until skeptic registers one.
- Facts cache is not versioned by extractor: delete `cache/pipeline/` when plugins change.
- `/api/decide` returns 501; `engine/reconcile` stub; a2a not started (W3). Planner path is only tested with a fake LLM; no real LLM calls made.
- Door-schedule intents have no fixed spec (takeoff `door_schedule.py` should provide a voter).
- Element conventions assumed for vector facts: kinds room/door/window/wall/slab/fixture, `attrs.storey`, `attrs.area_m2`,
  `attrs.length_m`, `attrs.volume_m3`, `attrs.side_area_m2`, `attrs.apartment`, `attrs.leaf`, `attrs.entrance`. Vector should match or tell me.

## Run
`make api` | `python -m evalkit.run --engine pipeline --limit 100 --split dev` | `python -m scripts.router_lolo` | `python -m scripts.pipeline_smoke 8 [nosib]`
Verda calls used: 0.
