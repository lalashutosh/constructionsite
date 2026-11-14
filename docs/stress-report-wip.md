# Stress report (big construction sheets)

## cache/stress/stoa1.png  (LLM off)
total 5.9 s, peak RSS 183 MB, steps {'profile_s': 0.17, 'analyze_s': 0.14, 'geometry_s': 0.02}
profile: {'width_px': 768, 'height_px': 497, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 584.23, 'line_density': 0.47, 'title_block': [708, 0, 767, 496], 'border': [0, 0, 767, 496], 'views': [{'box': [21, 4, 713, 489], 'ink_ratio': 0.452, 'n_words': 219, 'title': None, 'kind': 'plan', 'words_per_mpx': 652.5, 'n': 1}, {'box': [588, 164, 696, 274], 'ink_ratio': 0.0, 'n_words': 42, 'title': None, 'kind': 'notes', 'words_per_mpx': 3535.4, 'n': 2}, {'box': [517, 58, 597, 147], 'ink_ratio': 0.0, 'n_words': 10, 'title': None, 'kind': 'notes', 'words_per_mpx': 1404.5, 'n': 3}, {'box': [498, 230, 571, 296], 'ink_ratio': 0.0, 'n_words': 6, 'title': None, 'kind': 'notes', 'words_per_mpx': 1245.3, 'n': 4}, {'box': [407, 38, 491, 82], 'ink_ratio': 0.0, 'n_words': 6, 'title': None, 'kind': 'notes', 'words_per_mpx': 1623.4, 'n': 5}, {'box': [134, 118, 186, 185], 'ink_ratio': 0.0, 'n_words': 3, 'title': None, 'kind': 'notes', 'words_per_mpx': 861.1, 'n': 6}, {'box': [100, 299, 156, 340], 'ink_ratio': 0.0, 'n_words': 3, 'title': None, 'kind': 'notes', 'words_per_mpx': 1306.6, 'n': 7}, {'box': [374, 421, 447, 452], 'ink_ratio': 0.0, 'n_words': 2, 'title': None, 'kind': 'detail', 'words_per_mpx': 883.8, 'n': 8}, {'box': [97, 154, 150, 193], 'ink_ratio': 0.0, 'n_words': 1, 'title': None, 'kind': 'detail', 'words_per_mpx': 483.8, 'n': 9}], 'notes': [[588, 164, 696, 274], [517, 58, 597, 147], [498, 230, 571, 296], [407, 38, 491, 82], [134, 118, 186, 185], [100, 299, 156, 340]], 'tables': [], 'complexity': 0.647}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {}, 'route': 'cad'}
geometry: {'walls': 6, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (6 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None], [3, 'other', None], [4, 'other', None], [5, 'other', None], [6, 'other', None], [7, 'other', None], [8, 'other', None], [9, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 5.08 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 9 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 9 views, main plan view read from line geometry). | grey | 0.01 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 9 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.01 | 0.0 |

## cache/stress/stoa2.png  (LLM off)
total 3.6 s, peak RSS 185 MB, steps {'profile_s': 0.16, 'analyze_s': 0.14, 'geometry_s': 0.02}
profile: {'width_px': 768, 'height_px': 542, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 449.24, 'line_density': 0.348, 'title_block': [701, 0, 739, 541], 'border': None, 'views': [{'box': [11, 7, 703, 462], 'ink_ratio': 0.402, 'n_words': 165, 'title': 'FOUNDATION PLAN SLAB', 'kind': 'plan', 'words_per_mpx': 524.0, 'n': 1}, {'box': [60, 498, 691, 529], 'ink_ratio': 0.504, 'n_words': 5, 'title': 'FOUNDATION PLAN SLAB VE AND', 'kind': 'detail', 'words_per_mpx': 255.6, 'n': 2}, {'box': [87, 430, 356, 494], 'ink_ratio': 0.0, 'n_words': 43, 'title': 'FOUNDATION PLAN SLAB', 'kind': 'notes', 'words_per_mpx': 2497.7, 'n': 3}, {'box': [444, 469, 551, 502], 'ink_ratio': 0.366, 'n_words': 4, 'title': None, 'kind': 'detail', 'words_per_mpx': 1132.8, 'n': 4}, {'box': [618, 75, 695, 116], 'ink_ratio': 0.0, 'n_words': 8, 'title': None, 'kind': 'notes', 'words_per_mpx': 2534.1, 'n': 5}], 'notes': [[87, 430, 356, 494], [618, 75, 695, 116]], 'tables': [], 'complexity': 0.581}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'region': 1}, 'route': 'cad'}
geometry: {'walls': 8, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (8 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None], [3, 'other', None], [4, 'other', None], [5, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 2.86 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 5 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 5 views, main plan view read from line geometry). | grey | 0.01 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 5 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.01 | 0.0 |

## cache/stress/stoa3.png  (LLM off)
total 4.8 s, peak RSS 192 MB, steps {'profile_s': 0.15, 'analyze_s': 0.22, 'geometry_s': 0.02}
profile: {'width_px': 768, 'height_px': 497, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 657.59, 'line_density': 0.068, 'title_block': None, 'border': None, 'views': [{'box': [135, 55, 545, 454], 'ink_ratio': 0.067, 'n_words': 64, 'title': 'THE IN AS COMMUNICATIONS) DATA THE ROOM INTERACTIVE NOT ALL A AND COES INDICA) T', 'kind': 'plan', 'words_per_mpx': 391.2, 'n': 1}, {'box': [400, 3, 711, 314], 'ink_ratio': 0.038, 'n_words': 182, 'title': 'ROOM PLAN EXTERIOR I TAL WING', 'kind': 'notes', 'words_per_mpx': 1881.7, 'n': 2}, {'box': [571, 338, 760, 497], 'ink_ratio': 0.172, 'n_words': 25, 'title': 'KEY PLAN CONSTRUCTION SECOND FLOOR PLAN W FOR', 'kind': 'key_plan', 'words_per_mpx': 831.9, 'n': 3}, {'box': [708, 154, 760, 240], 'ink_ratio': 0.0, 'n_words': 6, 'title': None, 'kind': 'notes', 'words_per_mpx': 1341.7, 'n': 4}, {'box': [80, 306, 117, 397], 'ink_ratio': 0.0, 'n_words': 3, 'title': None, 'kind': 'notes', 'words_per_mpx': 891.0, 'n': 5}, {'box': [709, 246, 751, 325], 'ink_ratio': 0.327, 'n_words': 5, 'title': None, 'kind': 'detail', 'words_per_mpx': 1506.9, 'n': 6}, {'box': [87, 237, 124, 304], 'ink_ratio': 0.0, 'n_words': 3, 'title': None, 'kind': 'notes', 'words_per_mpx': 1210.2, 'n': 7}, {'box': [80, 152, 117, 210], 'ink_ratio': 0.0, 'n_words': 2, 'title': None, 'kind': 'detail', 'words_per_mpx': 932.0, 'n': 8}], 'notes': [[400, 3, 711, 314], [708, 154, 760, 240], [80, 306, 117, 397], [87, 237, 124, 304]], 'tables': [], 'complexity': 0.661}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'room': 14, 'footprint': 1}, 'route': 'cad'}
geometry: {'walls': 10, 'rooms': 14, 'note': 'construction sheet: walls read from line geometry of the main plan view (10 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None], [3, 'other', None], [4, 'other', None], [5, 'other', None], [6, 'other', None], [7, 'other', None], [8, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 3.66 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no individual rooms recognised (only colour-filled zones or none). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | The answer is 916.3 m². | amber | 0.23 | 0.0 |
| Which is the largest room and how big is it? | largest_room | The largest room is the colour module marked FLOOR COMMON AREA (280.5 m²). | amber | 0.01 | 0.0 |
| What is the overall length and width of the building? | overall_size | 45.83 m x 16.37 m. | amber | 0.02 | 0.0 |
| What is the scale of this drawing? | scale_info | 1 m = 3.7 px on this image (3 printed dimensions (139-10", 108-8", 137-4") matched to their dimension lines agree within 4%; printed dimension 133-10" matched to its dimension line; REJECTED: outside the 3.67 px/m agreement group). | amber | 0.01 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.01 | 0.0 |

## cache/stress/usace_p1_150dpi.png  (LLM off)
total 5.9 s, peak RSS 422 MB, steps {'profile_s': 0.45, 'analyze_s': 0.48, 'geometry_s': 0.2}
profile: {'width_px': 5100, 'height_px': 3300, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 31.08, 'line_density': 0.611, 'title_block': [3857, 73, 5024, 3226], 'border': [220, 73, 5024, 3226], 'views': [{'box': [529, 76, 3902, 3184], 'ink_ratio': 0.623, 'n_words': 415, 'title': 'SHEET TITLE COVER SHEET DRAWING INDEX CIVIL ABBREVIATIONS, LEGEND AND NOTES FUEL', 'kind': 'notes', 'words_per_mpx': 39.6, 'n': 1}], 'notes': [[529, 76, 3902, 3184]], 'tables': [], 'complexity': 0.706}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {}, 'route': 'cad'}
geometry: {'walls': 1, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (1 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 4.38 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.01 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.01 | 0.0 |

## cache/stress/usace_p13_150dpi.png  (LLM off)
total 4.9 s, peak RSS 424 MB, steps {'profile_s': 0.32, 'analyze_s': 0.53, 'geometry_s': 0.16}
profile: {'width_px': 5100, 'height_px': 3300, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 24.24, 'line_density': 0.39, 'title_block': [4759, 73, 5027, 3226], 'border': [223, 73, 5027, 3226], 'views': [{'box': [2397, 583, 4462, 2282], 'ink_ratio': 0.23, 'n_words': 128, 'title': 'BRIDGING CONT PLATE MASONRY (TYPICAL) SEE 12 FOR REQUIRED REINFORCING. CONT TYP ', 'kind': 'plan', 'words_per_mpx': 36.5, 'n': 1}, {'box': [459, 583, 1964, 2046], 'ink_ratio': 0.387, 'n_words': 70, 'title': 'FOUNDATION PLAN CONTROL BLDG TOS EL', 'kind': 'plan', 'words_per_mpx': 31.8, 'n': 2}, {'box': [912, 2416, 1884, 2939], 'ink_ratio': 0.0, 'n_words': 89, 'title': None, 'kind': 'notes', 'words_per_mpx': 175.1, 'n': 3}, {'box': [857, 2085, 1654, 2282], 'ink_ratio': 0.219, 'n_words': 7, 'title': 'FOUNDATION PLAN CONTROL BLDG SCALE', 'kind': 'detail', 'words_per_mpx': 44.4, 'n': 4}, {'box': [991, 1262, 1549, 1543], 'ink_ratio': 0.0, 'n_words': 16, 'title': None, 'kind': 'notes', 'words_per_mpx': 102.3, 'n': 5}, {'box': [4051, 2897, 4625, 3162], 'ink_ratio': 0.412, 'n_words': 12, 'title': None, 'kind': 'detail', 'words_per_mpx': 79.1, 'n': 6}], 'notes': [[912, 2416, 1884, 2939], [991, 1262, 1549, 1543]], 'tables': [], 'complexity': 0.75}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'region': 3, 'footprint': 1}, 'route': 'cad'}
geometry: {'walls': 12, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (12 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'floor_plan', 'line geometry'], [3, 'other', None], [4, 'other', None], [5, 'other', None], [6, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 3.3 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 6 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 6 views, main plan view read from line geometry). | grey | 0.01 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 6 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | 4.68 m x 3.49 m. | amber | 0.24 | 0.0 |
| What is the scale of this drawing? | scale_info | 1 m = 246.0 px on this image (scale note '1/2"=1'-0"' on ANSI D 34x22 (sheet size guessed from the aspect ratio); graphic scale bar labels -2, 0, 2, 4 ft; printed dimension 17-0" matched to its dimension line; REJECTED: outside the 246.01 px/m agreement group; printed dimension 4'-6" matched to its dimension line; REJECTED: outside the 246.01 px/m agreement group; printed dimension 14'-8 matched to its dimension line). | amber | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.01 | 0.0 |

## cache/stress/usace_p14_150dpi.png  (LLM off)
total 5.3 s, peak RSS 442 MB, steps {'profile_s': 0.35, 'analyze_s': 0.54, 'geometry_s': 0.1}
profile: {'width_px': 5100, 'height_px': 3300, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 28.94, 'line_density': 0.403, 'title_block': [4759, 73, 5027, 3226], 'border': [223, 73, 5027, 3226], 'views': [{'box': [271, 660, 3704, 2611], 'ink_ratio': 0.424, 'n_words': 227, 'title': 'TANKS SLOPE AND BY EQUAL TANK MANUFACTURER TANK MANUFACTURER GAL. (TYPICAL 4) TA', 'kind': 'plan', 'words_per_mpx': 33.9, 'n': 1}, {'box': [3685, 657, 4609, 1508], 'ink_ratio': 0.0, 'n_words': 144, 'title': None, 'kind': 'notes', 'words_per_mpx': 183.0, 'n': 2}, {'box': [4051, 3012, 4625, 3270], 'ink_ratio': 0.617, 'n_words': 11, 'title': None, 'kind': 'detail', 'words_per_mpx': 74.3, 'n': 3}, {'box': [1591, 2684, 2305, 2882], 'ink_ratio': 0.22, 'n_words': 8, 'title': None, 'kind': 'detail', 'words_per_mpx': 56.7, 'n': 4}], 'notes': [[3685, 657, 4609, 1508]], 'tables': [], 'complexity': 0.753}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'region': 11, 'footprint': 1}, 'route': 'cad'}
geometry: {'walls': 7, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (7 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None], [3, 'other', None], [4, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 3.67 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 4 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 4 views, main plan view read from line geometry). | grey | 0.01 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 4 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | 24.44 m x 13.63 m. | amber | 0.22 | 0.0 |
| What is the scale of this drawing? | scale_info | 1 m = 123.1 px on this image (scale note '1/4"=1'-0"' on ANSI D 34x22 (sheet size guessed from the aspect ratio); graphic scale bar labels -4, 0, 4, 8 ft; printed dimension [32-0"] matched to its dimension line; REJECTED: outside the 123.10 px/m agreement group). | amber | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.01 | 0.0 |

## cache/stress/usace_p33_150dpi.png  (LLM off)
total 7.3 s, peak RSS 421 MB, steps {'profile_s': 0.39, 'analyze_s': 0.48, 'geometry_s': 0.2}
profile: {'width_px': 5100, 'height_px': 3300, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 77.72, 'line_density': 0.315, 'title_block': [4625, 73, 5024, 3226], 'border': [220, 73, 5024, 3226], 'views': [{'box': [191, 29, 4670, 3258], 'ink_ratio': 0.304, 'n_words': 1156, 'title': 'IE EE DETAIL', 'kind': 'notes', 'words_per_mpx': 79.9, 'n': 1}], 'notes': [[191, 29, 4670, 3258]], 'tables': [], 'complexity': 0.875}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {}, 'route': 'cad'}
geometry: {'walls': 0, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (0 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 5.8 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.01 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.01 | 0.0 |

## cache/stress/usace_p13.pdf  (LLM off)
total 5.3 s, peak RSS 280 MB, steps {'profile_s': 1.02, 'analyze_s': 1.06}
profile: {'width_px': 5100, 'height_px': 3300, 'vector': True, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 12.24, 'line_density': 0.39, 'title_block': [4759, 73, 5027, 3226], 'border': [223, 73, 5027, 3226], 'views': [{'box': [2397, 583, 4462, 2282], 'ink_ratio': 0.23, 'n_words': 0, 'title': None, 'kind': 'plan', 'words_per_mpx': 0.0, 'n': 1}, {'box': [459, 583, 1964, 2046], 'ink_ratio': 0.387, 'n_words': 133, 'title': '8" REINFORCED MASONRY (TYPICAL) SEE SHEET S-002 MASONRY NOTE 12 FOR REQUIRED MAS', 'kind': 'notes', 'words_per_mpx': 60.4, 'n': 2}, {'box': [912, 2416, 1884, 2939], 'ink_ratio': 0.0, 'n_words': 0, 'title': None, 'kind': 'plan', 'words_per_mpx': 0.0, 'n': 3}, {'box': [857, 2085, 1654, 2282], 'ink_ratio': 0.219, 'n_words': 0, 'title': None, 'kind': 'detail', 'words_per_mpx': 0.0, 'n': 4}, {'box': [991, 1262, 1549, 1543], 'ink_ratio': 0.0, 'n_words': 0, 'title': None, 'kind': 'detail', 'words_per_mpx': 0.0, 'n': 5}, {'box': [4051, 2897, 4625, 3162], 'ink_ratio': 0.412, 'n_words': 0, 'title': None, 'kind': 'detail', 'words_per_mpx': 0.0, 'n': 6}], 'notes': [[459, 583, 1964, 2046]], 'tables': [], 'complexity': 0.68}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'room': 7, 'footprint': 1}, 'route': 'cad'}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | count_in_model | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 2.5 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no individual rooms recognised (only colour-filled zones or none). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.01 | 0.0 |
| Which is the largest room and how big is it? | largest_room | The largest room is the enclosed space on the left (24% of the area of all 7 rooms; set a real size for m²). | amber | 0.27 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | room_labelled | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.01 | 0.0 |
