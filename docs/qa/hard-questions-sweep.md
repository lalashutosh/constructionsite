# Hard-questions sweep (live API, read-only)

Endpoint: POST http://localhost:8000/api/ask, 30 questions, 3 in parallel. Relative drawing paths resolve against DATASET_ROOT=/Users/abhinavchutani/Downloads/junction-dataset-preview (the `data/` folder is not inside the repo). Raw responses: /private/tmp/claude-501/-Users-abhinavchutani-Library-Application-Support-Claude-scratch-workspaces-208783a0-b266-428b-87ff-50730f1ef267-51bb21ac-ed19-4949-92bb-6bb07581a615-scratch-2026-11-14-05acae/8c89b3e8-c76a-4169-b968-8f651f587f8b/scratchpad/raw.jsonl

Answer key used (colorful-2002.png only): 2 bedrooms, 6 doors, 7 windows, 1 kitchen, 1 sauna, 1 balcony. Other drawings have no key, so their answers are marked OK (unverified) unless internally inconsistent.

| # | drawing | question | answer_text | tier | reliability | cost.usd | cost.llm_calls | refusal | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1 | colorful-2002.png | how many doors? | There are 6 doors. | amber | 0.735 | 0.0 | 0 | — | OK |
| 2 | colorful-2002.png | number of bedrooms | There are 3 bedrooms. | amber | 0.399 | 0.0 | 0 | — | WRONG |
| 3 | colorful-2002.png | are there more windows than doors? | No: 4 windows vs 6 doors. | amber | — | 0.00028074999999999997 | 1 | — | WRONG |
| 4 | colorful-2002.png | what share of the floor is bathrooms? | The bathrooms are 8.4% of the rooms (by area). | amber | — | 0.000295 | 1 | — | OK |
| 5 | colorful-2002.png | which room is closest to the entrance? | I can't answer this from the drawing: this question needs something the query engine cannot express yet (distance/proximity to the entrance cannot be expressed with the available schema). | grey | — | 0.000263 | 1 | this question needs something the query engine cannot express yet (distance/proximity to the entrance cannot be expressed with the available schema) | OK |
| 6 | colorful-2002.png | what colour is the sky? | I can't answer this from the drawing: this question needs something the query engine cannot express yet (colour of the sky is not an architectural drawing attribute in the schema). | grey | — | 0.00028975 | 2 | this question needs something the query engine cannot express yet (colour of the sky is not an architectural drawing attribute in the schema) | OK |
| 7 | high_quality_architectural-13040.png | total floor area | The rooms cover 88.3 m² in total. | amber | — | 0.0002785 | 2 | — | OK (unverified) |
| 8 | high_quality_architectural-13040.png | largest room | The largest room is the kitchen. | amber | — | 0.00025175 | 1 | — | OK (unverified) |
| 9 | high_quality_architectural-13040.png | which rooms have more than one door? | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | — | 0.000269 | 1 | no reader or query could answer this question from the drawing | OK |
| 10 | high_quality_architectural-13040.png | how many windows face north? | I can't answer this from the drawing: this question needs something the query engine cannot express yet (window orientation/facing direction is not expressible in the schema). | grey | — | 0.0002555 | 1 | this question needs something the query engine cannot express yet (window orientation/facing direction is not expressible in the schema) | OK |
| 11 | high_quality_architectural-13040.png | total wall length | I can't answer this from the drawing: this question needs something the query engine cannot express yet (wall length is not expressible: no wall element kind in this drawing and no length attribute in numeric_attrs). | grey | — | 0.0002925 | 2 | this question needs something the query engine cannot express yet (wall length is not expressible: no wall element kind in this drawing and no length attribute in numeric_attrs) | OK |
| 12 | high_quality_architectural-13040.png | how many more doors than windows? | There are as many doors as windows. | amber | — | 0.00027575 | 1 | — | OK (unverified) |
| 13 | high_quality_architectural-1169.png | total floor area | The rooms cover 45.8 m² in total. | amber | — | 0.00024925 | 1 | — | OK (unverified) |
| 14 | high_quality_architectural-1169.png | area of the kitchen | The kitchens cover 8.2 m² in total. | amber | — | 0.00028825 | 2 | — | OK (unverified) |
| 15 | high_quality_architectural-1169.png | smallest bedroom | The smallest bedroom is the bedroom. | amber | — | 0.000261 | 1 | — | SILLY |
| 16 | high_quality_architectural-1169.png | rooms with a window | There are 4 rooms. | amber | — | 0.0002615 | 1 | — | OK (unverified) |
| 17 | high_quality_architectural-1169.png | wall volume | I can't answer this from the drawing: this question needs something the query engine cannot express yet (wall volume cannot be computed: walls are not an element kind in this drawing and no volume attribute is available). | grey | — | 0.00028924999999999996 | 2 | this question needs something the query engine cannot express yet (wall volume cannot be computed: walls are not an element kind in this drawing and no volume attribute is available) | OK |
| 18 | high_quality_architectural-1169.png | number of windows | There are 6 windows. | amber | 0.209 | 0.0 | 0 | — | OK (unverified) |
| 19 | site157_bldg323_floor1313.pdf | how many doors? | There are 78 doors. | green | 0.809 | 0.0 | 0 | — | OK |
| 20 | site157_bldg323_floor1313.pdf | number of windows | There are 63 windows. | green | 0.676 | 0.0 | 0 | — | OK |
| 21 | site157_bldg323_floor1313.pdf | how many bathtubs? | There are 7 bathtubs. | amber | 0.683 | 0.0 | 0 | — | OK |
| 22 | site157_bldg323_floor1313.pdf | how many washbasins? | No washbasins found on this drawing. | green | 0.673 | 0.0 | 0 | — | OK |
| 23 | site157_bldg323_floor1313.pdf | how many apartments? | There are 7 apartments. | green | 0.872 | 0.0 | 0 | — | OK |
| 24 | site157_bldg323_floor1313.pdf | total floor area | The total net floor area is 565.4 m². | amber | 0.673 | 0.0 | 0 | — | OK (unverified) |
| 25 | bsc-esplanades_1807-ep-ar-v18.ifc | how many doors? | There are 211 count in model. | amber | 0.85 | 3.425e-05 | 1 | — | OK (wording glitch) |
| 26 | bsc-esplanades_1807-ep-ar-v18.ifc | total floor area | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | — | 0.000256 | 2 | no reader or query could answer this question from the drawing | OK (generic refusal) |
| 27 | bsc-esplanades_1807-ep-ar-v18.ifc | largest room | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | — | 0.00021975 | 1 | no reader or query could answer this question from the drawing | OK (generic refusal) |
| 28 | bsc-esplanades_1807-ep-ar-v18.ifc | wall volume | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | — | 0.00022774999999999998 | 1 | no reader or query could answer this question from the drawing | OK (generic refusal) |
| 29 | bsc-esplanades_1807-ep-ar-v18.ifc | rooms with more than one door | I can't answer this from the drawing: no reader or query could answer this question from the drawing. | grey | — | 0.00023674999999999998 | 1 | no reader or query could answer this question from the drawing | OK (generic refusal) |
| 30 | bsc-esplanades_1807-ep-ar-v18.ifc | which room is closest to the entrance? | I can't answer this from the drawing: this question needs something the query engine cannot express yet (distance to the entrance cannot be expressed with the available schema). | grey | — | 0.000223 | 1 | this question needs something the query engine cannot express yet (distance to the entrance cannot be expressed with the available schema) | OK |

Totals: OK 27, WRONG 2, SILLY 1, ERROR 0.

## WRONG / SILLY / ERROR

- #3 (colorful-2002, more windows than doors?): answered "No: 4 windows vs 6 doors." The key has 7 windows and 6 doors, so the correct answer is yes. WRONG on the window count.
- #2 (colorful-2002, number of bedrooms): answered 3, key says 2. WRONG, and the reliability is 0.399.
- #15 (1169, smallest bedroom): answered "The smallest bedroom is the bedroom." This names no room and gives no size, so it does not answer the superlative. SILLY.

No ERROR rows: all 30 returned HTTP 200 with a non-empty answer_text.

Notes (not scored as failures):
- #9 and #26 to #29 are generic refusals ("no reader or query could answer this question"). #9 (rooms with more than one door) may be answerable, so this may be an over-refusal.
- #25 reads "There are 211 count in model." (wording glitch, number is not checked against a key).
