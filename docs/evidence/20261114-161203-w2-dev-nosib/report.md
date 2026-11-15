# evalkit report — w2-dev-nosib

engine: `pipeline` · split: `dev` · siblings: `off` · LLM_PROVIDER=`none`

Split is deterministic by `int(sha1(path), 16) % 5 == 0` -> holdout, else dev. Holdout is never used to tune anything.

## 1. Headline accuracy (quantitative types only; text excluded, see below)

- **dev**: 70.4% [69.3%, 71.5%] (n=6192)
- **holdout**: 0.0% [0.0%, 0.0%] (n=0)
- **overall**: 70.4% [69.3%, 71.5%] (n=6192)
- text (reported separately, excluded from headline): 0.0% [0.0%, 3.9%] (n=95)

## 2. Source x type

| source | type | accuracy [95% CI] (n) |
|---|---|---|
| cubicasa5k | count | 63.8% [62.2%, 65.4%] (n=3546) |
| ifc_bench | text | 0.0% [0.0%, 4.4%] (n=83) |
| ifc_models | area | 99.8% [99.1%, 99.9%] (n=816) |
| ifc_models | count | 77.1% [69.2%, 83.5%] (n=131) |
| ifc_models | length | 87.5% [64.0%, 96.5%] (n=16) |
| ifc_models | volume | 87.5% [71.9%, 95.0%] (n=32) |
| opening_design | area | 0.0% [0.0%, 29.9%] (n=9) |
| opening_design | count | 85.0% [64.0%, 94.8%] (n=20) |
| opening_design | text | 0.0% [0.0%, 24.3%] (n=12) |
| swiss_dwellings | area | 20.0% [16.8%, 23.7%] (n=520) |
| swiss_dwellings | count | 92.6% [90.9%, 94.0%] (n=1102) |

## 3. Per-intent (prior baseline alongside)

| intent | accuracy [95% CI] (n) | prior baseline acc |
|---|---|---|
| apartment_net_area | 12.5% [8.2%, 18.5%] (n=160) | 12.5% |
| apartments | 100.0% [95.9%, 100.0%] (n=90) | 35.6% |
| balconies | 71.2% [62.4%, 78.6%] (n=118) | 59.3% |
| bathrooms | 88.0% [82.6%, 92.0%] (n=184) | 88.0% |
| bathtubs | 100.0% [95.4%, 100.0%] (n=80) | 45.0% |
| bedrooms | 46.5% [40.5%, 52.6%] (n=258) | 30.2% |
| count_in_model | 11.1% [3.9%, 28.1%] (n=27) | 7.4% |
| count_on_storey | 95.0% [87.8%, 98.0%] (n=80) | 2.5% |
| door_schedule_by_frame | 100.0% [34.2%, 100.0%] (n=2) | 0.0% |
| door_schedule_by_material | 100.0% [20.7%, 100.0%] (n=1) | 100.0% |
| door_schedule_by_note | 100.0% [43.8%, 100.0%] (n=3) | 33.3% |
| door_schedule_by_type | 100.0% [61.0%, 100.0%] (n=6) | 0.0% |
| door_schedule_by_width | 100.0% [34.2%, 100.0%] (n=2) | 0.0% |
| door_schedule_total | 100.0% [20.7%, 100.0%] (n=1) | 100.0% |
| door_schedule_total_rooms | 100.0% [20.7%, 100.0%] (n=1) | 100.0% |
| doors | 55.7% [50.7%, 60.6%] (n=384) | 4.7% |
| doors_on_storey | 91.7% [74.2%, 97.7%] (n=24) | 33.3% |
| floors | 88.4% [84.9%, 91.2%] (n=398) | 80.4% |
| kitchens | 96.3% [93.4%, 98.0%] (n=272) | 96.3% |
| room_area | 42.2% [35.2%, 49.5%] (n=180) | 2.2% |
| room_area_labelled | 4.4% [1.7%, 10.9%] (n=90) | 4.4% |
| room_labelled | 100.0% [99.3%, 100.0%] (n=546) | 28.6% |
| room_net_area | 100.0% [99.5%, 100.0%] (n=776) | 1.0% |
| room_schedule_area | 0.0% [0.0%, 39.0%] (n=6) | 0.0% |
| saunas | 49.3% [43.4%, 55.2%] (n=272) | 57.4% |
| showers | 100.0% [87.1%, 100.0%] (n=26) | 38.5% |
| showers_baths | 71.8% [67.1%, 76.1%] (n=376) | 72.9% |
| sinks | 54.3% [49.4%, 59.2%] (n=394) | 54.8% |
| slabs_volume_storey | 87.5% [64.0%, 96.5%] (n=16) | 62.5% |
| text_freeform | 0.0% [0.0%, 4.4%] (n=83) | 0.0% |
| toilets | 79.4% [75.6%, 82.8%] (n=486) | 52.7% |
| total_net_area | 4.4% [1.7%, 10.9%] (n=90) | 4.4% |
| total_net_area_storey | 100.0% [86.2%, 100.0%] (n=24) | 41.7% |
| unknown | 5.3% [0.9%, 24.6%] (n=19) | 5.3% |
| walls_length_storey | 87.5% [64.0%, 96.5%] (n=16) | 62.5% |
| walls_side_area_storey | 87.5% [64.0%, 96.5%] (n=16) | 37.5% |
| walls_volume_storey | 87.5% [64.0%, 96.5%] (n=16) | 50.0% |
| washbasins | 100.0% [95.9%, 100.0%] (n=90) | 17.8% |
| wc_rooms | 64.5% [57.4%, 71.0%] (n=186) | 60.2% |
| windows | 27.0% [23.3%, 31.2%] (n=488) | 6.6% |

## 4. Tier calibration (benchmark mode always returns a value)

| tier | n | coverage | accuracy [95% CI] |
|---|---|---|---|
| green | 680 | 10.8% | 97.6% [96.2%, 98.5%] (n=680) |
| amber | 5607 | 89.2% | 65.9% [64.7%, 67.1%] (n=5607) |
| grey | 0 | 0.0% | 0.0% [0.0%, 0.0%] (n=0) |

### accuracy vs coverage (10 levels, ranked green>amber>grey)

| coverage | accuracy | n |
|---|---|---|
| 10% | 97.6% | 629 |
| 20% | 84.7% | 1257 |
| 30% | 78.4% | 1886 |
| 40% | 74.9% | 2515 |
| 50% | 73.2% | 3144 |
| 60% | 71.6% | 3772 |
| 70% | 70.8% | 4401 |
| 80% | 70.3% | 5030 |
| 90% | 69.8% | 5658 |
| 100% | 69.3% | 6287 |

## 5. Cost

- mean/median/p95 ms per question: 1001.47 / 4.86 / 3094.30
- tokens total: 0 · USD total: 0.0000 · llm_calls: 0 · planner_calls: 0
- first-question-of-drawing (analysis) mean ms: 6107.29 (cache-eligible; marginal mean ms for follow-up questions: 788.26)
- estimate: CPU-seconds per drawing: 6.1073 · per 14,000 drawings: 85502.0 (estimate, extrapolated)

## 6. Failure buckets (source|intent|width_bucket|direction -> n)

- cubicasa5k|windows|unknown|under: 160
- cubicasa5k|doors|unknown|over: 120
- cubicasa5k|windows|unknown|over: 114
- cubicasa5k|sinks|unknown|under: 106
- cubicasa5k|bedrooms|unknown|over: 106
- cubicasa5k|saunas|unknown|under: 92
- cubicasa5k|showers_baths|unknown|under: 78
- cubicasa5k|sinks|unknown|over: 74
- swiss_dwellings|windows|unknown|under: 72
- swiss_dwellings|apartment_net_area|unknown|over: 72
- swiss_dwellings|apartment_net_area|unknown|under: 68
- cubicasa5k|wc_rooms|unknown|under: 66
- swiss_dwellings|room_area|unknown|under: 54
- cubicasa5k|toilets|unknown|under: 52
- cubicasa5k|doors|unknown|under: 50
- swiss_dwellings|room_area|unknown|over: 50
- cubicasa5k|toilets|unknown|over: 48
- cubicasa5k|saunas|unknown|over: 46
- swiss_dwellings|room_area_labelled|unknown|under: 44
- swiss_dwellings|total_net_area|unknown|under: 44
- swiss_dwellings|total_net_area|unknown|over: 42
- swiss_dwellings|room_area_labelled|unknown|over: 42
- cubicasa5k|floors|unknown|under: 36
- cubicasa5k|balconies|unknown|under: 32
- cubicasa5k|bedrooms|unknown|under: 32

## 7. 20 random wrong examples

| path | question | truth | prediction | tier |
|---|---|---|---|---|
| data/cubicasa5k/high_quality_architectural-4561.png | Kuinka monta ovea pohjapiirustuksessa on? Laske oviaukot, joissa on ov | 11 | 12 | green |
| data/cubicasa5k/high_quality_architectural-9460.png | How many doors are shown on this floor plan? Count doorways fitted wit | 9 | 11 | amber |
| data/swiss_dwellings/site1040_bldg2136_floor9659.pdf | What is the net floor area of apartment B in m², summing all its rooms | 95.32 | 72.58 | amber |
| data/swiss_dwellings/site339_bldg710_floor3024.pdf | Qual è la superficie netta dell'appartamento B in m² (somma di tutti i | 90.73 | 72.58 | amber |
| data/cubicasa5k/high_quality_architectural-11826.png | How many doors are shown on this floor plan? Count doorways fitted wit | 6 | 3 | amber |
| data/cubicasa5k/high_quality_architectural-14612.png | How many toilet bowls (WC seats) are drawn on this floor plan? | 2 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-8755.png | Kuinka monta pesu- ja tiskiallasta (keittiö ja kylpytilat yhteensä; ka | 2 | 3 | amber |
| data/cubicasa5k/high_quality_architectural-2164.png | How many windows are shown on this floor plan? | 12 | 11 | amber |
| data/cubicasa5k/high_quality_architectural-3710.png | How many separate WC rooms (toilet rooms marked WC) are on this floor  | 1 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-8705.png | Kuinka monta pesu- ja tiskiallasta (keittiö ja kylpytilat yhteensä; ka | 4 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-7688.png | How many toilet bowls (WC seats) are drawn on this floor plan? | 2 | 1 | amber |
| data/cubicasa5k/high_quality_architectural-12864.png | How many saunas are on this floor plan? | 1 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-13161.png | How many saunas are on this floor plan? | 1 | 0 | amber |
| data/swiss_dwellings/site2146_bldg2990_floor13636.pdf | Wie gross ist die Nettofläche von Raum 3.02 («Zimmer») in m²? | 14.34 | 11.42 | amber |
| data/cubicasa5k/high_quality_architectural-11012.png | How many sinks and wash basins (kitchen and bathroom combined; a doubl | 2 | 4 | amber |
| data/cubicasa5k/high_quality_architectural-2164.png | How many showers and bathtubs are drawn on this floor plan in total? | 2 | 1 | amber |
| data/swiss_dwellings/site1098_bldg2234_floor10334.pdf | How many windows are drawn on this floor plan? | 26 | 7 | amber |
| data/swiss_dwellings/site289_bldg536_floor2149.pdf | What is the total net floor area in m² of all numbered indoor rooms on | 392.82 | 197.75 | amber |
| data/cubicasa5k/high_quality_architectural-14341.png | How many sinks and wash basins (kitchen and bathroom combined; a doubl | 6 | 3 | amber |
| data/cubicasa5k/high_quality-5080.png | Kuinka monta ovea pohjapiirustuksessa on? Laske oviaukot, joissa on ov | 7 | 8 | amber |

## 8. Invariant violations and exceptions

- invariant violations: 0
- exceptions: 0

## 9. Reproduce

- command: `python -m evalkit.run --engine pipeline --split dev --workers 4 --tag w2-dev-nosib --no-siblings`
- git commit: `5df2863`
- n_questions: 6287 · n_drawings: 252
- split sizes: `{'cubicasa5k': {'dev': 3546, 'holdout': 724}, 'ifc_bench': {'dev': 83, 'holdout': 166}, 'ifc_models': {'dev': 995, 'holdout': 54}, 'opening_design': {'dev': 41, 'holdout': 23}, 'swiss_dwellings': {'dev': 1622, 'holdout': 736}, 'TOTAL': {'dev': 6287, 'holdout': 1703}}`
