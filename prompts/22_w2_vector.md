# W2 · VECTOR (agent: vector, branch w2/vector, budget ~90 min)

Mission: when the drawing exists in an exact format, read the exact format and say so. This is a large share of the questions: swiss_dwellings 2,358 (pdf with same-stem .dxf and .png), ifc_models 1,049 (827 on .ifc itself, 222 on pdf with an svg sibling), opening_design 64 (door-schedule PDFs), ifc_bench 249 (text). Exact sources are labelled `exact` in the proof and are never confused with pixel guesses.

Read first: `AGENTS.md`, `engine/registry.py`, `vendor/planlab/README.md` + `analysis.py` (DXF parser from our earlier prototype), `docs/recon.md` (swiss, ifc_models, opening_design templates), `docs/handoff/evaluator.md`.

You own: `engine/vector/`, `engine/siblings.py`, `tests/test_vector*.py`. Expose through `engine/vector/plugin.py::register()`.

## Step 1 · sibling resolver (`engine/siblings.py`, `register_resolver`, priority 10)
`resolve(path, allow_siblings) -> Resolved | None`. Same directory, same stem, other extension. Priority: `.ifc`, `.dxf`, `.svg`, vector `.pdf`, `.png`. `allow_siblings=False` returns None always. The README rule: files with the same name and a different extension are the same drawing in another format. Optional stretch (separate flag `--related`, always reported as its own number): a model-level IFC for a per-storey PDF whose name starts with the IFC stem. Never silently enable it.

## Step 2 · IFC (CORE; `engine/vector/ifc.py`)
`pip install ifcopenshell` into the venv (wheels exist for macOS arm64/x86 and Linux). Intents: `room_net_area{room,storey}`, `doors_on_storey`, `walls_length{storey}`, `walls_volume{storey}`, `slabs_volume{storey}`, plus counts. Strategy: (1) read the model's own `Qto_*BaseQuantities` (NetFloorArea, Length, NetVolume, GrossVolume) via `ifcopenshell.util.element.get_psets`; (2) fall back to geometry with `ifcopenshell.geom` + shapely when quantities are missing, and say which in `Voter.note`; (3) match storey and room names after NFKC + casefold + whitespace squeeze; question language differs from model language (Estonian, Danish, Finnish), so match on the quoted name and the storey token, not on translated words. Two voters when possible: `ifc_quantity` and `ifc_geometry`; they agree within 2% -> green. Units: read `IfcUnitAssignment`; never assume metres.

## Step 3 · DXF (`engine/vector/dxf.py`)
Wrap `vendor/planlab` (parses the Swiss Dwellings layers ROOM_OUTLINE, DOOR, WINDOW, WALL, UNIT_OUTLINE, ROOM_TEXT, ... and reached 88.9% on a Swiss slice earlier). Intents: `apartments, doors, windows, toilets, washbasins, bathtubs, total_net_area, apartment_net_area{letter}`. Known open problem: door counts disagreed with the key (37 of 65 matched) — the likely cause is a counting convention (doorways fitted with a leaf only; paired leaves; entrance doors). Run `devcheck`, diff predicted vs truth per file, find the rule from the data, document it with the question template in the code. Net area excludes balconies, loggias and terraces: use `$INSUNITS` plus a known dimension to verify units.

## Step 4 · schedules and vector PDFs (`engine/vector/pdfvec.py`, `schedule.py`)
- `opening_design` PDFs are door schedules with a text layer: PyMuPDF `page.find_tables()` (fallback: `get_text("words")` clustering by x/y) -> rows. Generic row filter parsed from the question: total rows; by type code (A1, B2 ...), material (WD-1), frame (STL-2, AL-1), note letter, width string like 3'-0". The question's parenthetical text tells you the column. Evidence = cell bounding boxes mapped to rendered-page pixel coordinates (render at 150 dpi, scale factor 150/72).
- Vector floor-plan PDFs: `page.get_drawings()` exposes exact paths; if rooms/doors can be rebuilt from path groups do it, otherwise render at 150 dpi and hand off to the pixel route (return None; the integrator falls back).
- SVG siblings: parse paths and groups directly (`xml.etree`), same intent set as DXF where layer or id names allow.
- Scanned schedule (no text layer): return None. Do not guess.

## Step 5 · voters
Register voters with `exact=True` for exact sources. For counts try to provide a second INDEPENDENT voter on the same exact file (for example door count from the layer vs door count from swing-arc blocks; IFC quantity vs geometry; schedule rows vs the schedule's printed total). Single exact voter -> tier amber with note "exact source, single voter" (never claim green on one voter).

## Step 6 · dev loop (`engine/vector/devcheck.py`)
Reads `questions.jsonl`, DEV split (`int(sha1(path).hexdigest(),16) % 5 != 0`), per source and intent: accuracy with Wilson CI, runtime per file. Show the 15 worst failures with paths. Iterate on the biggest bucket first (swiss doors, ifc areas). Stop when two iterations gain < 1 point or after 90 minutes.

## Gates
```
.venv/bin/python -m engine.vector.smoke          # 10 swiss + 10 ifc + 5 schedule samples, exit 0
.venv/bin/python -m engine.vector.devcheck --source swiss_dwellings
.venv/bin/python -m engine.vector.devcheck --source ifc_models
.venv/bin/python -m engine.vector.devcheck --source opening_design
.venv/bin/python -m pytest tests -q -k vector
```
Handoff: per-source, per-intent DEV accuracy with CIs, the door counting rule you derived, seconds per file, anything you could not read.

## Don'ts
No network. Never assume units. Do not use siblings when `allow_siblings=False`. Do not report an exact-source number as if it came from pixels: `provenance.resolved_from` is mandatory. Never tune on HOLDOUT.

## Handoff
`docs/handoff/vector.md`. Commits `vector: <what>`.
