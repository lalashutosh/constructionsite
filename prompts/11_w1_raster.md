# W1 · RASTER EXTRACTOR (agent: raster-extractor, branch w1/raster, budget ~90 min)

Mission: read small raster floor plans (cubicasa5k: 4,270 of 7,990 questions, PNG, 240-490 px, Finnish labels, often rotated) into `SheetFacts` with polygons in ORIGINAL pixel coordinates, and answer the 12 cubicasa count intents as accurately as possible. Every count must point at the elements that produced it.

Read first: `AGENTS.md`, `contracts/proof.py` (SheetFacts, Element, Voter), `docs/recon.md` (cubicasa section: templates and answer ranges). View at most 6 sample images, downscaled to <= 1000 px wide.

You own: `engine/raster/`, `engine/count/`, `weights/` (untracked), `docs/decisions/weights.md`. Nothing else.

The 12 intents (the answer key counts exactly what each question says):
`windows, floors, toilets (WC seats), sinks (double bowl = 1), showers_baths (together), doors (door leaf present; open doorways do NOT count), saunas, kitchens (incl. kitchenette/open), bedrooms (MH), wc_rooms (separate WC rooms), bathrooms (KH/KPH/PH/PESUH/SH, not WC rooms), balconies (parveke, incl. glazed)`.
Evaluator builds the official classifier in parallel; until it lands use your own 12-keyword English map in `engine/count/kw.py` and switch to `evalkit.intents.classify` after the merge.

## Step 0 · weights probe (hard timebox: 10 minutes)
The cubicasa5k images come from the public CubiCasa5k dataset (Kalervo et al. 2019, CC BY-NC-SA 4.0 per the dataset README). Its authors published a pretrained multi-task model (rooms + icons: window, door, closet, electrical appliance, toilet, sink, sauna bench, fire place, bathtub, chimney).
1. WebSearch "CubiCasa5k pretrained weights model_best_val_loss_var.pkl"; read the official repo README for the download link (Google Drive). Try `pip install gdown` in the venv and download into `weights/`. Install CPU torch: `.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`.
2. If the model loads and runs on a 490 px image in < 2 s on CPU: ROUTE A. Otherwise ROUTE B (classical CV + OCR). Write the decision, the evidence and the licence note to `docs/decisions/weights.md`.
3. **Leakage check (mandatory if route A):** CubiCasa ships `train.txt / val.txt / test.txt` with folder ids such as `/high_quality_architectural/6044/`. Map each dataset image name (`colorful-11397.png`, `high_quality-1647.png`, ...) to its id and compute the share of dev images that are in the model's TRAIN list. From now on report accuracy twice: all dev images, and only those NOT in the model's train list. The honest number is the second one. If the mapping cannot be established, say so in the handoff and report only classical-CV numbers as "clean".

## Step 1 · preprocessing (`engine/raster/prep.py`)
Load RGB, composite alpha on white, ensure the long side is at least 800 px (Lanczos), keep a 3x3 transform matrix back to original pixels for every variant. Build the TTA set: scales {1.0, 1.5 (if small)} x rotations {0, 90, 180, 270} x flip {no, yes} (cap at 8 variants for speed). Unit-test that mapping a polygon back from every variant lands within 1 px of the original (use a synthetic marker image).

## Step 2 · extraction (`engine/raster/extract.py`)
Implement `extract(path, *, allow_siblings=True) -> SheetFacts` (the Extractor protocol). Route A: run the model on each variant, un-transform outputs, merge by non-maximum suppression, build elements: `door` (leaf with swing), `door_open` (opening without leaf), `window`, `toilet`, `sink`, `bath`, `shower`, `sauna_bench`, `fireplace`, `room` (subtype from model class + OCR label), `wall`. Route B: wall mask by dark/saturated pixel threshold + morphology; rooms by flood-fill of the wall-free mask; doors by quarter-circle arc detection plus a gap in the wall; windows by thin parallel-line triples inside walls; fixtures by multi-scale, multi-rotation template matching with templates cropped from DEV images (document which images). OCR: `pytesseract` with `-l fin+eng --psm 11` on upscaled grayscale at 4 rotations; map tokens through `engine/raster/lexicon_fi.yaml` (MH bedroom, K/KEITT kitchen, OH living, KH/KPH/PH/PESUH/SH bathroom, WC, S/SAUNA, VAR storage, ET entry, PARVEKE balcony, ...). OCR and lexicon are HYPOTHESES: confirm every mapping against dev answers before trusting it.
Every element gets `conf` and a polygon in original pixels. Cache `SheetFacts` JSON under `cache/raster/<sha256>.json`.

## Step 3 · counting (`engine/count/`)
`count(intent, facts) -> (value, element_ids, runs)` where `runs` is the list of per-TTA-variant counts (this becomes `Voter.runs`; its spread is the uncertainty). Rules go in `engine/count/rules.py`, one function per intent, each with a docstring that quotes the question template and states the rule (e.g. "doors: leaf present only"). `floors`: number of disjoint plan views (connected content blobs of comparable size), default 1. `balconies/saunas/kitchens/bedrooms/bathrooms/wc_rooms`: room instances by class and OCR evidence; two labels in one room count once.

## Step 4 · dev loop (`engine/count/devcheck.py`)
Reads `questions.jsonl`, takes the DEV split by the same hash rule (`int(sha1(path).hexdigest(),16) % 5 != 0`), English cubicasa questions only, runs extract+count on a random 150 images (seed 7), prints exact-match accuracy per intent next to the per-intent median baseline, and writes the worst 20 failures with overlay PNGs to `docs/shots/raster/`. Iterate by failure bucket (rotated, black-wall, colour-wall, scanned, tiny). View overlays downscaled. After each fix re-run devcheck. Stop when two consecutive iterations gain < 1 point overall or when 90 minutes are used.

## Gates
```
.venv/bin/python -m engine.raster.smoke     # 20 images, < 2 s each, writes overlays, exit 0
.venv/bin/python -m engine.count.devcheck --n 150
.venv/bin/python -m pytest tests -q -k "raster or count"
```
Write `docs/claims/raster.json` as `{"clean_acc": <dev accuracy on images NOT in the weights' train list, or null>}`.
Handoff must contain the per-intent accuracy table (all dev, and clean subset if route A), seconds per image, the route chosen, and the top three failure buckets with counts.

## Don'ts
Never import `engine.skeptic` or read its output (independence). No network calls inside `extract`/`count`. No tuning on holdout (never run it). Do not hard-code answers or image names. If an intent cannot beat the prior median, say so and leave it tier amber rather than faking it.

## Handoff
`docs/handoff/raster.md`: route, how to run, table, speed, failure buckets, licence/credit strings for the weights and dataset. Small commits `raster: <what>`.
