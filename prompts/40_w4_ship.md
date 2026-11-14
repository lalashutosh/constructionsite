# W4 · SHIP (main session, `claude --model sonnet`, ~60 min). CODE FREEZE is at T-90 min; this prompt runs after it.

Mission: freeze, measure once on the untouched HOLDOUT, generate every public claim from the report, and produce the submission package. No feature work. If something is broken, fix the smallest thing or cut it from the demo.

## Steps
1. **Freeze.** `git status` clean; `git tag freeze`. Run `make test` (all green) and `cd web && npm run build`.
2. **Holdout, once.** `make eval-holdout` then `.venv/bin/python -m evalkit.run --engine pipeline --split holdout --no-siblings --tag final-nosib`. Then the hard set once on holdout, LLM off and planner on: `.venv/bin/python -m evalkit.run --engine pipeline --split holdout --hard --tag final-hard` (run with each `LLM_PROVIDER`). These are the only holdout runs. Never tune after seeing them. If something is embarrassing, the README says so.
3. **Claims.** `make claims`. Open `evalkit/out/latest/claims.json`; every number the README or video uses must come from there.
4. **README.** Create `docs/README.template.md` with `{{claim:key}}` placeholders and `scripts/gen_readme.py` that fills them from `claims.json` and FAILS if a placeholder has no value or if a number-like token (`\d+(\.\d+)?%`) exists outside a placeholder. Sections: (1) one-liner: "Plumb: blueprints that show their work. Every number points at the pixels it came from." (2) What a judge sees in 90 seconds (link to video), (3) How we score on the four criteria with measured numbers: accuracy on held-out drawings with and without siblings and with the Wilson interval, tier calibration (what green means), verification (proof object, duel, receipt), creativity (decision ledger, door schedule, reconcile, tamper test, A2A), cost (LLM calls, ms, CPU-seconds per drawing, extrapolation labelled as estimate), (4) architecture in one diagram (text/mermaid) and the rule "frontier models make our verification layer more valuable, not obsolete", (5) run it in 3 commands, (6) honesty section: what we do not do, benchmark-vs-product modes, the CubiCasa train-split caveat with the clean-subset number, synthetic and demo data are always labelled, licences and credits, (7) team. Then `make readme`.
5. **Submission text.** `docs/SUBMISSION.md`: title, 40-word summary, 180-word description, the four-criteria paragraph, links (repo, video), tags. Facts only from claims.json.
6. **Video.** Run `prompts/41_w4_video_kit.md` steps if not done; otherwise re-run `bash scripts/make_video.sh`. Check duration (85-110 s) and that the numbers on screen match claims.json.
7. **Fresh-clone proof.** `rm -rf /tmp/fresh && git clone . /tmp/fresh && cd /tmp/fresh && cp ../.env .env 2>/dev/null; make setup && make test`. Paste the tail of the output into `docs/handoff/ship.md`.
8. **Package.** `git tag submission && git archive --format=zip -o plumb-submission.zip HEAD` (no `.env`, no weights, no cache). List the zip size and top-level contents.

## Final output (max 20 lines)
Holdout headline (with and without siblings), what green means in numbers, cost numbers, video path, repo tag, anything still broken.

## Don'ts
No tuning after the holdout run. No hand-typed numbers anywhere. Never commit `.env`, weights, caches, or dataset files.
