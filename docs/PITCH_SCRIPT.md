# Plumb — pitch script and recording plan

Total: 3:00. Slides: `docs/pitch/slides/slide01.png` … `slide13.png` (also `docs/pitch/Plumb_pitch.pptx` with these
notes). Every answer quoted below was produced by the live engine (`docs/pitch/feature_check.md`, run before
writing this). If a number on screen differs while recording, say the number on screen.

Judging, 25% each: accuracy · reasoning a human can verify · creativity · low inference cost.

---

## PART A — what you record (screen clips, in this order)

Open the app at http://localhost:5173 (engine running: `LLM_PROVIDER=verda .venv/bin/python -m uvicorn
api.main:app --port 8001`). Record each clip separately; I cut them together.

| Clip | File (open with the project picker or upload) | Do this | You should see |
|---|---|---|---|
| C1 | `data/cubicasa5k/colorful-2002.png` | Point at each door with the cursor: 1, 2 … 6. Then ask "How many doors?" | **"There are 6 doors."** |
| C2 | dorm `us_daf_dorm_sd_drawings_april_2026_p003.png` | Upload it. Let the "Deep read in progress" panel show for 3 s. | animated progress, stages named |
| C3 | dorm | Click **Where?** next to the scale badge (top right). | pins on the note, bar, dimensions |
| C4 | dorm | Ask "How many doors?", then click **See proof**. | **139 doors**, per wing, every door boxed |
| C5 | dorm | In "What's on this sheet", click **Beds**, then **Chairs**. | every bed / chair lights up in 3D |
| C6 | dorm | Ask "Are there more doors or toilets and sinks?" | **"Doors: 139 vs toilets + sinks: 96 (48 + 48)."** |
| C7 | piping `us_aw_078-24-28_march_2020_p096.png` | Ask "How many valves are there?" then "How many check valves are there?" | **12**, every tag listed · **5** ("TYP. OF 5", 4 tags legible) |
| C8 | piping | Layers menu: switch Piping off and on; orbit with the octagon. | blue pipe runs, pink equipment posts |
| C9 | foundation `us_aw_078-24-33_p056.png` | Ask "What is the motor control center trench length?" | **"The sheet prints 'MOTOR CONTROL CENTER TRENCH LENGTH 4275'"** |
| C10 | dorm | Build plan tab: scroll the headline tiles, the finishes map, Plumbing, Electrical. | pipework ~2,023 m, cable ~418 m |
| C11 | dorm | Ask "How much waste water flow?" | **"About 7.99 l/s … EN 12056-2 …"** |
| C12 | `colorful-2002.png` | Ask the same question in 4 languages: "Montako makuuhuonetta asunnossa on?" · "Wie viele Schlafzimmer gibt es?" · "Combien de chambres y a-t-il ?" · "¿Cuántos dormitorios hay?" | **2 bedrooms** each time, $0.0000 |
| C13 | `data/cubicasa5k/colorful-13685.png` | Open it (tabs "1. KERROS · 2. KERROS"); ask "How many bedrooms are on the second floor?" | 2 floors; **"4 bedrooms on 2. KERROS"** |
| C14 | `data/cubicasa5k/high_quality_architectural-1967.png` (faint scan) | Ask "What is the scale of this drawing?" | scale from printed dimensions + printed room areas |
| C15 | any plan without a scale, e.g. `high_quality_architectural-594.png` | **Set real size**: click both ends of one door, type 0.9 m. | every size on the sheet updates |
| C16 | a portrait photo (any JPG of a person) | Upload it, ask "How many doors?" | **"…this does not look like a floor plan."** |
| C17 | the folder `data/opening_design/Sports_Complex` (27 files) | Folder upload. | sorted in ~30 s: floor plans vs schedules and other sheets |
| C18 | any new upload | Let the first-time tour run through 2 steps. | the walk-through |
| C19 | any answer | Hold on the cost line "0 tokens · $0.0000" for 2 s. | the cost line |

---

## PART B — the 3:00 voiceover (slide or clip on screen in brackets)

**0:00–0:12 · Hook** [C1, then hard cut to the dorm, C2]
"How many doors in this plan? One, two, three, four, five, six. Easy.
Now this one. Ten thousand pixels wide. And while you're at it: beds, hinges, pipe, cable, concrete, stairs."

**0:12–0:22 · The problem** [slide 3, then slide 4]
"That's a site engineer's afternoon. Every day. General AI models guess at drawings like this, and you can't
check a guess. So the question is: can a drawing answer, and show where?"

**0:22–0:35 · The idea** [slide 5]
"Plumb reads the sheet, counts by code, two independent ways, and shows the receipt. A model only names each
kind of symbol, once. It never produces a number."

**0:35–0:55 · Verify in seconds** [C3, C4, slide 6]
"The scale is read from the sheet itself, and it caught a trap: this is a half-size print. The printed note
would make everything twice too big; the scale bar and the dimensions outvote it. Then: a hundred and thirty-nine
doors, every one boxed on the drawing. Click. Check. Done."

**0:55–1:15 · The deep read** [C5, C6, slide 7]
"On a big sheet Plumb does a deep read, by itself, and tells you it will take a minute. Beds, chairs, sinks,
toilets, staircases. Click one: every copy lights up. And you can ask the questions you actually have:
more doors, or toilets and sinks? A hundred and thirty-nine against ninety-six."

**1:15–1:35 · Hard sheets, honest answers** [C7, C9, slide 8]
"A piping plan. Twelve valves, every tag listed. Check valves: five, because the sheet says 'typical of five',
and Plumb tells you only four tags were legible. It reads the notes too: trench length, forty-two seventy-five,
quoted from the sheet. No silent guesses."

**1:35–2:00 · From drawing to what to buy** [C10, C11, C8, slide 10]
"Then the drawing becomes a shopping list: concrete, doors and hinges, fixtures, finishes room by room. No
plumbing sheet? Pipework and wiring are estimated by European rules, and labelled as estimates. Every system is
its own layer, like a body."

**2:00–2:25 · Whatever you throw at it** [rapid montage, 3 s each: C12, C13, C14, C15, C16, C17, C18]
"Finnish, German, French, Spanish: same answer, zero cents. Two floors on one sheet. A faint old scan. No
scale? Measure one door, every size follows. A photo: not a floor plan, it says so. A messy folder of
twenty-seven files: sorted in thirty seconds."

**2:25–2:40 · Proof and cost** [slide 9, C19, slide 11]
"Measured, not claimed: twenty-four of twenty-five harder questions on Stoa's full-size sheets, the scale within
two percent on all three. Most answers cost nothing: zero tokens, zero cents. A deep read of a sixty-seven
megapixel sheet: about ten cents, once."

**2:40–3:00 · Why it lasts, close** [slide 12, slide 13]
"Models name things. Code measures. So when next year's model is better, Plumb gets better. It doesn't get
replaced. Can a drawing answer, and show where? With Plumb: yes. Every number, boxed on the drawing."

---

## Speaker notes per slide (also in the pptx)

| Slide | Spoken | Seconds |
|---|---|---|
| 1 Title | "I'm Abhinav, and this is Plumb." | 3 |
| 2 Character | "Meet the site engineer. One dormitory floor, ten thousand pixels wide." | 6 |
| 3 Problem | "A hundred and thirty-nine doors, eighty-four chairs, forty-eight sinks… and that is only the start." | 8 |
| 4 Question | "A guess, or a receipt? Can a drawing answer, and show where?" (pause) | 7 |
| 5 Solution | Part B 0:22 | 13 |
| 6 Demo | Part B 0:35 (over C3/C4) | 20 |
| 7 Deep read | Part B 0:55 (over C5/C6) | 20 |
| 8 Honest | Part B 1:15 (over C7/C9) | 20 |
| 9 Proof | Part B 2:25 first sentence | 8 |
| 10 Build plan | Part B 1:35 (over C10/C11) | 25 |
| 11 Cost | Part B 2:25 second half | 8 |
| 12 Why it lasts | Part B 2:40 first half | 10 |
| 13 Thank you | Part B 2:40 last line | 6 |

DO NOT SAY: "employing people for this is stupid"; any accuracy number not in the reports; "certified to EN
standards" (the services are estimates); "counts every symbol perfectly" (some symbol names can be wrong).

## IF ASKED (Q&A)
- **Accuracy?** CubiCasa dataset plans 81.5% exact counts (n = 400); Swiss dwelling counts 91.3% (n = 206);
  24/25 on our harder questions over Stoa's three full-size sheets (docs/stress-report-r9.md).
- **What does the LLM do?** Names each symbol type once, classifies a new question, reviews a scan. It never
  outputs a count or a measurement; code does, and every number has a box and a tag (drawn / specified / chosen /
  estimate).
- **Cost?** Most answers 0 tokens. Deep read of the 67-MP dorm sheet about $0.10, cached per drawing. Open-weight
  models through Verda; Gemini or Claude can be swapped in.
- **What if a name is wrong?** The count stays right; rename the symbol once (pencil) and every copy follows.
- **Limits?** Some symbol names; doors on piping sheets are partial; wing lengths aren't answered yet.

## Sending me the recording (I do the edit)
Put everything in one folder, e.g. `~/Downloads/plumb_video/`:
- the screen clips, named by clip number: `C1.mov`, `C2.mov` … (QuickTime screen recording is fine; record at
  1920x1080 or the full screen; no need to trim, I cut them);
- your voiceover as one file `voiceover.m4a` (read Part B straight through; a mistake? pause two seconds and
  repeat the sentence, I keep the last take). Or talk over the clips while recording; both work.
I then cut: slides (`docs/pitch/slides/`) between the clips, the voiceover on top, captions for the key numbers,
and export `Plumb_pitch.mp4` at 1080p, under 3:00.
