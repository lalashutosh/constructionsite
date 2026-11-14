# WAVE GATE (run as: claude --agent architect "$(cat prompts/05_gate.md)" with WAVE=<w1|w2|w3> substituted in the first line below)

WAVE under review: **w1**   <- the human edits this word before running (w1, w2 or w3)

You are the architect. All wave branches have been merged into main by `scripts/merge_wave.sh`. Do not edit builder source code. Be brief and factual.

## Steps
1. `git log --oneline -30 | cat` and `ls docs/handoff`. Read every `docs/handoff/*.md` of the reviewed wave (not the code).
2. `make test 2>&1 | tail -15`. Record pass/fail counts.
3. Run the evaluation for the wave:
   - w1: `make eval-stub` then `.venv/bin/python -m evalkit.run --engine prior --split dev`; record the stub and prior baselines.
   - w2: `.venv/bin/python -m evalkit.run --engine pipeline --split dev` and again with `--no-siblings`. Record headline, per-source, tier calibration (green/amber/grey n + accuracy), mean ms, tokens, USD. Then the hard set (`--hard`) with `LLM_PROVIDER=none` and with the planner on; record both accuracies, planner calls and USD.
   - w3: same as w2 plus `make web-build` (or `cd web && npm run build`) and the end-to-end demo path in `docs/DEMO_SCRIPT.md` section "Dry run".
4. Compare with the thresholds in `RUNBOOK.md` section "Gates" for this wave. Per agent decide GO or NO-GO. NO-GO means a named, measurable gap.
   For w2 this is the CORE GATE in `RUNBOOK.md`. If it is NO-GO: rewrite `prompts/30_w3_wow_ui.md` to its core beats only, mark `31_w3_wow_engine.md` and the A2A part of `32_w3_a2a.md` as skipped, and put the effort into `fix_*.md` prompts.
5. Write `docs/STATUS.md` (replace the rows of this wave): status, measured numbers, link to the handoff.
6. Rewrite the NEXT wave's prompt files so they contain the measured facts: best extraction route, per-intent failure buckets worth fixing first, things to skip. Edit only `prompts/*.md` and `docs/*`. Mark every edit with `<!-- gate:<wave> -->`.
7. For every NO-GO write `prompts/fix_<agent>.md`: max 25 lines, the measured gap, the one most promising fix, the command that proves it is fixed. The human decides whether to run it.
8. Contract change requests (`docs/decisions/contract-*.md`): accept only additive, backwards-compatible changes; update fixtures, `scripts/check_contract.py`, tests in the same commit. Otherwise reject in writing in the same file.
9. `git add -A && git commit -m "gate <wave>: <GO|NO-GO summary>" && git tag <wave>-gated`.

## Final output (max 15 lines)
GO/NO-GO per agent with the key number each, the single biggest risk for the next wave, and the exact next command.
