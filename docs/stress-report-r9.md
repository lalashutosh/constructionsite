# Stress report (big construction sheets)
**score: 24/25 graded answers correct**

## cache/stress/m101a.png  (LLM off)
total 82.2 s, peak RSS 1247712 MB, steps {'profile_s': 0.84, 'analyze_s': 3.49, 'deep_read_s': 52.3, 'geometry_s': 0.49}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'footprint': 1, 'region': 2, 'room': 3}, 'route': 'cad'}
deep read: [['Pipe supports (PS)', 22], ['Control valves (FSCV)', 7], ['Doors', 5], ['Fuel pumps (FP)', 5], ['Indicators (FSI)', 5], ['Check valves (CV)', 4], ['Stair flights', 3], ['Staircases', 1]]
geometry: {'walls': 1, 'rooms': 5, 'note': 'construction sheet: outline 23.49 x 15.96 m from screened background layer (the building printed in grey under the black piping/services); notes, legends, title block and dimension chains excluded', 'views': [[1, 'other', None], [2, 'other', None]]}

| question | intent | answer | tier | ok | s | $ |
|---|---|---|---|---|---|---|
| What is the scale of this drawing? | scale_info | 1 m = 247.6 px on this image (scale note '1/4" = 1'-0"' on ANSI D 34x22 (sheet size guessed from the aspect ratio); scale note '1/4" = 1'-0"' if printed on ANSI B 17x11 (half/double-size print); REJECTED: outside the 247.75 px/m agreement group; graphic scale bar labels 0, 2, 4 ft). | amber | OK | 4.45 | 0.0 |
| How many fuel pumps are there? | unknown | 5 (5 distinct FP tags read on the sheet (FP-1, FP-2, FP-3, FP-4, FP-5); FP = fuel pumps from initials of 'fuel pumps'). | amber | OK | 5.09 | 0.0 |
| How many check valves are there? | unknown | 5 (the sheet prints 'NON-SURGE CHECK VALVE (CV) W/ RATE OF FLOW CONTROLLER (TYP. OF 5)'; but 4 distinct CV tags read on the sheet (CV-1, CV-2, CV-3, CV-4); CV = check valves from initials of 'check valves'). | amber | OK | 2.43 | 0.0 |
| How many filter separators are there? | unknown | 7 (6 distinct FS tags read on the sheet (FSI-1, FSI-2, FSI-3, FSI-4, FSI-5, FSR-2); FS = filter separators from initials of 'filter separators'; the numbering implies 7 (not read: FSR-1)). | amber | OK | 6.98 | 0.0 |
| What is the overall length and width of the building? | overall_size | 23.49 m x 15.97 m. | amber | OK | 0.47 | 0.0 |
| What is the floor area of the pumphouse? | unknown | 358.3 m² measured inside the building outline (23.49 x 15.96 m, screened background layer (the building printed in grey under the black piping/services); scale 247.7 px/m from the sheet). | amber | OK | 0.47 | 0.0 |
| How many doors are there? | deep_read_count | There are 5 doors on this sheet. | amber | - | 1.39 | 0.0 |
| How many valves are there? | unknown | 12 valves tagged on the sheet — 7 FSCV (control valve; ISA-5.1 tag letters: FSCV ends in 'CV' = control valve: FSCV-1, FSCV-2, FSCV-3, FSCV-4, FSCV-5, FSCV-6, FSCV-7); 4 CV (check valve; standard abbreviation CV = check valve: CV-1, CV-2, CV-3, CV-4); 1 BPCV (control valve; ISA-5.1 tag letters: BPCV | amber | OK | 3.07 | 0.0 |
| What is the total length of the walls? | unknown | The walls around the outside of the building add up to 78.9 m (length of its outline, measured with the sheet's printed scale). | amber | OK | 0.47 | 0.0 |

## cache/stress/s100f.png  (LLM off)
total 144.2 s, peak RSS 999232 MB, steps {'profile_s': 0.79, 'analyze_s': 3.62, 'deep_read_s': 132.3, 'geometry_s': 0.42}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'footprint': 1, 'region': 1, 'room': 13}, 'route': 'cad'}
deep read: [['Columns', 71], ['Symbol Type 9s', 5]]
geometry: {'walls': 1, 'rooms': 14, 'note': 'construction sheet: outline 27.45 x 15.96 m from paired wall / slab-edge lines (dimension lines excluded); notes, legends, title block and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None]]}

| question | intent | answer | tier | ok | s | $ |
|---|---|---|---|---|---|---|
| What is the scale of this drawing? | scale_info | 1 m = 233.4 px on this image (scale note '1:50' on ISO A1 (sheet size guessed from the aspect ratio); scale note '1:50' if printed on ARCH E1 42x30 (half/double-size print); REJECTED: outside the 232.50 px/m agreement group; scale note '1:50' if printed on ISO A0 (half/double-size print); REJECTED:  | amber | OK | 4.08 | 0.0 |
| What is the overall length and width of the building? | overall_size | 27.00 m x 15.52 m (27000 x 15522 printed on the sheet; width 27000: it equals the printed chain 19800 + 7200; depth 15522: its dimension line measures true at the solved scale). | amber | OK | 0.02 | 0.0 |
| What is the total slab area? | total_room_area | 341.2 m² measured inside the building outline (27.45 x 15.96 m, paired wall / slab-edge lines (dimension lines excluded); scale 232.5 px/m from the sheet). | amber | OK | 0.38 | 0.0 |
| How thick is the slab? | unknown | The sheet prints '300 SLAB-ON- GRADE W/ D22'; also printed: 'TOP OF SLAB EL. 10000'; also printed: '150 SLAB-ON-GRADE W/ D13'. | amber | OK | 0.31 | 0.0 |
| What is the motor control center trench length? | unknown | The sheet prints 'MOTOR CONTROL CENTER TRENCH LENGTH 4275'; also printed: '1. APPROXIMATE TRENCH LENGTHS ARE PROVIDED BELOW. COORDINATE WITH EQUIPMENT MANUFACTURER FOR EXACT LENGTH OF TRENCHES. MOTOR CONTROL CENTER TRENCH LENGTH 4275'; also printed: 'NOTES: 1. APPROXIMATE TRENCH LENGTHS ARE PROVIDED | amber | OK | 0.19 | 0.0 |
| How big is the sump? | total_room_area | The sheet prints 'SUMP 600 X 600 X 300 DEEP ~\'. | amber | OK | 0.89 | 0.0 |
| How many rooms are there? | deep_read_count | There are 13 rooms on this sheet. | amber | - | 0.66 | 0.0 |

## cache/stress/a2dorm.png  (LLM off)
total 79.5 s, peak RSS 1067984 MB, steps {'profile_s': 1.52, 'analyze_s': 7.33, 'deep_read_s': 61.6, 'geometry_s': 0.41}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'zone': 6, 'footprint': 1, 'room': 54}, 'route': 'cad'}
deep read: [['Doors', 139], ['Chairs', 96], ['Beds', 51], ['Sinks', 48], ['Toilets', 48], ['Symbol Type 12s', 45], ['Columns', 35], ['Side tables', 16], ['Symbol Type 15s', 14], ['Stair flights', 12], ['Symbol Type 18s', 7], ['TVs', 7], ['Symbol Type 24s', 6], ['Staircases', 5]]
geometry: {'walls': 1, 'rooms': 60, 'note': 'construction sheet: outline 105.11 x 90.27 m from union of the legend colour zones; notes, legends, title block and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None], [3, 'other', None]]}

| question | intent | answer | tier | ok | s | $ |
|---|---|---|---|---|---|---|
| What is the scale of this drawing? | scale_info | 1 m = 49.3 px on this image (scale note '1" = 40'-0"' on ANSI D 34x22 (sheet size guessed from the aspect ratio); REJECTED: outside the 49.28 px/m agreement group; scale note '1" = 40'-0"' if printed on ANSI B 17x11 (half/double-size print); graphic scale bar labels 0, 7, 20 ft; 2 printed dimensions | amber | OK | 4.32 | 0.0 |
| What is the overall length and width of the building? | overall_size | 98.55 m x 87.17 m (323'-4" x 286-0" printed on the sheet; width 323'-4": it equals the printed chain 133'-10" + 55'-8" + 133'-10"; depth 286-0": a drawn dimension line of that length (at the solved scale) runs beside it). | amber | OK | 0.5 | 0.0 |
| What is the total area of all rooms? | total_room_area | 26,562 SF = 2467.7 m² (the sheet prints 'TOTAL SECOND FLOOR 26,562 SF'; measured from the drawing: 3548 m² (+44%)). | amber | OK | 0.27 | 0.0 |
| How many dorm rooms are on this floor? | unknown | 48 (the sheet prints 'SECOND FLOOR 48 DORMS'). | amber | OK | 0.68 | 0.0 |
| What is the total square footage of the west wing? | total_room_area | 7,009 SF = 651.2 m² (the sheet prints 'TOTAL WEST WING 7,009 SF'). | amber | OK | 0.15 | 0.0 |
| How long is the north wing? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | WRONG | 0.14 | 0.0 |
| Which is the largest room and how big is it? | largest_room | The largest room and zone is the space in the centre (972.0 m²). | amber | - | 0.02 | 0.0 |
| How many staircases are there? | deep_read_count | There are 5 staircases on this sheet. | amber | OK | 0.39 | 0.0 |
| How many sinks are there? | deep_read_count | There are 48 sinks on this sheet; 16 in Dormitory (bottom left), 16 in Dormitory (top left), 16 in Dormitory (bottom right). | amber | OK | 0.39 | 0.0 |
| How many toilets are there? | deep_read_count | There are 48 toilets on this sheet; 16 in Dormitory (bottom left), 15 in Dormitory (top left), 16 in Dormitory (bottom right). | amber | OK | 0.4 | 0.0 |
| How many beds are there? | deep_read_count | There are 51 beds on this sheet; 18 in Dormitory (bottom left), 11 in Dormitory (top left), 16 in Dormitory (bottom right), 3 in 2ND Floor Common Area (bottom). | green | OK | 0.37 | 0.0 |
| Are there more doors or toilets and sinks? | deep_read_compare | Doors: 139 vs toilets + sinks: 96 (48 + 48). More doors, by 43. | amber | OK | 0.01 | 0.0 |
| How much pipework do we need? | estimated_pipe_m | About 2646.7 m of pipework (ESTIMATE: this set has no plumbing sheet; 140 wet fixtures from the deep read, branches to 4 wing mains, orthogonal runs + 30% routing allowance (estimate, no plumbing sheet)). | amber | - | 0.02 | 0.0 |
