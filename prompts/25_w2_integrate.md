# W2.5 · INTEGRATION PASS (agent: integrator, on main after merge_wave.sh w2, ~30-45 min)

The three W2 agents worked in parallel. Now make the real components work together. Short loops, measure after every change.

1. `make test 2>&1 | tail -15`. Fix interface mismatches in YOUR files (`engine/pipeline.py`, `engine/router.py`, `api/`). If a defect lives in another agent's package, write the smallest possible patch with the commit message `fix(<pkg>): <what> [integrator]` and list it in your handoff; do not refactor.
2. `.venv/bin/python -c "from engine import registry as R; print(R.autodiscover()); print([n for n,_ in R.voters_for('count')])"` — expect raster, skeptic, vector plugins.
3. Smoke through the real pipeline: `.venv/bin/python -m evalkit.run --engine pipeline --split dev --limit 200 --tag smoke`. Zero crashes. Open `evalkit/out/latest/report.md` section 8 (exceptions, invariant violations) and fix the top three causes.
4. Full DEV run in the background and read the report: `.venv/bin/python -m evalkit.run --engine pipeline --split dev --workers 4 --tag w2-dev` then `--no-siblings --tag w2-dev-nosib`.
5. Train the skeptic's calibrator and stacker on the new DEV results: `.venv/bin/python -m engine.skeptic.train --run latest` (it must use DEV only). Re-run the DEV evaluation once to confirm the stacker helps; if not, disable it per intent.
5b. Hard set: `.venv/bin/python -m evalkit.run --engine pipeline --split dev --hard --tag w2-hard` with `LLM_PROVIDER=none`, then with `LLM_PROVIDER=verda`. The planner run should beat the LLM-off run; log USD and check the `BUDGET_*` caps held. Report green coverage next to green accuracy.
6. Calibration sanity: green must be more accurate than amber on DEV. If it is not, find out why (usually voters sharing a bug) and write it up in `docs/handoff/integrator.md` rather than hiding it.
7. Speed: print mean ms per question and CPU-seconds per drawing from the report; if > 5 s per drawing, profile (`python -X importtime`, `cProfile`) and fix the top hotspot only.
8. Commit `integrator: w2 integration pass`, update `docs/handoff/integrator.md` with the numbers (headline DEV, with and without siblings, tier calibration, ms, LLM calls). Do NOT run HOLDOUT.
