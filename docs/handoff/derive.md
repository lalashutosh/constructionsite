# Derived quantities (tiles, paint, carpet, lights, skirting)

Owner: takeoff. Files: `engine/takeoff/derive.py`, `tests/test_derive.py`; small edits in `engine/pipeline.py` (one delimited
block at the top of `ask`), `engine/answer_text.py` (room labels), `engine/query/planner.py` (tolerates a `derive` object),
`engine/takeoff/materials.py` (`tiles_count` rounds before `ceil`: 19.8*1.1/0.09 is 242.00000000000003 in floats).

## How it works
`derive.parse(question)` (regex; en, fi, de, fr, it) -> `DeriveSpec` or None. `ask` then calls `derive.answer`, which runs a base
question through the normal `ask` (siblings, triage, scale, tiers, evidence all as usual) on a copy of the engine, and
`derive.wrap` replaces value / unit / answer_text / assumptions / decisions. The LLM never produces the number.
- Named room we have a code for (living, bedroom, kitchen, bathroom, wc, hallway, sauna, balcony, storage, entry, dining) or
  "whole flat": the base spec `{select room, aggregate sum_area, where room_type}` is built by code and fed to the planner
  slot through a zero-cost stub (`_SpecLLM`), so there are 0 LLM calls, with or without `LLM_PROVIDER`. The base question text is
  deliberately neutral ("derived quantity base: ...") so no fixed template (e.g. sheet-level `total_room_area`) hijacks it.
- Room phrase with no code ("study"): LLM on -> the real planner translates it; LLM off -> grey, asks to name the room.
- Base is run with `benchmark=False`: a derived quantity is never built on the dev-median prior.
- Tile size missing: no guess. value None, tier grey, answer says what is needed, `decisions_open` has `tile_size` with the count per
  option (30x30 / 45x45 / 60x60 / 60x120, 10% waste).
- Assumptions: stated parameters are tagged `chosen` ("user (in the question)"); defaults (waste 10%, 2 coats, 8 m2/l, 2.5 m,
  4 m roll, 300 lx, 1500 lm, u 0.6) are `defaulted`, source `code table v1`. Waste / coats get an open Decision with the spread.
- Scale: the derived answer inherits the base tier; if the scale is only the door prior it says so and gets an interval
  (dA/A = 2 ds/s, counts at both ends). `_restore_scale` puts the engine's ScaleInfo back, because a planner-built area on a raster
  drawing otherwise ends with the "px_per_m=1 real units" placeholder (a pipeline bug in `_attach_scale` when the route kind was count).
- Perimeter / short side for paint, skirting, carpet, cut notes come from the evidence room outlines, scaled by the area (no new scale).
- Planner: a `derive` object in the planner reply is validated (`derive.from_obj`) and kept on `Plan.derive`; NOT yet carried into
  the proof (follow-up for the integrator: `_plan_vote` -> `derive.wrap`). The planner prompt does not ask for it yet.
- False-positive guard: 8,000 dataset + hard questions -> 0 hijacked (needs "how many <material>" with a purchase cue, a size, or a
  first-person need; "how many tiles are in the bathroom" and "how many rooms have a ceramic tile base" fall through).

## Measured
`DATASET_ROOT=... pytest tests/test_derive.py tests/takeoff -q` green. Full suite: 1 failure,
`tests/test_count_rules_finetune.py::test_colorful_2002_has_two_bedrooms` (3 != 2), fails identically without my edits.
E2E on `data/cubicasa5k/colorful-6327.png` (door-prior scale, one living room, 25.8 m2): "how many 3x3 metre tiles do i need for my
living room ?" -> 4 tiles, amber, interval 3..4, both LLM off and LLM_PROVIDER=verda (0 LLM calls, $0).

## Known gaps
- Door/window openings are not deducted from paint (listed as assumption `openings_deducted_m2 = 0`).
- Skirting does not subtract door widths. Multi-floor sheets: perimeter uses evidence outlines only when they agree with the area.
- Languages beyond en/fi/de/fr/it, and unit-less sizes (guessed: >=100 mm, >=8 cm, else m; noted) may mis-parse.
- Answer wording for the aggregate area sentence changed: one matched room -> "The living room covers 19.8 m²."
