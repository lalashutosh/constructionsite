# UI builder handoff

## Run
- `cd web && npm run dev` (fixtures mode, default). `predev`/`prebuild` copy `contracts/fixtures/*.json` into `web/public/fixtures/`.
- Live mode: `VITE_API=live npm run dev` (engine at `http://localhost:8000/api/{analyze,facts,ask,scale,decide,cost}`; only `analyze` and `facts` GETs are wired, `livePost` exists for the rest).
- Gates: `npm run typecheck`, `npm run build` (zero errors), `npm run shot` (needs Playwright chromium; serves `vite preview` on :4173, writes `docs/shots/ui/*.png`, exits 1 on console errors).
- URL knobs for demos/shots: `?hook=0` skip hook, `?hookAt=3` start hook clock at 3 s, `?fx=doors|area_before|area_after|refusal`, `?tab=`, `?view=scan|reading|overlay`, `?ask=1`, `?rule=yes`.
- Story pages: `/#/lab/<stack|answer|receipt|decide|scale|findings|cost|lens|hook>`.

## Files
- `src/types.ts` mirrors `contracts/proof.py` by hand. `src/derive.ts` holds every derived sentence (why, findings, receipt, disputed ids); all are pure functions of the ProofObject plus the user's clicks.
- Components (`src/components/`): `EvidenceStack` (props: proof, elements, size, answerIds, disputedIds, anchorIds, tier, mode, explode, wipe, highlightIds, pinnedId, lens, chipLimit?, trace?, sweep?), `AnswerCard`, `ReceiptPanel`, `DecisionCards`, `UncertaintyBand`, `ScaleAsk`, `FindingsList`, `CostMeter`, `TrustLens`, `Hook` (timeline array `buildTimeline`, tune timings there).
- Backend fields used: `value, unit, interval, tier, evidence[].polygon/kind/label, voters[].value/element_ids/runs/note, scale.anchors/needs_user/widths_relative, assumptions, decisions_open (impact, options.fits), provenance.credit/file/revision/resolved_from, cost, query_spec, refusal, notes`. Optional `SheetFacts` (walls/rooms/windows context, `width_px/height_px`) via `fetchFacts`.

## Behaviour
- Doors fixture: amber 7 vs 6, disputed element (in exactly one voter) pulses; "Yes, a door" turns the answer green and keeps value from the chosen voter. Area before: amber band, "Narrow the range" opens ScaleAsk; answering swaps to `demo_takeoff_area.json` (real takeoff output) and the band collapses with a spring. Refusal fixture: grey, icon + word.
- Credit line and SYNTHETIC DEMO ribbon are always shown with a drawing.

## Known rough edges
- No real scan image path exists in the contract; the Scan layer is a synthetic render (grain + faint outlines of the facts polygons), always ribboned when the credit says synthetic. Wire an image URL (extras) when the engine serves one.
- ScaleAsk "draw a line" and "type the scale" are shells; in fixtures mode every answer loads the after-fixture. In live mode they should call `livePost("scale", ...)` (not wired).
- Decision choice and vibe presets are UI-only state (no recompute) because fixtures carry `impact: 0` and no `total_delta`.
- 60 fps was not measured; the scene is 6 CSS-3D divs + SVG, no JS animation loop except the cost count-up.
- `claims.json` is shown in the footer as the first three scalar entries; schema unknown.
- Findings are generated from proof fields; the "draft ready / no schedule" phrasing from the spec is not shown because no schedule data is in the contract.

Screenshots: `docs/shots/ui/` (hook-0s/3s/5s/7s/9s, answer, answer-hover, duel-resolved, receipt, decide, findings, scale-ask, band-before, band-after, grey, overlay, scan, answer-1280).
