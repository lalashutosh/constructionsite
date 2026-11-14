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

## Status (update as you go)
- [x] handoff written (this file)
- [ ] deep-mode detection + ETA banner
- [ ] symbol discovery + naming + checklist (`engine/symbols.py`, `/api/checklist`)
- [ ] rooms named individually (Hallway n / Room n / Green room n / Gym)
- [ ] layers in geometry + viewer toggles
- [ ] 2D/3D toggle, mixed mode, pan/orbit/centre

## How to run / test
API: `LLM_PROVIDER=verda .venv/bin/python -m uvicorn api.main:app --port 8001`; web: `cd web && VITE_ENGINE=http://localhost:8001/api npx vite`.
Stress: `.venv/bin/python scripts/stress_big.py` (manifest `cache/stress/manifest.json`, 3 full-res Stoa sheets).
Bump `engine/cache.READER_VERSION` (facts + 3D) / `engine/raster/extract.RASTER_VERSION` whenever a reader changes.
