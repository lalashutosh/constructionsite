# Plumb architecture

Plumb is a geometry and verification layer: it turns a drawing into numbers with a receipt (what was measured,
what was printed, what was assumed) and shows every number on the drawing. This page follows one question through
the system and names the module responsible at each step.

## The one interface

`contracts/proof.py` (pydantic v2) is the only type that crosses module boundaries:

- **ProofObject**: `value`, `unit`, `interval`, `answer_text` (one sentence built by code, no LLM), `evidence`
  (the elements behind the answer, with polygons in the drawing's own coordinates), `voters` (each voter's value,
  element ids and per-run values), `tier` (green / amber / grey) and `reliability` (from a calibrator trained on DEV
  answers), `scale` (every scale anchor with its tag and error), `assumptions` (each with a tag `drawn | specified |
  chosen | defaulted | open`, a `source` and `depends_on`), `decisions_open`, `query_spec` (exactly what code
  computed when the planner was used), `refusal`, `provenance` (`resolved_from`, `credit`) and `cost`
  (`llm_calls`, `planner_calls`, tokens, USD, ms).
- **SheetFacts**: the extracted drawing: walls, rooms, openings, fixtures, symbols, scale, views.

The API returns ProofObjects, and the web UI renders them. No module invents another format.

## A question, step by step

1. **Cache** (`engine/cache.py`): everything is keyed by the file's SHA-256 and a reader version, so re-asking costs
   nothing and results are deterministic (seed 7).
2. **Triage** (`engine/triage/`, `engine/scancheck.py`): floor plan, section, elevation, site plan, photo or
   illegible. Non-plans are refused in product mode with the reason, and get a best guess in benchmark mode. Several
   views on one sheet are split; multiple floors are recognised only from printed floor names.
3. **Siblings** (`engine/siblings.py`): "same name, different extension = same drawing". If a more exact format
   exists (DXF or IFC next to a PDF or PNG), it is used and disclosed in `provenance.resolved_from`. Reports always
   give both numbers.
4. **Extract**: exact formats are parsed directly (`engine/vector/`: DXF via ezdxf, IFC via IfcOpenShell, vector
   PDF via PyMuPDF). Scans go through `engine/raster/` (CubiCasa5k CNN, OCR, stairs, door leaves). Big construction
   sheets go through `engine/bigsheet.py` and `engine/outline.py` (title block, border, legends and dimension chains
   excluded; the building outline is read from paired wall lines or from the screened background layer under
   piping).
5. **Scale** (`engine/scale/sheet_scale.py`, `engine/scale/anchors.py`): candidates from scale notes ("1/4" = 1'-0"",
   "1:50"), graphic scale bars (RANSAC on ticks), dimension strings measured against their lines, and paper sizes
   (including half-size prints). A consensus family wins and outliers are listed as REJECTED. A length the user
   measures overrides everything. If the scale rests only on an assumed door width, sizes are flagged as relative.
6. **Deep read** (`engine/symbols.py`), for detailed sheets and every upload: repeated symbols are discovered by
   clustering strokes, counted by normalised cross-correlation with shape verification and a median-exemplar check,
   parts of bigger symbols are dropped, door swings are fitted as arcs, and stair flights are found from tread
   rhythm. Two vision-model reviewers name each symbol type once (cached by contact-sheet hash). Counts are grouped
   per zone or wing.
7. **Printed facts** (`engine/sheet_lookup.py`, `engine/sheet_findings.py`): what the sheet prints (equipment tags
   such as CV-1…CV-4, "TYP. OF 5", schedules, area tables, notes) is read back with the exact text as the receipt.
   ISA-5.1 tag letters and sheet legends explain abbreviations. Printed facts win over detected ones and the
   disagreement is reported.
8. **Route** (`engine/router.py`, `engine/router_lexicon.yaml`): fixed intents first (cheapest), with a multilingual
   lexicon (en, fi, sv, de, fr, es, nl, et). Questions about a selected element go to `engine/selected.py`. Unmatched
   questions go to the **query engine** (`engine/query/`): an LLM, if enabled, drafts a `query_spec`, which is
   validated and then executed by code over SheetFacts (filters, areas, lengths, perimeters with shapely).
9. **Vote and tier** (`engine/pipeline.py`, `engine/skeptic/`): every count has two independent voters (for example
   the CNN symbol detector and arc geometry, or a printed count and the tags that could be read). The tier comes from
   their agreement, calibrated on DEV answers; a model's self-reported confidence is never used.
10. **Quantities and plan** (`engine/takeoff/`, `engine/plan/`, `engine/layers.py`): areas, wall lengths, paint,
    flooring, doors and hinges, concrete; estimated services where the set has no MEP sheet (EN 806-3 loading
    units, EN 12056-2 waste flow Qww = K·√ΣDU, EN 12464-1 lumen method for lighting, socket counts per room),
    always tagged `defaulted` with the rule cited.

## Where the LLM is allowed

`LLM_PROVIDER=none | verda | featherless | gemini | anthropic` (default `none`). When enabled it does only these jobs:
classify each distinct question template once (cached), draft a `query_spec` for unmatched questions, name symbol
types in the deep read, and review a scan check. It never returns a value that becomes the answer. Every call is
counted in `Cost` (`engine/cost.py`), so the UI can show "0 tokens · $0.0000" or "2 LLM reviews · $0.0785".

## Service and UI

- `api/main.py` (FastAPI): `/api/ask`, `/api/geometry`, `/api/scale`, `/api/checklist`, `/api/building` (folders),
  `/api/upload` (starts the deep read in the background). Paths are resolved safely; traversal attempts return 400.
- `web/` (Vite, React, TypeScript, three.js): 2D/3D viewer with a view cube, zoom to cursor, body-like layer toggles,
  the "What's on this sheet" checklist (click a row to light up every copy), answers with **See proof**, scale badge
  with **Where?**, the measuring tool, and the Build plan tab.

## Evaluation

`evalkit/` scores the dataset questions as the challenge does (counts exact; area, length and volume within 2%) on a
deterministic split (`int(sha1(path), 16) % 5 == 0` → holdout, never tuned on). Reports go to
`evalkit/out/<run>/report.md` with confidence intervals, per-intent accuracy, tier calibration and cost. The
hand-written hard set (`evalkit/hard_questions.jsonl`) is scored separately and never used for tuning.
`scripts/stress_big.py` runs the harder questions on the full-size Stoa sheets (`docs/stress-report-r9.md`).
