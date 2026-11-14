# Stress report (big construction sheets)
**score: 17/18 graded answers correct**

## cache/stress/m101a.png  (LLM off)
total 15.8 s, peak RSS 813712 MB, steps {'profile_s': 0.89, 'analyze_s': 3.26, 'geometry_s': 0.42}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'footprint': 1, 'region': 2}, 'route': 'cad'}
geometry: {'walls': 1, 'rooms': 2, 'note': 'construction sheet: outline 23.49 x 15.96 m from screened background layer (the building printed in grey under the black piping/services); notes, legends, title block and dimension chains excluded', 'views': [[1, 'other', None], [2, 'other', None]]}

| question | intent | answer | tier | ok | s | $ |
|---|---|---|---|---|---|---|
| What is the scale of this drawing? | scale_info | 1 m = 247.6 px on this image (scale note '1/4" = 1'-0"' on ANSI D 34x22 (sheet size guessed from the aspect ratio); scale note '1/4" = 1'-0"' if printed on ANSI B 17x11 (half/double-size print); REJECTED: outside the 247.75 px/m agreement group; graphic scale bar labels 0, 2, 4 ft). | amber | OK | 3.91 | 0.0 |
| How many fuel pumps are there? | unknown | 5 (5 distinct FP tags read on the sheet (FP-1, FP-2, FP-3, FP-4, FP-5); FP = fuel pumps from initials of 'fuel pumps'). | amber | OK | 1.86 | 0.0 |
| How many check valves are there? | unknown | 5 (the sheet prints 'NON-SURGE CHECK VALVE (CV) W/ RATE OF FLOW CONTROLLER (TYP. OF 5)'; but 4 distinct CV tags read on the sheet (CV-1, CV-2, CV-3, CV-4); CV = check valves from initials of 'check valves'). | amber | OK | 1.5 | 0.0 |
| How many filter separators are there? | unknown | 7 (6 distinct FS tags read on the sheet (FSI-1, FSI-2, FSI-3, FSI-4, FSI-5, FSR-2); FS = filter separators from initials of 'filter separators'; the numbering implies 7 (not read: FSR-1)). | amber | OK | 2.3 | 0.0 |
| What is the overall length and width of the building? | overall_size | 23.49 m x 15.97 m. | amber | OK | 0.48 | 0.0 |
| What is the floor area of the pumphouse? | unknown | 358.3 m² measured inside the building outline (23.49 x 15.96 m, screened background layer (the building printed in grey under the black piping/services); scale 247.7 px/m from the sheet). | amber | OK | 0.46 | 0.0 |
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | - | 0.24 | 0.0 |

## cache/stress/s100f.png  (LLM off)
total 9.7 s, peak RSS 836944 MB, steps {'profile_s': 0.85, 'analyze_s': 3.06, 'geometry_s': 0.39}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'footprint': 1, 'region': 1}, 'route': 'cad'}
geometry: {'walls': 1, 'rooms': 1, 'note': 'construction sheet: outline 27.45 x 15.96 m from paired wall / slab-edge lines (dimension lines excluded); notes, legends, title block and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None]]}

| question | intent | answer | tier | ok | s | $ |
|---|---|---|---|---|---|---|
| What is the scale of this drawing? | scale_info | 1 m = 233.4 px on this image (scale note '1:50' on ISO A1 (sheet size guessed from the aspect ratio); scale note '1:50' if printed on ARCH E1 42x30 (half/double-size print); REJECTED: outside the 232.50 px/m agreement group; scale note '1:50' if printed on ISO A0 (half/double-size print); REJECTED:  | amber | OK | 3.62 | 0.0 |
| What is the overall length and width of the building? | overall_size | 27.00 m x 15.52 m (27000 x 15522 printed on the sheet; width 27000: it equals the printed chain 19800 + 7200; depth 15522: its dimension line measures true at the solved scale). | amber | OK | 0.01 | 0.0 |
| What is the total slab area? | total_room_area | 341.2 m² measured inside the building outline (27.45 x 15.96 m, paired wall / slab-edge lines (dimension lines excluded); scale 232.5 px/m from the sheet). | amber | OK | 0.31 | 0.0 |
| How thick is the slab? | unknown | The sheet prints '300 SLAB-ON- GRADE W/ D22'; also printed: 'TOP OF SLAB EL. 10000'; also printed: '150 SLAB-ON-GRADE W/ D13'. | amber | OK | 0.25 | 0.0 |
| What is the motor control center trench length? | unknown | The sheet prints 'MOTOR CONTROL CENTER TRENCH LENGTH 4275'; also printed: '1. APPROXIMATE TRENCH LENGTHS ARE PROVIDED BELOW. COORDINATE WITH EQUIPMENT MANUFACTURER FOR EXACT LENGTH OF TRENCHES. MOTOR CONTROL CENTER TRENCH LENGTH 4275'; also printed: 'NOTES: 1. APPROXIMATE TRENCH LENGTHS ARE PROVIDED | amber | OK | 0.16 | 0.0 |
| How big is the sump? | total_room_area | The sheet prints 'SUMP 600 X 600 X 300 DEEP ~\'. | amber | OK | 0.81 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 2 views, main plan view read from line geometry). | grey | - | 0.0 | 0.0 |

## cache/stress/a2dorm.png  (LLM off)
total 9.8 s, peak RSS 932048 MB, steps {'profile_s': 1.0, 'analyze_s': 3.25, 'geometry_s': 0.51}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'zone': 7, 'footprint': 1}, 'route': 'cad'}
geometry: {'walls': 4, 'rooms': 7, 'note': 'construction sheet: walls read from line geometry of the main plan view (4 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None], [3, 'other', None]]}

| question | intent | answer | tier | ok | s | $ |
|---|---|---|---|---|---|---|
| What is the scale of this drawing? | scale_info | 1 m = 49.3 px on this image (scale note '1" = 40'-0"' on ANSI D 34x22 (sheet size guessed from the aspect ratio); REJECTED: outside the 49.28 px/m agreement group; scale note '1" = 40'-0"' if printed on ANSI B 17x11 (half/double-size print); graphic scale bar labels 0, 7, 20 ft; 2 printed dimensions | amber | OK | 3.62 | 0.0 |
| What is the overall length and width of the building? | overall_size | 98.55 m x 87.17 m (323'-4" x 286-0" printed on the sheet; width 323'-4": it equals the printed chain 133'-10" + 55'-8" + 133'-10"; depth 286-0": a drawn dimension line of that length (at the solved scale) runs beside it). | amber | OK | 0.45 | 0.0 |
| What is the total area of all rooms? | total_room_area | 26,562 SF = 2467.7 m² (the sheet prints 'TOTAL SECOND FLOOR 26,562 SF'; measured from the drawing: 2353 m² (-5%)). | amber | OK | 0.23 | 0.0 |
| How many dorm rooms are on this floor? | unknown | 48 (the sheet prints 'SECOND FLOOR 48 DORMS'). | amber | OK | 0.32 | 0.0 |
| What is the total square footage of the west wing? | total_room_area | 7,009 SF = 651.2 m² (the sheet prints 'TOTAL WEST WING 7,009 SF'). | amber | OK | 0.11 | 0.0 |
| How long is the north wing? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | WRONG | 0.11 | 0.0 |
| Which is the largest room and how big is it? | largest_room | The largest room and zone is the colour module marked DORMITORY at the bottom left (602.9 m²). | amber | - | 0.02 | 0.0 |
