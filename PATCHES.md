# Merged-plan patches to the Plumb pack

Already applied in this folder.

| File | Change |
|---|---|
| AGENTS.md | Judging marked as working assumption + "harder questions" note; tagline without sponsor comparison; CubiCasa licence CC BY-NC-SA 4.0; rule 8 rewritten (LLM = template classification + planner, never the number; providers verda/featherless/anthropic); rules 10 (hard set) and 11 (core gate); integrator owns `engine/router.py`, `engine/query/` |
| RUNBOOK.md | W2 row is now the core gate; W3 launch conditional; two reported rows (LLM off, planner on); humans write the hard set; new section 10 compute and keys |
| contracts/proof.py | Additive: `Cost.planner_calls`, `ProofObject.query_spec` (both default empty, fixtures still valid) |
| contracts/invariants.py | Planner answers must carry `query_spec` |
| prompts/00_bootstrap.md | Pack-file check; `.env` key names; contract snapshot update allowed for the two new fields only |
| prompts/05_gate.md | Hard-set rows in W2 eval; NO-GO on W2 blocks the extras |
| prompts/10_w1_evaluator.md | Hard-set harness (`--hard`, verified rows only), new claims keys, `llm_mode` in reports |
| prompts/11_w1_raster.md | Licence string |
| prompts/12_w1_takeoff.md | Scale, area, door schedule are core; materials/vibes/ledger are stretch |
| prompts/13_w1_ui.md | AnswerCard shows `query_spec` for planner answers |
| prompts/20_w2_integrator.md | Query engine + planner as router layer 4, with tests |
| prompts/25_w2_integrate.md | Hard-set runs, LLM off vs planner on, budget check, green coverage |
| prompts/30, 31, 32 | Gated on W2 GO (30 keeps its core beats) |
| prompts/40_w4_ship.md | Tagline; hard set on holdout once |
| prompts/90_review.md | Checks 12 (hard set) and 13 (planner honesty) |
| docs/DEMO_SCRIPT.md | Harder-question beat added; extra beats marked W2-gated; sponsor comparison removed; licence string; 60-second cut uses the core beats |
| .env.example | All key names, budget caps, `LLM_PROVIDER=none` |
| tests/test_contract_merge.py | Tests for the new contract fields and invariant |
| START_HERE.md | Short path for a solo run, incl. overnight |
| ORCHESTRATOR.md | Single-session lead instructions: cycle protocol, delegation, Verda use, phases P0 to P4, time rules |
| docs/STATE.md | Checklist and next action; the only memory between sessions |
| scripts/overnight.sh | Supervisor: restarts the lead after usage limits, turn caps or crashes; opus to sonnet fallback; stops on DONE, BLOCKED, STOP_AT or no progress |
| scripts/verda.py | One-shot Verda/Featherless calls with cost ledger and budget cap |
| .claude/agents/scout.md | Haiku helper for mechanical work; reviewer now on sonnet |
| .claude/settings.json | Allow list extended (git init/tag, cd, sed, scripts, .venv/bin, ffmpeg ...) so headless runs do not get stuck |
