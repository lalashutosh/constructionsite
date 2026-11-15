# Plumb: blueprints that show their work

> Reviewing or judging this project? Start with [`docs/JUDGES.md`](docs/JUDGES.md) (criteria mapped to evidence), [`llms.txt`](llms.txt) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). This file is the build instructions the coding agents followed.

Junction 2026, Stoa challenge "Make Blueprints Talk". Judging (working assumption until Stoa publishes the criteria): **accuracy · visualised reasoning a human can verify · creativity · low inference cost.**
Stoa has said the judges will use questions HARDER than the dataset. Fixed intents alone are not enough.
Solutions must not be obsoleted by next year's frontier models: we are a geometry + verification layer, not a chatbot.

One sentence: *turn a drawing into numbers with a receipt (what was measured, assumed, chosen) and a short list of decisions to make before ordering.*
Positioning: every number points at the exact elements on the drawing that produced it.

## Mode
Default is SINGLE-SESSION mode: one lead session runs `ORCHESTRATOR.md`, spawns subagents (`.claude/agents/`) and commits for them; progress lives in `docs/STATE.md`. Prompt-file instructions about branches, worktrees, merge scripts or agents committing do not apply in this mode. Subagents never commit.

## Read first
`RUNBOOK.md` (order of work, gates) · `contracts/proof.py` (the ONLY interface) · `docs/DEMO_SCRIPT.md` (what the judges must see).

## Dataset facts (verified from the preview README + questions.jsonl)
- Root = `$DATASET_ROOT` (the folder that contains `questions.jsonl` and `data/`). Question `path` is relative to it.
- 7,990 preview questions: cubicasa5k 4,270 (png, count only) · swiss_dwellings 2,358 (pdf, with same-stem .dxf and .png siblings; 1,614 count + 744 area) · ifc_models 1,049 (827 on .ifc, 222 on pdf with svg sibling; many area) · ifc_bench 249 (text) · opening_design 64 (pdf, door-schedule style).
- Types: count 6,076 · area 1,599 · text 265 · volume 34 · length 16. **Scoring: counts exact; area/length/volume within 2%; text free-form.**
- "Files with the same name and a different extension are the same drawing in another format." So a sibling resolver may answer from the most exact format and must say so in `provenance.resolved_from`.
  Always report two numbers: `--no-siblings` (pure given-file) and with siblings.
- Non-plan images exist (elevations, museum scans, tiny thumbnails). Correct behaviour is triage and refusal in product mode, best-guess in benchmark mode.
- Cubicasa plans are small (240-490 px), Finnish labels (OH, MH, KK, ET, PH, S, WC...), often rotated text, "not to scale".
- **Licences:** CubiCasa5k is CC BY-NC-SA 4.0 (per the dataset README): use that exact string. Show the credit string (`provenance.credit`) whenever a drawing is displayed. NonCommercial files: non-commercial use only. ShareAlike adaptations (e.g. our synthetic revision demo) must carry the same licence. NoDerivatives files must stay unchanged.

## Non-negotiables (design rules)
1. No unsourced number. Every value has a Tag: drawn / specified / chosen / defaulted / open.
2. No silent assumption. Assumptions are listed with `source` and `depends_on`.
3. No circular evidence: if scale comes only from the door prior, report widths as relative (`widths_relative=True`).
4. Counts never need scale. Only ask the user for scale when a question needs it, cheapest question first.
5. Two independent voters per count. Tier is computed from voter agreement, never from a model's own confidence.
6. Benchmark mode always returns a best guess. Product mode may refuse (grey tier) with a reason.
7. Fail loudly on bad input (triage), never invent geometry.
8. Extraction and voting make no network calls. LLM is optional: `LLM_PROVIDER=none|verda|featherless|anthropic`, default none. When on, it does exactly two things: (a) classify each DISTINCT question template once (cached), (b) turn a question no template matches into a validated `query_spec` that the query engine (`engine/query/`) executes. The LLM never produces the number. Every call is logged in `Cost` (`llm_calls`, `planner_calls`). Reported runs give two rows: LLM off and planner on. `anthropic` (Claude) is reserved for the live demo.
9. Every claim in README/demo must come from `evalkit/out/latest/report.md`. No hand-typed numbers.
10. The hand-written hard set (`evalkit/hard_questions.jsonl`) is a TEST set: scored separately, never used for tuning.
11. Core gate: W3 extras (receipt/vibes, door-schedule reconcile, tamper test, A2A) start only after the W2 gate is GO.

## Stack
Python 3.11+ (FastAPI, numpy, opencv-python-headless, scikit-image, shapely, networkx, pydantic v2, pytesseract, pymupdf, ezdxf, scikit-learn). Optional: torch CPU (pretrained plan model), ifcopenshell, a2a-sdk.
Web: Vite + React + TypeScript, plain SVG and CSS 3D transforms (no heavy 3D lib).

## Ownership (avoid merge conflicts)
| path | owner agent |
|---|---|
| `contracts/` | frozen after W0 (change requests only) |
| `evalkit/`, `tests/test_eval*` | evaluator |
| `engine/raster/`, `engine/count/` | raster-extractor |
| `engine/skeptic/`, `engine/triage/` | skeptic |
| `engine/scale/`, `engine/takeoff/`, `engine/decide/` | takeoff |
| `engine/vector/`, `engine/siblings.py` | vector |
| `engine/pipeline.py`, `engine/api.py`, `engine/router.py`, `engine/query/`, `api/`, `a2a/` | integrator |
| `web/` | ui-builder |
| `docs/`, `prompts/`, `.claude/`, `ORCHESTRATOR.md`, `scripts/verda.py`, `scripts/overnight.sh` | lead session (orchestrator) |
| notes and summaries it is asked to write | scout |

## Engineering rules
- Small commits, message `area: what`. Never rewrite history. Never touch files you do not own.
- Deterministic: seed everything (seed 7). Cache by file sha256.
- Every module has a `python -m <module>.smoke` or pytest that runs in < 30 s on 20 samples.
- When you finish: write `docs/handoff/<agent>.md` (what works, numbers measured, known failures, how to run) and commit.
- If blocked > 10 minutes on a dependency (weights, download), write the decision to `docs/decisions/<topic>.md` and take the fallback.

## Token discipline (the team's Claude quota may be tight)
- Never read big files or images whole. Downscale images to <= 1000 px before viewing. `head`/`grep`/`wc` first.
- Heavy compute runs in Python scripts, results go to files; only summaries enter the conversation.
- Do not re-read files you just wrote. Do not paste long logs: `| tail -30`.
- Use subagents with the cheapest model that can do the job (agent files set it). Mechanical work: haiku.
