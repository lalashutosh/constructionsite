# WOW UI handoff (ui-builder, W3 core beats)

Scope: core beats 1, 2, 3, 4, 8, 9, 10, 12. Beats 5, 6, 7, 11: **pending gate** (not built, W2 gate not yet GO).
Only `web/` was edited (plus this file). Nothing committed. Verda: 0 calls.

## Run
- Gates: `cd web && npm run typecheck && npm run build`, then `npm run shot` (writes `docs/shots/ui/` = W1 fixtures, `docs/shots/wow/` = W3).
  `ONLY=fx|real|mock npm run shot` runs one section. The script uses :5173 (the engine's CORS allows only that origin). If a dev server already owns :5173 the shot run just uses it. Playwright falls back to any cached chromium headless shell.
- Mode: `?api=live|fixtures` > `VITE_API` > auto (probe `localhost:8000/health`, 900 ms). Live is the default when the engine answers. Fixtures stay as fallback.
- URL knobs (new): `sample=<id>`, `q=<index into the sample's questions>`, plus the W1 ones (`hook=0`, `hookAt=`, `fx=`, `tab=`, `view=`).
- `npm run predev/prebuild` now also copies `evalkit/out/latest/claims.json` to `web/public/claims.json` (scalars only, no run paths).

## Files
- New: `src/timeline.ts` (every hook timing, `TIMING`), `components/SampleStrip.tsx`, `components/ScaleDrawer.tsx`, `public/samples/*` + `samples.json` (credit strings, questions, tags).
- Changed: `api.ts` (initMode, liveAsk/liveOverride/liveClearOverrides/liveScale/liveUpload, loadImage, fetchSamples), `App.tsx` (live flow), `derive.ts` (IoU-matched disputes, refusalWords, calibrationSentence, anchorWeight), `EvidenceStack.tsx` (real scan image, readers overlay, true-size, chip size scales with the drawing), `AnswerCard.tsx` (grey card, Yes/No per element, RunStrip, calibration line, "how computed"), `ScaleAsk.tsx` (tap a door + type its width, sends `{px_length,length_m}`), `CostMeter.tsx`, `Hook.tsx`, `index.css`, `index.html` (title).

## Beats, click paths, screenshots (`docs/shots/wow/` unless noted)
1. **Live end to end.** Open `/`: sample strip (9 samples + "Your drawing" upload). Pick one; `/api/ask`, `/api/facts`, `/api/image` load; the Scan layer is the real picture, evidence polygons share its pixel space (rasters). Credit string under every drawing and in the footer (sample credit from LICENSE.md wins over the engine's short form). Shots: `real-raster-tiny`, `real-raster-rotated`, `real-swiss-doors`, `real-swiss-receipt`, `real-swiss-area`.
   Samples (all CubiCasa5k DEV split, chosen by looks): tiny-scan (colorful-11960, 240x161), rotated-text (high_quality-729), sideways (high_quality_architectural-13040), tall-terraced (-247), narrow-strip (-5742, 200 px), hand-marked (colorful-2002), two-floors (-1967), clean-bw (high_quality-11553); plus swiss-vector (site157_bldg323_floor1313.pdf, 3 questions) and two non-plans (wikimedia 3561257 elevation, wikimedia 22959557 tiny thumbnail). First sample is `tiny-scan` (hook default).
2. **Hook.** Auto-plays once when the first live answer is non-grey and has pixel-space evidence (or fixtures `doors`). Scan at true pixel size (dim) -> scan-line + wall trace -> explode -> chips -> tally + `0 tokens . $0.00 . ms` meter -> fold + big number -> title. Skip: any key or click. "Replay intro" button in the header. Shots `real-hook-0s-true-size`, `-2s-sweep`, `-3s-explode`, `-5s-chips`, `-7s-big`, `-9s-title` (real engine, clean-bw). Caption mentions "Finnish labels"/"No scale" only if the sample is tagged so.
3. **Skeptic Duel.** Two readers = ring (blue) vs diamond (pink) overlays on a "Two readers" layer; banner `A vs B` with disputed count; disputed elements pulse amber (IoU < 0.3 or one-reader-only). Click or keyboard (Tab to a pulsing chip, Enter) -> "Is this a door? Yes / No" card -> `POST /api/override` -> proof replaced (value, tier, chip colours, receipt gets the "chosen" line, panels re-animate). `undo` -> `DELETE /api/override` + re-ask. Readers whose elements live in different coordinate spaces (vector file vs its PDF render) are not compared element by element (no false disputes). Real engine shows the duel on rasters today (`real-raster-tiny`: 5 vs 3, `real-raster-rotated`: 6 vs 8, 14 disputed). Flow shots use a mocked engine: `mock-duel-1-disputed`, `-2-card`, `-3-settled`, `-4-receipt`.
4. **Scale band collapse.** Area answer with an interval + amber + no user anchor shows "Range is wide / Narrow the range" -> modal: tap a door, "Yes, 0.9 m" (or type a width) -> `POST /api/scale` with `{kind:user, px_length, length_m}` -> band springs to the new interval. "Show how this was computed": anchors, sigma, weight = 1/sigma^2, combined px/m. Shots `mock-scale-1-band`, `-2-ask`, `-3-collapsed`, `-4-how` (mocked engine; no real raster area question exists in the dataset).
8. **Honest refusal.** Grey: "no number", reason in plain language, "What would make it answerable", scan dimmed behind, 0 tokens. Shots `real-refusal-elevation` (engine says: elevation, no enclosed rooms), `real-refusal-tiny` (125 px image), plus `docs/shots/ui/grey.png`.
9. **Test-time-augmentation strip.** "Spread across runs and readers": one dot per run/value per reader on a shared axis; calibration sentence from `claims.json` (green_acc / amber_acc, labelled "development" until `headline_acc_holdout` exists) and the engine's own "historically right N%" note. In the answer card of every shot.
10. **Cost + scale.** Footer: ms / tokens / USD, `LLM calls: N` (from the response), `estimate: ... CPU for 14,000 drawings` (claims `cpu_per_drawing_s` x 14000; 14000 is the brief's figure, constant `CORPUS_DRAWINGS`), "How we scale" drawer with claims numbers only. Shot `real-cost-scale-drawer`.
12. **Polish.** Title, favicon, reduced-motion media query (already global), focus rings, 1440x900 and 1920x1080 (`real-swiss-1920`) and 1280 (`ui/answer-1280`), keyboard path for the duel, no console errors in the shot run (the run exits 1 on any).

## Mocked vs real (read this before trusting a shot)
`mock-*` shots answer `/api/ask|override|scale|facts` from the contract fixtures (stretched onto the real scan of high_quality-11553; ribbon `SYNTHETIC DEMO` stays on); `/api/image` is real. They exercise the live code paths only. All `real-*` shots are the real engine as it was at 2026-11-14 14:30.

## Known gaps / for the lead
- Engine CORS does not `expose_headers` `X-Plumb-Coords`; the UI infers it from the file extension (png/jpg = pixels). Cheap fix: `expose_headers=["X-Plumb-Coords"]`.
- Vector files (Swiss): evidence is in DXF units, the scan is a PDF render, so overlays are NOT on the picture; the scan is labelled "reference". Needs a transform from the engine (extras) to align.
- Swiss doors/windows currently come back amber with a 0-valued `query_engine` voter; the banner shows readers `78 = 78` and the card says voters agree on the first two. Engine-side question, not UI.
- Raster counts today: detector reader often has 0 elements (no OCR): duel then shows `0 vs 7` with no overlay for the detector. Re-pick right/amber samples once OCR works.
- "Type the scale" is a typed door width (a ratio needs dpi); "draw a line" was cut.
- Typing a free question works against `/api/ask`; the `planned by LLM` badge appears only when `query_spec` comes back.
- Dependent rows after a verdict are Findings and Receipt (door schedule is beat 6, pending gate).
- `as of revision` scrubber stays disabled (beat 7, pending gate).
