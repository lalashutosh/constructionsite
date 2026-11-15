# Plumb: blueprints that show their work

**Ask a construction drawing a question in plain language (in any of 8 languages). Get the number, and see exactly
which elements on the drawing produced it.**

Junction 2026 · Stoa challenge *"Make Blueprints Talk"* ·
[2-minute video](docs/SUBMISSION.md) · [pitch deck (PDF)](docs/pitch/Plumb_pitch_deck.pdf) ·
[web UI](https://plumb-blueprints.vercel.app) · **Reviewers:** [evaluation guide](docs/JUDGES.md) · [`llms.txt`](llms.txt) · [architecture](docs/ARCHITECTURE.md)

> Plumb is a geometry and verification layer for technical drawings, not a chatbot. Computer vision, OCR and fixed
> engineering formulas produce every number. A language model is used for two narrow jobs (naming a symbol type
> once, and turning a new question into a query that code runs), and it **never outputs a count or a measurement**.
> So a better model next year makes Plumb better instead of making it obsolete.

---

## What it does

| You give it | You get |
|---|---|
| A scan, PNG, PDF, DXF, IFC, or a whole project folder | Triage first: floor plan, section, site plan, photo ("not a drawing") or unreadable, and a refusal with a reason when it can't read it |
| "How many doors?" / "Montako makuuhuonetta?" / "How many check valves?" | One sentence, **every counted element boxed on the drawing**, and a tag on each value: *drawn* (measured), *specified* (printed on the sheet), *chosen* (by you) or *defaulted* (an assumption, listed) |
| A sheet with a printed scale | The scale **read from the sheet itself** (scale note, graphic bar, dimension strings, paper size), cross-checked; a "Where?" button pins each piece of evidence |
| A sketch with no scale | Measure **one** thing you know (click both ends of a door, type 0.9 m) and every room size, wall length and area follows |
| A 10,000-pixel construction sheet | A **deep read**: every repeated symbol found by computer vision and counted (beds, chairs, sinks, toilets, doors, staircases, valves...), every room named, per wing, with thumbnails |
| Any plan | A 3D model with **layers like a body**: envelope, walls, furniture, piping, electrical. A **build plan**: concrete, doors, hinges, finishes, and pipe and cable estimated by European rules (EN 806-3, EN 12056-2, EN 12464-1), always labelled *estimate* |

## Measured results

Every number below comes from a report in this repo. The holdout split is never used for tuning.

| What | Result | Source |
|---|---|---|
| Harder questions on Stoa's three full-size sheets (piping M-101A, foundation S-100F, dormitory A-2) | **24 / 25** correct; scale within 2% on all three | [`docs/stress-report-r9.md`](docs/stress-report-r9.md) |
| CubiCasa5k scanned plans, exact counts (DEV sample, LLM off) | **81.5%** [77.4, 85.0] (n = 400), mean 214 ms, 0 tokens | [`docs/evidence/20261115-024003-gate_r9/report.md`](docs/evidence/20261115-024003-gate_r9/report.md) |
| Swiss Dwellings, exact counts (given file only) | **91.3%** [86.6, 94.4] (n = 206) | `docs/evidence/20261115-022504-gate_sw8/report.md` |
| Full DEV split, all sources (6,192 questions) | **75.0%** using sibling files, **70.4%** given file only | [`docs/evidence/…-w2-dev/`](docs/evidence/20261114-154539-w2-dev/report.md), [`…-w2-dev-nosib/`](docs/evidence/20261114-161203-w2-dev-nosib/report.md) |
| IFC models, areas (within 2%) | **99.8%** (n = 816) | same `w2-dev` report |
| Swiss Dwellings with the DXF sibling: counts / areas | **100%** / **97.7%** | same `w2-dev` report |
| Deep read of the 67-megapixel dormitory sheet | 139 doors, 84 chairs, 48 sinks, 48 toilets, 46 beds, 5 staircases; **about $0.08, once** (cached per file) | in-app receipt; [`docs/handoff/deep-sheets.md`](docs/handoff/deep-sheets.md) |

Scoring follows the dataset: counts must be exact; areas, lengths and volumes within 2%. Both numbers are always
reported: *given file only* and *with siblings* (the same drawing in a more exact format, e.g. DXF next to a PDF,
disclosed in `provenance.resolved_from`).

**Known limits (stated, not hidden):** symbol *names* can be wrong while counts are right (one-click rename); doors on
piping sheets are partial; some scanned-plan intents (windows, bedrooms) are weaker; Swiss areas without the DXF
sibling are weak. Low-agreement answers are shown amber ("needs a look"), never green.

## Why judges can trust a number

1. **No unsourced number.** Every scale anchor and assumption carries a tag (drawn, specified, chosen, defaulted,
   open), a source and what it depends on; every answer carries the elements that produced it. See [`contracts/proof.py`](contracts/proof.py), the single interface between engine, API and UI.
2. **Two independent voters per count.** Reliability tiers come from voter agreement, calibrated on DEV answers,
   never from a model's own confidence ([`engine/skeptic/`](engine/skeptic/)).
3. **No circular evidence.** If the scale only came from an assumed door width, sizes are reported as relative.
4. **Fail loudly.** Photos, elevations and illegible scans are refused in product mode, with the reason.
5. **The LLM never makes the number.** It is optional (`LLM_PROVIDER=none` by default), every call is logged in
   `Cost`, and extraction and voting make no network calls.

## Low inference cost

- Most answers: **0 tokens, $0.0000**, about 0.2 s, on a laptop CPU.
- A deep read of a huge sheet: two vision-model reviews to name the symbol types, about $0.08 for the dormitory sheet,
  once; re-reads are free (cached by file SHA-256).
- Pluggable providers: none (default), Verda / Featherless (open-weight models), Gemini, Anthropic.

## How it works

```mermaid
flowchart LR
  A[Drawing or folder] --> T[Triage: plan? legible?]
  T --> S[Siblings: most exact format]
  S --> X[Extract: vector parse / CNN + OCR / big-sheet readers]
  X --> SC[Scale from the sheet: note, bar, dimensions, paper size]
  X --> D[Deep read: symbol discovery by repetition, template counts]
  Q[Question, any language] --> R[Router: fixed intents, printed text, query planner]
  R --> V[Two voters + calibrated tier]
  SC --> V
  D --> V
  V --> P[ProofObject: value, tag, boxes, assumptions, cost]
  P --> UI[Web: answer + See proof, 3D layers, build plan]
```

Details, module by module: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Run it

```bash
make setup                                    # .venv + requirements (+ requirements-optional.txt for IFC, torch)
cp .env.example .env                          # DATASET_ROOT, optional LLM keys (never commit .env)
.venv/bin/python -m uvicorn api.main:app --port 8001          # engine (LLM_PROVIDER=none by default)
cd web && VITE_ENGINE=http://localhost:8001/api npm run dev    # http://localhost:5173
.venv/bin/python -m pytest -q                 # 255 passed, 18 skipped (dataset-dependent tests skip cleanly)
make eval                                     # reproduce the accuracy report (evalkit/out/<run>/report.md)
```

The hosted UI (https://plumb-blueprints.vercel.app) talks to an engine on `localhost:8001`. Not in git: the
CubiCasa5k weights (`weights/`, see `docs/HANDOFF.md`) and the dataset (`DATASET_ROOT`).

## Repository map

| Path | What is there |
|---|---|
| `contracts/proof.py` | The ProofObject contract (pydantic v2): value, evidence elements, voters, tier, scale, tagged assumptions, cost |
| `engine/pipeline.py` | The engine: cache, triage, siblings, extract, vote, tier, ProofObject |
| `engine/scale/` | Scale from the sheet (`sheet_scale.py`), anchors and the user's measurement (`anchors.py`) |
| `engine/symbols.py` | Deep read: symbol discovery, counting, naming, rooms and zones |
| `engine/sheet_lookup.py`, `engine/sheet_findings.py` | What the sheet itself prints (tags, schedules, notes), read back with a receipt |
| `engine/raster/`, `engine/vector/`, `engine/bigsheet.py`, `engine/outline.py` | Readers for scans, exact formats and big construction sheets |
| `engine/skeptic/`, `engine/triage/` | Second voter, calibration, refusal |
| `engine/query/` | Query engine for new questions (an LLM may draft the spec; code runs it) |
| `engine/layers.py`, `engine/takeoff/`, `engine/plan/` | Body-like layers, EU-rule service estimates, quantities and build plan |
| `api/main.py` | FastAPI service |
| `web/` | React + TypeScript + three.js UI |
| `evalkit/` | Scoring harness, deterministic DEV/holdout split, reports in `evalkit/out/` |
| `docs/` | [Evaluation guide](docs/JUDGES.md), [architecture](docs/ARCHITECTURE.md), [evidence](docs/evidence/) (the cited evaluation reports), stress reports, decisions, pitch |

## CI on CRACI

Every push runs `.github/workflows/ci.yml` on CRACI runners: the Python suite on native amd64 and arm64, the FastAPI
server booted and probed with the path-traversal requests our stress test found (all must return 400), right-sized
machines per job, no secrets needed (dataset-dependent tests skip), and the web build uploaded as an artifact. An
`egress-proof` job checks the network policy instead of trusting it; on 2026-11-14 the lock was not in force for our
project, and we report that rather than claim it.

## Credits and licences

CubiCasa5K (Kalervo, Ylioinas, Haikiö, Karhu, Kannala, 2019), CC BY-NC-SA 4.0, non-commercial use only. Swiss Dwellings
v3.0.0 (Archilyse AG), CC BY 4.0. IFC sample models and Opening Design drawings under the licences listed in each
`data/<source>/LICENSE.md`. The credit for a drawing is shown whenever that drawing is shown.

Progress log: [issue #1](https://github.com/lalashutosh/constructionsite/issues/1) · `docs/HANDOFF.md`.
