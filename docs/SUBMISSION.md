# Junction 2026 submission: field-by-field (copy and paste)

## Project name
Plumb

## Punchline
Blueprints that show their work: every answer boxed on the drawing, for cents.

## Description
Site engineers spend hours every day pulling numbers out of drawings: how many doors, beds and valves, how much
pipe, cable and concrete. General AI models guess at technical drawings, and a guess can't be checked.

Plumb answers natural-language questions about construction drawings and shows where every answer came from.
It reads the scale from the sheet itself (scale notes, scale bars and printed dimensions, cross-checked; on Stoa's
dormitory sheet it caught that the print is half-size), finds every repeated symbol by computer vision, and counts
each one two independent ways. A vision model only names each kind of symbol, once; it never produces a number.
Every answer comes back with the exact elements boxed on the drawing and a tag saying whether the value was
measured, printed, chosen by the user or estimated.

It works on simple apartment plans and on 10,000-pixel construction sheets: a dormitory floor (139 doors, 48
sinks, 5 staircases), a piping plan (12 valves, each tag listed; it says when only 4 of 5 check-valve labels are
legible), a foundation plan (quoting the printed trench length). It turns a drawing into a build plan with
quantities, and where a set has no plumbing or electrical sheet it estimates pipe runs and wiring by European
rules (EN 806-3, EN 12056-2, EN 12464-1), clearly labelled as estimates. Questions work in English, Finnish,
Swedish, German, French, Spanish, Dutch and Estonian.

Measured on the dataset: 81.5% exact counts on 400 CubiCasa questions, 91.3% on 206 Swiss-dwelling counts, and
24 of 25 harder questions on Stoa's three full-size sheets, with the scale within 2% on all three. Most answers cost
zero tokens; an in-depth read of a 67-megapixel sheet costs about $0.10 once. Because models only name things and
code measures, a better model next year makes Plumb better, not obsolete.

## Challenge
Stoa: Make Blueprints Talk

## Technologies used
Python, FastAPI, OpenCV, scikit-image, Shapely, NetworkX, Tesseract OCR, PyMuPDF, ezdxf, IfcOpenShell, PyTorch
(CubiCasa5k floor-plan model), open-weight vision and language models via Verda, React, TypeScript, Vite,
three.js, Vercel.

## Demo and source code links
- Video: <your YouTube / Vimeo link, set to Public or Unlisted-public>
- Source code: https://github.com/lalashutosh/constructionsite (or your copy once created:
  https://github.com/abhinavchutani/constructionsite)
- Web app: https://plumb-blueprints.vercel.app (the interface; the engine runs locally, so judges should rely on
  the video for the demo)

## Source code publicity
Public.

## Pitch deck (pdf)
docs/pitch/Plumb_pitch_deck.pdf (13 slides).

## Credited / phone / Discord
Fill in yourself.
