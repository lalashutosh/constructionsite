# Stress test: single drawings (smoke, 15 drawings)

Read-only run against the live API at http://localhost:8000. Script: `/tmp/claude-501/stress-a/run_stress.py`, raw results: `/tmp/claude-501/stress-a/results.json`. Sample seed 42.

Assumptions: non-plan images (wikimedia, europeana, finna, habs) have no entries in questions.jsonl, so they got geometry and plan calls only. Free questions were judged by hand from the answer text (no image viewed).

## Drawings

- **cubicasa5k** `cubicasa5k/high_quality_architectural-3710.png` | geometry 200, 80.73s, walls 8, coords pixels, warnings: none | plan 200, 36.64s, building.type=dwelling
- **cubicasa5k** `cubicasa5k/high_quality-13137.png` | geometry 200, 0.0s, walls 2, coords pixels, warnings: View 2: reviewers disagree on what it is; check it | plan 200, 1.98s, building.type=dwelling
- **cubicasa5k** `cubicasa5k/colorful-2002.png` | geometry 200, 11.96s, walls 4, coords pixels, warnings: View 1 (floor plan): some walls may be wrong; View 2: reviewers disagree on what it is; check it | plan 200, 2.09s, building.type=dwelling
- **cubicasa5k** `cubicasa5k/high_quality_architectural-594.png` | geometry 200, 11.27s, walls 5, coords pixels, warnings: View 1 (floor plan): some walls may be wrong | plan 200, 3.82s, building.type=dwelling
- **swiss_dwellings** `swiss_dwellings/site3238_bldg4922_floor22515.pdf` | geometry 200, 0.17s, walls 13, coords dxf-render, warnings: none | plan 200, 0.03s, building.type=dwelling
- **swiss_dwellings** `swiss_dwellings/site285_bldg527_floor51568.pdf` | geometry 200, 0.45s, walls 25, coords dxf-render, warnings: none | plan 200, 0.03s, building.type=apartment_building
- **swiss_dwellings** `swiss_dwellings/site261_bldg473_floor1873.pdf` | geometry 200, 0.7s, walls 36, coords dxf-render, warnings: none | plan 200, 0.08s, building.type=apartment_building
- **ifc_models** `ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc` | geometry 200, 0.09s, walls 2, coords ifc-render, warnings: none | plan 200, 12.36s, building.type=apartment_building
- **ifc_models** `ifc_models/bsc-clinic_clinic-plumbing.ifc` | geometry 200, 0.38s, walls 0, coords ifc-render, warnings: none | plan 200, 8.85s, building.type=apartment_building
- **opening_design** `opening_design/Sports_Complex/Sheets - Current Set/A-801 - Door and Finish Schedules & Wall Types.pdf` | geometry 200, 5.75s, walls 0, coords pdf-render, warnings: View 1: reviewers disagree on what it is; check it; View 1 looks like a legend: no walls built there | plan 200, 13.02s, building.type=apartment_building
- **opening_design** `opening_design/CTR/Most Current Set/Full size sheets/A700 - SCHEDULES.pdf` | geometry 200, 6.05s, walls 0, coords pdf-render, warnings: View 1: reviewers disagree on what it is; check it | plan 200, 5.39s, building.type=apartment_building
- **wikimedia** `wikimedia/67128939.jpg` | geometry 200, 10.73s, walls 15, coords pixels, warnings: none | plan 200, 2.66s, building.type=dwelling
- **europeana** `europeana/0940415__nn5Vdgp.jpg` | geometry 200, 40.27s, walls 23, coords pixels, warnings: 5 floor plans on one sheet: shown as 5 floors | plan 200, 18.94s, building.type=dwelling
- **finna** `finna/hka.139877703731200_160499798085100.jpg` | geometry 200, 16.54s, walls 0, coords pixels, warnings: View 1 looks like a site plan: no walls built there | plan 200, 7.08s, building.type=dwelling
- **habs** `habs/ca3442_sheet_00008.jpg` | geometry 200, 42.0s, walls 0, coords pixels, warnings: View 1 looks like a section: no walls built there | plan 200, 33.76s, building.type=dwelling

## Summary

- Drawings: 15 (plan 11, non-plan 4)
- Numeric keyed questions: 49; OK 38; WRONG 11; accuracy 77.6% (38/49)
- Text questions recorded (no key check): 2
- Keyed WRONG with no numeric value (grey refusal): 2
- Free questions: OK 12, SILLY 2, REFUSED 8
- HTTP errors: 0; slow (>60 s): 1

## Questions

Verdict legend: OK / WRONG (keyed, count exact or 2 percent), RECORDED (text), SILLY / REFUSED (free questions, manual). Key column is the answer key.

| drawing | question | key | value | tier | reliability | verdict | s | answer_text |
|---|---|---|---|---|---|---|---|---|
| cubicasa5k/high_quality_architectural-3710.png | How many bathrooms or washrooms (e.g. KH, KPH, PH, PESUH, SH) are on this floor plan, not counting separate WC rooms? | 2 | 1 | amber | 0.81 | WRONG | 0.01 | There is 1 bathroom. |
| cubicasa5k/high_quality_architectural-3710.png | Kuinka monta kylpy- tai pesuhuonetta (esim. KH, KPH, PH, PESUH, SH) pohjapiirustuksessa on, erillisiä WC-tiloja lukuun ottamatta? | 2 | 1 | amber | 0.81 | WRONG | 0.01 | There is 1 bathroom. |
| cubicasa5k/high_quality_architectural-3710.png | How many showers and bathtubs are drawn on this floor plan in total? | 3 | 1 | amber | 0.784 | WRONG | 0.01 | There is 1 shower or bath. |
| cubicasa5k/high_quality_architectural-3710.png | How many windows are shown on this floor plan? | 16 | 15 | amber | 0.632 | WRONG | 0.01 | There are 15 windows. |
| cubicasa5k/high_quality_architectural-3710.png | Kuinka monta kerrosta pohjapiirustuksessa on esitetty? | 2 | 2 | amber | 0.947 | OK | 0.01 | There are 2 floors. |
| cubicasa5k/high_quality_architectural-3710.png | Which room is the largest? | - | living | amber | - | OK | 0.85 | The largest room is the living. [living] |
| cubicasa5k/high_quality_architectural-3710.png | What share of the floor area is bathrooms? | - | 0.1008 | amber | - | OK | 1.19 | The bathrooms are 10.1% of the rooms (by area). [10.1% of rooms] |
| cubicasa5k/high_quality-13137.png | How many floors (storeys) does this floor plan show? | 1 | 1 | amber | 0.953 | OK | 0.01 | There is 1 floor. |
| cubicasa5k/high_quality-13137.png | Kuinka monta WC-istuinta pohjapiirustukseen on piirretty? | 1 | 1 | amber | 0.952 | OK | 0.01 | There is 1 toilet. |
| cubicasa5k/high_quality-13137.png | Kuinka monta saunaa pohjapiirustuksessa on? | 0 | 1 | amber | 0.629 | WRONG | 0.01 | There is 1 sauna. |
| cubicasa5k/high_quality-13137.png | Kuinka monta keittiötä (myös keittokomerot, avo- ja tupakeittiöt sekä apukeittiöt) pohjapiirustuksessa on? | 1 | 1 | amber | 0.899 | OK | 0.01 | There is 1 kitchen. |
| cubicasa5k/high_quality-13137.png | How many balconies (parveke, including glazed balconies) are on this floor plan? | 1 | 1 | amber | 0.8 | OK | 0.01 | There is 1 balcony. |
| cubicasa5k/high_quality-13137.png | Which room is the largest? | - | OH | amber | - | OK | 1.05 | The largest room is the oh. [raw label OH printed as 'the oh'] |
| cubicasa5k/high_quality-13137.png | What share of the floor area is bathrooms? | - | 0.2536 | amber | - | SILLY | 1.01 | The bathrooms are 25.4% of the rooms (by area). [25.4% bathroom share for a 1-bathroom plan; denominator is 'rooms (by area)'] |
| cubicasa5k/colorful-2002.png | How many sinks and wash basins (kitchen and bathroom combined; a double-bowl sink counts as one) are drawn on this floor plan? | 2 | 2 | amber | 0.733 | OK | 0.01 | There are 2 sinks and basins. |
| cubicasa5k/colorful-2002.png | How many bathrooms or washrooms (e.g. KH, KPH, PH, PESUH, SH) are on this floor plan, not counting separate WC rooms? | 1 | 1 | amber | 0.851 | OK | 0.01 | There is 1 bathroom. |
| cubicasa5k/colorful-2002.png | How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a door leaf do not count. | 6 | 6 | amber | 0.715 | OK | 0.12 | There are 6 doors. |
| cubicasa5k/colorful-2002.png | Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on? | 2 | 2 | amber | 0.726 | OK | 0.01 | There are 2 bedrooms. |
| cubicasa5k/colorful-2002.png | How many floors (storeys) does this floor plan show? | 1 | 1 | amber | 0.955 | OK | 0.01 | There is 1 floor. |
| cubicasa5k/colorful-2002.png | Which room is the largest? | - | OH | amber | - | OK | 1.11 | The largest room is the oh. [raw label OH printed as 'the oh'] |
| cubicasa5k/colorful-2002.png | What share of the floor area is bathrooms? | - | 0.0885 | amber | - | OK | 1.44 | The bathrooms are 8.8% of the rooms (by area). [8.8%] |
| cubicasa5k/high_quality_architectural-594.png | Kuinka monta WC-istuinta pohjapiirustukseen on piirretty? | 2 | 0 | amber | 0.721 | WRONG | 0.01 | No toilets found on this drawing. |
| cubicasa5k/high_quality_architectural-594.png | How many saunas are on this floor plan? | 1 | 1 | amber | 0.792 | OK | 0.01 | There is 1 sauna. |
| cubicasa5k/high_quality_architectural-594.png | How many separate WC rooms (toilet rooms marked WC) are on this floor plan? | 1 | 0 | amber | 0.823 | WRONG | 0.01 | No separate WC rooms found on this drawing. |
| cubicasa5k/high_quality_architectural-594.png | How many kitchens (including kitchenettes, open kitchens and utility kitchens) are on this floor plan? | 1 | 1 | amber | 0.919 | OK | 0.01 | There is 1 kitchen. |
| cubicasa5k/high_quality_architectural-594.png | How many bathrooms or washrooms (e.g. KH, KPH, PH, PESUH, SH) are on this floor plan, not counting separate WC rooms? | 1 | 1 | amber | 0.834 | OK | 0.01 | There is 1 bathroom. |
| cubicasa5k/high_quality_architectural-594.png | Which room is the largest? | - | living | amber | - | OK | 1.36 | The largest room is the living. [living] |
| cubicasa5k/high_quality_architectural-594.png | What share of the floor area is bathrooms? | - | - | grey | - | SILLY | 3.82 | I can't answer this from the drawing: no bathroom recognised on this drawing. [says no bathroom recognised, but keyed Q on same drawing returned 'There is 1 bathroom.'] |
| swiss_dwellings/site3238_bldg4922_floor22515.pdf | Quante docce sono disegnate in questa pianta? | 2 | 2 | amber | 0.872 | OK | 0.0 | There are 2 showers. |
| swiss_dwellings/site3238_bldg4922_floor22515.pdf | How many rooms labelled 'Bagno' are there on this floor? | 2 | 2 | green | 0.809 | OK | 0.0 | There are 2 rooms with that label. |
| swiss_dwellings/site3238_bldg4922_floor22515.pdf | Quanti locali con la denominazione «Cucina» ci sono in questo piano? | 1 | 1 | green | 0.809 | OK | 0.0 | There is 1 room with that label. |
| swiss_dwellings/site3238_bldg4922_floor22515.pdf | What is the net floor area of room 1.06 ('Cucina') in m²? | 13.86 | 13.859 | amber | 0.693 | OK | 0.0 | The room's area is 13.9 m². |
| swiss_dwellings/site3238_bldg4922_floor22515.pdf | What is the net floor area of room 1.04 ('Corridoio') in m²? | 26.73 | 26.7336 | amber | 0.693 | OK | 0.0 | The room's area is 26.7 m². |
| swiss_dwellings/site3238_bldg4922_floor22515.pdf | Which room is the largest? | - | Stanza (1.07), 27.9 m² | amber | - | OK | 0.97 | The largest room is Stanza (1.07), 27.9 m². [largest room named with area] |
| swiss_dwellings/site3238_bldg4922_floor22515.pdf | What share of the floor area is bathrooms? | - | 0.0978 | amber | - | OK | 1.06 | The bathrooms are 9.8% of the rooms (by area). [share given] |
| swiss_dwellings/site285_bldg527_floor51568.pdf | How many toilets (WC) are drawn on this floor plan? | 4 | 4 | green | 0.878 | OK | 0.01 | There are 4 toilets. |
| swiss_dwellings/site285_bldg527_floor51568.pdf | What is the total net floor area in m² of all numbered indoor rooms on this floor (excluding balconies, loggias, terraces and other outdoor spaces, shafts and voids)? | 270.04 | 270.0439 | green | 0.673 | OK | 0.0 | The total net floor area is 270.0 m². |
| swiss_dwellings/site285_bldg527_floor51568.pdf | How many rooms labelled 'Cage d'escalier' are there on this floor? | 2 | 2 | green | 0.809 | OK | 0.0 | There are 2 rooms with that label. |
| swiss_dwellings/site285_bldg527_floor51568.pdf | How many rooms labelled 'Pièce' are there on this floor? | 1 | 1 | green | 0.809 | OK | 0.01 | There is 1 room with that label. |
| swiss_dwellings/site285_bldg527_floor51568.pdf | Quelle est la surface nette de la pièce 2.18 (« Chambre à coucher ») en m² ? | 16.15 | 16.1475 | green | 0.693 | OK | 0.01 | The room's area is 16.1 m². |
| swiss_dwellings/site285_bldg527_floor51568.pdf | Which room is the largest? | - | Séjour (2.19), 17.8 m² | amber | - | OK | 0.93 | The largest room is Séjour (2.19), 17.8 m². [largest room named with area] |
| swiss_dwellings/site285_bldg527_floor51568.pdf | What share of the floor area is bathrooms? | - | 0.0602 | amber | - | OK | 1.02 | The bathrooms are 6.0% of the rooms (by area). [share given] |
| swiss_dwellings/site261_bldg473_floor1873.pdf | What is the total net floor area in m² of all numbered indoor rooms on this floor (excluding balconies, loggias, terraces and other outdoor spaces, shafts and voids)? | 441.9 | 441.9012 | amber | 0.673 | OK | 0.01 | The total net floor area is 441.9 m². |
| swiss_dwellings/site261_bldg473_floor1873.pdf | Combien de pièces portant la désignation « Séjour/repas » y a-t-il à cet étage ? | 4 | 4 | green | 0.809 | OK | 0.01 | There are 4 rooms with that label. |
| swiss_dwellings/site261_bldg473_floor1873.pdf | What is the net floor area of room 1.06 ('Pièce') in m²? | 10.96 | 10.9637 | green | 0.693 | OK | 0.01 | The room's area is 11.0 m². |
| swiss_dwellings/site261_bldg473_floor1873.pdf | Combien de pièces portant la désignation « Séjour » y a-t-il à cet étage ? | 2 | 2 | green | 0.809 | OK | 0.01 | There are 2 rooms with that label. |
| swiss_dwellings/site261_bldg473_floor1873.pdf | Quelle est la surface nette totale en m² de toutes les pièces intérieures numérotées de cet étage (hors balcons, loggias, terrasses et autres espaces extérieurs, gaines et vides) ? | 441.9 | 441.9012 | amber | 0.673 | OK | 0.01 | The total net floor area is 441.9 m². |
| swiss_dwellings/site261_bldg473_floor1873.pdf | Which room is the largest? | - | Pièce (1.15), 25.3 m² | amber | - | OK | 0.85 | The largest room is Pièce (1.15), 25.3 m². [largest room named with area] |
| swiss_dwellings/site261_bldg473_floor1873.pdf | What share of the floor area is bathrooms? | - | 0.0523 | amber | - | OK | 0.95 | The bathrooms are 5.2% of the rooms (by area). [share given] |
| ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc | What is the net floor area of the room 'TUALETTRUUM (13-3)' on '2.korrus', in m²? | 5.83 | 5.8265 | green | 0.85 | OK | 0.13 | The room's net area is 5.8 m². |
| ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc | What is the net floor area of the room 'ESIK (75-3)' on '5.korrus', in m²? | 7.73 | 7.7338 | green | 0.85 | OK | 0.02 | The room's net area is 7.7 m². |
| ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc | Kui suur on ruumi „ESIK (45-2)“ netopõrandapind korrusel „3.korrus“ (m²)? | 5.1 | 5.096 | green | 0.85 | OK | 0.01 | The room's net area is 5.1 m². |
| ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc | What is the net floor area of the room 'KORIDOR (302)' on '3.korrus', in m²? | 78.4 | 78.4009 | green | 0.85 | OK | 0.01 | The room's net area is 78.4 m². |
| ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc | Kui suur on ruumi „VENTILATSIOONIRUUM (503)“ netopõrandapind korrusel „5.korrus“ (m²)? | 58.88 | 58.8765 | green | 0.85 | OK | 0.02 | The room's net area is 58.9 m². |
| ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc | Which room is the largest? | - | - | grey | - | REFUSED | 1.04 | I can't answer this from the drawing: no reader or query could answer this question from the drawing. [grey tier, no answer] |
| ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc | What share of the floor area is bathrooms? | - | - | grey | - | REFUSED | 1.08 | I can't answer this from the drawing: no reader or query could answer this question from the drawing. [grey tier, no answer] |
| ifc_models/bsc-clinic_clinic-plumbing.ifc | How many sanitary fixtures are there in the model 'Medical-Dental Clinic - plumbing'? | 119 | 119 | amber | 0.85 | OK | 0.05 | There are 119 sanitary in the model. |
| ifc_models/bsc-clinic_clinic-plumbing.ifc | Which room is the largest? | - | - | grey | - | REFUSED | 1.15 | I can't answer this from the drawing: no reader or query could answer this question from the drawing. [grey tier, no answer] |
| ifc_models/bsc-clinic_clinic-plumbing.ifc | What share of the floor area is bathrooms? | - | - | grey | - | REFUSED | 1.23 | I can't answer this from the drawing: no reader or query could answer this question from the drawing. [grey tier, no answer] |
| opening_design/Sports_Complex/Sheets - Current Set/A-801 - Door and Finish Schedules & Wall Types.pdf | On sheet A-801 of the Xcel Sports Complex drawings, what is the floor finish of room 113 (Aerobics & Yoga), and what does it mean? | F4 - resilient flooring (T.B.D.) | - | grey | - | RECORDED | 1.3 | I can't answer this from the drawing: this question needs something the query engine cannot express yet (floor finish material and its meaning are not expressible in the schema). [text answer, no numeric key check] |
| opening_design/Sports_Complex/Sheets - Current Set/A-801 - Door and Finish Schedules & Wall Types.pdf | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule carry note C (card reader)? | 5 | 5 | amber | 0.73 | OK | 0.1 | There are 5 doors. |
| opening_design/Sports_Complex/Sheets - Current Set/A-801 - Door and Finish Schedules & Wall Types.pdf | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are door type B2 (double aluminium door with glazing)? | 10 | 10 | amber | 0.807 | OK | 0.05 | There are 10 doors. |
| opening_design/Sports_Complex/Sheets - Current Set/A-801 - Door and Finish Schedules & Wall Types.pdf | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are door type A2 (double swing door)? | 1 | 1 | amber | 0.807 | OK | 0.03 | There is 1 door. |
| opening_design/Sports_Complex/Sheets - Current Set/A-801 - Door and Finish Schedules & Wall Types.pdf | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are 7'-0" high? | 13 | 13 | amber | 0.85 | OK | 0.01 | There are 13 doors. |
| opening_design/Sports_Complex/Sheets - Current Set/A-801 - Door and Finish Schedules & Wall Types.pdf | Which room is the largest? | - | - | grey | - | REFUSED | 0.9 | I can't answer this from the drawing: no reader or query could answer this question from the drawing. [grey tier, no answer] |
| opening_design/Sports_Complex/Sheets - Current Set/A-801 - Door and Finish Schedules & Wall Types.pdf | What share of the floor area is bathrooms? | - | - | grey | - | REFUSED | 1.59 | I can't answer this from the drawing: no reader or query could answer this question from the drawing. [grey tier, no answer] |
| opening_design/CTR/Most Current Set/Full size sheets/A700 - SCHEDULES.pdf | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), what fire rating is scheduled for the unit doors (type U01)? | 20 MIN. | - | grey | - | RECORDED | 2.08 | I can't answer this from the drawing: this question needs something the query engine cannot express yet (fire rating is not an attribute the schema can express). [text answer, no numeric key check] |
| opening_design/CTR/Most Current Set/Full size sheets/A700 - SCHEDULES.pdf | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many Marvin Essential sliding patio doors are scheduled in total? | 27 | - | grey | - | WRONG | 1.07 | I can't answer this from the drawing: no reader or query could answer this question from the drawing. |
| opening_design/CTR/Most Current Set/Full size sheets/A700 - SCHEDULES.pdf | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many door leaves of the types whose description starts with 'SWING' are scheduled? | 418 | 2 | amber | 0.807 | WRONG | 1.17 | There are 2 door. |
| opening_design/CTR/Most Current Set/Full size sheets/A700 - SCHEDULES.pdf | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many Marvin Essential sliding patio doors are scheduled on the 3rd floor? | 15 | 0 | amber | 0.712 | WRONG | 1.01 | No marvin found on this drawing. |
| opening_design/CTR/Most Current Set/Full size sheets/A700 - SCHEDULES.pdf | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many windows (window assemblies) are listed in the window schedule in total? | 235 | - | grey | - | WRONG | 0.96 | I can't answer this from the drawing: no reader or query could answer this question from the drawing. |
| opening_design/CTR/Most Current Set/Full size sheets/A700 - SCHEDULES.pdf | Which room is the largest? | - | - | grey | - | REFUSED | 1.14 | I can't answer this from the drawing: no reader or query could answer this question from the drawing. [grey tier, no answer] |
| opening_design/CTR/Most Current Set/Full size sheets/A700 - SCHEDULES.pdf | What share of the floor area is bathrooms? | - | - | grey | - | REFUSED | 0.98 | I can't answer this from the drawing: no reader or query could answer this question from the drawing. [grey tier, no answer] |

## Errors (HTTP != 200 or exception)

- none

## Slow calls (>60 s)

- geometry data/cubicasa5k/high_quality_architectural-3710.png -> HTTP 200 in 80.73s
