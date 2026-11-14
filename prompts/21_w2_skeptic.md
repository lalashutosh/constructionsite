# W2 · SKEPTIC (agent: skeptic, branch w2/skeptic, budget ~90 min)

Mission: be the independent second opinion. The product claim "two independent voters per count" lives or dies here. You also decide when the system must refuse, and you learn from the answered questions how well to trust each answer.

Read first: `AGENTS.md`, `engine/registry.py`, `contracts/proof.py` (Voter, SheetFacts), `docs/recon.md` (cubicasa and swiss sections), `docs/handoff/evaluator.md`. You MAY read pixels and contract types. You may NOT import from `engine/raster` or read its cached outputs (`cache/raster/`): independence is the point.

<!-- gate:w1 -->
## Measured facts from gate w1 (commit 5bfd71c)
- DEV prior (per-intent median) per cubicasa intent, full DEV: windows 6.6 · doors 4.7 (mixed with swiss) · bedrooms 30.2 · sinks 54.8 · toilets 52.7 · saunas 57.4 · balconies 59.3 · wc_rooms 60.2 · showers_baths 72.9 · floors 80.4 · bathrooms 88.0 · kitchens 96.3. A voter below its intent's prior is not worth registering for that intent.
- Raster (the voter you must be independent of) on DEV150: windows 40 · doors 57 (over-counts by 1-3 on busy plans) · sinks 46 · bedrooms 33 · toilets 71 · showers_baths/kitchens/bathrooms = prior fallback (no detector evidence; the CNN has NO shower class and over-segments rooms).
- Priority order for your voters (where a second opinion moves the score most): 1) `doors_arc` and `windows_lines` (largest buckets, n=384/488, prior < 7%), 2) `fixtures_template` for shower/bath and sink (raster has no shower detector; sinks are below prior), 3) `rooms_fixture_logic` for bathrooms/kitchens/bedrooms. `floors_ocr` last (prior already 80%).
- Only 27/150 (18%) of raster's DEV150 images are outside the pretrained CNN's train split (docs/handoff/raster.md); report your voter accuracy on all DEV AND on that clean subset if you can get the list (`engine/raster/leakage.py` is a file you may read, not import).
- Triage: there are no non-plan folders confirmed in the preview set yet; check `ls $DATASET_ROOT/data` first and say so in the handoff if none exist (then use small/odd cubicasa images as the hard negatives).
- Calibration inputs today are prior/stub runs only (all amber); train the script, but expect real training after the W2 integration run (prompts/25 step 5).
- Skip if short on time: stacker (Step 3.2). Keep triage + doors_arc + windows_lines + fixtures_template.

You own: `engine/skeptic/`, `engine/triage/`, `tests/test_skeptic*.py`. Expose everything through `engine/skeptic/plugin.py::register()`.

## Step 1 · independent voters (`engine/skeptic/voters/`)
Register with `registry.register_voter(name, fn, kinds=("count",))`. Each voter takes `Ctx`, reads the image itself, and returns `VoterResult(Voter(name, value, element_ids, runs, note), evidence=[Element...])` with polygons in ORIGINAL pixels.
- `doors_arc`: quarter-circle swing arcs by Hough circles/contour fitting + a gap in the wall line next to it; open doorways (gap without arc or leaf) are NOT counted (answer key rule).
- `windows_lines`: thin parallel line pairs/triples embedded in the wall mask, length filtered by wall thickness.
- `fixtures_template`: multi-scale, multi-rotation normalised cross-correlation for toilet, sink, bathtub/shower. Crop templates from DEV images only (log which ones in `docs/handoff/skeptic.md`).
- `rooms_fixture_logic`: room-type counts from what is INSIDE each flood-filled room, not from OCR: bathroom = contains bath or shower; wc_room = contains toilet and no bath; kitchen = sink plus cooker symbol; sauna = bench pattern or the label; balcony = adjacent outdoor region with railing lines.
- `rooms_ocr`: OCR-only counting of room labels (pytesseract fin+eng, 4 rotations, your own lexicon file `engine/skeptic/lexicon.yaml`) as a separate voter for the same room intents.
- `floors_ocr`: floor markers in text ("KERROS", "1. krs", "2nd floor") and number of disjoint plan blobs.
Voters must not look at each other. Where a voter is weak for an intent, say so in `Voter.note` and do not register it for that intent.

## Step 2 · triage (`engine/triage/`, `register_triage`)
Classify the sheet: floor_plan / elevation / section / site_plan / detail / multi_view / schedule / not_a_plan, plus legibility (too small below ~150 px, too blurry via Laplacian variance, no right-angle structure via Hough angle histogram, mostly photograph via colour entropy), plus language guess. Set `refuse` with a human reason ("this is an elevation: floor-plan questions do not apply", "image is 96 px wide: below the readable minimum"). Evaluate on every non-plan image you can find: `$DATASET_ROOT/data/*` folders other than cubicasa5k/swiss_dwellings/ifc_models/ifc_bench/opening_design (europeana, finna, habs ... if present) plus 100 random cubicasa images as negatives for false refusals. Report the confusion table. False refusals of real floor plans must be < 1%.

## Step 3 · calibration and stacker (`engine/skeptic/calibrate.py`, `stacker.py`)
Inputs: rows of `evalkit/out/<run>/results.jsonl` (needs the evaluator's output with `po`, `correct`, `split`). Use DEV rows only; use 5-fold cross-validation grouped by path hash for any model selection.
1. **Calibrator** (`register_calibrator`): features = [number of voters, voter disagreement (max-min), TTA spread, median element confidence, image width, intent id, sheet_type]; model = scikit-learn gradient boosting or logistic regression; output P(correct). Save a reliability table (10 bins) to `docs/handoff/skeptic.md`.
2. **Stacker** (`register_finalizer`): per intent, predict the residual `truth - median(voter values)` in {-2..+2} from the same features; adopt it for an intent ONLY if cross-validated accuracy improves by >= 1.0 point and the Wilson interval of the gain does not include 0. Log the adopted/rejected intents with numbers. Persist as `engine/skeptic/models/*.joblib` (small) with the git commit of the training data in a sidecar JSON.
3. Seeds fixed (7). Never touch HOLDOUT.
Until the W2 integration run exists, train from whatever `results.jsonl` the evaluator produced with the prior/stub engines; write the training script (`python -m engine.skeptic.train --run latest`) so it can be re-run after the merge.

## Gates
```
.venv/bin/python -m engine.skeptic.smoke            # 20 images, each voter runs, evidence polygons valid, < 3 s/image
.venv/bin/python -m engine.skeptic.devcheck --n 150  # per-voter accuracy per intent on DEV (own quick loop, reads questions.jsonl)
.venv/bin/python -m engine.triage.eval               # confusion table
.venv/bin/python -m pytest tests -q -k skeptic
```
Handoff must show: per-voter, per-intent DEV accuracy, the triage confusion table, and the calibrator's reliability table once trained. You never see the Counter's output, so agreement between voters is measured later by the integrator.

## Don'ts
No peeking at `engine/raster`. No network. No tuning on HOLDOUT. Do not call a voter "independent" if it shares a preprocessing function with another voter; if you reuse code, put the shared function in `engine/common/` and say so in the handoff.

## Handoff
`docs/handoff/skeptic.md`. Commits `skeptic: <what>`.
