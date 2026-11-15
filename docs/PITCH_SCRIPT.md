# Plumb — pitch script and recording plan

Total: under 2:00, strictly (Junction rule). Target 1:45. Slides: `docs/pitch/slides/slide01.png` … `slide13.png` (also `docs/pitch/Plumb_pitch.pptx` with these
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

## PART B — the voiceover (one continuous story, HARD LIMIT 2:00)

Junction: "not a second longer than 2 minutes, and we will be very strict". This reads in about 1:40, which leaves
room for a slower take and the closing card. Brackets say what is on screen; they are not read.

[C1 · a small apartment plan, cursor taps the doors]
Here's a simple floor plan. How many doors? One, two, three, four, five, six. Easy.

[C2 · hard cut to the dormitory sheet, zoom out]
Now here's a real one: an Air Force dormitory floor, ten thousand pixels wide. And it's not just doors any more.
It's beds, hinges, pipe, concrete. For a site engineer that's an afternoon of counting, every day, and a general AI
model hands you a confident number you can't check.

[slide 4]
So we asked: can a drawing answer, and show where the answer came from? That's Plumb.

[C3 · scale badge, click "Where?"]
It starts with the scale, read from the sheet itself, and here it caught a trap. This is a half-size print, so the
printed note would make everything twice too big. The scale bar and the dimensions disagree, so Plumb trusts them,
and shows you where it looked.

[C5, then C4 · checklist, then "How many doors?" and See proof]
Then it counts. It finds every symbol that repeats, doors, beds, chairs, sinks, and counts each one two ways. An AI
model only names each symbol; it never produces the number. So all one hundred and thirty-nine doors come back
boxed on the drawing. You can check them in seconds.

[C7 · piping plan, valves]
On a piping plan it reads the tags: twelve valves, each listed. And when the sheet says five check valves but only
four labels are legible, Plumb says exactly that.

[C10 · Build plan tab]
Then the drawing becomes a shopping list, with pipe and wiring estimated by European rules and marked as estimates.

[C19, then slide 11]
Most answers cost zero cents. Reading this whole sheet costs about ten cents, once.

[slide 12, then slide 13]
Models name things; code measures. So a better model next year makes Plumb better, not obsolete. That's Plumb:
blueprints that show their work.

(Clips C11–C18 are spare footage: not needed for the 2-minute cut.)

## Speaker notes per slide (also in the pptx)

| Slide | Spoken | Seconds |
|---|---|---|
| 1 Title | "I'm Abhinav, and this is Plumb." | 3 |
| 2 Character | "Meet the site engineer. One dormitory floor, ten thousand pixels wide." | 6 |
| 3 Problem | "A hundred and thirty-nine doors, eighty-four chairs, forty-eight sinks… and that is only the start." | 8 |
| 4 Question | "A guess, or a receipt? Can a drawing answer, and show where?" (pause) | 7 |
| 5 Solution | the 'It starts with the scale' paragraph's lead-in ("So we asked…") | 13 |
| 6 Demo | 'It starts with the scale…' (over C3) | 20 |
| 7 Deep read | 'Then it counts…' (over C5/C4) | 20 |
| 8 Honest | 'On a piping plan…' (over C7) | 20 |
| 9 Proof | optional: '24 of 25 harder questions, scale within 2%' (Q&A material) | 8 |
| 10 Build plan | 'Then the drawing becomes a shopping list…' (over C10) | 25 |
| 11 Cost | 'And it's cheap…' | 8 |
| 12 Why it lasts | 'Models name things; code measures…' | 10 |
| 13 Thank you | 'That's Plumb: blueprints that show their work.' | 6 |

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
