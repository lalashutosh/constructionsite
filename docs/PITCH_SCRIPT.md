# Plumb — the 2-minute pitch (video + deck)

Hard limit: 2:00 (Junction is strict). Target 1:55. Judging, 25% each: accuracy · reasoning a human can verify ·
creativity · low inference cost. The video is one continuous app demo with the voiceover on top; the deck
(`docs/pitch/Plumb_pitch_deck.pdf`) follows the same story with real outputs from the app.

---

## 1. Who does what

- **Abhinav records only the voiceover** (`docs/pitch/VOICEOVER.md`), and sends the audio file (m4a, wav or mp3).
  Quiet room, phone or laptop mic 20 cm away, read straight through at a calm pace, and **leave a 1-second pause
  between paragraphs**: I use the pauses to line the pictures and the stickman up with the voice.
- **I record the app and edit the video**: real app screens captured at 1080p, smooth 60 fps camera moves,
  a hand-drawn stickman presenter beside the app (instant pose swaps as you speak: pointing, hands up, thinking),
  captions, the slides in between. Builder: `docs/pitch/video/build_video.py`.
- The chatbot test is done: ChatGPT thought for 1 min 10 s and answered **104** (`docs/pitch/chatbot.png`, slide 3).

## 2. The voiceover (read straight through, ~1:50)

[V2] Here's a floor plan. How many doors? Six. Easy.

[V3] Now this one: an Air Force dormitory, ten thousand pixels wide. You can't count this by eye, and nobody
should have to.

[V1 / slide 3] We asked ChatGPT. It thought for over a minute and said a hundred and four, with no way to check
it. Plumb says a hundred and thirty-nine, and it boxes every single door on the drawing.

[V4, V5, V6 · REASONING] That's Plumb: ask in plain language, in any language, and it answers with its working shown.
More doors, or toilets and sinks? A hundred and thirty-nine against ninety-six. Every one it counted is on
screen, tagged measured, printed or estimated.

[V7, V8 · CREATIVITY] Every size starts with the scale, and Plumb reads it off the sheet itself: the note, the
scale bar, the dimension lines. No scale on the drawing? Measure any one thing you know, a door or a wall, and
every dimension in the building follows.

[V9, V10, V11] Then it builds the floor in 3D, layer by layer like a body: walls, furniture, pipes and wiring. It
counts every bed, chair and staircase. And it turns the drawing into a build plan: concrete, doors,
finishes, and pipe and cable estimated by European engineering rules.

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
