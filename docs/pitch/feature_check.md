# Feature check (live engine)
run 2026-11-15 05:03


## Ask in any language (data/cubicasa5k/colorful-2002.png)

- **How many bedrooms are there?** -> There are 2 bedrooms.  [green, 1.8 s, $0.0000]
- **Montako makuuhuonetta asunnossa on?** -> There are 2 bedrooms.  [green, 0.0 s, $0.0000]
- **Hur många sovrum finns det?** -> There are 2 bedrooms.  [green, 0.0 s, $0.0000]
- **Wie viele Schlafzimmer gibt es?** -> There are 2 bedrooms.  [green, 0.0 s, $0.0000]
- **Mitu magamistuba on?** -> There are 2 bedrooms.  [green, 0.0 s, $0.0000]
- **Combien de chambres y a-t-il ?** -> There are 2 bedrooms.  [green, 0.0 s, $0.0000]
- **Hoeveel slaapkamers zijn er?** -> There are 2 bedrooms.  [green, 0.0 s, $0.0000]
- **¿Cuántos dormitorios hay?** -> There are 2 bedrooms.  [green, 0.0 s, $0.0000]
- **How many doors?** -> There are 6 doors.  [amber, 0.1 s, $0.0000]
- **Montako ovea?** -> There are 6 doors.  [amber, 0.1 s, $0.0000]
- **What is the total length of the walls of the kitchen?** -> The walls around the kitchen add up to 14.7 m (length of its outline, measured with a scale guessed from standard door widths (give one real length to confirm)).  [amber, 0.0 s, $0.0000]

## Photo or blueprint? (a portrait photo uploaded as a 'drawing')

- **photo: How many doors?** -> I can't answer this from the drawing: no right-angle wall structure and no room labels were found: this does not look like a floor plan.  [grey, 0.5 s, $0.0000]

## One picture, two floors (data/cubicasa5k/colorful-13685.png)

- **floors found** -> 2: ['1. KERROS', '2. KERROS']
- **How many bedrooms on the second floor?** -> There are 4 bedrooms on 2. KERROS.  [amber, 0.2 s, $0.0000]

## Faint scan (data/cubicasa5k/high_quality_architectural-1967.png)

- **What is the scale of this drawing?** -> 1 m = 65.2 px on this image (printed dimensions (2566, 5224 mm) match plan lengths at one scale within 3%; room areas printed on the drawing (MH 10.5, TUPA 18.5, KHH 7.0, K 11.0) agree within 7% across 4 rooms; 1 rooms disagreed (merged or split outlines); printed dimension :573 matched to its dimension line; OUTLIER: 33.7 sigma from the median of all anchors (67.95 px/m): rejected as outlier).  [amber, 0.1 s, $0.0000]
- **What is the total area of all rooms?** -> The answer is 85.4 m².  [amber, 0.0 s, $0.0000]
- **How many bedrooms are there?** -> There is 1 bedroom.  [amber, 0.0 s, $0.0000]

## One measurement gives every size (data/cubicasa5k/high_quality_architectural-594.png)

- **before: total area** -> The answer is 311.2 m².  [amber, 0.1 s, $0.0000]
- **after ONE length (90 px = 4.5 m)** -> The answer is 283.1 m². | 32.14 m x 15.64 m.

## A messy folder (data/opening_design/Sports_Complex)

- **27 files** -> 1 floors in order: ['Transfer/_Archive/20150720 - Door Schedule to Door Consultant/20150720 - XSC - floor plan and door schedule.pdf']; 26 other sheets; 30 s; keys ['building', 'method', 'floors', 'alternatives', 'other', 'groups']

## Big sheets

- **dorm: How many doors?** -> There are 139 doors on this sheet; 44 in Dormitory (bottom left), 39 in Dormitory (top left), 47 in Dormitory (bottom right), 3 in 2ND Floor Common Area (bottom).  [amber, 0.4 s, $0.0000]
- **dorm: How many staircases?** -> There are 5 staircases on this sheet.  [amber, 0.3 s, $0.0000]
- **dorm: How many beds?** -> There are 46 beds on this sheet; 16 in Dormitory (bottom left), 14 in Dormitory (top left), 16 in Dormitory (bottom right).  [green, 0.3 s, $0.0000]
- **dorm: Are there more doors or toilets and sinks?** -> Doors: 139 vs toilets + sinks: 96 (48 + 48). More doors, by 43.  [amber, 0.0 s, $0.0000]
- **dorm: How much pipework do we need?** -> About 2023.3 m of pipework (ESTIMATE: this set has no plumbing sheet; 109 wet fixtures from the deep read, branches to 4 wing mains, orthogonal runs + 30% routing allowance (estimate, no plumbing sheet)).  [amber, 0.0 s, $0.0000]
- **dorm: How much cable?** -> About 417.7 m of cable (ESTIMATE: this set has no electrical sheet; room-to-room circuit tree from a panel near the building centre over 52 rooms, +30% routing (circuits per HD 60364 / IEC 60364; cross-sections not sized here)).  [amber, 0.0 s, $0.0000]
- **dorm: How much waste water flow?** -> About 7.99 l/s peak waste water flow (ESTIMATE: this set has no plumbing sheet; EN 12056-2: Qww = K x sqrt(sum DU) = 0.7 x sqrt(130.4) (discharge units: WC 2.0, washbasin 0.5, shower 0.6, bath 0.8; K = 0.7 frequent use)).  [amber, 0.0 s, $0.0000]
- **dorm: What is the scale of this drawing?** -> The sheet prints the scale 1" = 40'-0"; it reads as 1 m = 49.2 px (scale note '1" = 40'-0"' on ANSI D 34x22 (sheet size guessed from the aspect ratio); REJECTED: outside the 49.22 px/m agreement group; scale note '1" = 40'-0"' if printed on ANSI B 17x11 (half/double-size print); graphic scale bar labels 0, 7, 20 ft; 3 printed dimensions (52'.8", 133'-10", 133'-10") matched to their dimension lines agree within 0%; printed dimension 323'-4" matched to its dimension line; REJECTED: outside the 49.22 px/m agreement group; printed dimension 55'.8" matched to its dimension line; REJECTED: outside the 49.22 px/m agreement group; printed dimension 40'-0" matched to its dimension line; REJECTED: outside the 49.22 px/m agreement group; printed dimension 20' matched to its dimension line; REJECTED: outside the 49.22 px/m agreement group).  [amber, 2.2 s, $0.0000]
- **piping: How many valves are there?** -> 12 valves tagged on the sheet — 7 FSCV (control valve; ISA-5.1 tag letters: FSCV ends in 'CV' = control valve: FSCV-1, FSCV-2, FSCV-3, FSCV-4, FSCV-5, FSCV-6, FSCV-7); 4 CV (check valve; standard abbreviation CV = check valve: CV-1, CV-2, CV-3, CV-4); 1 BPCV (control valve; ISA-5.1 tag letters: BPCV ends in 'CV' = control valve).  [amber, 3.3 s, $0.0000]
- **piping: How many check valves are there?** -> 5 (the sheet prints 'NON-SURGE CHECK VALVE (CV) W/ RATE OF FLOW CONTROLLER (TYP. OF 5)'; but 4 distinct CV tags read on the sheet (CV-1, CV-2, CV-3, CV-4); CV = check valves from initials of 'check valves').  [amber, 2.2 s, $0.0000]
- **piping: How many fuel pumps are there?** -> 5 (5 distinct FP tags read on the sheet (FP-1, FP-2, FP-3, FP-4, FP-5); FP = fuel pumps from initials of 'fuel pumps').  [amber, 3.8 s, $0.0000]
- **piping: What is the motor control center trench length?** -> I can't answer this from the drawing: no MOTOR CONTROL CENTER TRENCH recognised on this drawing.  [grey, 20.0 s, $0.0261]
- **piping: where is the sheet's printed scale?** -> The sheet prints the scale 1/4" = 1'-0"; it reads as 1 m = 247.6 px (scale note '1/4" = 1'-0"' on ANSI D 34x22 (sheet size guessed from the aspect ratio); scale note '1/4" = 1'-0"' if printed on ANSI B 17x11 (half/double-size print); REJECTED: outside the 247.75 px/m agreement group; graphic scale bar labels 0, 2, 4 ft).  [amber, 0.0 s, $0.0000]
- **foundation: What is the motor control center trench length?** -> The sheet prints 'MOTOR CONTROL CENTER TRENCH LENGTH 4275'; also printed: '1. APPROXIMATE TRENCH LENGTHS ARE PROVIDED BELOW. COORDINATE WITH EQUIPMENT MANUFACTURER FOR EXACT LENGTH OF TRENCHES. MOTOR CONTROL CENTER TRENCH LENGTH 4275'; also printed: 'NOTES: 1. APPROXIMATE TRENCH LENGTHS ARE PROVIDED BELOW. COORDINATE WITH EQUIPMENT MANUFACTURER FOR EXACT LENGTH OF TRENCHES. MOTOR CONTROL CENTER TRENCH LENGTH 4275'.  [amber, 0.9 s, $0.0000]
- **foundation: How big is the sump?** -> The sheet prints 'SUMP 600 X 600 X 300 DEEP ~\'.  [amber, 0.5 s, $0.0000]
- **foundation: How thick is the slab?** -> The sheet prints '300 SLAB-ON- GRADE W/ D22'; also printed: 'TOP OF SLAB EL. 10000'; also printed: '150 SLAB-ON-GRADE W/ D13'.  [amber, 0.2 s, $0.0000]
- **foundation: What is the overall length and width of the building?** -> 27.00 m x 15.52 m (27000 x 15522 printed on the sheet; width 27000: it equals the printed chain 19800 + 7200; depth 15522: its dimension line measures true at the solved scale).  [amber, 0.0 s, $0.0000]
