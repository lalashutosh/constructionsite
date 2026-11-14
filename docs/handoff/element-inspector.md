# Element inspector (web)

Files: `web/src/inspector.tsx` (new), `web/src/api.ts` (fetchElements, overrideElement, undoElement, ElementsUnavailable), `web/src/App.tsx` (state, refresh), `web/src/panels.tsx` (ViewerPane picking), `web/src/viewer3d.ts` (floor raycast + outline), `web/src/index.css` (end of file).

Behaviour
- Inspector sits under the Checks block in the right column. Elements are fetched once the drawing is read; a 404/405/501 shows "Inspector not available" and nothing else breaks.
- 2D: drawing with every element polygon; hover highlights, click selects (smallest outline wins, so a door beats its room). Credit and a SYNTHETIC DEMO ribbon (when the credit says synthetic) stay visible on the map.
- 3D: `PlumbViewer.onElementPoint` raycasts the floor planes (no per-mesh picking, because walls/tiles are merged meshes), converts the hit to drawing pixels (adds the crop offset on split sheets) and picks with the same `pickAt`. The selected/hovered element is outlined in 3D (`setElementOutline`). Picking is off while the scale tool is measuring.
- Detail: kind/subtype + label, size (room m2, otherwise w x h m, or "scale not solved"), source tag, confidence meter (reuses `Meter`), feeds, explanation (always shown, with a fallback sentence), type picker (door / window / wall opening / fixture / wall / room / stair / not an element) plus room type, "Not a <kind>, remove", Restore, Undo.
- "you changed this" badge: `user_changed`, tag `chosen`, or changed in this session.
- After any override/undo: refetch elements, geometry (3D), checks, and re-ask all findings in place (`refreshAfterElement`, reuses `reask`).

Contract assumptions: GET /api/elements returns an array (or {elements|items}); retype sends `kind` (door|window|opening|fixture|wall|room|stair) and `subtype` (room type). "Wall opening" is sent as kind `opening`; confirm the engine's name. Optional `user_changed` and `removed` booleans on elements are honoured.

Verified: `cd web && npm run build` passes (tsc + vite). API on :8000 healthy but /api/elements returned 404 at the time, so only the "not available" path was exercised.
Unverified: everything against a live elements endpoint (2D/3D picking, override round trip, refresh), visual screenshots, picking on split multi-plan sheets.
