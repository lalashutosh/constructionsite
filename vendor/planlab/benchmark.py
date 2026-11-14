import sys, glob, json, re, time, os, collections, resource
sys.path.insert(0, "/home/claude/planlab")
import planlab as pl, analysis as A, fixtures as FX
FP = json.load(open("/tmp/fixture_params.json"))
def classify(c, p=FP):
    nC, nP, L, S = c["nC"], c["nP"], c["L"], c["S"]
    if nC == 0 and nP == 2 and p["wc_lo"] <= L <= p["wc_hi"] and 0.3 <= S <= 0.7: return "wc"
    if nC == 1 and nP == 2 and L >= p["tub_lo"] and S <= 1.0: return "tub"
    if nC == 1 and nP == 2 and p["sh_lo"] <= L <= p["sh_hi"] and S >= p["sh_s_lo"]: return "shower"
    if nC == 1 and nP == 2 and L <= p["basin_hi"]: return "basin"
    return None
Q = [json.loads(l) for l in open("/tmp/zipscan/junction-dataset-preview__questions.jsonl")]
byplan = collections.defaultdict(list)
for q in Q:
    if q["path"].startswith("data/swiss_dwellings") and q["question"].isascii() or (q["path"].startswith("data/swiss_dwellings") and q["question"].replace("²", "").isascii()):
        byplan[q["path"].split("/")[-1].rsplit(".", 1)[0]].append(q)
def answer(q, plan, fx):
    t = q["question"]
    m = re.search(r"labelled '([^']+)'", t)
    if t.startswith("How many rooms labelled") and m: return sum(1 for r in plan["rooms"] if r["name"] == m.group(1)), "rooms_by_name"
    if t.startswith("How many apartments"): return len(plan["units"]), "apartments"
    if t.startswith("How many doors"): return len(plan["doors"]), "doors"
    if t.startswith("How many windows"): return len(plan["windows"]), "windows"
    if t.startswith("How many toilets"): return fx["wc"], "wc"
    if t.startswith("How many washbasins"): return fx["basin"], "basin"
    if t.startswith("How many bathtubs"): return fx["tub"], "tub"
    if t.startswith("How many showers"): return fx["shower"], "shower"
    m = re.search(r"room (\d+\.\d+)", t)
    if m and t.startswith("What is the net floor area"):
        r = next((r for r in plan["rooms"] if r["id"] == m.group(1)), None)
        return (round(r["poly"].area, 2) if r else None), "room_area"
    return None, None
failures = []; rows = []; per_type = collections.defaultdict(lambda: [0, 0]); stage = collections.defaultdict(list)
stems = sorted(os.path.basename(p)[:-4] for p in glob.glob("/tmp/swiss/*.dxf"))
for stem in stems:
    path = f"/tmp/swiss/{stem}.dxf"
    try:
        t0 = time.perf_counter(); plan = pl.load(path); t1 = time.perf_counter()
        G = pl.build_graph(plan); t2 = time.perf_counter()
        fx = collections.Counter(classify(c) for c in FX.clusters(path)); t3 = time.perf_counter()
        plan2, G2, F, U, P, uniq = A.analyze(path); t4 = time.perf_counter()
    except Exception as ex:
        failures.append((stem, repr(ex)[:100])); continue
    sim = (t4 - t3) - (t1 - t0) - (t2 - t1)            # analyze() re-parses; subtract parse+graph to isolate rules+sampling
    stage["parse_ms"].append((t1 - t0) * 1e3); stage["graph_ms"].append((t2 - t1) * 1e3); stage["fixtures_ms"].append((t3 - t2) * 1e3)
    stage["rules_and_sim_ms"].append(sim * 1e3); stage["total_ms"].append((t1 - t0 + t2 - t1 + t3 - t2 + sim) * 1e3)
    nsim = sum(P["n_personas"] for _ in U)
    stage["personas"].append(nsim)
    for q in byplan[stem]:
        pred, typ = answer(q, plan, fx)
        if pred is None: continue
        ok = abs(pred - q["answer"]) <= 0.02 * abs(q["answer"]) if isinstance(q["answer"], float) else pred == q["answer"]
        per_type[typ][1] += 1; per_type[typ][0] += int(ok)
    rows.append(dict(stem=stem, findings=[f["rule"] for f in F]))
n = len(stems)
med = lambda a: sorted(a)[len(a) // 2]
summary = dict(plans=n, failures=failures, per_type={k: v for k, v in per_type.items()},
    median_ms={k: round(med(v), 1) for k, v in stage.items()}, max_total_ms=round(max(stage["total_ms"]), 1),
    sum_total_s=round(sum(stage["total_ms"]) / 1e3, 2), personas_total=sum(stage["personas"]),
    rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
    findings_by_rule=dict(collections.Counter(r for row in rows for r in row["findings"])),
    plans_with_high=sum(1 for row in rows if any(r in ("WALK_THROUGH_ROOM", "UNREACHABLE", "WET_ROOM_THROUGH_ROOM", "KITCHEN_THROUGH_ROOM", "DOOR_SWING_CLASH") for r in row["findings"])))
json.dump(summary, open("/home/claude/out/benchmark.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
tot = sum(v[1] for v in per_type.values()); ok = sum(v[0] for v in per_type.values()); print("overall", ok, "/", tot)
