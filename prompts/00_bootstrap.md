# W0 BOOTSTRAP (single session, main branch, ~20 min)

You are the bootstrap engineer for project Plumb. Work in the repo root (current directory). Be mechanical and fast; do NOT build any product feature. Show only short summaries (`| tail -30`).

Read first (and nothing else): `AGENTS.md`, `RUNBOOK.md` (sections "Gates" and "Quota"), `contracts/proof.py` headers only.

## Steps (do them in order, stop at the first hard failure and report it)

1. **Git.** `git status`. If this is not a git repo: `git init -b main`. Commit the pack as-is: `git add -A && git commit -m "w0: add plumb pack"`. If there are pre-existing project files, leave them untouched.
1b. **Pack check.** Confirm these exist: `AGENTS.md`, `RUNBOOK.md`, `contracts/`, `engine/registry.py`, `vendor/planlab/`, `docs/DEMO_SCRIPT.md`, `scripts/recon.py`, `scripts/check_contract.py`, `scripts/check_env.py`, `scripts/launch_wave.sh`, `scripts/merge_wave.sh`, `.env.example`, `.claude/agents/`. If any is missing: `W0 BLOCKED: missing <list>`.
2. **Environment.** `make setup` (creates `.venv`, installs `requirements.txt`). If a single package fails (usually `opencv-python-headless` or `pymupdf` wheels), retry once with `--only-binary :all:` and note it in `docs/decisions/env.md`. Optional deps (`requirements-optional.txt`) are installed LATER by the agents that need them.
3. **Dataset.** `cp -n .env.example .env`. Find the dataset: `find ~ -maxdepth 4 -name questions.jsonl -not -path "*/node_modules/*" 2>/dev/null | head`. If exactly one result, set `DATASET_ROOT=<its folder>` in `.env`. If none or several: STOP and print "Set DATASET_ROOT in .env to the folder that contains questions.jsonl and data/" with the candidates. Never print the contents of `.env`. Check only that the key NAMES from `RUNBOOK.md` section 10 exist (add empty ones if missing) and that `LLM_PROVIDER=none` and `BUDGET_ANTHROPIC_USD=0`.
4. **Check.** `make check` must exit 0. If tesseract is missing: STOP with `W0 BLOCKED` and the install command for the human (Fedora: `sudo dnf install tesseract tesseract-langpack-fin`; macOS: `brew install tesseract tesseract-lang`). Never run sudo. Fix only what the check reports.
5. **Recon.** `.venv/bin/python scripts/recon.py` -> `docs/recon.md`. Then write `docs/recon_notes.md` (max 25 lines) with: (a) number of questions per source x type, (b) the list of distinct English templates per source (these ARE the intents), (c) which sources are answerable from the given file alone and which have a same-stem sibling, (d) three surprises you noticed. Facts only, copied from `docs/recon.md`.
6. **Contract and tests.** `.venv/bin/python scripts/check_contract.py && make test`. Both must pass. The merged plan added two optional fields before freezing the contract (`Cost.planner_calls`, `ProofObject.query_spec`) and one invariant. If `check_contract.py` fails ONLY because of these, regenerate its snapshot or schema the way the script documents, record it in `docs/decisions/contract-merge.md`, and re-run. Anything else failing: stop and report.
7. **Scaffolding.** `mkdir -p docs/handoff docs/decisions docs/shots weights cache logs`; make sure `weights/ cache/ logs/` are in `.gitignore`. Create `docs/STATUS.md` as a table: wave | agent | status | measured numbers | handoff link. All rows `todo`, W0 row `done`.
8. **Quota probe.** Run `claude --version` and write the result into `docs/decisions/env.md`. If `claude update` is needed (Sonnet 5.5 needs >= 2.1.284), say so there.
9. **Commit and tag.** `git add -A && git commit -m "w0: bootstrap verified" && git tag w0-done`.

## Final output (exactly this, nothing else)
```
W0 DONE
dataset: <path>  questions: <n>  sources: <list>
tests: <passed>/<total>   contract: ok
NEXT: scripts/launch_wave.sh w1
```
If anything failed: `W0 BLOCKED: <one line>` followed by the exact command the human must run.

## Don'ts
No engine code. No contract edits. No reading images. No long logs. No pushing to a remote.
