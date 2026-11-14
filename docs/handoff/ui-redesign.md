# UI redesign handoff (web/)

One workspace, live engine only (`/api/geometry`, `/api/image`, `/api/ask`, `/api/plan`, `/api/upload` on :8000). Fixtures mode was removed.

## On screen (1440x900, 61.8 / 38.2 splits, hairline rules, no cards)
- Left rail 56 px: Plumb mark, upload image, upload folder (files stack as floors), drawings drawer (samples.json + uploads), theme toggle (sun/moon, follows `prefers-color-scheme`, remembered in localStorage).
- Left column: 3D viewer (three.js, plain, `web/src/viewer3d.ts`) over ASK (input, chips incl. harder questions, answer card: 55 px mono value, tier word + icon, cost line).
- Right column: switch Findings | Build plan over HOW WE KNOW.
  - Findings: Scan check block (warnings or "Scan check passed", reviewer cost line), then one-liners per fixed question set (cubicasa / swiss / ifc chosen from the path). Click selects the answer.
  - Build plan: building label + confidence (expand for evidence), vibe pills, Steps stepper or Checklist (grouped, qty + unit, tag word, basis on expand), Play. If `/api/plan` is unreachable, `src/mockPlan.json` is shown with a visible note.
  - HOW WE KNOW: numbered steps from ProofObject fields only (file, each voter with element chips, assumptions, final rating from the `tier:` note), then Sources with "show on model". With no answer selected it lists the detected views (type, type_source, reader, why).
- Viewer: drawing image under the model (Drawing on/off), foundation slab, floor tile per room, extruded walls with edges, door/window/fixture markers, pins for the selected answer (only when `coords == "pixels"`; otherwise "exact file read: pins not mapped to this view"), view tags per `check.views`, faint drafting grid, credit line always visible. Build steps animate: walls rise, openings, services lines, room tint, roof (cumulative by step order).
- Themes: dark (#0A1828, turquoise #178582, gold #BFA181) and light (white, #970747). IBM Plex Sans/Mono via @fontsource, lucide-react icons.

## Click path
Drawings icon -> pick sample -> findings fill in -> click a finding -> pins appear, hover a pin or chip to cross-highlight -> Build plan tab -> click step or Play.

## Run
`cd web && VITE_API=live npm run dev`, `npm run typecheck`, `npm run build`, `THEME=dark|light npm run shot` (needs dev server on :5173 and engine on :8000; writes `docs/shots/redesign/*-dark.png|*-light.png`). The shot script uses the Playwright Chrome-for-Testing build found in `~/Library/Caches/ms-playwright/chromium-1217` (override with `PLUMB_CHROME`).

## Known issues
- Image texture needs `imageOrientation: "flipY"` on the ImageBitmap (done); verified with printed text reading upright.
- Engine answers shown verbatim, including odd ones ("Are there more windows than doors?" returned a number or a refusal depending on run; "Which room is the largest?" refuses). Engine-side, not UI.
- `check.views[].why` is shown verbatim and may contain engine wording such as "readers disagree".
- Elevations/non-plans still get a 3D model from whatever walls the geometry endpoint returns; the refusal text explains it.
- Software GL in headless screenshots is slow; real GPUs run at 60 fps.
- The "Reader" count in the scan-check line is 2 when any view carries an agreement score, otherwise the number of distinct readers.
- Old fixtures-mode components, derive.ts, geometry.ts, timeline.ts, Lab.tsx were deleted; `public/fixtures` and `scripts/copy-fixtures.mjs` are left in place but unused.

## Round 3 additions
- Findings show `reliability` ("84% reliable" plus a 34 px hairline bar); "single check" wording removed; query-computed answers say "Computed from a query · check the parts".
- Answer headline by kind (integer, 1 decimal + m²/m/m³, text word at 34 px with compared parts for yes/no); never a bare dash. USD with 4 decimals plus LLM calls; one-time read cost under the viewer from `/api/geometry` `cost`.
- Set real size: ruler icon on the viewer or the "Set real size" link under an answer that assumes door sizes (assumption `scale_px_per_m`, tag defaulted). Click two points on the drawing, type metres, POST `/api/scale`, shows the recomputed answer.
- Build plan opens on the Materials checklist (grouped, qty + unit, tag, tap for basis and `source`); qty null shows "needs real size" or an IT-load input that refetches `/api/plan?it_load_kw=`. Build steps and Play are a second view.
- 3D: pins are a 5 px dot, 1 px leader and a compact mono tag (overlapping tags collapse to the dot, number on hover); 1 turn per 60 s rotation that pauses on drag and resumes after 3 s; staggered build-up on load (~1.2 s); idle layer separation (6 s cycle) after 6 s without interaction; all of it off under `prefers-reduced-motion`.
- Known: the measure tool's first click right after toggling can be missed in automated runs; the planner LLM sometimes fails on a free-form question (engine side), shown as a refusal.

## Round 4: one story
- Layout 70 / 30, base text 15 px, titles 24 px, answer sentence 26 px. The 55 px number and the always-visible HOW WE KNOW panel are gone; "Why?" (answer bar, each finding, the story line) slides a sheet over the right column.
- Story: Reading the drawing -> Found N floor plans · checked by 2 readers + 2 AI reviewers -> Built in 3D. On open a scan line sweeps the flat drawing, walls rise (~2.5 s), camera eases into the orbit; a click skips it. Findings stream in as the engine's `answer_text` sentences (numbers bold) with a reliability word.
- Set real size: big button on the viewer. Camera goes top-down, drawing near full opacity, "Click both ends of a wall or door you know", two taps, "How long is this? __ m", POST /api/scale, then dimension labels (wall lengths, room m²), a count-up banner from the refetched `/api/plan` basis, changed checklist rows flash, camera eases back. Until set, the build plan says sizes come from a typical 0.9 m door.
- How it works: rail book icon, 4 steps with SVG figures, numbers strip read only from `/claims.json`.
- `web/public/claims.json` changed schema during this round (flat single-run keys, no with/without siblings, no per-source accuracy). The page handles both the old nested and the flat schema; per-source and with/without numbers appear only if the file carries them again.
- `scripts/shot.mjs` drives the measure flow with raw pointerdown/pointerup events (no pointermove). `scripts/shot-how.mjs` re-shoots only the how page.
