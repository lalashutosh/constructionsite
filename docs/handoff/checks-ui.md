# Checks UI handoff (web/)

Contract: docs/decisions/checks-api.md (GET /api/checks, POST /api/checks/answer).

## Built
- `web/src/checks.tsx`: ChecksBlock (top of Findings), Meter (role=meter, % + word Sure / Fairly sure / Not sure + icon; bands >=80, 50-79, <50), `scaleBrief`.
  Max 3 open questions (first shows summary + impact, others compact), then confirmed/auto rows, rejected rows, "N more questions". Scale question has "Type a length instead" (reuses Set real size).
- Hover/focus on a check row draws its evidence boxes as numbered pins on the drawing (PlumbViewer.setPins, via `checkEv` prop of ViewerPane in panels.tsx).
- `web/src/api.ts`: `Check` types, `fetchChecks`, `answerCheck`. `VITE_API=mock` serves a stateful local sample (scale 62%, plan view 71%, units 46%, sheet type auto). In live mode a failing endpoint means no Checks block (nothing invented). `VITE_ENGINE` overrides the API base (e.g. http://localhost:8013/api).
- `web/src/App.tsx`: fetches checks once geometry is ready; answer -> POST, GET, re-fetch geometry when scale/units, re-ask all findings + selected answer in place, confirmation line ("Scale confirmed: areas and lengths updated", aria-live).
- Scale confidence beside sizes: "from scale 1" = 40'-0", 92% sure" under area/length/volume answers (Ask card and Findings rows).
- CSS appended to `web/src/index.css` (tokens only, light/dark, <=520 px tweaks).

## Run
`VITE_API=mock VITE_ENGINE=http://localhost:8013/api npm run dev` (API CORS allows only :5173). `scripts/shot-checks.mjs` (env THEME, W, H, TAG, PLUMB_PATH, PLUMB_URL) writes docs/shots/checks/. The API refuses absolute paths outside dataset/uploads: upload the drawing via /api/upload and pass that path.

## Known
- Live endpoints were not present when built; only mock was exercised. Shot 4 (size line) shows a grey refusal for the area question on stoa3, so the "from scale" line was not seen on screen; it renders only for area/length/volume proofs.
- Phone width 400 px keeps the existing two-column layout (not changed).
- Verda review returned empty output three times (reasoning model exhausted max tokens, up to 9000); no review text obtained.
