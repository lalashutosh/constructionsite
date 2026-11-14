# Decision: raster reader route (prompts/11_w1_raster.md Step 0)

## Route chosen: A (pretrained CubiCasa5k multi-task CNN)

Evidence on disk (read-only, verified this session without re-running the model):
- `weights/model_best_val_loss_var.pkl` present (CubiCasa5k authors' checkpoint).
- `weights/_src/CubiCasa5k-master/floortrans/...` vendored (not committed/shipped — gitignored,
  per the "weights/ untracked" ownership rule in `.claude/agents/raster-extractor.md`).
- `weights/_splits/{train,val,test}.txt` present (4199 / 399 / 399 folder ids) — this is what
  `engine/raster/leakage.py` maps dataset filenames against for the clean-subset check.
- `weights/_explore/{orig.png,rooms.npy,icons.npy,hq1000_small.png}` — saved tensors from a prior
  exploratory forward pass, i.e. the model was actually loaded and run on CPU at some point in the
  interrupted session, not just downloaded.
- `engine/raster/model.py` implements `available()`/`get_model()`/`infer()` against this checkpoint
  (44-channel output head: 12 room classes + 11 icon classes, per the authors' own `eval.py`
  layout, documented in the module docstring).
- `engine/raster/extract.py` calls `cc_model.infer()` as the primary path and only falls back to
  classical CV (`_route_b`) if `cc_model.available()` is false or the forward pass raises.

So Route A was reachable within the 10-minute timebox in the earlier (interrupted) session —
weights downloaded, torch CPU installed, architecture vendored, a forward pass run and its output
saved to `weights/_explore/`. **This session could not re-verify the "<2s/image on CPU" timing or
re-run the model**, because Bash execution of interpreters is blocked this cycle (see "Execution
blocked this session" below); the ~1.2-1.9s/image figure quoted in `engine/raster/extract.py`'s
module docstring is carried over from that earlier session's own comment and has NOT been
independently re-measured by this handoff.

## Licence / credit (must be shown wherever the drawing is shown)
- Dataset: CubiCasa5k (Kalervo, Ylioinas, Haikiö, Karhu, Kannala, 2019) — **CC BY-NC-SA 4.0**.
- `engine/raster/extract.py` bakes this into every `SheetFacts.provenance` as
  `CREDIT = "CubiCasa5k dataset (Kalervo, Ylioinas, Haikio, Karhu, Kannala, 2019), CC BY-NC-SA 4.0"`.
- Pretrained weights are the same authors' release, same licence — NonCommercial, ShareAlike.

## Leakage check (Step 0.3)
`engine/raster/leakage.py` maps `<category>-<id>.png` to the authors' own train/val/test split
folders and exposes `is_clean(path) -> bool | None` (True = not in TRAIN, i.e. the honest subset).
Mapping is established for images matching `(colorful|high_quality|high_quality_architectural)-
<digits>.png`, which is 100% of the cubicasa5k filenames seen so far — `model_split()` returns
`None` only for names that don't match this pattern at all (shouldn't occur for this dataset).
`docs/claims/raster.json` carries the resulting `clean_acc` (0.375 as last persisted — see
`docs/handoff/raster.md` for the caveat on how stale that number is).

## Route B (classical CV fallback)
Implemented in `engine/raster/extract.py::_route_b`: Otsu dark-pixel wall mask, flood-fill free
space for room blobs, OCR for subtype, no icon detection (windows/doors/fixtures always 0 on this
path). It only exists so `extract()` degrades instead of crashing if `weights/` is absent in some
other checkout — it is explicitly NOT the measured route for this handoff.

## Execution blocked this session (infrastructure, not a code decision)
Every Bash call that would actually run an interpreter (`python3 -c ...`, `python3 -m ...`,
`.venv/bin/python ...`, `pytest`, `make`, even `git --version`) was denied this cycle with:

> Ignoring 63 permissions.allow entries from .claude/settings.json: this workspace has not been
> trusted. Run Claude Code interactively here once and accept the trust dialog, or set
> projects["/home/ashutosh/Downloads/plumb"].hasTrustDialogAccepted: true in ~/.claude.json.

(seen verbatim in `logs/overnight/cycle-001.log` for the 12:36 headless cycle). Only a fixed set of
read-only/introspection commands (`ls`, `cat`, `find`, `grep`, `git log`, `git status`, `echo`,
`date`, `whoami`, `python3 --version`) got through; anything that executes project code did not,
regardless of the allow-list in `.claude/settings.json`. This is a one-time human action (accept
the trust dialog interactively, or edit the global `~/.claude.json` trust flag) — not something an
agent should or can do on its own (that file is global Claude Code trust/permission config, outside
this project, and changing it is exactly the kind of permission-settings change no agent may
self-authorize). Consequently the gate commands in `prompts/11_w1_raster.md` could not be re-run
this cycle; see `docs/handoff/raster.md` for exactly what is and isn't verified as a result.
