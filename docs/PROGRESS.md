# Progress report

Running log of what the lead session is doing, newest on top. Updated after every milestone.
Branch: `p2-finish` (off `main` at `a1b7642`). Nothing pushed. Detailed checklist: `docs/STATE.md`.

## Where we are (13:59)

| Phase | State |
|---|---|
| Setup on this Mac | done except **tesseract** (still compiling under Intel Homebrew, 9/38 deps) |
| P2 vector | **done**, handoff written |
| P2 skeptic | measured without OCR; voters weak, triage blocked on tesseract |
| P2 integrator | 3 real bugs found and fixed; 2 new API endpoints in progress |
| Integration pass + G2 gate | waiting on tesseract (cubicasa = 3,546 of 6,287 DEV questions needs OCR) |
| P3 demo, P4 pre-ship | not started |

**Blocker:** tesseract. Without it, raster extraction and the triage OCR veto can't run, so no cubicasa numbers yet.

## Measured numbers so far (DEV split, from commands run here)

- Tests: **144 passed**, 1 skipped (was 139 at start).
- Pipeline on vector sources (swiss + ifc + opening_design): **97.8%** [97.2, 98.3], n=2,646, every intent at or above prior.
- Vector devcheck with siblings: swiss **99.3%** (n=1,622), IFC **96.6%** (n=995; 98.0% with `--related`), opening_design 55.2% (n=29).
- Without siblings: swiss 66.8% (the PDF alone can't give areas or windows), IFC 96.0%.
- Router: leave-one-language-out **0.8085 → 0.8511**; paraphrases not in the dataset **6/16 → 23/24**.
- Skeptic voters on DEV150 (no OCR): doors_arc 12%, windows_lines 3%, toilets 18%, sinks 2%, all far below raster.
- Triage false refusals on cubicasa plans: 1.66% (gate needs < 1%). All 4 cases are OCR-veto misses, expected to clear once tesseract is in.

## Fixed so far

1. **Vector answers were never green, and refused in the API.** The pipeline wanted `engine.vector.plugin.extract()`, which didn't exist, so DXF/IFC fell through to the raster extractor. Added it, with per-file licence and credit read from the dataset's `LICENSE.md`.
2. **Router misrouted simple paraphrases.** "How many doors are there on this floor plan?" went to *windows*. Added a hand-written multilingual object-noun lexicon plus kind cues (area vs count). Dataset routing is unchanged.
3. **A weak voter could override a strong one.** With two voters, the 12%-accurate doors_arc won the tie against the 57%-accurate detector. Skeptic voters are now "second opinions": they affect the tier, never the number.
4. **Invariant contradicted the 2% rule.** Green areas agreeing within 0.03% were flagged as violations. Accepted the change request: non-count kinds agree within 2%.

## Decisions I made (you said I decide)

- Work on branch `p2-finish`, commit per milestone, never push.
- Left swiss unnamed-room net-area rule alone (a fix would gain 8 and break 18).
- `--related` IFC resolver stays opt-in and reported separately, as the spec requires.
- Hard set (`evalkit/hard_questions.jsonl`, 0/10 verified) stays a **human TODO**: it's the test set, so I don't check it myself.
- Records: `docs/decisions/second-opinion-voters.md`, `docs/decisions/contract-invariants-area-tolerance.md`.

## Next

1. Finish `/api/override` (Skeptic Duel "Is this a door?") and `/api/image` (real scan layer), with tests.
2. When tesseract lands: triage eval, skeptic devcheck with OCR, full DEV run with and without siblings, then the G2 gate.
3. P3 core demo beats.

## Things for you

- Four stray venv folders in the repo root (`#if/`, `nenv/`, `not/`, `created/`) came from `python3 -m venv .venv #if nenv not created`; zsh doesn't treat `#` as a comment. They're not committed. Safe to delete.
- `DATASET_ROOT` in `.env` now points at `~/Downloads/junction-dataset-preview` (only that line changed).
