# Element overrides (engine + API)

Users can change what an element is; every count/area recomputes with their decision.

## What works
- `engine/overrides_el.py`: storage `cache/element_overrides/<sha>.json` (atomic write). Records
  `{element_id, action: retype|remove|restore, kind?, subtype?, at}`; last record per element wins, `restore` cancels,
  `undo` pops the last record. Kinds: door, window, opening, fixture, wall, room, stair, not_element (= remove). Room
  subtypes: bedroom kitchen living bathroom wc sauna storage hall(->"hallway", the extractor's spelling) balcony other.
- `apply(facts, sha)` returns a copy: retyped elements get new kind/subtype, conf 1.0,
  `attrs["user_override"]={"from_kind","from_subtype","tag":"chosen"}`; removed ones leave `elements` and are listed in
  `extras["removed_by_user"]` (original element kept). `extras["cnn_runs"][kind]` is shifted by the user's delta, so the
  detector voter's runs agree with the new count. Also stamps `extras["overrides_hash"]` and `extras["user_overrides"]`.
- Pipeline hook (`engine/pipeline.py`, TWO small blocks marked `# --- element overrides (user) ---`): one right after
  `facts = ctx.facts` (apply before voting), one right before the numpy-attrs cleanup (receipt via `overrides_el.annotate`):
  note "you changed element <id> from X to Y" + `Assumption(key="user_element:<id>", tag=chosen)`, also for removed
  elements and for elements that were lost from / gained by this intent.
- Cache: there is no ProofObject answer cache; cache/pipeline holds the pure extraction and overrides are applied on a
  copy AFTER the lookup, so an override takes effect on the next question. `overrides_hash(sha)` ("" when none) is the key
  to use if an answer cache is added.
- Tier: unchanged logic (voter agreement). The user's decision is visible as `chosen` assumptions and notes.

## API (`api/main.py`)
- `GET /api/elements?path=&allow_siblings=true` ->
  `{"elements":[{"id":"door3","kind":"door","subtype":null,"label":null,"conf":0.82,"polygon":[[x,y],...],
  "size_m":{"w":0.9,"h":0.1} | null,"tag":"drawn|specified|chosen","feeds":["doors"],
  "explanation":"This is a door, read from the CubiCasa model (82% sure). Counts toward 'How many doors'.",
  "user_override":null}], "removed_by_user":[{id,from_kind,from_subtype,at}], "overrides_hash":"", "allowed_kinds":[...],
  "room_subtypes":[...]}`. Rooms also carry `size_m.area_m2`. `size_m` is null when the scale is unsolved.
- `POST /api/elements/override` `{"path":..., "element_id":"door3","action":"retype","kind":"window"}` (or
  `"action":"remove"`, `"restore"`, rooms: `"kind":"room","subtype":"kitchen"`) ->
  `{"element":{...row, "tag":"chosen"} | null (removed), "removed":false,
  "findings":[{"intent":"doors","question":"How many doors are there?","value":2,"unit":"count","tier":"amber",
  "answer_text":"...","notes":["you changed element door3 from door to window (no longer counted here)"]},
  {"intent":"windows","value":15,...}], "overrides_hash":"ab12..."}`. 404 unknown element, 422 bad kind/subtype/action.
- `POST /api/elements/undo` `{"path":...}` -> `{"undone":{record}|null, "findings":[...], "overrides_hash":...}`.
- Findings are recomputed in product mode (`benchmark=false`): a drawing the triage refuses returns grey/null values.
- Not covered: removing a `label` element does not change counts that read raw OCR labels from other sources; per-floor
  split (`sheetfloor`) and the 3D geometry builders read their own caches and do not yet see overrides.

## Run
`.venv/bin/python -m pytest tests/test_element_overrides.py -q` (7 tests, ~4 s, no network). No existing `tests/test_checks*.py`.
