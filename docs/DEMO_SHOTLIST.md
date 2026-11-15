# Demo shot list (videos + pitch)

Ranked by the judging criteria we work from (AGENTS.md: accuracy, reasoning a human can verify, creativity, low
inference cost; judges will ask harder questions than the dataset). Numbers are from measured runs in this repo.

1. **Scale from the sheet itself, with a trap caught** (A-2 dorm). Open it: "Scale read from the drawing · 94% sure ·
   Where?" -> pins on the scale note, the bar and the dimension strings. Say: the printed note 1" = 40'-0" on 34x22 paper
   would be 2x wrong; it is a half-size print; three independent checks outvote it. Then a hand sketch: no scale ->
   it asks for ONE length, every size updates. [scale within 2% on all 3 Stoa sheets, docs/stress-report-r9.md]
2. **Hard questions answered with a receipt** (M-101A piping). "How many valves?" -> 12, every tag listed, meaning from
   the sheet legend / ISA-5.1 letters. "How many check valves?" -> 5 because the sheet prints "TYP. OF 5" although only
   4 tags are legible: it says so. "MCC trench length?" -> 4275, citing the note. Click See proof.
3. **The deep read** (dorm, 10200x6600 px). It announces it will take longer, shows progress, then: 139 doors, 84 chairs,
   48 sinks, 48 toilets, 46 beds, 5 staircases, per wing; thumbnails of each symbol; click a row -> every copy lights up
   in 3D. "Are there more doors or toilets and sinks?" -> 139 vs 96 (48 + 48). Paid once (cents), re-reads free.
   The model only names symbol types; code counts them twice.
4. **Services by European rules where there is no MEP sheet**: pipework ~2,023 m, cable ~418 m, EN 12464-1 lighting
   (lumen method), EN 806-3 loading units (148 LU), EN 12056-2 waste flow (~8.0 l/s). Layers toggle in 3D (blue pipes,
   amber cable); Build plan tab shows them as line items with a drawn service map. Always labelled ESTIMATE.
5. **Piping sheet in 3D**: the building read from the grey background layer under the black piping, pipes as raised
   runs, every tagged pump / valve standing up as a labelled marker.
6. **Honesty as a feature**: "How many TVs?" -> "not found; shapes first named TV were parts of beds". A measurement
   contradicted by a misread label is no longer forced on you ("Keep my measurement").
7. **Residential base still solid**: CubiCasa DEV 81.5% exact counts (n=400), Swiss counts 91.3% (n=206).

Say before a judge finds it: symbol NAMES can be wrong while counts are right (rename in one click); doors on piping
sheets are partial; wing lengths are not answered yet; the deep read takes 1-5 min on a 67-megapixel sheet.
