# evalkit report — gate_sw8

engine: `pipeline` · split: `dev` · siblings: `off` · LLM_PROVIDER=`none`

Split is deterministic by `int(sha1(path), 16) % 5 == 0` -> holdout, else dev. Holdout is never used to tune anything.

## 1. Headline accuracy (quantitative types only; text excluded, see below)

- **dev**: 68.3% [62.9%, 73.3%] (n=300)
- **holdout**: 0.0% [0.0%, 0.0%] (n=0)
- **overall**: 68.3% [62.9%, 73.3%] (n=300)
- text (reported separately, excluded from headline): 0.0% [0.0%, 0.0%] (n=0)

## 2. Source x type

| source | type | accuracy [95% CI] (n) |
|---|---|---|
| swiss_dwellings | area | 18.1% [11.6%, 27.1%] (n=94) |
| swiss_dwellings | count | 91.3% [86.6%, 94.4%] (n=206) |

## 3. Per-intent (prior baseline alongside)

| intent | accuracy [95% CI] (n) | prior baseline acc |
|---|---|---|
| apartment_net_area | 3.3% [0.6%, 16.7%] (n=30) | 6.7% |
| apartments | 100.0% [82.4%, 100.0%] (n=18) | 55.6% |
| bathtubs | 100.0% [80.6%, 100.0%] (n=16) | 62.5% |
| doors | 100.0% [82.4%, 100.0%] (n=18) | 0.0% |
| room_area | 50.0% [33.6%, 66.4%] (n=32) | 0.0% |
| room_area_labelled | 0.0% [0.0%, 19.4%] (n=16) | 0.0% |
| room_labelled | 100.0% [96.4%, 100.0%] (n=104) | 44.2% |
| toilets | 100.0% [80.6%, 100.0%] (n=16) | 12.5% |
| total_net_area | 0.0% [0.0%, 19.4%] (n=16) | 0.0% |
| washbasins | 100.0% [80.6%, 100.0%] (n=16) | 12.5% |
| windows | 0.0% [0.0%, 17.6%] (n=18) | 11.1% |

## 4. Tier calibration (benchmark mode always returns a value)

| tier | n | coverage | accuracy [95% CI] |
|---|---|---|---|
| green | 18 | 6.0% | 100.0% [82.4%, 100.0%] (n=18) |
| amber | 264 | 88.0% | 70.8% [65.1%, 76.0%] (n=264) |
| grey | 18 | 6.0% | 0.0% [0.0%, 17.6%] (n=18) |

### accuracy vs coverage (10 levels, ranked green>amber>grey)

| coverage | accuracy | n |
|---|---|---|
| 10% | 93.3% | 30 |
| 20% | 78.3% | 60 |
| 30% | 73.3% | 90 |
| 40% | 75.8% | 120 |
| 50% | 75.3% | 150 |
| 60% | 74.4% | 180 |
| 70% | 73.3% | 210 |
| 80% | 73.3% | 240 |
| 90% | 73.0% | 270 |
| 100% | 68.3% | 300 |

## 5. Cost

- mean/median/p95 ms per question: 208.99 / 7.18 / 1212.36
- tokens total: 0 · USD total: 0.0000 · llm_calls: 0 · planner_calls: 0
- first-question-of-drawing (analysis) mean ms: 1544.61 (cache-eligible; marginal mean ms for follow-up questions: 167.69)
- estimate: CPU-seconds per drawing: 1.5446 · per 14,000 drawings: 21624.6 (estimate, extrapolated)

## 6. Failure buckets (source|intent|width_bucket|direction -> n)

- swiss_dwellings|apartment_net_area|unknown|under: 21
- swiss_dwellings|windows|unknown|n/a: 18
- swiss_dwellings|total_net_area|unknown|under: 14
- swiss_dwellings|room_area_labelled|unknown|under: 10
- swiss_dwellings|room_area|unknown|under: 8
- swiss_dwellings|apartment_net_area|unknown|over: 8
- swiss_dwellings|room_area|unknown|over: 8
- swiss_dwellings|room_area_labelled|unknown|over: 6
- swiss_dwellings|total_net_area|unknown|over: 2

## 7. 20 random wrong examples

| path | question | truth | prediction | tier |
|---|---|---|---|---|
| data/swiss_dwellings/site719_bldg1540_floor6678.pdf | Qual è la superficie netta del locale 2.01 («Balcone») in m²? | 6.2 | 11.42 | amber |
| data/swiss_dwellings/site719_bldg1540_floor6678.pdf | What is the net floor area of apartment A in m², summing all its rooms | 73.74 | 20.2881498051667 | amber |
| data/swiss_dwellings/site11711_bldg18268_floor48991.pdf | What is the total net area in m² of all rooms labelled 'Camera da lett | 53.01 | 83.5 | amber |
| data/swiss_dwellings/site644_bldg1390_floor6077.pdf | Quante finestre sono disegnate in questa pianta? | 29 | None | grey |
| data/swiss_dwellings/site4267_bldg7556_floor30516.pdf | What is the net floor area of apartment B in m², summing all its rooms | 58.05 | 2.3746018492057077 | amber |
| data/swiss_dwellings/site3421_bldg5295_floor23605.pdf | What is the net floor area of apartment B in m², summing all its rooms | 65.51 | 0.554184954547695 | amber |
| data/swiss_dwellings/site1000_bldg2082_floor9385.pdf | What is the total net area in m² of all rooms labelled 'Zimmer' on thi | 184.93 | 83.5 | amber |
| data/swiss_dwellings/site644_bldg1390_floor6077.pdf | What is the total net floor area in m² of all numbered indoor rooms on | 420.05 | 0.5027599111546025 | amber |
| data/swiss_dwellings/site1102_bldg2242_floor10281.pdf | What is the total net floor area in m² of all numbered indoor rooms on | 193.49 | 43.491246722513004 | amber |
| data/swiss_dwellings/site11711_bldg18268_floor48991.pdf | Qual è la superficie netta dell'appartamento B in m² (somma di tutti i | 66.01 | 72.58 | amber |
| data/swiss_dwellings/site4267_bldg7556_floor30516.pdf | What is the total net floor area in m² of all numbered indoor rooms on | 117.79 | 11.316611147356994 | amber |
| data/swiss_dwellings/site719_bldg1540_floor6678.pdf | What is the net floor area of apartment B in m², summing all its rooms | 87.3 | 72.58 | amber |
| data/swiss_dwellings/site11711_bldg18268_floor48991.pdf | Qual è la superficie netta dell'appartamento A in m² (somma di tutti i | 64.54 | 72.58 | amber |
| data/swiss_dwellings/site11711_bldg18268_floor48991.pdf | What is the net floor area of apartment A in m², summing all its rooms | 64.54 | 1150.8452564165257 | amber |
| data/swiss_dwellings/site644_bldg1390_floor6077.pdf | What is the net floor area of apartment D in m², summing all its rooms | 112.92 | 0.07281871068573574 | amber |
| data/swiss_dwellings/site3421_bldg5295_floor23605.pdf | What is the net floor area of room 3.09 ('Küche') in m²? | 10.8 | 11.42 | amber |
| data/swiss_dwellings/site4267_bldg7556_floor30516.pdf | What is the total net area in m² of all rooms labelled 'Zimmer' on thi | 32.5 | 4.050173108972894 | amber |
| data/swiss_dwellings/site3421_bldg5295_floor23605.pdf | What is the net floor area of room 3.02 ('Bad') in m²? | 4.21 | 11.42 | amber |
| data/swiss_dwellings/site4267_bldg7556_floor30516.pdf | Wie gross ist die gesamte Nettogeschossfläche in m² aller nummerierten | 117.79 | 11.316611147356994 | amber |
| data/swiss_dwellings/site1102_bldg2242_floor10281.pdf | Qual è la superficie netta dell'appartamento B in m² (somma di tutti i | 94.34 | 72.58 | amber |

## 8. Invariant violations and exceptions

- invariant violations: 0
- exceptions: 0

## 9. Reproduce

- command: `python -m evalkit.run --engine pipeline --split dev --no-siblings --limit 300 --sources swiss_dwellings --workers 4 --tag gate_sw8`
- git commit: `5df538b`
- n_questions: 300 · n_drawings: 9
- split sizes: `{'cubicasa5k': {'dev': 3546, 'holdout': 724}, 'ifc_bench': {'dev': 83, 'holdout': 166}, 'ifc_models': {'dev': 995, 'holdout': 54}, 'opening_design': {'dev': 41, 'holdout': 23}, 'swiss_dwellings': {'dev': 1622, 'holdout': 736}, 'TOTAL': {'dev': 6287, 'holdout': 1703}}`
