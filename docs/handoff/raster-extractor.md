# Handoff: raster-extractor

Full handoff is at `docs/handoff/raster.md` (the path required by `prompts/11_w1_raster.md` and
`AGENTS.md`'s ownership table, which this file mirrors by reference per the task's explicit
request for `docs/handoff/raster-extractor.md`). Decision doc: `docs/decisions/weights.md`.

One-line status: code (Route A pretrained CNN + Route B classical-CV fallback, 12 count rules,
smoke + devcheck harnesses) is complete and unchanged this cycle; gate re-run was blocked this
session by an untrusted-workspace Bash restriction (see `docs/decisions/weights.md` →
"Execution blocked this session"), so the per-intent table in `docs/handoff/raster.md` is the last
persisted artifact (`docs/claims/raster.json`: `clean_acc=0.375`), not a fresh measurement.
