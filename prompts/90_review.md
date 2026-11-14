# REVIEW (agent: reviewer, model opus, read-only on source). Run before submission and after any big merge.

You did not write this code. Find what would embarrass the team in front of the judges. Write only `docs/review.md`.

## Checks (run the commands, quote their output)
1. **Claims trace.** Extract every number from `README.md`, `docs/SUBMISSION.md`, `docs/DEMO_SCRIPT.md` (regex `\d+(\.\d+)?\s?(%|ms|s|USD|\$|tokens)`). Each must equal a value in `evalkit/out/latest/claims.json` or `report.md`. List every untraceable number.
2. **Holdout integrity.** `git log --all --oneline -- evalkit/out` and `grep -rn "holdout" engine/ | head`: did any training/tuning code read holdout results? `engine/skeptic/train.py` must filter `split == "dev"`. Check the split function is the documented hash.
3. **Calibration.** In the final report: is green more accurate than amber and amber more accurate than grey-with-benchmark-guess? By how many points, with CIs? If not, say so loudly.
4. **Spot-check 20 proofs.** Pick 20 ProofObjects from `results.jsonl` (stratify: 8 green, 8 amber, 4 wrong). For each, render or open the evidence polygons on the image (downscale to <= 1000 px), count by eye, and record agree/disagree plus whether the tier was sensible.
5. **Circularity.** Search results for any reported width, area or length whose scale anchors are only `door_prior` without `widths_relative`; each is a bug.
6. **Independence.** `grep -rn "engine.raster" engine/skeptic engine/triage` must be empty. Voters must not share cached outputs.
7. **Cost honesty.** Confirm `llm_calls == 0` in the default configuration, that no code path performs network calls during `ask`, and that the per-drawing CPU estimate in the report is computed, not typed.
8. **Licences.** Credit string visible next to every displayed drawing (open the UI, check every beat). Synthetic and demo data ribboned everywhere (door-schedule order, tamper test). No NonCommercial data redistributed beyond what the demo needs. Weights licence stated.
9. **Secrets.** `git log -p | grep -i -E "api[_-]?key|secret|token" | head`; confirm `.env` is untracked.
10. **Fresh clone.** `git clone . /tmp/review-fresh && cd /tmp/review-fresh && make setup && make test`; report exactly what breaks. Then run the demo path from `docs/DEMO_SCRIPT.md` section "Dry run" against a clean `cache/`.
11. **Judge's questions.** Answer each in one honest paragraph using only repo evidence: Is the benchmark leaked to the pretrained weights? What happens on a language we have not seen? What happens when the scan has no scale? What is the cost per 1,000 questions? Why would a frontier model not make this obsolete? What does the system do when it is wrong?

12. **Hard set.** Holdout hard-set numbers exist for LLM off and planner on, and the README states both. `git log -- evalkit/hard_questions.jsonl` shows no edits after the first holdout run.
13. **Planner honesty.** Every ProofObject with `cost.planner_calls > 0` has a `query_spec`, and re-running that spec on the facts with no LLM gives the same value.

## Output (`docs/review.md`)
A ranked findings table (severity, what, repro command, suggested fix, owner agent), then the answers to check 11, then a GO/NO-GO for submission. Be concrete: file, line, command.
