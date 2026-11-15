# Plumb: pitch video script (about 2:45)

Judging, 25% each: accuracy · reasoning a human can verify · creativity · low inference cost.
Stoa's own words to echo: "engineers spend hours every day looking for information", "general-purpose AI models
frequently fail", "shows where in the drawing it came from so a human can verify it in seconds", "solutions next
year's frontier models won't make obsolete".

Every number below must be read off the screen during the recording (the app changed after some runs). Bracketed
numbers are what the last runs showed.

---

## 0:00 – 0:20 · Hook (the escalation)
SCREEN: a small apartment plan (dataset `colorful-2002`). A cursor taps each door.
VO: "How many doors are in this plan? One, two, three, four, five, six. Easy."
SCREEN: hard cut to the dormitory sheet (`us_daf_dorm_sd_drawings_april_2026_p003`), 10,200 × 6,600 px, zoom out.
VO: "Now this one. And while you're at it: how many beds to order, how many hinges, how much pipe, how much concrete,
and where are the stairs?"
SCREEN: beat of silence on the huge sheet.
VO: "That's a site engineer's afternoon. Every day."

## 0:20 – 0:35 · The problem
VO: "General AI models guess at drawings like this, and you can't check their guess. Stoa asked for answers that are
right and that show where they came from, so a human can verify them in seconds. That's Plumb."

## 0:35 – 1:05 · Verify in seconds (criterion: visualised reasoning)
SCREEN: open the dorm. The scale badge: "Scale read from the drawing · 94% sure · Where?". Click Where? Pins land on
the scale note, the scale bar and the dimension strings.
VO: "Plumb first reads the scale from the sheet itself. And it caught a trap: this is a half-size print. The note says
1 inch = 40 feet, which would make everything twice too big. The scale bar and the printed dimensions outvote it."
SCREEN: ask "How many doors?". Answer [139] with per-wing split. Click See proof: every door boxed on the drawing.
VO: "Every number points at the exact symbols it counted. Click, check, done."

## 1:05 – 1:40 · The deep read (criterion: creativity)
SCREEN: the "What's on this sheet" checklist with thumbnails: doors, chairs, sinks, toilets, beds, staircases.
Click "Beds": every bed lights up in 3D.
VO: "On a big sheet Plumb does a deep read. It finds every symbol that repeats, counts every copy two independent
ways, and only then asks a vision model what each symbol is, once per symbol. The model never counts. Code does."
SCREEN: ask "Are there more doors or toilets and sinks?" -> [139 vs 96 (48 + 48)].
VO: "So you can ask the questions you actually have."

## 1:40 – 2:05 · Hard sheets, honest answers (criterion: accuracy)
SCREEN: the piping plan (M-101A). Ask "How many valves?" -> [12], every tag listed. Ask "How many check valves?" ->
[5, the sheet prints TYP. OF 5, only 4 tags are legible].
VO: "On a piping plan it reads the equipment tags and the legend. When the sheet says five but only four labels are
legible, Plumb says exactly that. No silent guesses."
SCREEN (optional, 3 s): "How many TVs?" -> "Not found; the shapes first named TV were parts of beds."

## 2:05 – 2:25 · From drawing to shopping list
SCREEN: Build plan tab. Headline tiles, then the finishes map (rooms coloured by floor finish, m² per finish), then the
Plumbing section with the drawn pipe runs and [~2,023 m], Electrical with [~418 m] of cable, lights, sockets.
VO: "Then it turns the drawing into what to buy: concrete, walls, doors and hinges, fixtures, finishes room by room.
No plumbing sheet in this set? It estimates pipework and wiring by European rules (EN 806, EN 12056, EN 12464) and
labels every number as an estimate."

## 2:25 – 2:45 · Why it lasts, and what it costs (criterion: low inference cost)
SCREEN: the cost line under an answer ("0 tokens · $0.0000") and the checklist header ("$0.0x to read the whole sheet").
VO: "Most answers are pure geometry: zero tokens, zero cents. A deep read of a 67-megapixel sheet costs a few cents,
once. Models only name things; geometry and code measure. So when next year's model is better, Plumb gets better too.
It doesn't get replaced."
SCREEN: end card: Plumb · "Blueprints that show their work".

---

## Numbers you may quote (from reports in this repo)
- CubiCasa dataset counts: 81.5% exact (400 dev questions); Swiss dwelling counts 91.3% (206).
- Three full-resolution Stoa sheets, harder questions: 24/25 (docs/stress-report-r9.md); scale within 2% on all three.

## Lines to avoid
- "Employing people for this is stupid." Stoa sells to construction companies; their users are the engineers. Say
  "an engineer's afternoon, every day" instead: same punch, and it makes the engineer the hero.
- Any accuracy number not in the reports above.
