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
