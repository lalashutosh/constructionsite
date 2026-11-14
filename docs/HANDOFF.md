# Handoff — where the build stands and how to continue

Written 2026-11-14 13:30 when the build was paused (Claude usage limit). Everything below is committed.
Read this file first, then `docs/STATE.md` (the live checklist) and `AGENTS.md` (project rules).

## 1. What Plumb is (30 seconds)
Junction 2026, Stoa challenge "Make Blueprints Talk". Plumb turns a drawing (PNG/PDF/DXF/IFC) into numbers
with a receipt: every count/area points at the drawing elements that produced it, and lists what was
measured, assumed and chosen. Scoring on the preview dataset: counts exact, area/length/volume within 2%.
The LLM never produces numbers; it only classifies question templates and plans queries for unseen questions.

## 2. Where we are
Progress: 12 of 25 checklist items in `docs/STATE.md`.

| Phase | State | Key numbers (from committed reports/handoffs) |
|---|---|---|
| P0 bootstrap | done | `make check` OK (7,990 questions, tesseract eng+fin) |
| P1 evaluator | done | stub 6.9%, prior-only floor **37.3% DEV** [36.1, 38.5], n=6,192 |
| P1 takeoff | done | scale + area + door schedule, 44 tests |
| P1 raster-extractor | done (GO, conditional) | DEV150 **61.3%** vs prior 47.3%; beats prior on 8/12 intents; cold 2.21 s/image |
| P1 ui-builder | done | web build clean, 19 screenshots in `docs/shots/` |
| G1 gate | **GO** all 4 | see `docs/STATUS.md` |
| **P2 vector / skeptic / integrator** | **IN PROGRESS, interrupted** | code committed as WIP (`68ee2c1`); not yet verified by the lead |
| G2, P3 demo, P4 pre-ship | not started | |

Test suite at pause: **140 passed** (`.venv/bin/python -m pytest -q`, ~7 s).

What exists from P2 (WIP, unverified):
- `engine/vector/`: dxf, ifc, pdfvec, svgvec, swisspdf, schedule, sibling resolver `engine/siblings.py`
- `engine/skeptic/`: second voter(s), calibration, lexicon; `engine/triage/`: features + rules
- integrator: `engine/pipeline.py`, `router.py`, `query/` (planner, rules, schema), `cache.py`, `cost.py`, `api/main.py`,
  tests for router/query/pipeline/api, `scripts/pipeline_smoke.py`, `scripts/api_probe.py`
- handoffs written so far: `docs/handoff/integrator.md` (vector and skeptic handoffs NOT yet written)

## 3. Next steps, in order
1. **Finish P2.** For each of vector, skeptic, integrator: read its handoff if present, run its smoke/devcheck,
   finish missing pieces, write `docs/handoff/<agent>.md`. Check `git show 68ee2c1 --stat` for what changed;
   note that `engine/raster/` and `engine/takeoff/` were also touched during P2 (likely integrator wiring hooks):
   confirm these are small and don't break `raster`/`takeoff` tests.
2. **Integration pass** (`prompts/25`): DEV runs with and without siblings; hard set with LLM off vs planner on.
3. **G2 gate** (`prompts/05_gate.md`, WAVE=w2) → GO/NO-GO in `docs/STATUS.md`; up to 2 fix rounds.
4. **P3 demo** (`prompts/30`), then extras (`31`, `32`) if G2 is GO.
5. **P4 pre-ship** (`prompts/90`, `41`, `40` step 4) and `docs/MORNING.md`. Never run the HOLDOUT split until ship.

## 4. Human TODOs (agents must not do these)
- **Verify `evalkit/hard_questions.jsonl`**: 10 hand-written hard questions, 0/10 verified. It is the TEST set:
  check each expected answer by hand against the drawing; never tune on it.
- Push target: this repo had no remote at pause. Add one (`git remote add origin <url>`); never push to the
  parent `~/Downloads` repo (that is an unrelated course repo; see below).

## 5. Setup on a new machine
```
git clone <repo> plumb && cd plumb
make setup                      # creates .venv, installs requirements.txt (+ requirements-optional.txt for ifcopenshell, torch)
cp .env.example .env            # fill in values; never commit .env
make check                      # dataset + tesseract (eng+fin) + contract
.venv/bin/python -m pytest -q   # expect 140 passed
```
Dataset: download the Junction preview, set `DATASET_ROOT` to the folder containing `questions.jsonl` and `data/`
(it is NOT in git; 1.2 GB; CubiCasa is CC BY-NC-SA 4.0).

`.env` key names (values come from the team, never paste them in chat/commits):
`DATASET_ROOT`, `LLM_PROVIDER` (default `none`), `VERDA_BASE_URL_FAST`, `VERDA_BASE_URL_STRONG`, `VERDA_MODEL_FAST`,
`VERDA_MODEL_STRONG`, `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` (or `VERDA_API_KEY`), `BUDGET_VERDA_USD`, `HF_TOKEN`,
`FEATHERLESS_*`, `BUDGET_ANTHROPIC_USD=0`.

Verda = our Modal endpoints (OpenAI-compatible): fast = DeepSeek 4.1 Flash, strong = Kimi K3.1 Pro.
Base URLs **must end in `/v1`** (without it you get HTTP 404). Check with:
```
.venv/bin/python scripts/verda.py --ping --model fast
.venv/bin/python scripts/verda.py --ping --model strong
.venv/bin/python scripts/verda.py --spent        # running cost (was $0.0065 at pause)
```
First call after idle can take minutes (Modal cold start); the script prints each attempt.

## 6. Running the autonomous build
```
cd plumb && claude              # FIRST TIME ONLY: accept the "trust this folder" prompt, then /exit
STOP_AT=never setsid nohup bash scripts/overnight.sh > logs/overnight/supervisor.out 2>&1 < /dev/null &
```
- One lead session (Opus) follows `ORCHESTRATOR.md`, spawns builder subagents (`.claude/agents/`), commits, and
  updates `docs/STATE.md`. The supervisor restarts it after each cycle and sleeps through usage limits
  ("session limit · resets HH:MM").
- Watch: `docs/STATE.md`, `tail -f logs/overnight/SUPERVISOR.md`, `git log --oneline | head`.
- Stop: `kill $(pgrep -f 'bash scripts/[o]vernight.sh'); kill $(pgrep -f '^claude -p')`.
- Cheaper: `ORCH_MODEL=sonnet` gives more cycles per usage window.
- Before restarting after a manual pause, make sure line 1 of STATE is `STATUS: IN_PROGRESS` (BLOCKED/DONE stop it).
- Or work interactively: open `claude` in the folder and say "follow ORCHESTRATOR.md from docs/STATE.md".

## 7. Gotchas we already hit (don't repeat)
- **Nested git repo:** plumb used to live inside a `~/Downloads` git repo (a course project). The supervisor's
  `git add -A` swept 5,900 unrelated files into it (never pushed). Plumb is now its own repo; `overnight.sh`
  refuses to run unless plumb is the repo root and stages only `.`.
- **Folder trust:** a new repo root is an untrusted Claude Code project; headless runs then get every command
  denied and the lead marks STATE BLOCKED. Fix: run `claude` once in the folder, accept. `overnight.sh` now checks.
- **Session-limit message** wasn't recognised before and killed the run; fixed (sleeps until reset).
- **Background subagents lack Bash**: the lead spawns builders in the foreground.
- **Verda underused**: builders preferred writing code themselves ($0 spent on Verda during P1–P2). ORCHESTRATOR
  says "Verda-first"; if you want the Claude quota to last, make it a hard rule in briefs (e.g. tests/fixtures
  and lexicons must be drafted by Verda first, then checked by the builder).
- Some cycle-log timestamps in STATE are estimates by the lead (e.g. "~13:15"); trust git commit times instead.

## 8. Map of the important files
| file | what |
|---|---|
| `docs/STATE.md` | live checklist + cycle log (source of truth for progress) |
| `docs/STATUS.md` | gate tables with measured numbers, GO/NO-GO |
| `docs/handoff/*.md` | per-agent: what works, numbers, failures, how to run |
| `docs/decisions/*.md` | 3-line decision records |
| `ORCHESTRATOR.md`, `RUNBOOK.md` | how the lead works; phase order and gates |
| `prompts/` | the spec for each phase/agent |
| `contracts/proof.py` | the only interface between modules (frozen) |
| `evalkit/` | scoring harness; `evalkit/out/latest/report.md` is the only source for claimed numbers |
| `scripts/overnight.sh`, `scripts/verda.py` | supervisor; Verda client with budget + cost ledger |
