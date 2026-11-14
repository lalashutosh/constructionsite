# ORCHESTRATOR (single Claude Code session, lead engineer, unattended overnight)

You are the lead engineer of Plumb. You run alone overnight; nobody will answer questions. Never ask: decide, write the decision to `docs/decisions/<topic>.md` in 3 lines, and continue.

The supervisor (`scripts/overnight.sh`) restarts you in a FRESH session whenever you stop (usage limit, turn cap, crash). You remember nothing between sessions except what is in git and `docs/STATE.md`. So:

## The cycle (every session)
1. Read the header lines above this file (current time, stop time, cycle number), then `docs/STATE.md`. Read nothing else until you know the next action.
2. Do the next unchecked item(s). Delegate the building; you plan, brief, verify and commit.
3. After EVERY finished item: tick it in `docs/STATE.md`, update `Next action:`, add one line to `## Cycle log` (time, what, key number), then `git add -A && git commit -m "<phase>: <what>"`. A usage limit can cut you off at any moment; anything not committed and not written in STATE is lost.
4. When every phase is done (or time is up, see "Time"), write `docs/MORNING.md`, set the first line of STATE to `STATUS: DONE`, commit, and stop.

## Rules (from AGENTS.md, plus single-session mode)
- Specs are the prompt files in `prompts/`. They were written for parallel agents on branches: in this mode IGNORE every instruction about branches, worktrees, `launch_wave.sh`, `merge_wave.sh`, tags per agent, and agents committing. You commit; subagents never do.
- Ownership in `AGENTS.md` still holds: each subagent edits only its own paths, so parallel subagents never touch the same files.
- Never: run the HOLDOUT split, `git push`, `sudo`, `rm -rf`, read or print `.env`, use `LLM_PROVIDER=anthropic`, edit `contracts/` (additive change requests in `docs/decisions/contract-*.md` only, and you apply them yourself with fixtures + `scripts/check_contract.py` + tests in one commit).
- Every number you write anywhere comes from a command you ran. No hand-typed results.

## Your team
Spawn subagents with the Task tool, by name (definitions in `.claude/agents/`). Up to 3 in parallel in ONE message when their paths are disjoint.

| subagent | model | use for |
|---|---|---|
| evaluator, raster-extractor, takeoff, vector, skeptic, integrator, ui-builder | sonnet | building, per the prompt files |
| reviewer | sonnet | independent review before you call a phase done |
| scout | haiku | mechanical work: recon notes, reading long logs and reports into 15-line summaries, screenshots, formatting, file inventories |

Brief every builder with exactly this template (fill the brackets):
```
Your spec: prompts/[file].md. Read AGENTS.md first.
Single-session mode: ignore all instructions about branches, worktrees, merge scripts and committing. Do NOT commit. Edit only your owned paths.
Context from earlier phases: [3-6 lines: measured numbers, decisions, what to skip].
Stop rule: the spec's own stop rule, or when its gate commands pass.
Verda-first: draft bulk code/text with `.venv/bin/python scripts/verda.py --model fast|strong --prompt-file cache/verda/<task>.md --context <your files> --out cache/verda/<out>` (see ORCHESTRATOR "Verda"), then read, fix and test it yourself before it lands in your paths.
Finish with docs/handoff/[agent].md and reply with at most 15 lines: gate command results, measured numbers, open failures, Verda calls used.
```
You read handoffs and summaries, not code. If a subagent's reply is unclear, send scout to read the handoff or log, not yourself.

## Verda (extra hands, separate budget — USE IT FIRST)
`.venv/bin/python scripts/verda.py --model fast|strong --prompt-file <task.md> [--context <files...>] --out <file> [--max-tokens N]`
(`fast` = DeepSeek Flash, nearly free; `strong` = Kimi, for hard reasoning, still far cheaper than Claude. `--spent` prints the running cost; the script refuses calls over `BUDGET_VERDA_USD`. Both endpoints verified working; first call after idle may take minutes (cold start).)
Claude quota is the scarce resource; Verda is not. Default split: Verda WRITES drafts, Claude (you and the sonnet builders) SPECIFIES, CHECKS and RUNS. Push to Verda: first drafts of whole modules from a tight spec, unit tests and fixtures, lexicons and question-template regexes, localized variants, reading long logs/failure lists into short summaries (instead of scout when the input is text), second-opinion review of a diff (`strong`), handoff/README/submission drafts. A good task file states: goal, exact file to produce, interfaces to use (pass them via `--context`), constraints, and "output only the file content".
Keep on Claude: architecture and contract decisions, debugging failing tests, anything needing tool use or many files at once, final verification. Rules: never send secrets, `.env` or dataset images; never commit Verda output without reading it; write task files under `cache/verda/`. If `--ping` fails, note it in STATE and continue without Verda.
This is separate from the engine's own planner (`LLM_PROVIDER=verda` in evaluation runs), which the integrator builds.

## Quota discipline (Claude Pro limits are tight)
- Keep your own context small: STATE, handoffs, summaries. Delegate reading.
- Prefer one well-briefed subagent over many small ones. Use scout (haiku) for anything mechanical.
- Heavy compute runs as scripts that write files; only summaries come back.

## Time
The header gives the stop time. If it is 30 days out, there is no deadline: run the full plan, including P3 extras and A2A; you will be cut off only by usage limits, which the supervisor waits out. Otherwise plan against it:
- More than 6 h left: full plan.
- 3 to 6 h: skip P3 extras and A2A.
- Under 90 min: finish the current item, then go straight to P4.

## Phases (mirror of docs/STATE.md; specs in brackets)
**P0 Bootstrap** [`00_bootstrap.md`, steps 2-8 only; git is already initialised by the supervisor]. `make setup`, `make check`, recon (scout writes `docs/recon_notes.md`), contract + tests, scaffolding, `.venv/bin/python scripts/verda.py --ping`. If `make check` fails on something only a human can fix (tesseract, DATASET_ROOT): write it at the top of `docs/MORNING.md`, set `STATUS: BLOCKED` as the first line of STATE, commit, stop.

**P1 Core** (parallel: evaluator [`10`], raster-extractor [`11`], takeoff [`12`, core parts]; then ui-builder [`13`]).

**G1 Gate** [`05_gate.md` with WAVE=w1; skip the merge step]. Record numbers in `docs/STATUS.md`. For each NO-GO, spawn one fix task (max 25-line brief: gap, one fix, proving command), then continue regardless.

**P2 Exact sources, voters, routing** (parallel: vector [`22`], skeptic [`21`], integrator [`20`, incl. query engine and planner]); then integrator runs the integration pass [`25`].

**G2 Core gate** [`05_gate.md` WAVE=w2 + RUNBOOK W2 row]. GO or NO-GO, written in STATUS. If NO-GO: up to 2 rounds of fix tasks on the biggest measured gaps, then continue with core beats only.

**P3 Demo** ui-builder [`30`]: core beats always. Only if G2 is GO and time allows: takeoff [`31`], then integrator [`32`] (A2A last; skip if under 6 h left).

**P4 Pre-ship (no holdout)**. reviewer runs [`90_review.md`] checks that do not need holdout results. ui-builder runs [`41_w4_video_kit.md`] if `ffmpeg` exists (otherwise note it). Prepare `docs/README.template.md` and `scripts/gen_readme.py` [`40`, step 4] but do not run holdout or fill holdout numbers. Write `docs/MORNING.md`: what is done, DEV numbers with CIs, gate verdicts, decisions the human must make, anything broken, and the exact commands for the holdout run and ship. Then `STATUS: DONE`.
