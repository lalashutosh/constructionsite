# evalkit report — gate_r9

engine: `pipeline` · split: `dev` · siblings: `off` · LLM_PROVIDER=`none`

Split is deterministic by `int(sha1(path), 16) % 5 == 0` -> holdout, else dev. Holdout is never used to tune anything.

## 1. Headline accuracy (quantitative types only; text excluded, see below)

- **dev**: 81.5% [77.4%, 85.0%] (n=400)
- **holdout**: 0.0% [0.0%, 0.0%] (n=0)
- **overall**: 81.5% [77.4%, 85.0%] (n=400)
- text (reported separately, excluded from headline): 0.0% [0.0%, 0.0%] (n=0)

## 2. Source x type

| source | type | accuracy [95% CI] (n) |
|---|---|---|
| cubicasa5k | count | 81.5% [77.4%, 85.0%] (n=400) |

## 3. Per-intent (prior baseline alongside)

| intent | accuracy [95% CI] (n) | prior baseline acc |
|---|---|---|
| balconies | 83.3% [64.1%, 93.3%] (n=24) | 66.7% |
| bathrooms | 100.0% [85.1%, 100.0%] (n=22) | 100.0% |
| bedrooms | 60.0% [42.3%, 75.4%] (n=30) | 40.0% |
| doors | 85.7% [68.5%, 94.3%] (n=28) | 7.1% |
| floors | 95.2% [84.2%, 98.7%] (n=42) | 81.0% |
| kitchens | 100.0% [89.3%, 100.0%] (n=32) | 100.0% |
| saunas | 82.4% [66.5%, 91.7%] (n=34) | 35.3% |
| showers_baths | 84.2% [69.6%, 92.6%] (n=38) | 84.2% |
| sinks | 71.4% [56.4%, 82.8%] (n=42) | 66.7% |
| toilets | 95.2% [84.2%, 98.7%] (n=42) | 81.0% |
| wc_rooms | 75.0% [55.1%, 88.0%] (n=24) | 75.0% |
| windows | 52.4% [37.7%, 66.6%] (n=42) | 9.5% |

## 4. Tier calibration (benchmark mode always returns a value)

| tier | n | coverage | accuracy [95% CI] |
|---|---|---|---|
| green | 16 | 4.0% | 62.5% [38.6%, 81.5%] (n=16) |
| amber | 384 | 96.0% | 82.3% [78.2%, 85.8%] (n=384) |
| grey | 0 | 0.0% | 0.0% [0.0%, 0.0%] (n=0) |

### accuracy vs coverage (10 levels, ranked green>amber>grey)

| coverage | accuracy | n |
|---|---|---|
| 10% | 75.0% | 40 |
| 20% | 76.2% | 80 |
| 30% | 75.8% | 120 |
| 40% | 77.5% | 160 |
| 50% | 77.0% | 200 |
| 60% | 78.8% | 240 |
| 70% | 79.3% | 280 |
| 80% | 79.1% | 320 |
| 90% | 80.3% | 360 |
| 100% | 81.5% | 400 |

## 5. Cost

- mean/median/p95 ms per question: 214.08 / 8.39 / 1039.98
- tokens total: 0 · USD total: 0.0000 · llm_calls: 0 · planner_calls: 0
- first-question-of-drawing (analysis) mean ms: 952.18 (cache-eligible; marginal mean ms for follow-up questions: 171.13)
- estimate: CPU-seconds per drawing: 0.9522 · per 14,000 drawings: 13330.5 (estimate, extrapolated)

## 6. Failure buckets (source|intent|width_bucket|direction -> n)

- cubicasa5k|windows|unknown|under: 14
- cubicasa5k|sinks|unknown|under: 12
- cubicasa5k|wc_rooms|unknown|under: 6
- cubicasa5k|showers_baths|unknown|under: 6
- cubicasa5k|windows|unknown|over: 6
- cubicasa5k|bedrooms|unknown|under: 6
- cubicasa5k|bedrooms|unknown|over: 6
- cubicasa5k|balconies|unknown|under: 4
- cubicasa5k|saunas|unknown|over: 4
- cubicasa5k|floors|unknown|under: 2
- cubicasa5k|saunas|unknown|under: 2
- cubicasa5k|toilets|unknown|under: 2
- cubicasa5k|doors|unknown|under: 2
- cubicasa5k|doors|unknown|over: 2

## 7. 20 random wrong examples

| path | question | truth | prediction | tier |
|---|---|---|---|---|
| data/cubicasa5k/high_quality-11459.png | Kuinka monta ikkunaa pohjapiirustuksessa on? | 5 | 8 | amber |
| data/cubicasa5k/high_quality-11459.png | How many windows are shown on this floor plan? | 5 | 8 | amber |
| data/cubicasa5k/colorful-34.png | How many separate WC rooms (toilet rooms marked WC) are on this floor  | 2 | 0 | amber |
| data/cubicasa5k/colorful-2194.png | How many windows are shown on this floor plan? | 2 | 3 | amber |
| data/cubicasa5k/colorful-34.png | How many saunas are on this floor plan? | 1 | 0 | amber |
| data/cubicasa5k/high_quality-10785.png | Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on? | 0 | 1 | amber |
| data/cubicasa5k/colorful-7513.png | How many windows are shown on this floor plan? | 5 | 4 | amber |
| data/cubicasa5k/colorful-13685.png | How many saunas are on this floor plan? | 1 | 2 | amber |
| data/cubicasa5k/colorful-2194.png | How many balconies (parveke, including glazed balconies) are on this f | 1 | 0 | amber |
| data/cubicasa5k/colorful-34.png | Kuinka monta ikkunaa pohjapiirustuksessa on? | 17 | 0 | green |
| data/cubicasa5k/colorful-2002.png | Kuinka monta ikkunaa pohjapiirustuksessa on? | 7 | 4 | amber |
| data/cubicasa5k/colorful-13685.png | How many windows are shown on this floor plan? | 16 | 14 | amber |
| data/cubicasa5k/colorful-2002.png | How many windows are shown on this floor plan? | 7 | 4 | amber |
| data/cubicasa5k/colorful-2194.png | Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on? | 1 | 2 | amber |
| data/cubicasa5k/colorful-13685.png | Kuinka monta suihkua ja kylpyammetta pohjapiirustukseen on piirretty y | 2 | 1 | amber |
| data/cubicasa5k/colorful-13685.png | How many showers and bathtubs are drawn on this floor plan in total? | 2 | 1 | amber |
| data/cubicasa5k/colorful-8759.png | How many sinks and wash basins (kitchen and bathroom combined; a doubl | 2 | 1 | amber |
| data/cubicasa5k/colorful-13685.png | Kuinka monta saunaa pohjapiirustuksessa on? | 1 | 2 | amber |
| data/cubicasa5k/colorful-8389.png | Kuinka monta ikkunaa pohjapiirustuksessa on? | 7 | 3 | green |
| data/cubicasa5k/colorful-13685.png | Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on? | 4 | 3 | amber |

## 8. Invariant violations and exceptions

- invariant violations: 0
- exceptions: 0

## 9. Reproduce

- command: `python -m evalkit.run --engine pipeline --split dev --no-siblings --limit 400 --sources cubicasa5k --workers 4 --tag gate_r9`
- git commit: `2e460a1`
- n_questions: 400 · n_drawings: 22
- split sizes: `{'cubicasa5k': {'dev': 3546, 'holdout': 724}, 'ifc_bench': {'dev': 83, 'holdout': 166}, 'ifc_models': {'dev': 995, 'holdout': 54}, 'opening_design': {'dev': 41, 'holdout': 23}, 'swiss_dwellings': {'dev': 1622, 'holdout': 736}, 'TOTAL': {'dev': 6287, 'holdout': 1703}}`
