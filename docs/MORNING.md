# MORNING — human action required

## BLOCKER (fix this first)
**The overnight run is dead until you accept the workspace trust dialog.**
Every execution command (python, pytest, make, npm, even `git --version`) is denied with:

> this workspace has not been trusted... run Claude Code interactively here once and accept the trust dialog

Fix:
1. `cd /home/ashutosh/Downloads/plumb && claude` interactively, accept the trust prompt
   (or set `hasTrustDialogAccepted:true` for this project in `~/.claude.json`).
2. Restart `scripts/overnight.sh`.

Until then no subagent can run tests, builds, or `scripts/verda.py`. No code was lost —
all P0 + committed P1 code is intact in git. These writes (MORNING.md, STATE.md,
decisions/workspace-trust-block.md) are **uncommitted** because git exec is also blocked;
commit them after trust is fixed, or just let the next session re-derive state.

## Where things stand
- P0 Bootstrap: done (prior sessions).
- P1: evaluator done (stub 6.9%, prior-floor 37.3% DEV, 29 tests). takeoff done (44 tests).
- P1 raster-extractor: route = A (pretrained CubiCasa5k CNN), confirmed by read-only
  inspection; last persisted `docs/claims/raster.json` clean_acc=0.375 (NOT re-verified).
  No per-intent table on disk yet — prior session was cut off before writing it.
  Known gaps: `showers_baths` undercounts to 0 (no shower class), doors slightly under on
  dense plans (conf threshold 0.5 maybe too high).
- P1 ui-builder: NOT finished (blocked by trust). web/ scaffold on disk.
- G1 gate: not run.

## Resume commands after trust is fixed
- raster table: `.venv/bin/python -m engine.raster.smoke` ; `.venv/bin/python -m engine.count.devcheck --n 150 | tee logs/raster_devcheck.log` ; `.venv/bin/pytest tests -q -k "raster or count"`
- ui: `cd web && npm run build` ; then screenshots to docs/shots/
- then G1 gate: prompts/05_gate.md WAVE=w1
