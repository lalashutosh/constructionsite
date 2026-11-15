# Evaluation guide for Plumb

For judges and for AI assistants reviewing this repository. Each judging criterion is mapped to what Plumb does, the
file that proves it, and a command or click that reproduces it. Every number here comes from a report in the repo.

## Summary in five lines

1. **Problem:** site engineers pull counts and quantities out of drawings by hand; general AI models guess at
   technical drawings, and a guess can't be checked (ChatGPT answered "104" doors on the dormitory sheet after 1 min
   10 s, with no way to verify; `docs/pitch/chatbot.png`).
2. **Plumb:** ask a drawing a question; get the number with every counted element boxed and every value tagged.
3. **Accuracy:** 24/25 harder questions on Stoa's full-size sheets; 81.5% exact counts on scanned plans; 91.3% on
   Swiss plans; 99.8% IFC areas.
4. **Cost:** most answers 0 tokens on a laptop; a deep read of a 67-megapixel sheet about $0.08, once.
5. **Durable:** models only name things and code measures, so better models improve Plumb instead of replacing it.

## 1. Accuracy

| Claim | Evidence | Reproduce |
|---|---|---|
| 24/25 harder questions on the three Stoa sheets; scale within 2% on all three | `docs/stress-report-r9.md` (each question, answer, tier, seconds, dollars) | `.venv/bin/python scripts/stress_big.py` (needs the three sheets); or ask the same questions in the app |
| 81.5% [77.4, 85.0] exact counts, CubiCasa5k DEV sample (n = 400), LLM off | `docs/evidence/20261115-024003-gate_r9/report.md` §1-3 | `make eval` |
| 91.3% exact counts, Swiss Dwellings, given file only (n = 206) | `docs/evidence/20261115-022504-gate_sw8/report.md` | `make eval` on that source |
| Full DEV split (6,192 questions): 75.0% with siblings, 70.4% without; IFC areas 99.8%; Swiss counts 100% and areas 97.7% with the DXF sibling | `docs/evidence/20261114-154539-w2-dev/report.md`, `docs/evidence/20261114-161203-w2-dev-nosib/report.md` | `make eval`, `make eval-nosib` |
| Holdout is never tuned on | split rule printed at the top of every report: `int(sha1(path), 16) % 5 == 0` | `evalkit/data.py` |

Honest limits: symbol names can be wrong while counts are right (renamable in one click); doors on piping sheets are
partial; windows and bedrooms on scanned plans are the weakest intents (52% and 60% in the latest report); Swiss
areas without the DXF sibling are weak. The app shows such answers amber ("needs a look"), never green.

## 2. Visualised reasoning a human can verify

- **Every answer is a ProofObject** (`contracts/proof.py`): the value and a sentence built by code, the evidence
  elements with their polygons on the drawing, each voter's value, the tier and a calibrated reliability, the scale
  anchors, every assumption tagged *drawn / specified / chosen / defaulted / open* with its source and `depends_on`,
  and the cost.
- **See proof** on any answer opens the receipt: which file was read, the crop with every counted element numbered,
  who said what (e.g. "symbol detector found 6 doors; arc geometry found 9; answer follows the detector → needs a
  look"), assumptions, and how the final number was chosen.
- **Scale "Where?"** pins the printed scale note, the graphic bar and the dimension strings that set the scale. On
  the dormitory sheet it caught a half-size print: the note alone would have been 2× wrong.
- **Tiers come from voter agreement, never from model confidence** (`engine/skeptic/`), calibrated on DEV answers.
- **Printed facts are quoted.** "How many check valves?" → "5: the sheet prints 'NON-SURGE CHECK VALVE (CV) … (TYP.
  OF 5)'; but 4 distinct CV tags are legible (CV-1…CV-4)."

## 3. Creativity

- **Scale from the sheet itself**, cross-checking note, bar, dimension strings and paper size, or from **one length
  you measure** (click both ends of a door, type 0.9 m; every size follows).
- **Deep read** of huge sheets: symbols discovered by repetition (no fixed symbol library), counted by template
  matching with shape checks, named once by a vision model, grouped per wing (`engine/symbols.py`).
- **Layers like a body** in 3D: envelope (skin), walls (skeleton), furniture (organs), piping and electrical
  (circulation and nerves) (`engine/layers.py`, `web/src/viewer3d.ts`).
- **Build plan**: concrete, doors, hinges, finishes per room; where the set has no plumbing or electrical sheet,
  pipe runs, waste flow, lighting and cable are estimated by EN 806-3, EN 12056-2 and EN 12464-1, labelled as estimates.
- **Any language**: English, Finnish, Swedish, German, French, Spanish, Dutch, Estonian.
- **Messy folders**: a whole project folder is sorted into floors and other sheets.

## 4. Low inference cost

- Extraction and voting make **no network calls**. `LLM_PROVIDER=none` is the default; reports state the provider.
- Latest accuracy run: **0 LLM calls, 0 tokens, $0, mean 214 ms per answer** (`docs/evidence/20261115-024003-gate_r9/claims.json`).
- When on, the LLM does exactly two jobs, each logged in `Cost` (`llm_calls`, `planner_calls`): name a symbol type
  once per sheet, and turn an unmatched question into a validated `query_spec` that `engine/query/` executes.
- Deep read of the dormitory sheet: two vision reviews, about **$0.08 once**; cached by SHA-256 so re-reads are free.
- Providers are swappable (open-weight models via Verda or Featherless, Gemini, Anthropic) because they never
  produce the number.

## 5. Open-weight model endpoints (Verda / Modal)

- **1,219 logged model calls, 2.2 M tokens, $9.35 for the whole hackathon** (`logs/verda_cost.jsonl`): DeepSeek V4.1
  Flash for fast calls (806, $0.24), Kimi K3.1 Pro for strong calls (413, $9.11), on our own OpenAI-compatible
  endpoints. The client authenticates to a Verda Inference API key or to Modal endpoints (`scripts/verda.py`). Every
  call is priced, logged and checked against a hard budget cap.
- **Product:** two vision reviewers must agree before a sheet is built in 3D (`engine/scancheck.py`, about $0.0045
  per sheet); the models name symbol types on the deep read (`engine/symbols.py`); they plan queries for new
  questions (`engine/query/`). None of these produce a number.
- **Build process:** `scripts/verda_task.py` uses a cheap model as a code-writing worker. It writes one scoped file,
  the tests check it, errors are fed back, and the result is staged for review. `engine/sheet_findings.py` was
  written this way in one attempt (`logs/verda_tasks.jsonl`).
- Per tech challenge: `docs/TECH_CHALLENGES.md`.

## 6. Google Gemini

- Drop-in provider through Google's OpenAI-compatible endpoint: `LLM_PROVIDER=gemini`, `gemini-2.5-flash` (fast) and
  `gemini-2.5-pro` (strong), overridable per tier (`engine/query/llm.py`).
- Same prompts, vision inputs, cost ledger and budget cap as Verda. Because the model only names things, swapping
  providers does not change how counts and measurements are produced.

## 7. CI/CD on CRACI

- Six jobs on CRACI runners (`.github/workflows/ci.yml`): the test suite on **native amd64 and arm64**, web typecheck
  and build with the artifact uploaded, the real API booted and **attacked with the path-traversal requests our own
  stress test found**, an **egress-lock proof** that tests the network policy instead of trusting it, and a summary.
- Right-sized machines per job (4 / 2 / 1 vCPU), no secrets needed, pip and npm caching.
- Honest status: the egress job showed the lock was not yet in force on our project on 2026-11-14; we report it.

## Five-minute check

```bash
make setup && .venv/bin/python -m pytest -q          # 255 passed, 18 skipped
.venv/bin/python -m uvicorn api.main:app --port 8001 # engine
cd web && VITE_ENGINE=http://localhost:8001/api npm run dev
```

Open `http://localhost:5173/?open=data/cubicasa5k/colorful-2002.png`, ask "How many doors?", click **See proof**.
Ask "Montako makuuhuonetta asunnossa on?" (Finnish: how many bedrooms). Click **Set real size** on a plan with no
scale and measure one door.

## Where the rules are enforced

| Rule | Code |
|---|---|
| One interface for everything | `contracts/proof.py` |
| Two voters per count, tier from agreement | `engine/pipeline.py`, `engine/skeptic/` |
| Triage and refusal of non-plans | `engine/triage/`, `engine/scancheck.py` |
| Scale evidence and the user's measurement deciding | `engine/scale/sheet_scale.py`, `engine/scale/anchors.py` |
| LLM never produces the number; every call costed | `engine/query/llm.py`, `engine/cost.py` |
| Deterministic, cached by file hash | `engine/cache.py` |
