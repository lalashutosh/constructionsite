# Handoff: deep reading of very complex sheets (judges' ask, 2026-11-14 ~23:10)

The judges looked at `us_daf_dorm_sd_drawings_april_2026_p003.png` (A-2 dorm, 10200x6600 px; our copy
`cache/stress/a2dorm.png`, upload sha `a92115880ee3...`). The foundations we have are good: scale (49.2 px/m, half-size
print), outer walls (legend-zone union), wings, printed tables. What they want next:

1. **Complexity -> deep mode.** Detect that a sheet is huge/dense (px, ink density, repeated symbols, many rooms) and
   switch to a slower in-depth pass; TELL the user up front ("deep read: ~2-4 min") and show progress.
2. **Every room individually labelled**: Hallway 1, Hallway 2, Room 1 ..., "Green room 1..n" (legend colour), Gym,
   Common area, stairs. Each element (door, closet, bed, side table, sofa, chair, desk/table, TV, gym equipment, stair
   flight) is its own node (selectable in 2D/3D, inspector already exists: web/src/inspector.tsx, /api/elements).
3. **Final checklist**: totals per kind (doors, closets, beds, side tables, sofas, chairs, tables/desks, TVs, stair sets,
   gym items), each count clickable to its evidence boxes, per wing (bottom-left, bottom-right, middle, top).
4. **Layers like a body (skin / skeleton / organs / nerves)**: envelope/walls one colour, piping another, electrical
   another, furniture another; toggle each layer in the viewer. Piping/electrical come from MEP sheets (M-101A is a piping
   plan: black linework over the screened grey architecture = engine/outline.py already separates the two layers).
5. **Viewer**: 2D / 3D toggle in the top-right (like a CAD view cube), mixed mode (selected areas 3D, rest 2D), top/side
   views, pan, orbit, zoom, re-centre.

## Plan (how, within the rules: the LLM never produces a number)
- **Symbol discovery by repetition (code)**: inside each room, connected thin-line ink components (furniture symbols)
  are normalised (size, rotation 0/90/180/270, mirror) and clustered; a cluster that repeats is a symbol TYPE. Counts =
  cluster sizes (code). A vision model names each type ONCE from one exemplar crop (bed / desk / chair / sofa / TV /
  closet / door swing / treadmill ...), cached per type (rule 8a: classify each distinct template once). Second voter:
  per-module structure (48 identical dorm modules x symbols per module) or template matching (NCC) of the exemplar.
- **Rooms**: `engine/outline.subrooms` already finds the enclosed spaces (58 on the dorm); name them by legend colour
  ("Green room n" = DORMITORY zone), printed words, or the vision label reader; corridors = long thin spaces -> "Hallway n".
- **Deep mode**: `engine/profile.py` complexity + px count -> `profile["deep"]=True`; `/api/geometry` returns
  `deep: {eta_s, stages}`; UI shows "Deep read, about N min" banner.
- **Layers**: geometry JSON gets `layers: {envelope, walls, furniture, piping, electrical}`; piping = dark linework of an
  MEP sheet clipped to the screened building; electrical when an E-sheet is present (or none: say so).
- **Viewer**: web/src/viewer3d.ts + panels.tsx: view cube (2D/3D/top/side), layer toggles, pan/orbit/re-centre.

## Status (2026-11-15 ~00:40)
- [x] handoff written (this file)
- [x] deep-mode detection + ETA: `engine/symbols.deep_info` (>= 20 MP and complexity >= 0.55 or >= 20 rooms);
  `/api/geometry` carries `deep {on, reason, eta_s}`; checklist panel says "Deep read ... about N min" before starting
  and shows a progress bar (dorm: on, ~4 min estimate, real ~2 min).
- [x] symbol discovery + naming + checklist: `engine/symbols.py`, `GET /api/checklist?path=` (cached
  cache/symbols/<sha>-v6*.json). Dorm (upload a9211588...): Sinks 48 (green: 2 exemplars agree), Toilets 48, Beds 46
  (green), plus noisier types (Columns 32, Fridges 29, Bathtubs 23 = probably showers, Side tables 16, TVs 8, Chairs 4,
  Tables 5, 2 unnamed). ~$0.10 and ~2 min per sheet, paid once. Names come from 2 Verda vision reviewers on a context
  contact sheet with real sizes; code rejects names whose size is implausible (`SIZE_M`). Counting is code: shape
  clusters + template matching (NCC, 8 orientations, half resolution, every hit shape-verified, plausible <= 3.5x the
  cluster). WEAK SPOT: naming (fast reviewer often returns nothing; strong one varies run to run) -> next: let the user
  rename a type in the checklist (reuse the element override pattern), and add per-module structure as a 3rd voter.
- [x] rooms named individually: `symbols._room_names` -> "Dormitory n" (legend zone), "Hallway n" (aspect >= 4 or
  sprawling), printed space word, else "Room n" (from `engine/outline.subrooms`).
- [x] layers: `engine/layers.py` (envelope = verified outline, walls, furniture = checklist nodes, piping/electrical =
  black linework of an M-/P-/E- sheet over the screened building; discipline from the title-block sheet id). Viewer:
  `PlumbViewer.setLayers/setLayerVisible`, toggles `LayerToggles` (web/src/deepui.tsx). M-101A: 324 pipe runs.
- [x] viewer: octagon view cube top-right (`ViewCube`: tap = 2D top <-> 3D, drag = orbit, Top/Front/Side/3D, re-centre),
  zoom to cursor (OrbitControls.zoomToCursor), easeInOutCubic camera tweens, damping 0.07.
- [x] selection: chip above the question box; `/api/ask` takes `selected_id` (`engine/selected.py`: size / walls /
  what is this / how many X in here); checklist rows light up every instance (`setMulti`), rooms select + raise outline.
- [x] first-time tour (`Tour`, localStorage "plumb-tour"; "Tour" button re-opens): scale pins -> tags -> checklist -> view.
- [x] scans (CubiCasa hand-drawn): stairs via faint-ink + evenly-spaced-tread test; doors without arcs = interior wall
  openings (10000: 1 -> 6). DEV unchanged.
- [x] per wing / zone totals (`checklist.zones`, legend zones = wings, position words): dorm 3 dormitory wings x
  16 sinks / 16 toilets / 16 beds; common area tables. Stair flights row (tread detector inside the outline at 3000 px)
  finds none on the dorm yet (stairs there are small at that resolution) -> run it per wing at full resolution.
- [ ] NOT DONE: mixed 2D/3D "raise only the selected room" (currently the selected room is outlined + flown to, not
  extruded alone); per-wing totals (bottom-left / bottom-right / middle / top) in the checklist; electrical layer has no
  sheet in the stress set; browser QA of the new UI (built + type-checked only, not clicked through).

## Update 2026-11-15 ~01:30
- Deep read is the NORMAL read: the checklist panel starts it on open for every drawing (cached per sha); a sheet that
  is big says so with an ETA. The chatbot answers counts from it first (`symbols.answer` in `PipelineEngine.ask`):
  "how many beds" -> 46 with per-wing split; class words sum types ("valves" = control + check valves).
- Universal deep read (`engine/symbols.py` v12): stroke-level symbols + WHOLE symbols (strokes grouped: lounge sets,
  desk chairs, exercise bikes) + short heavy outlines (gym machines) + tagged equipment (FP/CV/FSCV via sheet defs /
  glossary / ISA-5.1) + printed tables + a code-built sheet summary ("Second Floor Plan ... Scale 1"=40'-0" ...").
  Names: 2 reviewers on a context contact sheet with sizes, size-checked by code, second pass for unnamed (direct, fast).
  Dorm: sinks 48 / toilets 48 / beds 46 / closets 29 / showers 23 ... (v11); treadmills still not grouped.
- Build plan: per-element units (`px_per_m` on elements; was 962790 m3 concrete), sheet's verified scale and deep-read
  counts for construction sheets; list layout fixed (`.flist .crow`).
- UI: themed view cube, layer bar bottom-left (+ room boundary lines), scale badge "Scale read from the drawing ·
  Where?" by the measuring button, findings hide refusals / zeros ("Not found on this sheet" collapsed), thumbnails
  in the checklist, selection chip -> `selected_id`.
- Gemini: `LLM_PROVIDER=gemini` + `GEMINI_API_KEY` (or GOOGLE_API_KEY) in .env, models GEMINI_MODEL_FAST/STRONG
  (default gemini-2.5-flash / -pro) via the OpenAI-compatible endpoint (`engine/query/llm.py`). NOT TESTED: no key in .env.
- Pitch notes: docs/PITCH_POINTERS.md.
- Open: shopping list merged with the checklist (today: Build plan tab has the materials, checklist has the counts);
  dorm doors (grey arcs); treadmills; per-type rename in the checklist.

## Update 2026-11-15 ~02:00 — the bottleneck is NAMING
- Detection finds and boxes far more than gets a good name. The Verda vision reviewers mis-name symbols (lounge set ->
  bed, desk chair -> sink); offering size-plausible candidate lists made it worse ('bathtub' for everything, reverted).
  Code's size check rejects impossible names (`rejected_names` in the cache json shows them).
- Fixes in place: (1) user rename in the checklist (pencil on a row -> `POST /api/checklist/rename`; every copy follows,
  same names merge, chatbot answers with it); (2) whole-symbol discovery (multi-stroke symbols) + short heavy outlines.
- NEXT: put `GEMINI_API_KEY` in .env and run with `LLM_PROVIDER=gemini` (or Claude for the demo) — the same pipeline
  with a stronger namer; template-match every NAMED type to catch copies touching walls (closets, TVs).
- Dorm cache currently = the best read (v11 copied to v14): sinks 48 / toilets 48 / beds 46 / closets 29 / showers 23.
- UI: right panel scrolls as a whole; element map collapsed by default; idle camera drift after 45 s at 1/4 speed.

## Update 2026-11-15 ~02:45
- Doors: `symbols.door_arcs` = grey, colourless strokes + RANSAC circle fit (radius 0.55-1.25 m, 55-135 deg span):
  dorm 141 doors (bifold closet doors count; angled corridor double doors and a few arcs missed). Code only.
- Staircases: `symbols.stair_flights` = tread detector on full-resolution tiles (whole-sheet downscale lost the treads);
  flights within 3 m = one staircase: dorm 4 staircases / 7 flights (wing ends, north end, central). The wide exterior
  stair beside the common area is still missed.
- Template counts: used only for DISTINCTIVE symbols (`_plain_box` rejects plain rectangles), up to 8x the clusters.
  Names cached per contact sheet (`cache/symbols/names-*.json`) so re-runs are stable.
- Estimated services (`engine/layers.estimate_services`) for sets without an MEP sheet: pipework 2023 m to 109 wet
  points, 418 m cable, 156 lights, 376 sockets on the dorm; layers marked "estimated", listed in the checklist,
  chatbot answers "how much pipework / how many sockets" with the basis. Tag: defaulted.
- UI: layers in a compact menu, no 'Other'/'space' tags in 3D, max 12 room tags, cube below the measuring button,
  low/light furniture blocks, "See proof" as a primary button.

## How to run / test
API: `LLM_PROVIDER=verda .venv/bin/python -m uvicorn api.main:app --port 8001`; web: `cd web && VITE_ENGINE=http://localhost:8001/api npx vite`.
Stress: `.venv/bin/python scripts/stress_big.py` (manifest `cache/stress/manifest.json`, 3 full-res Stoa sheets).
Bump `engine/cache.READER_VERSION` (facts + 3D) / `engine/raster/extract.RASTER_VERSION` whenever a reader changes.
