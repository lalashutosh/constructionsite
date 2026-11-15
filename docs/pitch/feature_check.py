"""Runs every feature the pitch video shows against the live engine (localhost:8001) and writes the real answers
to docs/pitch/feature_check.md, so the script only promises what works.  .venv/bin/python docs/pitch/feature_check.py"""
import json
import pathlib
import time

import httpx

API = "http://localhost:8001/api"
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/pitch/feature_check.md"
c = httpx.Client(timeout=900)
lines = ["# Feature check (live engine)", f"run {time.strftime('%Y-%m-%d %H:%M')}", ""]


def ask(path, q, **kw):
    t = time.time()
    try:
        r = c.post(f"{API}/ask", json={"path": path, "question": q, "benchmark": False, **kw})
        d = r.json()
        txt = d.get("answer_text") or d.get("refusal") or str(d.get("detail") or d.get("value"))
        return f"{txt}  [{d.get('tier', '?')}, {time.time() - t:.1f} s, ${(d.get('cost') or {}).get('usd', 0):.4f}]"
    except Exception as e:  # noqa: BLE001
        return f"ERROR {type(e).__name__}: {e}"


def section(title):
    lines.extend(["", f"## {title}", ""])


def row(q, a):
    lines.append(f"- **{q}** -> {a}")
    print(q, "->", a[:140], flush=True)


# 1 ask anything, in any language (same plan, six languages)
section("Ask in any language (data/cubicasa5k/colorful-2002.png)")
p = "data/cubicasa5k/colorful-2002.png"
for q in ["How many bedrooms are there?", "Montako makuuhuonetta asunnossa on?", "Hur många sovrum finns det?",
          "Wie viele Schlafzimmer gibt es?", "Mitu magamistuba on?", "Combien de chambres y a-t-il ?",
          "Hoeveel slaapkamers zijn er?", "¿Cuántos dormitorios hay?",
          "How many doors?", "Montako ovea?", "What is the total length of the walls of the kitchen?"]:
    row(q, ask(p, q))

# 2 photo vs blueprint (triage)
section("Photo or blueprint? (a portrait photo uploaded as a 'drawing')")
ph = pathlib.Path.home() / "Downloads/01Connery-appraisal-articleLarge.jpg"
if ph.exists():
    up = c.post(f"{API}/upload", files={"file": (ph.name, ph.read_bytes(), "image/jpeg")}).json()["path"]
    row("photo: How many doors?", ask(up, "How many doors?"))

# 3 one sheet, two floors (printed floor names)
section("One picture, two floors (data/cubicasa5k/colorful-13685.png)")
try:
    g = c.get(f"{API}/geometry", params={"path": "data/cubicasa5k/colorful-13685.png"}).json()
    fl = (g.get("check") or {}).get("floors") or []
    row("floors found", f"{len(fl)}: {[f.get('label') for f in fl]}")
except Exception as e:  # noqa: BLE001
    row("floors found", f"ERROR {e}")
row("How many bedrooms on the second floor?", ask("data/cubicasa5k/colorful-13685.png", "How many bedrooms are on the second floor?"))

# 4 a faint / blurry scan
section("Faint scan (data/cubicasa5k/high_quality_architectural-1967.png)")
p = "data/cubicasa5k/high_quality_architectural-1967.png"
for q in ["What is the scale of this drawing?", "What is the total area of all rooms?", "How many bedrooms are there?"]:
    row(q, ask(p, q))

# 5 one measurement gives every size
section("One measurement gives every size (data/cubicasa5k/high_quality_architectural-594.png)")
p = "data/cubicasa5k/high_quality_architectural-594.png"
row("before: total area", ask(p, "What is the total area of all rooms?"))
try:
    r = c.post(f"{API}/scale", json={"path": p, "anchors": [{"kind": "user", "px_length": 90, "length_m": 4.5}],
                                     "questions": ["What is the total area of all rooms?",
                                                   "What is the overall length and width of the building?"]}).json()
    row("after ONE length (90 px = 4.5 m)", " | ".join(x.get("answer_text") or "" for x in r) if isinstance(r, list) else str(r))
except Exception as e:  # noqa: BLE001
    row("after one length", f"ERROR {e}")

# 6 a messy folder
section("A messy folder (data/opening_design/Sports_Complex)")
folder = pathlib.Path.home() / "Downloads/junction-dataset-preview/data/opening_design/Sports_Complex"
files = [{"path": str(f.relative_to(folder.parents[2])), "name": str(f.relative_to(folder))}
         for f in sorted(folder.rglob("*")) if f.is_file()][:40]
t = time.time()
try:
    b = c.post(f"{API}/building", json={"files": files}).json()
    keys = list(b.keys())
    fl = b.get("floors") or []
    other = b.get("other") or b.get("sheets") or []
    row(f"{len(files)} files", f"{len(fl)} floors in order: {[f.get('name') or f.get('label') for f in fl][:8]}; "
                               f"{len(other)} other sheets; {time.time() - t:.0f} s; keys {keys[:6]}")
except Exception as e:  # noqa: BLE001
    row("folder", f"ERROR {e}")

# 7 the big sheets (deep read, services, piping)
section("Big sheets")
dorm = str(next((ROOT / "cache/uploads").glob("a92115880ee3*.png")))
pipe = str(next((ROOT / "cache/uploads").glob("b25805c1c751*.png")))
for q in ["How many doors?", "How many staircases?", "How many beds?", "Are there more doors or toilets and sinks?",
          "How much pipework do we need?", "How much cable?", "How much waste water flow?", "What is the scale of this drawing?"]:
    row(f"dorm: {q}", ask(dorm, q))
for q in ["How many valves are there?", "How many check valves are there?", "How many fuel pumps are there?",
          "What is the motor control center trench length?", "where is the sheet's printed scale?"]:
    row(f"piping: {q}", ask(pipe, q))
s100 = str(next((ROOT / "cache/uploads").glob("508c207e8dd5*.png")))
for q in ["What is the motor control center trench length?", "How big is the sump?", "How thick is the slab?",
          "What is the overall length and width of the building?"]:
    row(f"foundation: {q}", ask(s100, q))

OUT.write_text("\n".join(lines) + "\n")
print("wrote", OUT)
