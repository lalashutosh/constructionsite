"""Checks: confidence meter + yes/no questions for things that change numbers (docs/decisions/checks-api.md).

get_checks(abs_path, sha, rel_path) -> {"path", "items": [Check]};  answer(abs_path, sha, rel_path, id, answer, value).
A scale question is asked only when confidence < 0.8 or the evidence groups disagree (> 5%); one open scale question at a
time (a 'no' rejects that candidate and the next best one becomes the question). Answers live in cache/checks/<sha>.json.
"""
from __future__ import annotations

import pathlib
from typing import Any, Optional

from engine.scale import sheet_scale as SS

ROOT = pathlib.Path(__file__).resolve().parents[2]
THRESHOLD = 0.8
IMPACT = "All areas, lengths and volumes depend on this."


def _fmt_ppm(ppm: float) -> str:
    return f"{ppm:.2f} px/m" if ppm < 100 else f"{ppm:.1f} px/m"


def _label(lg: dict) -> str:
    """The dimension as printed, rebuilt from its value when OCR dropped the foot mark."""
    if lg["kind"] == "ftin":
        inches = round(lg["m"] / SS.M_PER_IN)
        return f"{inches // 12}'-{inches % 12}\""
    return lg["text"]


def _ask_for(c: dict) -> str:
    if c["family"] == "dim":
        lg = c["longest"]
        orient = "width" if lg["angle"] == 0 else "depth"
        words = "the overall" if lg["len_px"] >= 0.3 * max(1, c.get("sheet_px", 1)) else "the"
        return f"Is {words} {orient} {_label(lg)} ({lg['m']:.1f} m)?"
    if c["family"] == "ratio":
        return f"Is this sheet printed at {c['label']}?"
    return f"Does the graphic scale bar read {c['label'].split(' ', 2)[-1]}?"


def _evidence(c: dict) -> list[dict]:
    return [{"box": [round(v, 1) for v in b], "label": c["label"]} for b in c["boxes"][:8]]


def _order(c: dict) -> tuple:
    # cheapest, most checkable question first: printed ratio > bar > dimension; then by support
    rank = {"ratio": 0, "bar": 1, "dim": 2}[c["family"]]
    return (rank, -c["weight"])


def scale_check(st: dict) -> dict:
    cons, res = st["cons"], st["res"]
    win = cons["winner"]
    base = {"id": "scale", "kind": "scale", "evidence": [], "impact": IMPACT, "value": {}}
    if st["users"]:
        u = st["users"][0]
        return {**base, "id": u["id"], "status": "confirmed", "confidence": 0.99, "question": None,
                "summary": f"Scale confirmed by you: {u['label']} ({_fmt_ppm(u['ppm'])})",
                "evidence": [{"box": b, "label": u["label"]} for b in u["boxes"][:8]],
                "value": {"px_per_m": u["ppm"], "source": "user", "tag": "chosen"}}
    if win is None:
        none = res["none_notes"]
        if none:
            lab = none[0]["label"].upper()
            return {**base, "id": "scale:none", "status": "open", "confidence": 0.0,
                    "summary": f"The sheet says \"{lab}\": there is no scale to read.",
                    "question": f"This sheet is marked \"{lab}\". Treat areas and lengths as relative (no real units)?",
                    "evidence": [{"box": n["box"], "label": n["label"]} for n in none[:3]],
                    "value": {"px_per_m": None, "relative": True}}
        return {**base, "id": "scale:missing", "status": "open", "confidence": 0.0,
                "summary": "No scale note, scale bar or readable dimension was found.",
                "question": "No scale could be read. Do you have a known length on this sheet to measure?",
                "value": {"px_per_m": None}}
    conf = st["conf"]
    items = win["items"]
    kinds = ", ".join({"ratio": "scale note", "bar": "scale bar", "dim": "dimension strings"}[f] for f in win["families"])
    ev = [e for c in items for e in _evidence(c)][:10]
    val = {"px_per_m": win["ppm"], "source": items[0]["kind"], "tag": "specified" if any(c["tag"] == "specified" for c in items) else "defaulted"}
    other = [g for g in cons["groups"][1:] if g["score"] >= 0.5 * win["score"]]
    if conf >= THRESHOLD and not cons["conflict"]:
        return {**base, "status": "auto", "confidence": conf, "question": None, "evidence": ev, "value": val,
                "summary": f"Scale {_fmt_ppm(win['ppm'])}: {kinds} agree."}
    # ask the most checkable candidate of the leading group
    cand = sorted(items, key=_order)[0]
    cand = dict(cand, sheet_px=max(res["w"], res["h"]))
    why = (f"; {len(other)} other reading(s) disagree by more than {SS.AGREE:.0%}" if other else "")
    return {**base, "id": cand["id"], "status": "open", "confidence": conf, "evidence": _evidence(cand), "value": val,
            "summary": f"Scale {_fmt_ppm(win['ppm'])} from {kinds}, not certain{why}.", "question": _ask_for(cand)}


def get_checks(abs_path: str, sha: str, rel_path: str, max_px: int = 2000) -> dict:
    st = SS.sheet_state(abs_path, sha, max_px)
    items = [scale_check(st)]
    # at most 3 open questions per file, most impactful first (only one kind exists today)
    opens = 0
    for it in items:
        if it["status"] == "open":
            opens += 1
            if opens > 3:
                it["status"], it["question"] = "auto", None
    return {"path": rel_path, "items": items}


def invalidate(sha: str) -> None:
    """Drop caches that depend on scale: in-memory facts and rendered geometry for this sha."""
    try:
        from engine import cache as facts_cache
        for k in [k for k in facts_cache._MEM if k[0] == sha]:
            facts_cache._MEM.pop(k, None)
    except Exception:  # noqa: BLE001
        pass
    for f in (ROOT / "cache" / "geometry").glob(f"{sha}*.json"):
        try:
            f.unlink()
        except OSError:
            pass


def answer(abs_path: str, sha: str, rel_path: str, check_id: str, ans: str, value: Optional[float] = None,
           max_px: int = 2000) -> dict:
    if ans not in ("yes", "no"):
        raise ValueError("answer must be 'yes' or 'no'")
    st = SS.sheet_state(abs_path, sha, max_px)
    known = {c["id"] for c in st["cands"]} | {"scale:none", "scale:missing"} | {a for a in st["answers"]}
    if check_id not in known:
        raise KeyError(check_id)
    data = SS.load_answers(sha)
    rec: dict[str, Any] = {"answer": ans, "value": value}
    if check_id in ("scale:none", "scale:missing"):
        pass
    data["answers"][check_id] = rec
    SS.save_answers(sha, data)
    invalidate(sha)
    return get_checks(abs_path, sha, rel_path, max_px)
