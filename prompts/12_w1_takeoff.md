# W1 · TAKEOFF (agent: takeoff, branch w1/takeoff, budget ~75 min)

Mission: the "what would you order, and what must you decide first" brain. Pure Python, no model calls, every function tested against a hand-computed answer. Inputs are `SheetFacts` (contract) + choices; outputs are `ProofObject`s whose assumptions and open decisions are complete and honest.

Read first: `AGENTS.md`, `contracts/proof.py` (ScaleInfo, ScaleAnchor, Assumption, Decision, Option, Interval, ProofObject), `contracts/fixtures/sample_facts.json` and `sample_proof_area.json`.

**Merged-plan priority:** Step 1 (scale), `area.py` and `door_schedule.py` are core and are what the W1 gate checks. `materials.py`, the vibe files and the decision ledger (Step 3) are stretch: build them only after the core parts pass their tests; they are the first thing cut.

You own: `engine/scale/`, `engine/takeoff/`, `engine/decide/`, `engine/reconcile/` (stub only in W1), `tests/takeoff/`. Nothing else.

## Step 1 · scale (`engine/scale/anchors.py`)
`solve(facts, user_anchors=()) -> ScaleInfo`.
Anchors, best first: (1) `scale_bar` or `dimension` string (parse "3 600", "3.60 m", "12'-6\"" etc., match to a measured segment) · (2) `printed_ratio` + paper size (1:100 on A3 ...; sheet DPI from `facts.extras` if present) · (3) `printed_area` label (a room area printed in the drawing, e.g. "12.4 m2" -> px_per_m = sqrt(area_px / area_m2)) · (4) `door_prior` (median detected door leaf width = 0.9 m, rel_sigma 0.12, tag `defaulted`) · (5) `user` (tap/line; rel_sigma 0.01).
Combine anchors with inverse-variance weights; reject outliers beyond 3 sigma and record why. Rules (tested): if the only anchor is `door_prior` then `widths_relative = True` and `needs_user = True`; widths of doors must never be reported as measured in that case (circular evidence). Counts never need scale.
`next_question(facts, info)` returns the CHEAPEST question to ask the user, in order: "tap a door: is it 0.9 m?" -> "draw a line over something you know and type its length" -> "type the printed scale". Include the expected reduction in interval width for each.

## Step 2 · quantities (`engine/takeoff/`)
Use shapely; polygons are in original pixels; convert with `px_per_m`.
- `area.py`: polygon area, net floor area of a room, apartment total (exclude balconies, loggias, terraces), interval from scale: dA/A = 2 ds/s plus polygon error; confirm with a seeded Monte Carlo (n = 2000, seed 7) in a test.
- `materials.py`: paint litres V = n * (P*h - sum(opening areas)) / c (n coats, h ceiling height, c coverage); tiles N = ceil(A * (1 + w) / a_tile) with waste w; carpet by roll width with trim waste (strip packing along the longer axis); lights N = ceil(E * A / (F * u)) (E target lux, F lumens per fitting, u utilisation). Every constant comes from the chosen vibe YAML or the user and appears in `assumptions` with a `Tag`.
- `engine/decide/vibes/{budget,standard,premium,nordic}.yaml`: every value `source: assumption`, editable, NO prices and NO brand names. Include ceiling height, paint coats and coverage, tile size and waste, lux targets, door leaf width, door finish class.
- `door_schedule.py`: `build(facts) -> list[DoorRow]` with id, from-room, to-room (nearest two distinct room polygons to the door centre), leaf width (relative or metres), swing, element ids, open decisions; `to_csv(rows)`. This is the hero export: "draft door schedule generated from the plan".

## Step 3 · decisions (`engine/decide/ledger.py`)
`rank(facts, quantity, vibe, choices) -> list[Decision]`.
- Each decision (door leaf width, ceiling height, tile size, paint coats, fitting type ...) has options; compute the quantity for every option; impact `I_d = max_o Q(o) - min_o Q(o)` in the quantity's own unit; sort descending; mark the top 3 as questions, keep the rest defaulted but listed.
- Options are filtered by physical fit: opening width limits the leaf (clear passage != leaf != opening width). Show `fits=False` options greyed with the reason, never silently drop.
- Two lanes: `vibe` (pick a preset -> everything defaulted and tagged `defaulted`) and `decide` (the user answers; tags become `chosen`). Changing one answer recomputes the interval; the interval must shrink or stay equal when a decision is made (property test).
- `quote(facts, request, vibe, choices) -> list[ProofObject]` is the single entry point others call. `request.kind` in {floor_area, wall_paint, tiles, carpet, lights, door_schedule}.

## Step 4 · tests (`tests/takeoff/`)
Hand-computed cases for every formula (write the arithmetic in a comment), the circularity rule, outlier rejection, interval shrink property, option fit filtering, door schedule on the fixture, `invariants.check` on every ProofObject produced. All run in < 20 s.

## Gates
```
.venv/bin/python -m pytest tests/takeoff -q
.venv/bin/python -m engine.takeoff.demo contracts/fixtures/sample_facts.json --vibe standard   # prints receipt JSON, validates against ProofObject
.venv/bin/python -m engine.takeoff.demo contracts/fixtures/sample_facts.json --door-schedule   # prints CSV
```

## Don'ts
No prices, no brand names, no web calls, no randomness without seed 7. Never invent geometry; if the facts lack rooms, return a grey ProofObject with a refusal reason. Do not edit `contracts/` (write `docs/decisions/contract-<topic>.md` instead).

## Handoff
`docs/handoff/takeoff.md`: function signatures others call (`scale.solve`, `scale.next_question`, `takeoff.quote`, `door_schedule.build`), the vibe files, test summary, known limits. Small commits `takeoff: <what>`.
