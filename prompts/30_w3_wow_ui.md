# W3 · WOW UI (agent: ui-builder, branch w3/wow-ui, budget ~100 min)

**Gate:** beats 1, 2, 3, 4, 8, 9, 10 and 12 always. Beats 5, 6, 7 and 11 only if the W2 gate is GO; otherwise mark them cut in the handoff.

Mission: turn the W1 UI into the 90 seconds that win. Everything below is implemented against the REAL API (`VITE_API=live`) with fixtures kept as fallback. Exact beats and timings are in `docs/DEMO_SCRIPT.md`; this prompt is the build list. Judges score four equal quarters: accuracy, verifiable reasoning, creativity, low cost — each beat must prove one of them.

Read first: `AGENTS.md`, `docs/handoff/ui.md`, `docs/handoff/integrator.md`, `prompts/31_w3_wow_engine.md` (signatures), `prompts/32_w3_a2a.md` (endpoints), `docs/DEMO_SCRIPT.md`. You own `web/` only.

## Build list (in this order, commit after each)
1. **Live mode end to end**: upload or choose a sample -> real `/api/analyze` and `/api/ask`; the Stack shows REAL layers from the engine (real polygons over the real scan). Copy 8 cubicasa DEV-split samples (a mix: easy, rotated, tiny, Finnish) into `web/public/samples/` with `samples.json` carrying the credit strings (CubiCasa5k, CC BY-NC-SA 4.0) shown beside every drawing. Choose samples where the engine is right AND one where it is amber, AND one non-plan for the refusal beat.
2. **Hook (first 10 seconds)**: implement the timeline from `docs/DEMO_SCRIPT.md` exactly. A tiny ugly scan appears at its true pixel size, a scan-line sweeps it, walls trace in, the plan explodes into the evidence stack, numbered chips pop on doors, the tally bar fills, the cost meter reads `0 tokens · $0.00` and the millisecond counter runs. Skippable. Tunable from one `timeline.ts`.
3. **Skeptic Duel**: show the two independent voters as two overlays (two colours + two shapes), disagreements (matched by IoU < 0.3 or present in only one) pulse amber with a visible count "7 vs 6". Click a disputed element -> a two-button card "Is this a door? Yes / No" -> `POST /api/override` -> count flips, tier recomputes, dependent rows (door schedule, quantities) animate to new values. Everything keyboard accessible.
4. **Scale band collapse**: an area question on a plan without scale shows a wide band ("25-40 m2") with the cheapest scale question; one tap on a door (or a typed ratio) -> `POST /api/scale` -> the band collapses with a spring to the new interval. Show the arithmetic in a small "how this was computed" drawer (anchors, weights).
5. **Receipt printer**: the ReceiptPanel renders as a paper receipt that prints out line by line (Drawn / Specified / Chosen / Defaulted / Open) with a vibe slider (Budget -> Nordic) that re-prints with changed lines highlighted. Decision cards ranked by impact with bars; options that do not fit are greyed with the reason.
6. **Door schedule + reconcile**: button "Generate door schedule" -> table slides in, each row linked to its pin; "Reconcile with order" (demo order file, ribbon `DEMO DATA`) -> big cards: `14 ordered · 12 drawn · 2 ordered, drawn nowhere`, click -> highlights; Download CSV works.
7. **Tamper test**: select a door, "Simulate revision: remove" -> `POST /api/tamper` + `/api/delta` -> a delta card: `-1 door · -1 leaf · -1 frame · -3 hinges`, ribbon `SYNTHETIC REVISION`. The "as of revision" scrubber now has two stops and wipes between them.
8. **Honest refusal**: a non-plan or tiny image shows the grey state: no number, the reason in plain language, and what would make it answerable.
9. **Test-time augmentation strip**: for a count, show the per-run values as dots (the spread is the uncertainty) and the calibration sentence from the evaluation ("when voters agree like this we were right X% of the time on held-out drawings" — only if `/claims.json` has the number).
10. **Cost + scale proof**: the footer shows live ms / tokens / USD and, from `/claims.json`, `LLM calls: N` and `estimated CPU time for 14,000 drawings` (the label must say "estimate"). A small "How we scale" drawer (extract once per file hash, questions are lookups, cascade, routing by title block only) with ONLY numbers from claims.json.
11. **A2A beat**: a side panel "Ask from another agent" showing the A2A task states (`working` -> `input-required: door width?` -> answer -> `completed`) from `GET /api/trace/...` or the demo client log.
12. **Polish pass**: motion budget (nothing longer than 600 ms except the hook), reduced-motion media query, focus rings, 1440x900 and 1920x1080 layouts, favicon, page title, no console errors, no layout shift.

## Verify
`npm run typecheck && npm run build`, then `npm run shot` for every beat; LOOK at the screenshots (downscaled) and fix. Then the scripted recorder (`scripts/record_demo.mjs`, see `prompts/41_w4_video_kit.md`) must complete without errors against the live API.

## Don'ts
No invented numbers (everything from API responses or claims.json). Synthetic and demo data always ribboned. Credit strings always visible with a drawing. No external network at runtime. Do not edit outside `web/`.

## Handoff
`docs/handoff/wow-ui.md`: beats implemented (with screenshot names), anything cut, exact click path for each beat. Commits `wow-ui: <what>`.
