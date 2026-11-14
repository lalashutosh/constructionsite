STATUS: IN_PROGRESS

Next action: P1 — raster-extractor + ui-builder running (C1 12:50, trust fixed). On return: verify, tick, then G1 gate.

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
- [ ] raster-extractor (prompts/11): route chosen, clean-subset number, per-intent table (running C3)
- [x] takeoff (prompts/12): scale + area + door schedule — 44 tests green
- [ ] ui-builder (prompts/13): build clean, screenshots (running C3)

### G1 Gate
- [ ] gate w1 numbers in docs/STATUS.md, GO/NO-GO per agent
- [ ] fix tasks for NO-GOs (or none needed)

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
