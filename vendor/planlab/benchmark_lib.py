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
