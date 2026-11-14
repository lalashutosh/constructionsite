# Plumb: where we are

Plain-language status. Updated after every milestone. Branch `p2-finish` on GitHub (`main` untouched).
Last update: **15:20**

## 15:20 update: redesign + build plan + harder questions

**Done in the engine (tested, committed):**
- **Building type → checklist → build order** (`GET /api/plan`). Example, swiss plan: *Apartment building, high confidence (7 apartment outlines, 7 kitchens)* → 78 door sets, 63 windows, 6 toilets, 7 baths, 7 kitchens from the drawing; paint, boards, lights, sockets, tiles, concrete and roof area from the chosen style (budget / standard / premium / nordic). Steps: site → foundation → slab → walls → roof → windows/doors → wiring/pipes → boards → finishes → fittings → handover. Data centres get a different list (raster floor, UPS, cooling) that asks for the IT load.
- **Harder questions** ("which room is largest", averages, "more windows than doors", "rooms with a window", "toilets and sinks in total"): an LLM drafts a query, code computes the answer. About $0.0003 and 2 s each. Swiss examples: largest room Pièce 1.01, kitchens 7, bathroom area 24.33 m², windows − doors = −15.
- Hard questions no longer get hijacked by simple matchers (e.g. "average room area" used to return the total).
- **3D model data** (`GET /api/geometry`): walls with room openings from the CNN on normal plans, stroke tracing on big archival scans (no fake walls in site plans).

**In progress:** the UI agent is rebuilding the screen: left rail (upload image/folder), 3D model centre (fixing the mirror bug, adding an overlay on/off toggle and floor slabs), questions bottom-left, Findings | Build plan top-right with a step-by-step build animation. The full accuracy run is also still going.

## What it does

You give it a floor plan and a question ("how many doors?", "net area of apartment B?"). It answers with:
- **a number**, plus **pins on the drawing** showing exactly which elements produced it
- **two or more independent "readers"** that each count on their own: **green** = they agree, **amber** = look here first
- **cost**: 0 tokens, $0. No LLM involved in the number.

## Run it yourself

```bash
.venv/bin/python -m uvicorn api.main:app --port 8000
```
```bash
cd web && VITE_API=live npm run dev
```
Open http://localhost:5173/?hook=0 and click the sample thumbnails along the top.

## What works (checked in the browser at 14:35)

| Drawing type | Share of dataset | Status |
|---|---|---|
| Swiss apartment plans (PDF/DXF) | 30% | ✅ **Works.** 99.3% correct on DEV. Example: 78 doors, green, 3 readers agree |
| IFC building models | 13% | ✅ **Works.** 96.6% correct on DEV (98.0% with the related-model option) |
| Door schedules (PDF) | 1% | 🟡 Door schedules work; the room-area schedule isn't parsed yet |
| CubiCasa scans (PNG, Finnish labels) | 53% | 🟡 **Working since 14:30.** Example: 5 doors (correct). Full accuracy run in progress |
| Text questions (ifc_bench) | 3% | ⏸️ Out of scope for now (free text, not in the score) |

Combined for swiss + IFC + schedules: **97.9% correct**. Every "green" answer was right (1,874 of 1,874).

## What was broken and is now fixed

1. **CubiCasa scans counted 0 doors and 0 windows.** The neural-net weights were never pushed to GitHub. Downloaded them from the authors' official link.
2. **OCR (tesseract) missing.** Installed a native version in minutes; Homebrew was compiling for hours.
3. **Exact drawings (DXF/IFC) were refused in the app.** Missing connector between the vector reader and the pipeline.
4. **"How many doors are there?" was answered as windows.** The question router now knows object words in 8 languages.
5. **A weak reader could override a strong one.** Weak readers now only affect green/amber, never the number.
6. **App crashed on some answers** (numpy number in the JSON).
7. **Old cached results hid the fix.** Stale fallback results are now ignored once the model is available.

## In progress right now

- Full accuracy run on all 6,287 DEV questions, with and without sibling files (~15 min). That gives the real headline number.
- A UI helper (subagent) polishing the demo screens (intro animation, reader duel, scale question, refusal screen).

## Known rough edges (finetuning list)

- CubiCasa window counts run high (example: 8 vs 6).
- Swiss plan: pins stack in one spot (DXF coordinates not mapped onto the rendered PDF yet).
- "triage: triage:" printed twice on the answer card.
- 12 swiss net-area questions are about 6% off (unnamed shaft rooms).

## Needs a human

- Check the 10 hand-written hard questions (`evalkit/hard_questions.jsonl`). It's the test set, so I don't grade it myself.
- The final holdout run and the submission.
