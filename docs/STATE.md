STATUS: IN_PROGRESS

Next action: P2 — vector(22), skeptic(21), integrator(20) in parallel (foreground). Human TODO: verify evalkit/hard_questions.jsonl rows (0/10 verified).

## Checklist
### P0 Bootstrap
- [x] make setup (venv + requirements)
- [x] make check passes
- [x] recon: docs/recon.md + docs/recon_notes.md (scout)
- [x] scripts/check_contract.py and make test pass
- [x] scaffolding: docs/handoff, docs/decisions, docs/shots, weights, cache, logs; docs/STATUS.md table
- [x] verda.py --ping (ok or noted)

### P1 Core
- [x] evaluator (prompts/10): stub 6.9%, prior floor 37.3% DEV, 29 eval tests green
- [x] raster-extractor (prompts/11): route A; DEV150 61.3% (prior 47.3%), CLEAN 63.0% n=27 (in-sample after 2 fallback fixes)
- [x] takeoff (prompts/12): scale + area + door schedule — 44 tests green
- [x] ui-builder (prompts/13): typecheck+build+shot green, 19 shots, fixture-driven

### G1 Gate
- [x] gate w1 numbers in docs/STATUS.md, GO/NO-GO per agent (all GO; raster w/ conditions)
- [x] fix tasks for NO-GOs (none needed)

### P2 Exact sources, voters, routing
- [ ] vector (prompts/22): IFC, DXF, schedule devchecks
- [ ] skeptic (prompts/21): voters, triage confusion table
- [ ] integrator (prompts/20): pipeline, router, query engine, planner, API
- [ ] integration pass (prompts/25): DEV runs with/without siblings, hard set LLM off vs planner on

### G2 Core gate
- [ ] gate w2 verdict in docs/STATUS.md
- [ ] fix rounds (if NO-GO, max 2)

### P3 Demo
- [ ] ui-builder (prompts/30) core beats
- [ ] extras: takeoff (prompts/31) — only if G2 GO and time
- [ ] extras: integrator A2A (prompts/32) — only if G2 GO and > 6 h left

### P4 Pre-ship (no holdout)
- [ ] reviewer (prompts/90) non-holdout checks
- [ ] video kit (prompts/41) or noted why not
- [ ] README template + gen_readme.py (no holdout numbers)
- [ ] docs/MORNING.md written

## Cycle log
- 05:35 C1 P0 done: make check OK (7990 rows, tesseract eng+fin), 15 tests pass, contract OK, verda ping ok ($0.0034). Scaffolding + STATUS.md created.
- 06:06 C3 P1: verified evaluator (stub 6.9%, prior floor 37.3% DEV, 29 tests) + takeoff (44 tests) done from C2. Spawned raster-extractor (finish measurement+claims) + ui-builder (web from scratch) in parallel.
- 12:40 C1 BLOCKED: workspace trust gate denies all exec (python/pytest/make/npm/git) for lead AND subagents. raster-extractor+ui-builder did no real work; both stopped. Human must accept trust dialog. STATE/MORNING written to disk (uncommitted, git blocked). See docs/decisions/workspace-trust-block.md.
- 12:50 C1 restart: exec works again (trust fixed). Respawned raster-extractor (re-measure) + ui-builder (build+shots) in parallel.
- ~13:15 C1 P1 done: ui build+19 shots; raster DEV150 50.0%->61.3% after 2 prior-fallback fixes (CLEAN 44.4->63.0, n=27). Background subagents lack Bash -> use foreground.
- ~13:25 C1 G1 GO all 4: 94 tests, stub 6.9%, prior 37.3% DEV; raster cold 2.21s/img; ifcopenshell missing; hard set 0/10 verified.
