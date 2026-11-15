# Task: write engine/sheet_findings.py

Goal: the "Findings" panel for a BIG construction / commercial sheet (piping plan, foundation plan, architectural
floor plan with area tables) must list only what the sheet actually shows, each with the printed evidence. Never a
"0 bedrooms" style line. Pure text processing over OCR words; no network, no LLM, deterministic.

## Interface (exact)
```python
def findings(words: list[dict]) -> list[dict]:
    """words: OCR words [{"text": str, "box": [x0,y0,x1,y1], "conf": float, "angle": 0|90}] (original px).
    Returns findings ordered by usefulness, at most 12. Each finding:
      {"id": str, "kind": "area_table"|"count_table"|"equipment"|"pipe_sizes"|"slab_types"|"note",
       "title": str,               # short, e.g. "Floor areas printed on the sheet"
       "items": [{"label": str, "value": str, "boxes": [[x0,y0,x1,y1], ...]}],
       "text": str}                # one plain sentence summarising it, e.g. "West wing 7,009 SF; East wing 7,005 SF; ..."
    """
```
Use ONLY these helpers from `engine.sheet_lookup` (import them, do not copy): `rows(words)` -> text rows
`[{"text","box","angle","h","words"}]` (a row may span a wide table gap), `_numbers(text)` -> `[(raw, float, pos)]`,
`TAG_RX` (regex `^([A-Z]{1,4})-?(\d{1,3})([A-Z]?)$`), `_merge_confusable(found: dict[tag->word]) -> dict` (merges OCR
look-alike series such as FSL-2 into FSI-2), `AREA_UNIT` (regex for SF / SQ FT / M2 / m²). `engine.scale.sheet_scale.norm(text)`
normalises quotes/whitespace.

## Findings to produce (skip a kind entirely when nothing is found)
1. **area_table**: every row whose text contains an AREA_UNIT match and a number before it (e.g.
   "WEST WING DORMITORY = 6,095 SF", "TOTAL SECOND FLOOR 26,562 SF"). label = text before the number with a trailing
   "=" removed and title-cased ("West Wing Dormitory"); value = "6,095 SF". Keep printed order (top to bottom). Need >= 2 rows.
2. **count_table**: rows like "SECOND FLOOR = 48 DORMS" / "TOTAL = 144 DORMS": a number followed by a plural word
   (letters only, >= 3 chars) at the END of the row, and NOT followed by an area unit or an inch/foot mark.
   label = text before the number ("Second Floor"), value = "48 DORMS". Need >= 2 rows.
3. **equipment**: equipment tags matching TAG_RX on single words. Group by series letters (after `_merge_confusable`).
   Keep series with >= 3 distinct numbers, ignore series that are 1 letter long and the series "PS" is allowed.
   label = series (e.g. "FP"), value = f"{n} tags ({first}..{last})" where first/last are the sorted tags; boxes = all.
   Order by n descending. title "Tagged equipment".
4. **pipe_sizes**: single words like `8"`, `12"`, `2"`, `1-1/2"`, `16"` (inch mark, value 1/2..48). value = count of
   occurrences, label = size. Only if >= 8 such words in total and >= 2 distinct sizes. title "Pipe / duct sizes called out".
5. **slab_types**: rows/blocks containing `(\d{2,3})\s*SLAB` (thickness in mm or inches) - collect distinct texts
   (normalise whitespace). Also pick bar spec `D\d{1,2}\s*@\s*\d{2,3}` and elevation `EL\.?\s*=?\s*[\d.]+` from the same
   row or the next row directly below (within 1.8 row heights, overlapping x). label = "300 slab-on-grade", value =
   "D16 @ 300, top EL 9400" (whatever was found). Need >= 1.
6. **note**: rows that start with "SCALE" (value = rest of row) - at most one.

## Constraints
- Python 3.11, type hints, < 220 lines, no new dependencies, no I/O.
- Never raise on odd input: empty list in -> [] out.
- Do not edit any other file.

## Test it must pass: tests/test_sheet_findings.py (already written; read it).
