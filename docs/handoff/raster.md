# Handoff: raster-extractor (engine/raster/, engine/count/)

## Status
Route A (pretrained CubiCasa5k CNN, CPU, no network) works; smoke passes (20 images, route A, overlays written;
logs/raster_smoke.log). Counts via `engine.count.count(intent, facts) -> (value, element_ids, runs)`.
Weights decision: docs/decisions/weights.md. Fallback route B = classical CV (engine/raster/prep.py + extract.py).

## How to run
- `python -m engine.raster.smoke`
- `python -m engine.count.devcheck --n 150` (writes docs/claims/raster.json and failure overlays in docs/shots/raster/devcheck/)
  (times in the log are near 0 s because extraction is cached by sha256; cold run is ~1-5 s/image.)

## Dev-split accuracy (n=150, seed 7, English cubicasa5k dev questions; HOLDOUT never touched)
CAVEAT: the two fixes below were chosen after looking at these same 150 rows, so the "after" numbers are
OPTIMISTIC (in-sample). Only 27/150 images are outside the model's own TRAIN split ("clean"); the pretrained
model has seen the rest, so ALL-image numbers are inflated for detector intents too.

| intent | n | before | after | prior (dev median) |
|---|---|---|---|---|
| windows | 15 | 40.0 | 40.0 | 6.7 |
| floors | 16 | 87.5 | 87.5 | 81.2 |
| toilets | 17 | 70.6 | 70.6 | 64.7 |
| sinks | 13 | 46.2 | 46.2 | 53.8 |
| showers_baths | 17 | 0.0 | 58.8 | 58.8 |
| doors | 14 | 57.1 | 57.1 | 0.0 |
| saunas | 13 | 61.5 | 61.5 | 38.5 |
| kitchens | 10 | 50.0 | 80.0 | 80.0 |
| bedrooms | 15 | 33.3 | 33.3 | 20.0 |
| wc_rooms | 10 | 60.0 | 60.0 | 50.0 |
| bathrooms | 6 | 16.7 | 83.3 | 83.3 |
| balconies | 4 | 100.0 | 100.0 | 75.0 |
| TOTAL | 150 | 50.0 | 61.3 | 47.3 |
| CLEAN subset | 27 | 44.4 | 63.0 | n/a |

## Fixes made this cycle (engine/count/rules.py)
1. showers_baths was 0%: the model has a `bathtub` icon but no shower class, and the icon fires on ~10% of
   drawings, while truth is 1 on ~85%. Not a class-id bug. With zero bath icons the rule now returns the
   dev-median prior 1.
2. kitchens and bathrooms: the CNN over-segments rooms (2-3 for truth 1). When the detector count is not 1,
   the answer is the dev-median prior 1.
Both fallbacks are recorded in `facts.extras["count_defaults"][intent] = {value, reason}`. The proof builder
(integrator) MUST read this key and emit Tag.defaulted (not drawn) for those numbers. After these fixes the
three intents equal the prior; they carry no detector evidence when the fallback fires.

## Known failure buckets
- bedrooms (33%): CNN `bedroom` class over-segments, and truth is often 0 where we say 1-4 (likely rooms
  labelled differently in the key). Needs a rule learned from more answered questions.
- sinks (46%), windows (40%), doors (57%, over-counts by 1-3 on busy plans), toilets (71%).
- saunas/wc_rooms/balconies depend on OCR labels only (small n for balconies).
- Overlay evidence for the worst failures: docs/shots/raster/devcheck/.
- TTA is a confidence-threshold / cluster-radius bootstrap (stored in `Voter.runs`), not literal
  scale x rotation x flip, because that exceeds 10 s/image on this CPU.

## Open work
- Fix bedrooms and sinks by failure bucket with the overlays; consider a score-weighted merge of split rooms.
- Evaluate on a larger clean subset; the 18% clean share limits what we can claim.
- Shower-only bathrooms need a symbol detector (no shower class in the pretrained head).
