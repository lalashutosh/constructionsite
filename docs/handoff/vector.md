# Handoff: vector (W2)

Written by the lead on 2026-11-14 after verifying the P2 WIP (`68ee2c1`); the vector subagent was interrupted before writing this.
All numbers below come from `engine.vector.devcheck` runs on this machine (DEV split, `sha1(path) % 5 != 0`). Logs: `logs/p2/vector_dev_*.log` (gitignored).

## What exists
- `engine/siblings.py` + `engine/vector/plugin.py::register()`: resolver `vector_siblings`, priority 10, order dxf, ifc, svg, vector pdf, png.
  `allow_siblings=False` always returns None. `--related` (`PLUMB_RELATED=1`, a model IFC for a per-storey PDF whose name starts with the IFC stem)
  is opt-in only and reported as its own row.
- Readers: `dxf.py` + `dxf_query.py` (Swiss Dwellings layers), `ifc.py` + `ifc_query.py` (ifcopenshell 0.9.0, `Qto_*BaseQuantities` first, geometry
  fallback), `swisspdf.py` / `pdfvec.py` (vector PDF text + paths), `svgvec.py`, `schedule.py` (opening_design door schedules).
- Door counting rule (DXF): one door = one 5-point open polyline on layer `DOOR` (one frame per opening; a double door shares one frame);
  stacked ARC/leaf duplicates and the second arc of a double door are not counted. Gives 90/90 swiss `doors` on DEV.

## Measured (DEV)
| source | siblings on | no siblings | related | s/file median (max) |
|---|---|---|---|---|
| swiss_dwellings (n=1622) | **99.3%** [98.7, 99.6], green 1232 @ 100% | 66.8% [64.5, 69.1] | n/a | 0.13 (1.04) |
| ifc_models (n=995) | **96.6%** [95.3, 97.5], green 654 @ 100% | 96.0% [94.6, 97.0] | 98.0% [96.9, 98.7] | 1.11 (4.02); related 3.85 (15.4) |
| opening_design (n=29) | 55.2% [37.5, 71.6] | 55.2% | n/a | 0.25 |

Gate commands: `engine.vector.smoke` PASS in 4.4 s (swiss 20/20, ifc 9/10, opening 5/5); all three devchecks exit 0; `pytest -k vector` 9 passed.
Without siblings, swiss PDF answers counts from the PDF itself (doors, rooms, fixtures 100%) but not areas or windows (0%): those need the DXF.

## Known failures
- ifc `count_in_model` 1/27 (55.6% with `--related`): whole-model counts asked on a per-storey PDF. FZK-Haus has no IFC in the preview set,
  so those 12 are unanswerable from the given files.
- swiss `apartment_net_area` 152/160 and `total_net_area` 86/90: two buildings (site157, site1098) include unnamed, unlabelled rooms that the
  truth excludes. Tested "exclude every unnamed unlabelled room": fixes 8, breaks 18, so not applied. The truth likely uses a room-type
  attribute the DXF does not carry (shaft/void). Left as is.
- opening_design: `room_schedule_area` 0/6 and `door_schedule_total_rooms` 0/1 (room-finish schedule on A-801 not parsed); 7 `unknown`-intent
  questions mostly unanswered. Tiny bucket (29 DEV), lowest priority.
- ifc_bench (text) skipped as specified.

## Run
`.venv/bin/python -m engine.vector.smoke` · `.venv/bin/python -m engine.vector.devcheck --source <src> [--no-siblings] [--related]`
Verda calls used: 0.
