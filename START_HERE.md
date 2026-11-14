# Start here (one Claude Code session, overnight)

This is the Plumb pack with the merged plan applied, in **single-session mode**: one Claude Code session (Opus if your plan has it, otherwise Sonnet) is the lead engineer. It delegates the building to Sonnet subagents, mechanical work to a Haiku "scout", and bulk text to Verda through `scripts/verda.py`. A supervisor script restarts it automatically after every usage-limit reset, and it resumes from `docs/STATE.md` and git.

The specs, contracts and gates are unchanged from the merged plan (`PATCHES.md`). `ORCHESTRATOR.md` is the lead's instructions.

## 1. Once (Fedora)
```bash
sudo dnf install tesseract tesseract-langpack-fin ffmpeg-free nodejs git make python3
claude update
cd plumb
cp .env.example .env
```
Edit `.env`: `DATASET_ROOT` (the unzipped PREVIEW dataset: the folder with `questions.jsonl` and `data/`), the Verda keys and model IDs (`VERDA_BASE_URL` must be the OpenAI-compatible base, usually ending in `/v1`), optional Featherless keys. Keep `LLM_PROVIDER=none`.

## 2. Check before you sleep (2 minutes)
```bash
claude -p "say ok" --model opus      # if this fails, the supervisor will use sonnet; also try: --model sonnet
unset ANTHROPIC_API_KEY              # use your Pro subscription, not API billing
python3 -m venv .venv && .venv/bin/pip install -q httpx && .venv/bin/python scripts/verda.py --ping   # should print ok
tesseract --version | head -1
```

## 3. Start
```bash
STOP_AT=09:00 bash scripts/overnight.sh
```
Plugged in, lid open. The machine is kept awake for the run.
What happens: cycle 1 starts the lead. When Claude Pro's usage limit hits, the session ends; the supervisor waits 15 minutes and retries until the limit has reset, then a fresh session reads `docs/STATE.md` and continues. It stops at `STOP_AT`, when the plan is done, when it is blocked on something only you can fix, or after 4 cycles in a row with no progress.

## 4. Morning
1. `logs/overnight/SUPERVISOR.md`: one line per cycle.
2. `docs/MORNING.md`: what is done, DEV numbers, gate verdicts, decisions for you, the exact holdout and ship commands.
3. `docs/STATE.md`: the checklist. To continue later: `bash scripts/overnight.sh` again; it picks up where it stopped.

## 5. Your jobs (the lead cannot do these)
- Write the hard set `evalkit/hard_questions.jsonl` (format: `prompts/10_w1_evaluator.md` step 9): about 50 on DEV drawings and 20 on HOLDOUT drawings, answers checked by eye, `verified: true` only after checking.
- Run the holdout and ship step yourself (`prompts/40_w4_ship.md`): the lead never touches the holdout.

## What to expect on Claude Pro
Pro allows a limited amount of work per 5-hour window, shared by the lead and all its subagents. Expect P0 and P1, probably the G1 gate, possibly part of P2 by morning. The plan is ordered so the most valuable parts come first. Anything unfinished continues the next time you run the supervisor.

## Optional: parallel multi-agent mode
The original wave scripts (`scripts/launch_wave.sh`, `scripts/merge_wave.sh`, `RUNBOOK.md` section 0) still work if you later have more quota.
