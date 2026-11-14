# Handoff: takeoff (engine/scale, engine/takeoff, engine/decide, engine/reconcile)

## Status
Core scope for this cycle (scale anchors, area takeoff, draft door schedule) was
already implemented in a previous cycle (commit `79d8dc3`) and verified green;
this pass re-ran the gates, read every module end to end, and confirmed nothing
is stubbed or faked. No code changes were needed.

## Gate commands (all green)
```
.venv/bin/python -m pytest tests/takeoff -q
  -> 44 passed in 0.19s

.venv/bin/python -m engine.takeoff.demo contracts/fixtures/sample_facts.json --vibe standard
  -> prints ProofObject JSON; round-tripped through ProofObject(**json) -> validates,
     tier=green, value=20.0 m2, passes contracts/invariants.check (demo.py calls it
     before printing and would exit non-zero on a violation)

.venv/bin/python -m engine.takeoff.demo contracts/fixtures/sample_facts.json --door-schedule
  -> prints CSV, header + 7 door rows (d0..d6)
```

## Function signatures other agents call

### `engine/scale/anchors.py`
- `solve(facts: SheetFacts, user_anchors: tuple[dict, ...] = ()) -> ScaleInfo`
  Anchor priority: scale_bar/dimension string (rel_sigma 0.02) > printed_ratio +
  paper size/DPI (rel_sigma 0.03-0.10 depending on how DPI was obtained) >
  printed_area label matched to nearest room polygon (rel_sigma 0.02) > door_prior
  (median detected door leaf = 0.9 m, tag `defaulted`, rel_sigma 0.12) > user tap
  (tag `chosen`, rel_sigma 0.01 by default). Anchors are combined by
  inverse-variance weighting in log space; any anchor more than 3 sigma from the
  **unweighted median** of all anchor logs is rejected as an outlier (comment in
  the file explains why the median, not the weighted mean, is the outlier
  reference — an overconfident wrong anchor would otherwise never look like an
  outlier against its own weighted mean). If the only surviving anchor kind is
  `door_prior`, `ScaleInfo.widths_relative=True` and `needs_user=True` (circular
  evidence rule) — enforced by `test_door_prior_only_sets_widths_relative_and_needs_user`.
- `next_question(facts, info) -> list[NextQuestion]` — cheapest-first: tap a door
  -> draw+type a known length -> type the printed scale; each entry reports the
  resulting rel_sigma and the % drop in the area interval half-width
  (dA/A = 2 ds/s). Empty list when `info.needs_user` is already False.
- `parse_dimension(text) -> Optional[float]` handles "3 600" (space-grouped mm),
  "3.60 m", "3600 mm", `12'-6"`; returns `None` (never guesses) on unrecognised text.

### `engine/takeoff/area.py`
- `polygon_area_px` / `polygon_perimeter_px` — shoelace via shapely.
- `room_area_m2(room, px_per_m)`, `room_perimeter_m`.
- `apartment_total_m2(rooms, px_per_m, exclude_subtypes=...)` — excludes balcony/
  loggia/terrace by subtype by default.
- `area_interval(area_m2, scale_rel_sigma, polygon_rel_sigma=0.0) -> (lo, hi)` —
  analytic `dA/A ≈ 2*ds/s` combined in quadrature with polygon error; verified
  against a seeded Monte Carlo (n=2000, seed 7) in
  `test_area_interval_monte_carlo_matches_analytic`; `lo` is clamped at 0.

### `engine/takeoff/door_schedule.py`
- `DoorRow` dataclass: id, from_room, to_room, width_m, width_error_m (or
  `width_px_relative` when scale is circular-evidence-only), swing, element_ids,
  open_decisions.
- `build(facts, scale=None) -> list[DoorRow]` — matches each door to its two
  nearest distinct room polygons by centroid distance; a door touching only one
  room polygon is assumed exterior and gets an `open_decisions` note asking for
  confirmation; when `scale.widths_relative` is True, widths are reported in
  pixels under `width_px_relative`, never as metres (no circular evidence).
- `to_csv(rows) -> str` — header + one row per door, exportable.

### `engine/takeoff/materials.py` (stretch, implemented)
`paint_litres`, `tiles_count`, `lights_count`, `carpet_rolls` — formulas as in
the spec (paint V = n(Ph - sum openings)/c; tiles N = ceil(A(1+w)/a_t); lights
N = ceil(EA/(Fu)); carpet by roll width with trim waste). Hand-computed tests in
`tests/takeoff/test_materials.py`.

### `engine/decide/vibe.py` + `engine/decide/vibes/*.yaml`
Four presets (budget/standard/premium/nordic), every value `source: assumption`,
no prices, no brand names.

### `engine/decide/ledger.py` (stretch, partial)
`rank(specs: list[DecisionSpec]) -> list[Decision]` — impact = max(Q(option)) -
min(Q(option)), sorted descending, top 3 tagged as open questions, rest
`defaulted`; option fit filtering (clear passage <= leaf <= opening) tested in
`test_door_leaf_fit_filters_by_opening_width` / `test_clear_passage_minimum_also_filters`.
Note: the spec's full `rank(facts, quantity, vibe, choices)` / `quote(facts,
request, vibe, choices)` entry points described in `prompts/12_w1_takeoff.md`
Step 3 were marked lower priority than core ("stretch, cut first") and were not
built out to that full signature this cycle — `rank` currently takes pre-built
`DecisionSpec` objects rather than deriving them from `facts`. Flagging as the
known gap if Step 3 needs the full wiring.

## Test summary
`tests/takeoff/` — 44 tests, 0.19s, covering: dimension-string parsing (grouped
mm, metres, mm, feet-inches, unrecognised->None), door-prior-only circularity
rule, no-anchors needs_user, printed-area+door-prior combination, outlier
rejection (3-sigma, reason recorded on the anchor note), the sample fixture,
printed-ratio-with-dpi, user-anchor tagging, next_question ordering; polygon
area (square/triangle hand-computed), room area from fixture, non-positive
scale rejection, apartment total excluding balcony, area interval hand-computed
+ Monte Carlo cross-check + non-negative lo; door schedule two-room match,
single-room exterior assumption, no-rooms case, relative-width reporting (with
and without scale), CSV shape, sample fixture; ledger impact ranking, top-3
tagging, door-leaf/clear-passage fit filtering; materials paint/tiles/lights/
carpet hand-computed cases.

## Known limits
- `engine/decide/ledger.py` does not yet expose the `rank(facts, ...)` /
  `quote(facts, request, vibe, choices)` facts-driven entry points from the
  spec (see above) — it works from already-built `DecisionSpec`s.
- `engine/reconcile/` is still a stub (`__init__.py` only), as instructed for W1
  ("stub only in W1").
- No vector sibling resolution here (out of scope — owned by `engine/vector/`).

## How to run
```
.venv/bin/python -m pytest tests/takeoff -q
.venv/bin/python -m engine.takeoff.demo contracts/fixtures/sample_facts.json --vibe standard
.venv/bin/python -m engine.takeoff.demo contracts/fixtures/sample_facts.json --door-schedule
```
