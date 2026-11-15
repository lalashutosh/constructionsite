"""Dev-only stress harness for big construction sheets.

    .venv/bin/python scripts/stress_big.py [--llm off|on|both] [--files a.png b.pdf] [--manifest cache/stress/manifest.json]
Each (file, llm) pair runs in a fresh subprocess (clean peak RSS): profile -> analyze -> geometry -> scale -> questions.
Writes cache/stress/report.md (+ report.json)."""
from __future__ import annotations

import argparse
import json
import re
import os
import pathlib
import resource
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
QUESTIONS = [
    "How many doors are there?",
    "How many rooms are there?",
    "What is the total area of all rooms?",
    "Which is the largest room and how big is it?",
    "What is the overall length and width of the building?",
    "What is the scale of this drawing?",
    "How many dorm rooms are on this floor?",
]


def _nums(v) -> list[float]:
    if isinstance(v, (int, float)):
        return [float(v)]
    if isinstance(v, (list, tuple)):
        return [float(x) for x in v if isinstance(x, (int, float))]
    if isinstance(v, dict):
        return [float(x) for x in v.values() if isinstance(x, (int, float))]
    return []


def score(qd: dict, a: dict) -> dict:
    """ok True/False/None (None = no truth). Numbers: within tol (default exact for counts, 2% else)."""
    tr, kind = qd.get("truth"), qd.get("kind", "any")
    if tr is None:
        return {"ok": None}
    if kind == "text":
        norm = lambda x: re.sub(r"[\s,]", "", str(x or "")).upper()
        return {"ok": norm(tr) in norm(a.get("text")) or norm(tr) in norm(a.get("value"))}
    if kind == "scale":
        v = a.get("scale")
        return {"ok": bool(v) and abs(v - tr) / tr <= qd.get("tol", 0.03)}
    vals = _nums(a.get("value"))
    if not vals and a.get("text"):
        vals = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", (a.get("text") or "").replace(",", ""))]
    tol = qd.get("tol", 0.0 if kind == "count" else 0.02)
    trs = tr if isinstance(tr, list) else [tr]
    ok = all(any(abs(v - t) <= tol * max(abs(t), 1e-9) + 1e-9 for v in vals) for t in trs)
    return {"ok": ok}


def worker(path: str, llm: str) -> dict:
    os.environ["LLM_PROVIDER"] = "verda" if llm == "on" else "none"
    os.environ.setdefault("DATASET_ROOT", str(pathlib.Path("~/Downloads/junction-dataset-preview").expanduser()))
    out: dict = {"file": path, "llm": llm, "steps": {}, "answers": []}
    t_all = time.perf_counter()
    abs_path = str(ROOT / path) if not os.path.isabs(path) else path
    try:                                         # always measure a cold run (facts / raster / geometry caches cleared)
        from engine import cache as _fc
        _sha = _fc.sha256_file(abs_path)
        for d in ("pipeline", "raster", "geometry", "profile"):
            for f in (ROOT / "cache" / d).glob(f"{_sha}*"):
                f.unlink()
    except Exception:  # noqa: BLE001
        pass
    try:
        from engine import profile as P
        t = time.perf_counter()
        prof = P.profile(abs_path)
        out["steps"]["profile_s"] = round(time.perf_counter() - t, 2)
        out["profile"] = {k: prof.get(k) for k in ("width_px", "height_px", "vector", "sheet_type", "route", "text_density",
                                                  "line_density", "title_block", "border", "views", "notes", "tables", "complexity")}
    except Exception as e:  # noqa: BLE001
        out["profile_error"] = f"{type(e).__name__}: {e}"
    from engine.api import get_engine
    eng = get_engine("pipeline")
    t = time.perf_counter()
    try:
        facts = eng.analyze(abs_path)
        out["steps"]["analyze_s"] = round(time.perf_counter() - t, 2)
        kinds: dict = {}
        for e in facts.elements:
            kinds[e.kind] = kinds.get(e.kind, 0) + 1
        out["facts"] = {"sheet_type": facts.sheet_type, "legible": facts.legible, "elements": kinds,
                        "route": facts.extras.get("route")}
    except Exception as e:  # noqa: BLE001
        out["analyze_error"] = f"{type(e).__name__}: {e}"
    try:                                         # the deep read runs on open in the app: run it here too
        from engine import symbols
        from engine.query import llm as _L
        revs = None
        if llm == "on":
            fast = _L.VerdaLLM(_L.provider(), "fast"); fast.no_think = True
            strong = _L.VerdaLLM(_L.provider(), "strong"); strong.no_think = False; strong.timeout = 240
            revs = [fast, strong]
        t = time.perf_counter()
        ck = symbols.checklist(abs_path, facts.provenance.sha256, facts, llm=revs)
        out["steps"]["deep_read_s"] = round(time.perf_counter() - t, 1)
        out["deep_read"] = [(x["label"], x["count"]) for x in ck.get("totals", [])][:14]
    except Exception as e:  # noqa: BLE001
        out["deep_read_error"] = f"{type(e).__name__}: {e}"
    if abs_path.lower().endswith((".png", ".jpg")):
        t = time.perf_counter()
        try:
            import cv2
            from engine import geometry3d
            img = cv2.imread(abs_path)
            g = geometry3d.model(img, facts, "pixels", use_cnn=True, scan_check=True, llm=None)
            out["steps"]["geometry_s"] = round(time.perf_counter() - t, 2)
            out["geometry"] = {"walls": len(g["walls"]), "rooms": len(g["rooms"]), "note": g.get("wall_note"),
                               "views": [(v.get("n"), v.get("type"), v.get("reader")) for v in (g.get("check") or {}).get("views", [])]}
        except Exception as e:  # noqa: BLE001
            out["geometry_error"] = f"{type(e).__name__}: {e}"
    qs = [{"q": q} for q in QUESTIONS]
    try:
        man = json.loads((ROOT / "cache/stress/manifest.json").read_text())
        qs = next((m["qs"] for m in man if m["file"] == path and m.get("qs")), qs)
    except Exception:  # noqa: BLE001
        pass
    for qd in qs:
        q = qd["q"]
        t = time.perf_counter()
        try:
            po = eng.ask(abs_path, q, benchmark=False)
            out["answers"].append({"q": q, "intent": po.intent, "kind": po.kind, "value": po.value, "unit": po.unit,
                                   "tier": po.tier.value, "text": po.answer_text, "s": round(time.perf_counter() - t, 2),
                                   "usd": round(po.cost.usd, 5), "refusal": po.refusal,
                                   "scale": (po.scale.px_per_m if po.scale else None),
                                   "notes": [n for n in po.notes][-3:]})
            out["answers"][-1].update(score(qd, out["answers"][-1]))
        except Exception as e:  # noqa: BLE001
            out["answers"].append({"q": q, "error": f"{type(e).__name__}: {e}", "s": round(time.perf_counter() - t, 2)})
    out["total_s"] = round(time.perf_counter() - t_all, 1)
    out["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", default="off", choices=["off", "on", "both"])
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--manifest", default=str(ROOT / "cache/stress/manifest.json"))
    ap.add_argument("--out", default=str(ROOT / "cache/stress/report.md"))
    ap.add_argument("--worker", nargs=2)
    a = ap.parse_args()
    if a.worker:
        print("@@" + json.dumps(worker(*a.worker), default=str))
        return
    files = a.files or []
    if not files:
        man = json.loads(pathlib.Path(a.manifest).read_text())
        for m in man:
            files.append(m["file"])
            if m.get("pdf"):
                files.append(m["pdf"])
    modes = ["off", "on"] if a.llm == "both" else [a.llm]
    rows = []
    for f in files:
        for m in modes:
            r = subprocess.run([sys.executable, __file__, "--worker", f, m], capture_output=True, text=True, timeout=900, cwd=ROOT)
            line = next((l for l in r.stdout.splitlines() if l.startswith("@@")), None)
            if line:
                rows.append(json.loads(line[2:]))
            else:
                rows.append({"file": f, "llm": m, "error": (r.stderr or "")[-600:]})
            print(f, m, rows[-1].get("total_s"), rows[-1].get("peak_rss_mb"), flush=True)
    pathlib.Path(a.out).with_suffix(".json").write_text(json.dumps(rows, indent=1, default=str))
    md = ["# Stress report (big construction sheets)", ""]
    for r in rows:
        md.append(f"## {r['file']}  (LLM {r['llm']})")
        if "error" in r:
            md += ["```", r["error"], "```"]
            continue
        md.append(f"total {r.get('total_s')} s, peak RSS {r.get('peak_rss_mb')} MB, steps {r.get('steps')}")
        md.append(f"profile: {r.get('profile') or r.get('profile_error')}")
        md.append(f"facts: {r.get('facts') or r.get('analyze_error')}")
        md.append(f"deep read: {r.get('deep_read') or r.get('deep_read_error')}")
        if "geometry" in r or "geometry_error" in r:
            md.append(f"geometry: {r.get('geometry') or r.get('geometry_error')}")
        md.append("")
        md.append("| question | intent | answer | tier | ok | s | $ |")
        md.append("|---|---|---|---|---|---|---|")
        for x in r["answers"]:
            ans = x.get("error") or (x.get("text") or str(x.get("value"))).replace("|", "/")
            ok = {True: "OK", False: "WRONG", None: "-"}.get(x.get("ok"), "-")
            md.append(f"| {x['q']} | {x.get('intent','')} | {ans[:300]} | {x.get('tier','')} | {ok} | {x['s']} | {x.get('usd','')} |")
        md.append("")
    tot = [x.get("ok") for r in rows for x in r.get("answers", []) if x.get("ok") is not None]
    md.insert(1, f"**score: {sum(1 for t in tot if t)}/{len(tot)} graded answers correct**")
    pathlib.Path(a.out).write_text("\n".join(md))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
