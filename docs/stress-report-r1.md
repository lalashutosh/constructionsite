# Stress report (big construction sheets)

## cache/stress/stoa1.png  (LLM off)
total 2.5 s, peak RSS 184 MB, steps {'profile_s': 0.11, 'analyze_s': 0.06, 'geometry_s': 0.01}
profile: {'width_px': 768, 'height_px': 497, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 584.23, 'line_density': 0.47, 'title_block': [708, 0, 767, 496], 'border': [0, 0, 767, 496], 'views': [{'box': [21, 4, 713, 489], 'ink_ratio': 0.452, 'n_words': 219, 'title': None, 'kind': 'plan', 'words_per_mpx': 652.5, 'n': 1}, {'box': [588, 164, 696, 274], 'ink_ratio': 0.0, 'n_words': 42, 'title': None, 'kind': 'notes', 'words_per_mpx': 3535.4, 'n': 2}, {'box': [517, 58, 597, 147], 'ink_ratio': 0.0, 'n_words': 10, 'title': None, 'kind': 'notes', 'words_per_mpx': 1404.5, 'n': 3}, {'box': [498, 230, 571, 296], 'ink_ratio': 0.0, 'n_words': 6, 'title': None, 'kind': 'notes', 'words_per_mpx': 1245.3, 'n': 4}, {'box': [407, 38, 491, 82], 'ink_ratio': 0.0, 'n_words': 6, 'title': None, 'kind': 'notes', 'words_per_mpx': 1623.4, 'n': 5}, {'box': [134, 118, 186, 185], 'ink_ratio': 0.0, 'n_words': 3, 'title': None, 'kind': 'notes', 'words_per_mpx': 861.1, 'n': 6}, {'box': [100, 299, 156, 340], 'ink_ratio': 0.0, 'n_words': 3, 'title': None, 'kind': 'notes', 'words_per_mpx': 1306.6, 'n': 7}, {'box': [374, 421, 447, 452], 'ink_ratio': 0.0, 'n_words': 2, 'title': None, 'kind': 'detail', 'words_per_mpx': 883.8, 'n': 8}, {'box': [97, 154, 150, 193], 'ink_ratio': 0.0, 'n_words': 1, 'title': None, 'kind': 'detail', 'words_per_mpx': 483.8, 'n': 9}], 'notes': [[588, 164, 696, 274], [517, 58, 597, 147], [498, 230, 571, 296], [407, 38, 491, 82], [134, 118, 186, 185], [100, 299, 156, 340]], 'tables': [], 'complexity': 0.647}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'footprint': 1}, 'route': 'cad'}
geometry: {'walls': 6, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (6 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None], [3, 'other', None], [4, 'other', None], [5, 'other', None], [6, 'other', None], [7, 'other', None], [8, 'other', None], [9, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 2.08 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 9 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 9 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 9 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |

## cache/stress/stoa2.png  (LLM off)
total 1.7 s, peak RSS 185 MB, steps {'profile_s': 0.09, 'analyze_s': 0.06, 'geometry_s': 0.01}
profile: {'width_px': 768, 'height_px': 542, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 449.24, 'line_density': 0.348, 'title_block': [701, 0, 739, 541], 'border': None, 'views': [{'box': [11, 7, 703, 462], 'ink_ratio': 0.402, 'n_words': 165, 'title': 'FOUNDATION PLAN SLAB', 'kind': 'plan', 'words_per_mpx': 524.0, 'n': 1}, {'box': [60, 498, 691, 529], 'ink_ratio': 0.504, 'n_words': 5, 'title': 'FOUNDATION PLAN SLAB VE AND', 'kind': 'detail', 'words_per_mpx': 255.6, 'n': 2}, {'box': [87, 430, 356, 494], 'ink_ratio': 0.0, 'n_words': 43, 'title': 'FOUNDATION PLAN SLAB', 'kind': 'notes', 'words_per_mpx': 2497.7, 'n': 3}, {'box': [444, 469, 551, 502], 'ink_ratio': 0.366, 'n_words': 4, 'title': None, 'kind': 'detail', 'words_per_mpx': 1132.8, 'n': 4}, {'box': [618, 75, 695, 116], 'ink_ratio': 0.0, 'n_words': 8, 'title': None, 'kind': 'notes', 'words_per_mpx': 2534.1, 'n': 5}], 'notes': [[87, 430, 356, 494], [618, 75, 695, 116]], 'tables': [], 'complexity': 0.581}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'region': 1, 'footprint': 1}, 'route': 'cad'}
geometry: {'walls': 8, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (8 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None], [3, 'other', None], [4, 'other', None], [5, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 1.27 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 5 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 5 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 5 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |

## cache/stress/stoa3.png  (LLM off)
total 1.9 s, peak RSS 191 MB, steps {'profile_s': 0.11, 'analyze_s': 0.08, 'geometry_s': 0.01}
profile: {'width_px': 768, 'height_px': 497, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 657.59, 'line_density': 0.068, 'title_block': None, 'border': None, 'views': [{'box': [135, 55, 545, 454], 'ink_ratio': 0.067, 'n_words': 64, 'title': 'THE IN AS COMMUNICATIONS) DATA THE ROOM INTERACTIVE NOT ALL A AND COES INDICA) T', 'kind': 'plan', 'words_per_mpx': 391.2, 'n': 1}, {'box': [400, 3, 711, 314], 'ink_ratio': 0.038, 'n_words': 182, 'title': 'ROOM PLAN EXTERIOR I TAL WING', 'kind': 'notes', 'words_per_mpx': 1881.7, 'n': 2}, {'box': [571, 338, 760, 497], 'ink_ratio': 0.172, 'n_words': 25, 'title': 'KEY PLAN CONSTRUCTION SECOND FLOOR PLAN W FOR', 'kind': 'key_plan', 'words_per_mpx': 831.9, 'n': 3}, {'box': [708, 154, 760, 240], 'ink_ratio': 0.0, 'n_words': 6, 'title': None, 'kind': 'notes', 'words_per_mpx': 1341.7, 'n': 4}, {'box': [80, 306, 117, 397], 'ink_ratio': 0.0, 'n_words': 3, 'title': None, 'kind': 'notes', 'words_per_mpx': 891.0, 'n': 5}, {'box': [709, 246, 751, 325], 'ink_ratio': 0.327, 'n_words': 5, 'title': None, 'kind': 'detail', 'words_per_mpx': 1506.9, 'n': 6}, {'box': [87, 237, 124, 304], 'ink_ratio': 0.0, 'n_words': 3, 'title': None, 'kind': 'notes', 'words_per_mpx': 1210.2, 'n': 7}, {'box': [80, 152, 117, 210], 'ink_ratio': 0.0, 'n_words': 2, 'title': None, 'kind': 'detail', 'words_per_mpx': 932.0, 'n': 8}], 'notes': [[400, 3, 711, 314], [708, 154, 760, 240], [80, 306, 117, 397], [87, 237, 124, 304]], 'tables': [], 'complexity': 0.661}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'zone': 7, 'footprint': 1}, 'route': 'cad'}
geometry: {'walls': 10, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (10 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None], [3, 'other', None], [4, 'other', None], [5, 'other', None], [6, 'other', None], [7, 'other', None], [8, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 1.36 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 8 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | The answer is 2261.8 m². | amber | 0.13 | 0.0 |
| Which is the largest room and how big is it? | largest_room | The largest room and zone is the colour module marked DORMITORY 3 at the bottom left (597.0 m²). | amber | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | 45.83 m x 16.37 m. | amber | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | 1 m = 3.7 px on this image (3 printed dimensions (139-10", 108-8", 137-4") matched to their dimension lines agree within 4%; printed dimension 133-10" matched to its dimension line; REJECTED: outside the 3.67 px/m agreement group). | amber | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |

## cache/stress/usace_p1_150dpi.png  (LLM off)
total 2.5 s, peak RSS 421 MB, steps {'profile_s': 0.24, 'analyze_s': 0.24, 'geometry_s': 0.1}
profile: {'width_px': 5100, 'height_px': 3300, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 31.08, 'line_density': 0.611, 'title_block': [3857, 73, 5024, 3226], 'border': [220, 73, 5024, 3226], 'views': [{'box': [529, 76, 3902, 3184], 'ink_ratio': 0.623, 'n_words': 415, 'title': 'SHEET TITLE COVER SHEET DRAWING INDEX CIVIL ABBREVIATIONS, LEGEND AND NOTES FUEL', 'kind': 'notes', 'words_per_mpx': 39.6, 'n': 1}], 'notes': [[529, 76, 3902, 3184]], 'tables': [], 'complexity': 0.706}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {}, 'route': 'cad'}
geometry: {'walls': 1, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (1 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 1.72 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |

## cache/stress/usace_p1.pdf  (LLM off)
total 1.9 s, peak RSS 226 MB, steps {'profile_s': 0.35, 'analyze_s': 0.32}
profile: {'width_px': 2000, 'height_px': 1295, 'vector': True, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 172.97, 'line_density': 0.608, 'title_block': [1512, 28, 1971, 1265], 'border': [85, 28, 1971, 1265], 'views': [{'box': [208, 29, 1530, 1249], 'ink_ratio': 0.613, 'n_words': 437, 'title': 'SHEET NO. DRAWING INDEX SHEET TITLE COVER SHEET COV DRAWING INDEX G-101 REVISION', 'kind': 'notes', 'words_per_mpx': 270.8, 'n': 1}, {'box': [68, 10, 111, 1282], 'ink_ratio': 4.113, 'n_words': 0, 'title': None, 'kind': 'plan', 'words_per_mpx': 0.0, 'n': 2}], 'notes': [[208, 29, 1530, 1249]], 'tables': [], 'complexity': 0.626}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'footprint': 1}, 'route': 'cad'}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | count_in_model | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 1.01 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 2 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 2 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 2 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | room_labelled | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |

## cache/stress/usace_p13_150dpi.png  (LLM off)
total 2.5 s, peak RSS 422 MB, steps {'profile_s': 0.32, 'analyze_s': 0.28, 'geometry_s': 0.1}
profile: {'width_px': 5100, 'height_px': 3300, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 24.24, 'line_density': 0.39, 'title_block': [4759, 73, 5027, 3226], 'border': [223, 73, 5027, 3226], 'views': [{'box': [2397, 583, 4462, 2282], 'ink_ratio': 0.23, 'n_words': 128, 'title': 'BRIDGING CONT PLATE MASONRY (TYPICAL) SEE 12 FOR REQUIRED REINFORCING. CONT TYP ', 'kind': 'plan', 'words_per_mpx': 36.5, 'n': 1}, {'box': [459, 583, 1964, 2046], 'ink_ratio': 0.387, 'n_words': 70, 'title': 'FOUNDATION PLAN CONTROL BLDG TOS EL', 'kind': 'plan', 'words_per_mpx': 31.8, 'n': 2}, {'box': [912, 2416, 1884, 2939], 'ink_ratio': 0.0, 'n_words': 89, 'title': None, 'kind': 'notes', 'words_per_mpx': 175.1, 'n': 3}, {'box': [857, 2085, 1654, 2282], 'ink_ratio': 0.219, 'n_words': 7, 'title': 'FOUNDATION PLAN CONTROL BLDG SCALE', 'kind': 'detail', 'words_per_mpx': 44.4, 'n': 4}, {'box': [991, 1262, 1549, 1543], 'ink_ratio': 0.0, 'n_words': 16, 'title': None, 'kind': 'notes', 'words_per_mpx': 102.3, 'n': 5}, {'box': [4051, 2897, 4625, 3162], 'ink_ratio': 0.412, 'n_words': 12, 'title': None, 'kind': 'detail', 'words_per_mpx': 79.1, 'n': 6}], 'notes': [[912, 2416, 1884, 2939], [991, 1262, 1549, 1543]], 'tables': [], 'complexity': 0.75}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'room': 3, 'footprint': 2}, 'route': 'cad'}
geometry: {'walls': 12, 'rooms': 3, 'note': 'construction sheet: walls read from line geometry of the main plan view (12 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'floor_plan', 'line geometry'], [3, 'other', None], [4, 'other', None], [5, 'other', None], [6, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 1.53 | 0.0 |
| How many rooms are there? | rooms_count | There are 3 rooms. | amber | 0.09 | 0.0 |
| What is the total area of all rooms? | total_room_area | The answer is 1.0 m². | amber | 0.01 | 0.0 |
| Which is the largest room and how big is it? | largest_room | The largest room and zone is the enclosed space on the right (0.4 m²). | amber | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | 4.68 m x 3.49 m. | amber | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | 1 m = 246.0 px on this image (scale note '1/2"=1'-0"' on ANSI D 34x22 (sheet size guessed from the aspect ratio); graphic scale bar labels -2, 0, 2, 4 ft; printed dimension 17-0" matched to its dimension line; REJECTED: outside the 246.01 px/m agreement group; printed dimension 4'-6" matched to its dimension line; REJECTED: outside the 246.01 px/m agreement group; printed dimension 14'-8 matched to its dimension line). | amber | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |

## cache/stress/usace_p13.pdf  (LLM off)
total 1.8 s, peak RSS 246 MB, steps {'profile_s': 0.25, 'analyze_s': 0.18}
profile: {'width_px': 2000, 'height_px': 1295, 'vector': True, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 79.54, 'line_density': 0.39, 'title_block': [1865, 28, 1971, 1265], 'border': [86, 28, 1971, 1265], 'views': [{'box': [940, 229, 1750, 895], 'ink_ratio': 0.237, 'n_words': 42, 'title': '12K JOIST 8" REINFORCED MASONRY (TYPICAL) SEE SHEET S-002 MASONRY NOTE 12 FOR RE', 'kind': 'plan', 'words_per_mpx': 77.8, 'n': 1}, {'box': [180, 229, 770, 802], 'ink_ratio': 0.355, 'n_words': 14, 'title': '0\'-0" TYP CONTROL BLDG FOUNDATION PLAN', 'kind': 'plan', 'words_per_mpx': 41.4, 'n': 2}, {'box': [358, 948, 739, 1152], 'ink_ratio': 0.0, 'n_words': 55, 'title': None, 'kind': 'notes', 'words_per_mpx': 703.7, 'n': 3}, {'box': [335, 818, 650, 895], 'ink_ratio': 0.183, 'n_words': 4, 'title': 'CONTROL BLDG FOUNDATION PLAN', 'kind': 'detail', 'words_per_mpx': 163.9, 'n': 4}, {'box': [389, 494, 608, 605], 'ink_ratio': 0.0, 'n_words': 9, 'title': None, 'kind': 'notes', 'words_per_mpx': 369.8, 'n': 5}, {'box': [1589, 1136, 1814, 1240], 'ink_ratio': 0.451, 'n_words': 10, 'title': None, 'kind': 'detail', 'words_per_mpx': 428.4, 'n': 6}], 'notes': [[358, 948, 739, 1152], [389, 494, 608, 605]], 'tables': [], 'complexity': 0.716}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'room': 5, 'footprint': 2}, 'route': 'cad'}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | count_in_model | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 1.04 | 0.0 |
| How many rooms are there? | rooms_count | There are 5 rooms. | amber | 0.11 | 0.0 |
| What is the total area of all rooms? | total_room_area | The answer is 17.5 m². | amber | 0.01 | 0.0 |
| Which is the largest room and how big is it? | largest_room | The largest room and zone is the enclosed space marked SLAB-ON-GRADE TOS (14.3 m²). | amber | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | 5.79 m x 4.84 m. | amber | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | 1 m = 96.5 px on this image (scale note '1/2"=1'-0"' on ANSI D 34x22; graphic scale bar labels -2, 0, 2, 4 ft). | amber | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | room_labelled | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |

## cache/stress/usace_p14_150dpi.png  (LLM off)
total 2.6 s, peak RSS 442 MB, steps {'profile_s': 0.32, 'analyze_s': 0.28, 'geometry_s': 0.05}
profile: {'width_px': 5100, 'height_px': 3300, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 28.94, 'line_density': 0.403, 'title_block': [4759, 73, 5027, 3226], 'border': [223, 73, 5027, 3226], 'views': [{'box': [271, 660, 3704, 2611], 'ink_ratio': 0.424, 'n_words': 227, 'title': 'TANKS SLOPE AND BY EQUAL TANK MANUFACTURER TANK MANUFACTURER GAL. (TYPICAL 4) TA', 'kind': 'plan', 'words_per_mpx': 33.9, 'n': 1}, {'box': [3685, 657, 4609, 1508], 'ink_ratio': 0.0, 'n_words': 144, 'title': None, 'kind': 'notes', 'words_per_mpx': 183.0, 'n': 2}, {'box': [4051, 3012, 4625, 3270], 'ink_ratio': 0.617, 'n_words': 11, 'title': None, 'kind': 'detail', 'words_per_mpx': 74.3, 'n': 3}, {'box': [1591, 2684, 2305, 2882], 'ink_ratio': 0.22, 'n_words': 8, 'title': None, 'kind': 'detail', 'words_per_mpx': 56.7, 'n': 4}], 'notes': [[3685, 657, 4609, 1508]], 'tables': [], 'complexity': 0.753}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'room': 11, 'footprint': 1}, 'route': 'cad'}
geometry: {'walls': 7, 'rooms': 11, 'note': 'construction sheet: walls read from line geometry of the main plan view (7 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'floor_plan', 'line geometry'], [2, 'other', None], [3, 'other', None], [4, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 1.71 | 0.0 |
| How many rooms are there? | rooms_count | There are 11 rooms. | amber | 0.09 | 0.0 |
| What is the total area of all rooms? | total_room_area | The answer is 121.2 m². | amber | 0.0 | 0.0 |
| Which is the largest room and how big is it? | largest_room | The largest room and zone is the enclosed space at the bottom centre (28.8 m²). | amber | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | 24.44 m x 13.63 m. | amber | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | 1 m = 123.1 px on this image (scale note '1/4"=1'-0"' on ANSI D 34x22 (sheet size guessed from the aspect ratio); graphic scale bar labels -4, 0, 4, 8 ft; printed dimension [32-0"] matched to its dimension line; REJECTED: outside the 123.10 px/m agreement group). | amber | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |

## cache/stress/usace_p14.pdf  (LLM off)
total 1.8 s, peak RSS 246 MB, steps {'profile_s': 0.26, 'analyze_s': 0.26}
profile: {'width_px': 2000, 'height_px': 1295, 'vector': True, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 98.46, 'line_density': 0.441, 'title_block': [1865, 28, 1971, 1265], 'border': [86, 28, 1971, 1265], 'views': [{'box': [106, 259, 1454, 1025], 'ink_ratio': 0.489, 'n_words': 38, 'title': 'OF TANKS AND FOUND. TANK 12,000 GAL. (TYPICAL 4) CJ OR DCJ 6/S-501 TANK PAD FOUN', 'kind': 'plan', 'words_per_mpx': 36.8, 'n': 1}, {'box': [1444, 258, 1808, 591], 'ink_ratio': 0.0, 'n_words': 128, 'title': None, 'kind': 'notes', 'words_per_mpx': 1054.4, 'n': 2}, {'box': [1589, 1180, 1815, 1282], 'ink_ratio': 0.66, 'n_words': 2, 'title': None, 'kind': 'detail', 'words_per_mpx': 86.2, 'n': 3}, {'box': [624, 1052, 904, 1131], 'ink_ratio': 0.175, 'n_words': 4, 'title': 'TANK PAD FOUNDATION PLAN', 'kind': 'detail', 'words_per_mpx': 181.4, 'n': 4}], 'notes': [[1444, 258, 1808, 591]], 'tables': [], 'complexity': 0.676}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {'room': 41, 'footprint': 1}, 'route': 'cad'}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | count_in_model | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 1.01 | 0.0 |
| How many rooms are there? | rooms_count | There are 41 rooms. | amber | 0.1 | 0.0 |
| What is the total area of all rooms? | total_room_area | The answer is 258.5 m². | amber | 0.01 | 0.0 |
| Which is the largest room and how big is it? | largest_room | The largest room and zone is the enclosed space marked DCJ at the top centre (49.7 m²). | amber | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | 24.50 m x 13.75 m. | amber | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | 1 m = 48.2 px on this image (scale note '1/4"=1'-0"' on ANSI D 34x22; graphic scale bar labels -4, 0, 4, 8 ft; printed dimension 5'-10" matched to its dimension line). | amber | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | room_labelled | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |

## cache/stress/usace_p33_150dpi.png  (LLM off)
total 3.4 s, peak RSS 421 MB, steps {'profile_s': 0.3, 'analyze_s': 0.31, 'geometry_s': 0.15}
profile: {'width_px': 5100, 'height_px': 3300, 'vector': False, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 77.72, 'line_density': 0.315, 'title_block': [4625, 73, 5024, 3226], 'border': [220, 73, 5024, 3226], 'views': [{'box': [191, 29, 4670, 3258], 'ink_ratio': 0.304, 'n_words': 1156, 'title': 'IE EE DETAIL', 'kind': 'notes', 'words_per_mpx': 79.9, 'n': 1}], 'notes': [[191, 29, 4670, 3258]], 'tables': [], 'complexity': 0.875}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {}, 'route': 'cad'}
geometry: {'walls': 0, 'rooms': 0, 'note': 'construction sheet: walls read from line geometry of the main plan view (0 pieces); title block, notes, schedules and dimension chains excluded', 'views': [[1, 'other', None]]}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | doors | I can't answer this from the drawing: doors are not read on construction sheets yet: the symbol detectors are trained on small residential scans, so a '0' would be a guess. | grey | 2.41 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | unknown | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |

## cache/stress/usace_p33.pdf  (LLM off)
total 2.1 s, peak RSS 234 MB, steps {'profile_s': 0.41, 'analyze_s': 0.46}
profile: {'width_px': 2000, 'height_px': 1295, 'vector': True, 'sheet_type': 'cad_sheet', 'route': 'line_geometry', 'text_density': 278.76, 'line_density': 0.337, 'title_block': [1814, 28, 1971, 1265], 'border': [85, 28, 1971, 1265], 'views': [{'box': [68, 10, 1831, 1282], 'ink_ratio': 0.338, 'n_words': 712, 'title': 'E-85 STORAGE TANK (12,000 GALLON CAPACITY) GASOLINE STORAGE TANK (12,000 GALLON ', 'kind': 'notes', 'words_per_mpx': 317.2, 'n': 1}], 'notes': [[68, 10, 1831, 1282]], 'tables': [], 'complexity': 0.601}
facts: {'sheet_type': 'floor_plan', 'legible': True, 'elements': {}, 'route': 'cad'}

| question | intent | answer | tier | s | $ |
|---|---|---|---|---|---|
| How many doors are there? | count_in_model | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.98 | 0.0 |
| How many rooms are there? | rooms_count | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the total area of all rooms? | total_room_area | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| Which is the largest room and how big is it? | largest_room | I can't answer this from the drawing: no enclosed rooms or colour-filled zones were recognised on this sheet (cad sheet: 1 views, main plan view read from line geometry). | grey | 0.0 | 0.0 |
| What is the overall length and width of the building? | overall_size | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| What is the scale of this drawing? | scale_info | I can't answer this from the drawing: the drawing's scale is not known yet: give one real length (a printed dimension or a known door width). | grey | 0.0 | 0.0 |
| How many dorm rooms are on this floor? | room_labelled | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | 0.0 | 0.0 |
