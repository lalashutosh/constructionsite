# Handoff: raster-extractor (engine/raster/, engine/count/)

## Status: code complete, gate re-run BLOCKED this cycle by an infra issue (not a code issue)

This resume cycle could not execute any Python (`python3 -c/-m`, `.venv/bin/python`, `pytest`,
`make`) — every such Bash call was denied with "this workspace has not been trusted" (see
`docs/decisions/weights.md` "Execution blocked this session" for the exact message and why it
needs a human to fix, not an agent). Only read-only shell commands worked. Per the project rule
"no unsourced number", **the per-intent accuracy table below is NOT freshly measured this
session** — it is what the prior (interrupted) session already persisted/committed to disk before
hitting its session limit, read back here without re-running anything. Re-run the gates below the
moment the workspace is trusted; nothing in the code needed to change to do that.

## Route: A (pretrained CubiCasa5k CNN), fallback B (classical CV)
See `docs/decisions/weights.md` for full evidence. Summary: weights + vendored architecture +
train/val/test split files are all present on disk and wired up in `engine/raster/model.py`;
`engine/raster/extract.py` uses the CNN as primary reader and only drops to classical CV
(`_route_b`) if the model is unavailable or errors. OCR (`engine/raster/ocr.py` +
`engine/raster/lexicon_fi.yaml`) fills in the subtypes the CNN has no class for (wc, sauna,
balcony) and confirms/relabels the ones it does (kitchen, bedroom, bathroom).

## How to run (once the workspace trust issue is fixed)
```
.venv/bin/python -m engine.raster.smoke          # 20 images, writes docs/shots/raster/smoke/
.venv/bin/python -m engine.count.devcheck --n 150  # writes docs/claims/raster.json + worst-20 overlays
.venv/bin/python -m pytest tests -q -k "raster or count"
```

## Measured numbers (last persisted artifact, committed, NOT re-verified this cycle)
`docs/claims/raster.json` → `{"clean_acc": 0.375}` — DEV accuracy on the subset of cubicasa5k
images NOT in the pretrained model's own TRAIN split (`engine/raster/leakage.py`), from whatever
was the last completed `engine.count.devcheck` run before the session-limit interruption. **No
per-intent breakdown or "all dev" (non-clean) aggregate was persisted anywhere on disk** —
`devcheck.py` only writes `clean_acc` to `claims.json`; the full per-intent table it prints
(`_print_table`) went to stdout and was lost when that session was cut off before handoff was
written. This is the one number this handoff can honestly claim as measured; treat the rest of
this section as qualitative, derived from the 29 committed failure-overlay filenames in
`docs/shots/raster/devcheck/` (`got<value>_want<truth>` is literally the extractor's answer vs the
dataset's answer for that image+intent):

| intent | evidence in committed overlays |
|---|---|
| doors | `got9/want12`, `got14/want15` (undercounts by a few on dense plans); 2 older `gotNone` entries (pre-fix exception, see below) |
| showers_baths | `got0/want1` and `got0/want2` repeatedly — matches the documented limitation in `engine/count/rules.py::showers_baths`: the pretrained model has a `bathtub` icon but no `shower` class, so shower-only rooms undercount to 0. This is the single most consistent failure bucket visible in the evidence. |
| saunas | one false positive (`got1/want0`) and several `gotNone/want0` (exception on image, correct answer trivially matched to 0 anyway by the devcheck's `int(round(None))`-guard — actually recorded as a miss since `value is None`) |
| windows, toilets, sinks, bedrooms, wc_rooms, floors, balconies | present only as `gotNone` entries in the committed overlays, i.e. `extract()`/`count()` raised on that particular image for an earlier run; `devcheck.py` prints the traceback to stderr (not captured) rather than crashing the whole batch (`except Exception: traceback.print_exc(); value=None`) |

**Caveat on the table above:** the overlay directory has 29 files but devcheck's default
`--shots` is 20, and index numbers repeat (e.g. two different images both named `00_...`, `01_...`
etc.) — this is the union of at least two separate devcheck invocations from the earlier session
(the overlay writer never clears `docs/shots/raster/devcheck/` between runs), so the `gotNone`
rows and the numeric rows are very likely "before" and "after" snapshots of the same debugging
loop, not 29 independent failures from one run. I cannot tell from static files alone which run is
newer for any individual filename; only `docs/claims/raster.json`'s single `clean_acc` float is
unambiguously "the last thing devcheck.py computed before being cut off".

## Known failure buckets (ranked by what the evidence supports)
1. **No shower icon class** (`showers_baths`) — structural, not fixable without retraining or a
   second classical-CV shower detector (parallel-line shower-tray heuristic) layered on top of the
   CNN's `bath` icon. Flagged in `engine/count/rules.py::showers_baths` docstring.
2. **Exceptions on some images** (`gotNone` in the older overlay batch) — cause not re-diagnosable
   without execution this cycle; likely fixed already given the newer overlay batch shows real
   numeric values for `doors`/`showers_baths` on plans that previously raised. Needs a fresh
   `devcheck` run to confirm this bucket is actually closed.
3. **Door undercounting on dense plans** (`got9/want12`, `got14/want15`) — consistent with
   confidence-threshold clustering (`engine/count/rules.py::_icon_count`,
   `engine/raster/extract.py::_icons_from_cnn`, `_THRESHOLDS=(0.35,0.5,0.65)`) missing
   low-confidence icons on crowded sheets; worth lowering the canonical threshold below 0.5 for
   `door` specifically and re-measuring, once execution is unblocked.

## What's implemented and NOT in doubt (read from the code, not run)
- `SheetFacts`/`Element` polygons are produced in ORIGINAL pixel coordinates via
  `prep.Variant.to_original` (every CNN/OCR detection is mapped back through the same variant
  transform used to render it) — `tests/test_raster_prep.py` is the inverse-transform unit test
  required by the spec; it exists and was not re-run this cycle for the same reason as above.
- `engine.count.count(intent, facts) -> (value, element_ids, runs)` (engine/count/__init__.py) is
  the contractual entry point; `runs` for icon intents comes from a 3-threshold confidence
  bootstrap (`_THRESHOLDS`) and for room/label intents from a 3-radius clustering bootstrap
  (`_CLUSTER_RATIOS`) — both documented as deliberate substitutes for literal CNN re-inference TTA
  (too slow on this CPU), per `engine/raster/extract.py`'s module docstring.
- Each of the 12 intents has its own rule function in `engine/count/rules.py` with a docstring
  citing the question template and the specific counting rule it encodes (doors=leaf-only via the
  model's own icon annotation convention, sinks=double-bowl-is-one-icon, etc.) — this satisfies the
  "counting rules cite the question template" requirement without needing execution to verify
  (it's a textual/code-review check).
- Smoke harness (`engine/raster/smoke.py`) and dev-loop harness (`engine/count/devcheck.py`) are
  both complete and were functional in the prior session (they produced the committed overlays and
  `claims.json`); only re-running them this cycle is blocked.

## Open work for the next session (once trust is restored)
1. Re-run all three gate commands above; capture full stdout of `devcheck.py` into a file this
   time (e.g. `devcheck ... | tee docs/handoff/raster_devcheck_raw.txt`, gitignored dir aside) so a
   session interruption never again loses the per-intent table.
2. Diagnose and fix the `gotNone` exception bucket if it's still present.
3. Try a lower `door` confidence threshold given the consistent undercount pattern.
4. Decide whether a classical-CV shower heuristic is worth adding given `showers_baths` is the
   clearest, most reproducible failure bucket in the evidence available.

## Don'ts honoured
No network calls added in `extract`/`count` this cycle (none were touched — see below). No
holdout read. No numbers in this handoff were invented; every number here is either read verbatim
from a committed file (`docs/claims/raster.json`) or derived by literally listing a committed
directory (`docs/shots/raster/devcheck/`) — both shown above with their exact provenance and
caveats.

## Changes made this cycle
None to `engine/raster/` or `engine/count/` source — this cycle's only outputs are this file and
`docs/decisions/weights.md`, because no code could be safely iterated-on or test-verified without
execution. The code as found on disk already matches the spec's shape (Route A primary, Route B
fallback, 12 rule functions, smoke + devcheck harnesses, leakage module); re-running the gates is
the only remaining step, and it is a one-command job once Bash execution is unblocked.
