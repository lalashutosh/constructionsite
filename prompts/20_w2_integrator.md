# W2 · INTEGRATOR (agent: integrator, branch w2/integrator, budget ~90 min)

Mission: one service that takes (file, question) and returns a `ProofObject` with tier, evidence, cost; cached so analysis happens once per drawing and questions are lookups. Other W2 agents (skeptic, vector) work IN PARALLEL and plug in through `engine/registry.py`; you must not wait for them.

Read first: `AGENTS.md`, `engine/registry.py` (the plugin API, already written and tested), `contracts/interfaces.py`, `docs/handoff/{evaluator,raster,takeoff}.md`, `docs/STATUS.md`.

<!-- gate:w1 -->
## Measured facts from gate w1 (commit 5bfd71c)
- Baselines (DEV): stub 6.9%, **prior 37.3%** (n=6192). Prior by source/type: cubicasa count 54.6% · swiss count 24.5% · swiss area 6.2% · ifc area 2.9% (n=816) · ifc count 9.2% · opening_design count 25.0%. Every intent must reach >= prior or be amber (W2 core gate). Per-intent prior: `evalkit/out/20261114-130042-prior/report.md` section 3.
- NO plugins exist yet: `engine/raster/plugin.py`, `engine/takeoff/plugin.py`, `engine/skeptic/`, `engine/vector/`, `engine/triage/` are all absent. Step 1 is yours.
- Correct raster entry points: `engine.count.count(intent, facts) -> (value, element_ids, runs)` (NOT `engine.count.intents.count`) and `engine.raster.extract.extract(path, allow_siblings=True) -> SheetFacts` (cached by sha256 in `cache/raster/`). Cold extract median 2.21 s/image, 4.3 s first call (model load): load once per process.
- **count_defaults -> Tag.defaulted (REQUIRED).** For showers_baths, kitchens, bathrooms the raster rule may return the dev-median prior instead of a detection and writes `facts.extras["count_defaults"][intent] = {value, reason}`. When that key is present for the asked intent: the value's Tag is `defaulted` (never `drawn`), add an Assumption with the `reason` as source, the detector voter's note says "prior fallback, no detector evidence", and that voter does NOT count toward green agreement. Add a test with a fixture carrying `count_defaults`. Reviewer checks this (docs/decisions/count-defaults-tag.md).
- Raster DEV150 (in-sample): windows 40 · floors 87.5 · toilets 70.6 · sinks 46.2 (BELOW prior 53.8: keep sinks amber or prefer another voter) · doors 57.1 · saunas 61.5 · bedrooms 33.3 · wc_rooms 60 · balconies 100 (n=4). Prior-vs-raster per intent is the input for the "never below prior" rule: where a voter is below the intent's prior, the pipeline should fall back to amber.
- Biggest DEV buckets by lost questions (n x (1 - prior)): ifc room_net_area 776 @ 1.0% · swiss room_labelled 546 @ 28.6% · windows 488 @ 6.6% · doors 384 @ 4.7% · room_area 180 @ 2.2% · apartment_net_area 160 @ 12.5%. These come from vector and raster voters; your job is that the route reaches them and never crashes.
- Takeoff gaps: `engine.decide.quote(facts, request, vibe, choices)` does NOT exist (only `ledger.rank(specs)`). For `POST /api/decide` return 501 with a clear message or a thin wrapper in YOUR file; do not edit `engine/decide/`. `engine/reconcile/` is a stub.
- UI uses fixtures; it needs `/api/ask`, `/api/facts`, `/api/scale` live. Keep response = `ProofObject` JSON exactly.
- Hard set: `evalkit/hard_questions.jsonl` has 10 rows, **0 verified** -> `--hard` scores nothing until a human verifies rows. Build the planner path and its FAKE-LLM tests anyway; do not invent verified rows.
- `ifcopenshell` is not installed in `.venv` (vector installs it); the pipeline must not import it at module level.
- Skip in W2: `a2a/` (W3), SSE stream polish beyond stage names.

You own: `engine/pipeline.py`, `engine/api.py`, `engine/router.py`, `engine/query/`, `engine/cache.py`, `api/`, `a2a/`, `tests/test_pipeline*.py`, `tests/test_api*.py`. Do not edit other packages; if you need a hook, write `docs/decisions/hook-<topic>.md`.

## Step 1 · plugins for W1 code (20 min, do this first, commit immediately)
Create thin `engine/raster/plugin.py` and `engine/takeoff/plugin.py` ONLY if the owners did not (check first; owners win). `register()` must call `registry.register_voter("detector", ..., kinds=("count",))` using `engine.count.count` and `engine.raster.extract.extract` <!-- gate:w1 corrected name -->, and `registry.register_voter("area_polygons", ..., kinds=("area",))` using `engine.takeoff`. Voters return `VoterResult(Voter(name, value, element_ids, runs, note), evidence=[...])`.

## Step 2 · router (`engine/router.py`)
`route(question, path) -> Ctx fields (intent, params, kind, lang)`. Layers, cheapest first, stop at the first confident hit:
1. `evalkit.intents.classify` (regex and the localized-template table).
2. Language-agnostic fallback: nearest known template by character n-gram TF-IDF (scikit-learn) over `evalkit/out/intent_labels.jsonl`, with a distance threshold. Measure LEAVE-ONE-LANGUAGE-OUT accuracy on that file write the overall number to `docs/claims/integrator.json` as `{"router_lolo": <accuracy>}`, and report it per language in your handoff (this is how we know the router survives the ~30 languages of the hidden set). 
3. Optional (only if `LLM_PROVIDER != none`): classify each DISTINCT normalised template once (digits and quoted names stripped), cache in `cache/templates.json`, log every call in `Cost.llm_calls/tokens`. The point to prove: LLM calls <= number of distinct templates, not number of questions. Add a counter test.
4. **Planner + query engine (merged plan; CORE, not optional).** The judges use harder questions than the dataset.
   - Build `engine/query/` first, with no LLM: `run(spec, facts) -> Result{value, unit, evidence_ids, rule_applied, needs_scale, groups}` over SheetFacts. shapely for containment, adjacency and area; networkx for the room graph (apartments = connected groups behind entrance doors).
   - Spec: `{select, where{room_type, subtype, label, storey, has{kind}, adjacent_to{...}}, group_by, aggregate (count|sum_area|max_area|list|sum_length), rules[]}`; JSON schema in `engine/query/schema.json`. Convention rules are named, tested functions (door requires leaf, double bowl = 1 sink, separate WC is not a bathroom, kitchenettes count, glazed balconies count).
   - Re-express the 12 cubicasa intents as fixed specs and show on DEV that they give the same answers as the intent path.
   - Only if `LLM_PROVIDER != none`: send the question + schema + the element kinds and room types present in THIS drawing's facts + rule names; get a spec back; validate it (reject unknown keys and kinds); run it. Multi-part questions = several specs combined in code. LLM client: reuse the endpoint, auth and cost logic of `scripts/verda.py` (per-model base URL; Bearer key or Modal-Key/Modal-Secret headers; ledger and budget cap); do not write a second client. The LLM never returns the number. Set `po.query_spec`, count `cost.planner_calls`. A planner answer is amber at best unless an independent voter agrees.
5. Else `intent="unknown"` -> grey with a clear reason (product mode) or best guess from the answerer's nearest kind (benchmark mode).
Normalisation: NFKC, casefold, strip digits and text inside quotes before template matching.

## Step 3 · pipeline (`engine/pipeline.py`, class `PipelineEngine` implementing `contracts.interfaces.Engine`)
Order for `ask(path, question, allow_siblings, benchmark)`:
1. `registry.autodiscover()` once per process.
2. Route the question -> `Ctx`.
3. Cache lookup `(sha256(file), allow_siblings)` -> `SheetFacts` (`engine/cache.py`, JSON on disk under `cache/`, atomic writes).
4. Triage plugins. If a triager returns `refuse` and `benchmark=False` -> grey ProofObject with that reason (no value). In benchmark mode keep going, but add the note and force tier amber at best.
5. Resolvers in priority order (only if `allow_siblings`): set `ctx.resolved`; record `provenance.resolved_from`.
6. Extract facts if needed (raster plugin), then run ALL voters for `ctx.kind`; collect `VoterResult`s. A voter that raises is recorded as a note, never a crash.
7. Value and tier: count -> value = the exact-source voter if present, else the median of voters (ties -> the voter with the smaller TTA spread); tier green iff >= 2 independent voters agree exactly (area/length/volume: within 2%), amber if they disagree or only one voter exists, grey on refusal. Then run finalizers (stacker) which may adjust the value; record their note and a `Voter(name="stacker")`.
8. Area/volume/length: attach `ScaleInfo`, `assumptions`, `decisions_open`, `interval` from `engine.takeoff`/`engine.scale` where the intent needs them. Counts never need scale.
9. Cost: wall ms (perf_counter), tokens/usd/llm_calls (0 unless an LLM was used). Calibrators: store `notes += [f"historically right {p:.0%} of the time at this agreement level"]` ONLY when a calibrator exists.
10. Always run `contracts.invariants.check(po)`; if violations, downgrade tier to amber and append the violations to `notes` (fail loudly in logs, not in the user's face).
Must work with ZERO plugins registered (returns amber 0 with a note), so the stub path never breaks.

## Step 4 · API (`api/main.py`, FastAPI, CORS for http://localhost:5173)
`GET /health` · `POST /api/analyze` (multipart upload or JSON `{sample_id|path}`) -> `SheetFacts` · `POST /api/ask` `{path, question, allow_siblings, benchmark}` -> `ProofObject` · `POST /api/scale` `{path, anchors}` (user tap/line/typed scale) -> recomputed `ProofObject`s · `POST /api/decide` `{path, request, vibe, choices}` -> `engine.decide.quote(...)` · `GET /api/cost` (cumulative ms/tokens/usd/llm_calls) · `GET /api/stream/{job}` (SSE of stage names with timestamps: triage, resolve, extract, vote, finalize — the UI uses it for the live reasoning view). Uploads go to `cache/uploads/<sha256>.<ext>` and are never executed.

## Gates
```
.venv/bin/python -m pytest tests -q
make api &  sleep 3; curl -sS http://localhost:8000/health; kill %1
.venv/bin/python -m evalkit.run --engine pipeline --limit 100 --split dev    # end to end, no crashes
```
Plus tests for: zero plugins, a plugin that raises, a disagreement producing amber, two agreeing voters producing green, the LLM-call counter (<= distinct templates), the leave-one-language-out report, spec validation rejecting unknown fields, fixed specs matching the intent path on the fixture, and the planner path with a FAKE LLM setting `query_spec` and `planner_calls` and never taking a number from the LLM.

## Don'ts
No network calls in `ask` unless `LLM_PROVIDER != none`. Do not block on missing plugins. Do not reimplement extraction or voting logic. Do not touch the contracts.

## Handoff
`docs/handoff/integrator.md`: plugin API recap, router accuracy per language, LLM calls vs distinct templates, endpoints with example curl, how tiers are computed, known gaps. Commits `integrator: <what>`.