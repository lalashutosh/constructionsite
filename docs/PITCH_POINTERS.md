# Pitch pointers (what to say, what to show)

Every number below comes from a measured run in this repo; the source is in brackets. Do not round them up.

## One line
Plumb turns a drawing into numbers with a receipt: what was measured, what was assumed, and where on the sheet it came from.
Big, complex sheets get a deep read automatically.

## 1. Scale: automatic, and one reference is enough if it is missing
- Plumb reads the scale from the sheet itself: the printed scale note (`1/4" = 1'-0"`, `1:50`), the graphic scale bar
  and the printed dimension strings. These are independent checks; it uses them when they agree and says how sure it is.
- On the 3 Stoa example sheets at full resolution, the scale is within 2% of the truth on all three
  [docs/stress-report-r7.md].
- It caught a trap: the dormitory sheet is a **half-size print**. Its printed note `1" = 40'-0"` on 34x22 paper would be
  wrong by 2x. The scale bar and the dimension strings outvote it.
- Show: the scale badge top-right, then **Where?**. Pins appear on the exact note, bar and dimension it used.
- If a drawing has no scale (a hand sketch), Plumb says so and asks for **one** real length (a door, a wall). That one
  click fixes every size on the sheet.

## 2. Every number points at the drawing
- Each answer has a tag: drawn (measured), specified (printed on the sheet), chosen (you decided) or defaulted
  (an assumption we had to make). "See proof" shows the receipt.
- Overall size is only stated when it checks out, for example "27.00 m x 15.52 m: 27000 equals the printed chain
  19800 + 7200; 15522's dimension line measures true at the solved scale".

## 3. The deep read (complex sheets)
- A sheet over about 20 megapixels with many spaces switches to the deep read automatically and **says how long it
  will take before it starts**. Dormitory: 10200x6600 px, about 2-5 min, about $0.10, paid once per drawing.
- It finds every repeated symbol by code (beds, sinks, toilets, chairs ...), counts it twice (shape clustering and
  template matching), and a vision model only names each symbol type once. The model never produces a count.
- Dormitory: 48 sinks, 48 toilets, 46 beds, split per wing (16 / 15-16 / 16), which matches the sheet's printed
  "48 DORMS" per floor. Sinks and beds are green: two checks agree.
- The chatbot answers from it: "how many beds do I have?" gives "46 beds; 16 bottom-left wing, ...", with every bed boxed.

## 4. It understands piping plans (Stoa's "impress us")
- M-101A piping plan: the building is read from the grey background layer under the black piping. 324 pipe runs are
  traced as a separate layer.
- Equipment is read from its tags: 5 fuel pumps (FP-1..5), 7 control valves (FSCV), 4 check valves (CV), 22 pipe
  supports. "How many valves?" sums every valve type (11). The meaning of each tag comes from the sheet's own legend
  "(CV)", standard abbreviations or the ISA-5.1 instrument letters.
- The printed notes are answered too: "motor control center trench length" gives 4275, citing the note.

## 5. Layers, like a body
- Envelope, walls, rooms, furniture, piping and electrical are separate colour-coded layers you can toggle. A sheet that
  has no electrical layer says so; we never invent one.
- 2D / 3D / top / front / side views with the octagon top-right, and the zoom follows your cursor.

## 6. Honest limits (say them before a judge finds them)
- Symbol names can be wrong even when the counts are right. Names are size-checked and amber unless two checks agree;
  the next step is renaming a type in one click.
- Doors on the dormitory sheet are drawn as faint grey arcs and are not counted yet.
- Hand-drawn scans: doors without swing arcs come from wall openings, and each one is boxed so you can check it.

## Tech stack
Python, OpenCV, Tesseract OCR, shapely, FastAPI; React and three.js; open-weight vision and LLM models through Verda
(DeepSeek / Kimi-class, about cents per sheet); Google Gemini optional (`LLM_PROVIDER=gemini`, `GEMINI_API_KEY` in
.env). The models classify and name; code measures and counts.

## Numbers to quote (from the reports)
- Stress set (3 full-resolution Stoa sheets + harder questions): 19/20 graded answers [docs/stress-report-r7.md].
- Residential plans (CubiCasa DEV 400 questions): 81.5% exact; Swiss counts 91.3% [evalkit gate runs, 2026-11-14].
