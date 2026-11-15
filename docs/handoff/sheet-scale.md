# sheet-scale handoff (scale agent)

## Files
engine/scale/sheet_text.py (words), sheet_scale.py (notes, bars, dimension lines, paper, consensus, confidence),
checks.py (Checks API logic), anchors.py (wired: `_sheet_anchors`, REJECTED anchors skipped), printed_dims.py (big-sheet gate),
api/main.py (GET /api/checks, POST /api/checks/answer), tests/test_sheet_scale.py (stress), tests/test_sheet_scale_parsers.py (unit),
cache/stress/truth.json.

## Why p13 gave 610.7 (fixed)
printed_dims._plain_anchor accepts plain 3-5 digit OCR numbers as mm and matches them to room outlines. On a 5100 px sheet the OCR'd
numbers (2015, 2000, 627: years, room numbers) matched wall extents by chance at one px/m (2 values within 3%), tagged `specified`. That cue is
only valid on small plans; printed_dims.anchor now returns None when the long side >= 2400 px. Scale for big sheets comes from sheet_scale.

## Method
Evidence: scale notes (imperial/metric/NTS), graphic bars (collinear labels, least squares), dimension strings matched to a ticked dimension
line (ink run next to the text, nearest ticks outside 1 text height; vertical via transpose), paper size (PDF exact; raster from aspect/dpi).
Small rasters (< 2200 px, nothing found) get a line-first fallback: ticked hairlines first, then OCR of the label crop at 4x/6x.
Consensus: group candidates within 5% (ppm); winner = highest score of distinct families. Confidence = 1 - prod(1 - q_family),
q: bar 0.65, note on PDF 0.70, note on raster at standard dpi 0.55 (guessed size 0.2), n agreeing dims 0.6+0.12(n-1), single dim 0.35, each scaled by
(0.8+0.2*OCR conf); a competing printed group halves it. Auto if >= 0.8 and no conflict, else one yes/no question.
Answers: cache/checks/<sha>.json; "no" + value (metres) re-scales the asked dimension; geometry cache for the sha is deleted.

## Known limits
- 768 px thumbnails: stoa2/stoa1 text is 3-4 px tall, nothing readable -> open question "scale:missing" (not a guess). stoa3 works only through line-first dims
  (OCR misreads digits, e.g. 133-10" read as 139-10"; consensus absorbs it, ~1% off).
- stoa3 truth is 3.71 px/m, NOT 1.853: the image is a half-size print (note 1"=40' on a 17 in sheet). Paper size from aspect is ambiguous (34x22 vs 17x11);
  that is why raster note+paper carries low weight and why dimension strings decide.
- Several views at different scales: all notes are candidates; the largest agreeing group wins (no per-view assignment yet). plan_view/sheet_type/units checks not implemented.
- Dense PDF with outlined fonts: OCR fallback on a 4200 px render.
- tests/test_count_rules_finetune.py::test_colorful_2002_has_two_bedrooms fails (count rules, not scale).
- cache/uploads/stoa3_check.png was created for an API smoke test (can be deleted).

## Run
`DATASET_ROOT=... .venv/bin/python -m pytest tests/test_sheet_scale.py tests/test_sheet_scale_parsers.py -q`; `PLUMB_NO_SCALE_CACHE=1` bypasses the sha caches.
