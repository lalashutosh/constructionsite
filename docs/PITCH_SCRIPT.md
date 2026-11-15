# Plumb — the 2-minute pitch (video + deck)

Hard limit: 2:00 (Junction is strict). Target 1:55. Judging, 25% each: accuracy · reasoning a human can verify ·
creativity · low inference cost. The video is one continuous app demo with the voiceover on top; the deck
(`docs/pitch/Plumb_pitch_deck.pdf`) follows the same story with real outputs from the app.

---

## 1. The chatbot comparison (do this first, 5 minutes)

1. Open ChatGPT (or Claude). Upload `us_daf_dorm_sd_drawings_april_2026_p003.png` (the dorm sheet).
2. Ask exactly: **"How many doors are on this floor plan? Give one number."**
3. Screenshot the question and the answer. Save it as `docs/pitch/chatbot.png`.
4. Also screen-record it (5 s is enough) as clip **V1**.
5. Use it only if its number is wrong (Plumb finds 139, every door boxed). If it happens to be close, ask the
   follow-up "Show me where each door is." and record that it can't. Say the number it actually gave.

Then run `.venv/bin/python docs/pitch/make_slides.py`: slide 3 picks up the screenshot automatically.

## 2. Recording the app (smooth, 60 fps)

- OBS Studio: Settings → Video: 1920x1080 base and output, **60 FPS**; Output: recording quality "Indistinguishable",
  format MKV or MP4. Or QuickTime screen recording on a Retina Mac (60 fps by default).
- Browser full screen (Cmd+Ctrl+F), zoom 100%, dark theme, notifications off, cursor visible.
- Engine running: `LLM_PROVIDER=verda .venv/bin/python -m uvicorn api.main:app --port 8001`; app on
  http://localhost:5173. Open every drawing once BEFORE recording so its deep read is cached (instant on camera).
- Move the mouse slowly. Pause 1 s after each answer appears. One clip per row below; I cut and speed-ramp them.

| Clip | Drawing | Do | You should see |
|---|---|---|---|
| V2 | `data/cubicasa5k/colorful-2002.png` | Hover each door; ask "How many doors?" | **6 doors** |
| V3 | dorm | Open it; slow zoom out over the whole sheet | 10,200 px of detail |
| V4 | dorm | Ask "How many doors?" → **See proof** | **139**, per wing, every door boxed |
| V5 | dorm | Ask "Are there more doors or toilets and sinks?" | **"Doors: 139 vs toilets + sinks: 96 (48 + 48)"** |
| V6 | `colorful-2002.png` | Ask "Montako makuuhuonetta asunnossa on?", then "¿Cuántos dormitorios hay?" | **2 bedrooms** both, $0.0000 |
| V7 | dorm | Scale badge top right → **Where?** | pins on the scale note, bar, dimensions |
| V8 | `data/cubicasa5k/high_quality_architectural-594.png` (no scale) | **Set real size**: click both ends of one door, type 0.9 m | every room size updates |
| V9 | dorm | Octagon: tap 3D, drag to orbit; Layers: toggle Furniture, Piping, Electrical | the floor in 3D, layer by layer |
| V10 | dorm | "What's on this sheet": click Beds, then Staircases | every bed / stair lights up |
| V11 | dorm | Build plan tab: scroll tiles → finishes map → Plumbing/Electrical maps | concrete, hinges, pipe 2,023 m, cable 418 m |
| V12 | piping `us_aw_078-24-28_march_2020_p096.png` | Ask "How many check valves are there?" | **5** — "TYP. OF 5", only 4 tags legible |
| V13 | any answer | Hold on "0 tokens · $0.0000" | the cost line |
| V14 | (spare) a portrait photo; the `Sports_Complex` folder | Upload; ask "How many doors?" / folder upload | "not a floor plan" / sorted in ~30 s |

## 3. The voiceover (read straight through, ~1:50)

[V2] Here's a floor plan. How many doors? Six. Easy.

[V3] Now this one: an Air Force dormitory, ten thousand pixels wide. You can't count this by eye, and nobody
should have to.

[V1 / slide 3] We asked ChatGPT. It answered with one confident number, and no way to check it. [say its number]
Plumb says one hundred and thirty-nine, and it boxes every single door on the drawing.

[V4, V5, V6 · REASONING] That's Plumb: ask in plain language, in any language, and it answers with its working shown.
More doors, or toilets and sinks? A hundred and thirty-nine against ninety-six, with every one it counted on
screen, and a tag saying measured, printed or estimated. Checkable in seconds.

[V7, V8 · CREATIVITY] Every size starts with the scale, and Plumb reads it off the sheet itself: the note, the
scale bar, the dimension lines. No scale on the drawing? Measure any one thing you know, a door or a wall, and
every dimension in the building follows.

[V9, V10, V11] Then it builds the floor in 3D, layer by layer like a body: walls, furniture, pipes and wiring. It
counts every bed, chair and staircase. And it turns the drawing into a build plan: concrete, doors and hinges,
finishes room by room, and pipe and cable estimated with European engineering rules.

[V12 · ACCURACY] On hard sheets it stays honest: this piping plan says five check valves, only four labels are
legible, and Plumb says so. On Stoa's full-size sheets: twenty-four of twenty-five hard questions right.

[V13 · LOW COST] And almost none of this is an LLM. It's computer vision and fixed engineering formulas, running on
this laptop. Most answers cost zero tokens; reading this whole sheet costs about ten cents, once.

[slide 13] The model only names things; the code measures. So next year's better model makes Plumb better, not obsolete. Plumb: blueprints that show their work.

---

## Q&A (if asked)
- **Accuracy?** CubiCasa dataset plans 81.5% exact counts (n = 400); Swiss dwelling counts 91.3% (n = 206);
  24/25 harder questions on Stoa's three full-size sheets; scale within 2% on all three (docs/stress-report-r9.md).
- **What does the LLM do?** Names each symbol type once, classifies new questions, reviews a scan. It never outputs
  a count or a measurement. Swap in Gemini or Claude; the numbers still come from code.
- **Cost?** Most answers 0 tokens. Deep read of the 67-megapixel dorm sheet about $0.10, cached per drawing.
- **Limits?** Some symbol names; doors on piping sheets are partial; wing lengths aren't answered yet.

DO NOT SAY: "employing people for this is stupid"; any accuracy number not in the reports; "certified to EN
standards" (estimates); "counts every symbol perfectly".
