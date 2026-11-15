# evalkit report — w2-dev

engine: `pipeline` · split: `dev` · siblings: `on` · LLM_PROVIDER=`none`

Split is deterministic by `int(sha1(path), 16) % 5 == 0` -> holdout, else dev. Holdout is never used to tune anything.

## 1. Headline accuracy (quantitative types only; text excluded, see below)

- **dev**: 75.0% [73.9%, 76.1%] (n=6192)
- **holdout**: 0.0% [0.0%, 0.0%] (n=0)
- **overall**: 75.0% [73.9%, 76.1%] (n=6192)
- text (reported separately, excluded from headline): 0.0% [0.0%, 3.9%] (n=95)

## 2. Source x type

| source | type | accuracy [95% CI] (n) |
|---|---|---|
| cubicasa5k | count | 57.9% [56.3%, 59.5%] (n=3546) |
| ifc_bench | text | 0.0% [0.0%, 4.4%] (n=83) |
| ifc_models | area | 99.8% [99.1%, 99.9%] (n=816) |
| ifc_models | count | 81.7% [74.2%, 87.4%] (n=131) |
| ifc_models | length | 87.5% [64.0%, 96.5%] (n=16) |
| ifc_models | volume | 87.5% [71.9%, 95.0%] (n=32) |
| opening_design | area | 0.0% [0.0%, 29.9%] (n=9) |
| opening_design | count | 85.0% [64.0%, 94.8%] (n=20) |
| opening_design | text | 0.0% [0.0%, 24.3%] (n=12) |
| swiss_dwellings | area | 97.7% [96.0%, 98.7%] (n=520) |
| swiss_dwellings | count | 100.0% [99.7%, 100.0%] (n=1102) |

## 3. Per-intent (prior baseline alongside)

| intent | accuracy [95% CI] (n) | prior baseline acc |
|---|---|---|
| apartment_net_area | 95.0% [90.4%, 97.4%] (n=160) | 12.5% |
| apartments | 100.0% [95.9%, 100.0%] (n=90) | 35.6% |
| balconies | 71.2% [62.4%, 78.6%] (n=118) | 59.3% |
| bathrooms | 88.0% [82.6%, 92.0%] (n=184) | 88.0% |
| bathtubs | 100.0% [95.4%, 100.0%] (n=80) | 45.0% |
| bedrooms | 43.8% [37.9%, 49.9%] (n=258) | 30.2% |
| count_in_model | 11.1% [3.9%, 28.1%] (n=27) | 7.4% |
| count_on_storey | 100.0% [95.4%, 100.0%] (n=80) | 2.5% |
| door_schedule_by_frame | 100.0% [34.2%, 100.0%] (n=2) | 0.0% |
| door_schedule_by_material | 100.0% [20.7%, 100.0%] (n=1) | 100.0% |
| door_schedule_by_note | 100.0% [43.8%, 100.0%] (n=3) | 33.3% |
| door_schedule_by_type | 100.0% [61.0%, 100.0%] (n=6) | 0.0% |
| door_schedule_by_width | 100.0% [34.2%, 100.0%] (n=2) | 0.0% |
| door_schedule_total | 100.0% [20.7%, 100.0%] (n=1) | 100.0% |
| door_schedule_total_rooms | 100.0% [20.7%, 100.0%] (n=1) | 100.0% |
| doors | 45.6% [40.7%, 50.6%] (n=384) | 4.7% |
| doors_on_storey | 100.0% [86.2%, 100.0%] (n=24) | 33.3% |
| floors | 88.4% [84.9%, 91.2%] (n=398) | 80.4% |
| kitchens | 96.3% [93.4%, 98.0%] (n=272) | 96.3% |
| room_area | 100.0% [97.9%, 100.0%] (n=180) | 2.2% |
| room_area_labelled | 100.0% [95.9%, 100.0%] (n=90) | 4.4% |
| room_labelled | 100.0% [99.3%, 100.0%] (n=546) | 28.6% |
| room_net_area | 100.0% [99.5%, 100.0%] (n=776) | 1.0% |
| room_schedule_area | 0.0% [0.0%, 39.0%] (n=6) | 0.0% |
| saunas | 49.3% [43.4%, 55.2%] (n=272) | 57.4% |
| showers | 100.0% [87.1%, 100.0%] (n=26) | 38.5% |
| showers_baths | 72.3% [67.6%, 76.6%] (n=376) | 72.9% |
| sinks | 38.8% [34.1%, 43.7%] (n=394) | 54.8% |
| slabs_volume_storey | 87.5% [64.0%, 96.5%] (n=16) | 62.5% |
| text_freeform | 0.0% [0.0%, 4.4%] (n=83) | 0.0% |
| toilets | 64.4% [60.0%, 68.5%] (n=486) | 52.7% |
| total_net_area | 95.6% [89.1%, 98.3%] (n=90) | 4.4% |
| total_net_area_storey | 100.0% [86.2%, 100.0%] (n=24) | 41.7% |
| unknown | 5.3% [0.9%, 24.6%] (n=19) | 5.3% |
| walls_length_storey | 87.5% [64.0%, 96.5%] (n=16) | 62.5% |
| walls_side_area_storey | 87.5% [64.0%, 96.5%] (n=16) | 37.5% |
| walls_volume_storey | 87.5% [64.0%, 96.5%] (n=16) | 50.0% |
| washbasins | 100.0% [95.9%, 100.0%] (n=90) | 17.8% |
| wc_rooms | 64.5% [57.4%, 71.0%] (n=186) | 60.2% |
| windows | 37.7% [33.5%, 42.1%] (n=488) | 6.6% |

## 4. Tier calibration (benchmark mode always returns a value)

| tier | n | coverage | accuracy [95% CI] |
|---|---|---|---|
| green | 1914 | 30.4% | 98.7% [98.1%, 99.2%] (n=1914) |
| amber | 4373 | 69.6% | 63.0% [61.5%, 64.4%] (n=4373) |
| grey | 0 | 0.0% | 0.0% [0.0%, 0.0%] (n=0) |

### accuracy vs coverage (10 levels, ranked green>amber>grey)

| coverage | accuracy | n |
|---|---|---|
| 10% | 98.9% | 629 |
| 20% | 98.8% | 1257 |
| 30% | 98.8% | 1886 |
| 40% | 91.1% | 2515 |
| 50% | 85.0% | 3144 |
| 60% | 81.7% | 3772 |
| 70% | 78.5% | 4401 |
| 80% | 76.8% | 5030 |
| 90% | 75.3% | 5658 |
| 100% | 73.9% | 6287 |

## 5. Cost

- mean/median/p95 ms per question: 2955.10 / 12.92 / 20686.00
- tokens total: 0 · USD total: 0.0000 · llm_calls: 0 · planner_calls: 0
- first-question-of-drawing (analysis) mean ms: 17909.08 (cache-eligible; marginal mean ms for follow-up questions: 2330.67)
- estimate: CPU-seconds per drawing: 17.9091 · per 14,000 drawings: 250727.1 (estimate, extrapolated)

## 6. Failure buckets (source|intent|width_bucket|direction -> n)

- cubicasa5k|windows|unknown|under: 227
- cubicasa5k|sinks|unknown|under: 196
- cubicasa5k|toilets|unknown|under: 139
- cubicasa5k|doors|unknown|under: 117
- cubicasa5k|doors|unknown|over: 92
- cubicasa5k|saunas|unknown|under: 92
- cubicasa5k|showers_baths|unknown|under: 78
- cubicasa5k|windows|unknown|over: 77
- cubicasa5k|bedrooms|unknown|over: 73
- cubicasa5k|bedrooms|unknown|under: 72
- cubicasa5k|wc_rooms|unknown|under: 66
- cubicasa5k|saunas|unknown|over: 46
- cubicasa5k|sinks|unknown|over: 45
- cubicasa5k|floors|unknown|under: 36
- cubicasa5k|toilets|unknown|over: 34
- cubicasa5k|balconies|unknown|under: 32
- cubicasa5k|showers_baths|unknown|over: 26
- cubicasa5k|bathrooms|unknown|over: 14
- ifc_models|count_in_model|unknown|under: 12
- ifc_models|count_in_model|unknown|over: 12
- cubicasa5k|floors|unknown|over: 10
- swiss_dwellings|apartment_net_area|unknown|over: 8
- cubicasa5k|bathrooms|unknown|under: 8
- cubicasa5k|kitchens|unknown|over: 6
- cubicasa5k|kitchens|unknown|under: 4

## 7. 20 random wrong examples

| path | question | truth | prediction | tier |
|---|---|---|---|---|
| data/cubicasa5k/high_quality_architectural-4897.png | Kuinka monta suihkua ja kylpyammetta pohjapiirustukseen on piirretty y | 2 | 1 | amber |
| data/cubicasa5k/high_quality_architectural-6387.png | How many sinks and wash basins (kitchen and bathroom combined; a doubl | 4 | 2 | amber |
| data/cubicasa5k/high_quality-1647.png | How many windows are shown on this floor plan? | 2 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-1357.png | Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on? | 1 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-11572.png | How many bedrooms (makuuhuone, usually marked MH) are on this floor pl | 3 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-13075.png | How many bedrooms (makuuhuone, usually marked MH) are on this floor pl | 2 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-7567.png | How many showers and bathtubs are drawn on this floor plan in total? | 2 | 1 | amber |
| data/cubicasa5k/high_quality_architectural-14494.png | How many toilet bowls (WC seats) are drawn on this floor plan? | 1 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-9405.png | Kuinka monta ikkunaa pohjapiirustuksessa on? | 10 | 12 | amber |
| data/cubicasa5k/high_quality-1500.png | Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on? | 1 | 2 | amber |
| data/cubicasa5k/high_quality_architectural-11975.png | How many sinks and wash basins (kitchen and bathroom combined; a doubl | 2 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-4561.png | How many saunas are on this floor plan? | 1 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-1000.png | Kuinka monta ovea pohjapiirustuksessa on? Laske oviaukot, joissa on ov | 16 | 18 | amber |
| data/cubicasa5k/high_quality_architectural-11012.png | How many sinks and wash basins (kitchen and bathroom combined; a doubl | 2 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-13794.png | How many sinks and wash basins (kitchen and bathroom combined; a doubl | 2 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-1169.png | How many windows are shown on this floor plan? | 3 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-11011.png | How many toilet bowls (WC seats) are drawn on this floor plan? | 1 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-12943.png | How many windows are shown on this floor plan? | 5 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-1169.png | Kuinka monta WC-istuinta pohjapiirustukseen on piirretty? | 1 | 0 | amber |
| data/cubicasa5k/high_quality_architectural-14339.png | How many sinks and wash basins (kitchen and bathroom combined; a doubl | 2 | 0 | amber |

## 8. Invariant violations and exceptions

- invariant violations: 0
- exceptions: 0

## 9. Reproduce

- command: `python -m evalkit.run --engine pipeline --split dev --workers 4 --tag w2-dev`
- git commit: `bb697cf`
- n_questions: 6287 · n_drawings: 252
- split sizes: `{'cubicasa5k': {'dev': 3546, 'holdout': 724}, 'ifc_bench': {'dev': 83, 'holdout': 166}, 'ifc_models': {'dev': 995, 'holdout': 54}, 'opening_design': {'dev': 41, 'holdout': 23}, 'swiss_dwellings': {'dev': 1622, 'holdout': 736}, 'TOTAL': {'dev': 6287, 'holdout': 1703}}`
