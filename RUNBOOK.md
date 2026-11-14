# RUNBOOK: exact order of work

> Default is now single-session mode: `START_HERE.md` and `ORCHESTRATOR.md`. This runbook describes the original parallel multi-agent mode; its gates and rules still apply.

## 0. TL;DR (the whole thing in 12 commands)
```
# once
claude update && brew install tesseract tesseract-lang uv ffmpeg node
cd <your repo> && cp -R <pack>/. . && git add -A && git commit -m "add plumb pack"
cp .env.example .env            # set DATASET_ROOT=<folder with questions.jsonl and data/>
claude --model sonnet --permission-mode acceptEdits "$(cat prompts/00_bootstrap.md)"       # W0, ~20 min
scripts/launch_wave.sh w1       # prints 4 commands: open 4 terminals, paste one per terminal   (~90 min)
scripts/merge_wave.sh w1 && claude --agent architect "$(cat prompts/05_gate.md)"            # gate (edit WAVE word first)
scripts/launch_wave.sh w2       # 3 terminals                                                  (~90 min)
scripts/merge_wave.sh w2 && claude --agent integrator "$(cat prompts/25_w2_integrate.md)"   # integration pass (~40 min)
claude --agent architect "$(cat prompts/05_gate.md)"                                          # gate w2
scripts/launch_wave.sh w3       # ONLY the extras if gate w2 is GO; else fix prompts. 3 terminals                                                  (~100 min)
scripts/merge_wave.sh w3 && claude --agent ui-builder "$(cat prompts/41_w4_video_kit.md)"   # video kit
# FREEZE -> claude --model sonnet "$(cat prompts/40_w4_ship.md)" -> claude --agent reviewer "$(cat prompts/90_review.md)"
```

## 1. Models (what to run on what)
| job | model | why |
|---|---|---|
| W0 bootstrap, ship step | `sonnet` | mechanical |
| evaluator, raster, takeoff, ui-builder, vector, skeptic, integrator | `sonnet` (set in the agent files) | best cost/quality for building |
| architect (gates), reviewer | `opus` | independent judgement, short runs, few tokens |
| recon, screenshots, formatting | `haiku` if you delegate | cheap |
| the one hardest debug (raster failure analysis, door-count rule) | `fable` or `opus`, only if quota is plentiful | skip otherwise |
Do not run everything on Opus: parallel agents multiply usage. Check usage with `/usage` (subscription) or `/cost` between waves.

## 2. Quota reality (your accounts were "0 limits")
- Test first: `claude -p "say ok" --model sonnet`. If it fails, you cannot run Claude Code on that account.
- Fallback that works with the same repo: any agentic CLI that reads `AGENTS.md` (Codex CLI etc.). Paste the prompt files as the task; the agent files are role descriptions, use their text as the first paragraph. Everything else (scripts, Makefile, contracts) is tool-agnostic.
- If usage runs out mid-wave: agents are told to write `docs/handoff/<agent>.md` and commit. Resume with the same prompt plus "continue from the handoff and git log".
- Save usage: W1 and W2 are the expensive waves. If tight, run only raster + evaluator + ui in W1 and skip skeptic until time allows.

## 3. Gates (targets; the architect decides GO/NO-GO)
| after | must be true |
|---|---|
| W0 | `make check` ok, `make test` green, `docs/recon.md` exists |
| W1 | evaluator: stub + prior baselines reproduce, `report.md` has tier table. raster: smoke ok, <= 2 s/image, beats prior median on >= 8 of 12 intents. takeoff: tests green, demo prints a valid receipt. ui: `npm run build` clean, 8 screenshots |
| W2 (CORE GATE) | zero crashes and zero invariant violations on DEV; every intent >= prior or tier amber; skeptic triage false-refusal < 1%; vector: IFC and DXF devchecks run; green more accurate than amber on DEV, with green COVERAGE reported; with and without siblings reported; router leave-one-language-out reported; query engine fixed specs match the intent path; hard set reported with LLM off and planner on, planner row higher. NO-GO blocks the W3 extras |
| W3 | all 12 UI beats present or explicitly cut in `docs/handoff/wow-ui.md`; dry run in `docs/DEMO_SCRIPT.md` passes |
| W4 | holdout run done ONCE, README generated from claims, video 85-110 s, reviewer says GO |

## 4. Timelines (pick by how much time is really left)
**Plan A, 20+ h left:** W0 0:20 · W1 1:30 · gate 0:15 · W2 1:30 · integrate 0:40 · gate 0:15 · W3 1:40 · video kit 0:45 · freeze at T-90 min · ship 1:00 · review 0:30. Use spare time to raise accuracy on the biggest failure bucket per the reports.
**Plan B, about 10 h left:** W0 0:20 · W1 1:30 (skip nothing) · W2 1:15 with only integrator + vector + skeptic-lite (triage + one extra voter for doors and windows) · integrate 0:30 · W3 only wow-engine + wow-ui beats 1,2,3,4,6,8,10 (skip A2A) · video kit 0:40 · freeze T-90 · ship 0:50 · review 0:20. Gates are 5-minute skims.
**Cut line:** if at T-4h the pipeline is not end to end, stop building features. Spend the rest on the UI over the best working route and the video. A working demo with honest numbers beats an unfinished feature.

## 5. Parallel waves: how
`scripts/launch_wave.sh wN` creates one git worktree per agent (`../<repo>-wt-<name>`, branch `wN/<name>`), copies `.env`, links `.venv`, and prints one command per agent. Open one terminal per command and paste it. Agents work on disjoint folders (see AGENTS.md ownership). When all are done: `scripts/merge_wave.sh wN` merges with `--no-ff`, runs pytest, tags `wN-done`. Exit 2 = merge conflict (resolve by keeping the owner's version), exit 3 = tests failing (run the gate prompt).
Requires a clean git state before launching.

## 6. Night mode (headless)
`scripts/run_headless.sh prompts/11_w1_raster.md sonnet 200` runs unattended with a turn cap and logs to `logs/`. Set `BUDGET=15` for a dollar cap on API billing. Never run holdout headless.

## 7. Rules that protect the score
1. HOLDOUT is touched exactly once, in W4.
2. Every number in README/video comes from `evalkit/out/latest/claims.json`.
3. Synthetic and demo data are always ribboned; credits always visible.
4. Skeptic never imports raster. Counts never need scale.
5. Report two rows: `LLM_PROVIDER=none` and planner on (`verda`, DeepSeek Flash). Claude only in the live demo; `BUDGET_ANTHROPIC_USD=0` during the build.

## 8. What the humans do while agents run
- Person 1 (driver): launches waves, pastes gate outputs, makes GO/NO-GO calls.
- Person 2: reads `docs/DEMO_SCRIPT.md`, rehearses the 10-second hook and Q&A, prepares voiceover and a 3-minute live version.
- Person 3 (if any): picks the 8 demo samples (one easy, one rotated, one tiny, one amber, one non-plan), checks credits and licences, tests on a second laptop.
- Person 2 or 3: write the hard set, `evalkit/hard_questions.jsonl` (format in `prompts/10_w1_evaluator.md` step 9): about 50 on DEV drawings and 20 on HOLDOUT drawings, answers checked by eye on the drawing, `verified: true` only after checking. Mix filters (bedrooms with a window), grouping (area per apartment), adjacency, mixed count and area, IFC storey + room, and Finnish/Italian/German/Estonian wording. Do not show holdout rows to agents.
Solo: do 1 and 2 in the gaps; the agents wait for no one.

## 9. Troubleshooting
| symptom | fix |
|---|---|
| `launch_wave.sh`: "Commit or stash first" | `git add -A && git commit -m wip` |
| agent cannot find `--agent` | `claude update` (needs the version with agent files); fallback: `claude --model sonnet "$(cat .claude/agents/<name>.md) $(cat prompts/<file>)"` |
| pip fails on opencv/pymupdf | `pip install --only-binary :all:` ; Python 3.11 or 3.12 |
| `tesseract` not found | `brew install tesseract tesseract-lang` |
| weights download blocked | raster takes route B (classical CV); write it in `docs/decisions/weights.md` |
| merge conflict | keep the owner's file; contracts only via architect |
| UI shows nothing in live mode | `curl localhost:8000/health`; check `VITE_API=live`; fall back to `fixtures` |

## 10. Compute and keys (merged plan)
| resource | use |
|---|---|
| local CPU | default for extraction and eval (images are tiny) |
| Modal ($100 per participant) | deployed demo endpoint (`modal deploy`), batch eval if CPU is too slow, open VLM only if needed |
| Verda (EUR 200, tracked in USD by scripts/verda.py) | planner and template classification in dev: DeepSeek 4.1 Flash; Kimi K3.1 Pro for hard cases |
| Featherless ($25) | backup inference |
| Claude API ($20) | live demo planner only |

`.env` key NAMES (never print values): `DATASET_ROOT`, `LLM_PROVIDER` (none|verda|featherless|anthropic), `VERDA_API_KEY`, `VERDA_BASE_URL`, `VERDA_MODEL_FAST`, `VERDA_MODEL_STRONG`, `FEATHERLESS_API_KEY`, `FEATHERLESS_BASE_URL`, `ANTHROPIC_API_KEY`, `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `HF_TOKEN`, `BUDGET_VERDA_USD`, `VERDA_PRICE_{FAST,STRONG}_{IN,OUT}`, `BUDGET_FEATHERLESS_USD`, `BUDGET_ANTHROPIC_USD=0`.
Verda and Featherless are called through one OpenAI-compatible client in `engine/router.py` (check the base URLs in each console). Every call is logged with tokens and cost; a call that would exceed its `BUDGET_*` is refused.
