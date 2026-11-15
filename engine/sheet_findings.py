"""The Findings panel: only what the sheet itself prints, each with its printed evidence.

Pure text processing over OCR words (no I/O, no LLM). Every finding carries the boxes of the words it was read
from so the proof view can pin them; a kind with nothing found is simply absent (never a '0 bedrooms' line)."""
from __future__ import annotations

import re

from engine.scale.sheet_scale import norm
from engine.sheet_lookup import AREA_UNIT, TAG_RX, _merge_confusable, _numbers, rows

_COUNT = re.compile(r"(?<![\d.,'\"])(\d{1,4})\s+([A-Za-z]{3,})\s*$")
_INCH = re.compile(r"^(\d{1,2}(?:-\d/\d)?|\d/\d)\s*[\"”″]$")
_SLAB = re.compile(r"\b(\d{2,3})\s*SLAB\b", re.I)
_BAR = re.compile(r"\bD\d{1,2}\s*@\s*\d{2,3}\b", re.I)
_EL = re.compile(r"\bEL\.?\s*=?\s*[\d.]+", re.I)


def _title(s: str) -> str:
    return " ".join(w if w.isupper() and len(w) <= 3 and not w.isalpha() else w.capitalize()
                    for w in s.strip().split())


def _clean_label(s: str) -> str:
    s = re.sub(r"[=\-–:;,.]+\s*$", "", s.strip())
    return _title(s) if s else "Total"


def _boxes(rs: list[dict]) -> list[list[float]]:
    return [list(r["box"]) for r in rs]


def _areas(rs: list[dict]) -> dict | None:
    items = []
    for r in sorted(rs, key=lambda r: (r["angle"], r["box"][1], r["box"][0])):
        t = r["text"]
        m = AREA_UNIT.search(t)
        if not m:
            continue
        nums = [n for n in _numbers(t) if n[2] < m.start()]
        if not nums:
            continue
        n = nums[-1]
        unit = "m²" if "M" in m.group(1).upper() and "F" not in m.group(1).upper() else "SF"
        items.append({"label": _clean_label(t[: n[2]]), "value": f"{n[0]} {unit}", "boxes": _boxes([r])})
    if len(items) < 2:
        return None
    return {"id": "area_table", "kind": "area_table", "title": "Floor areas printed on the sheet", "items": items,
            "text": "; ".join(f"{i['label']} {i['value']}" for i in items) + "."}


_NOT_COUNTED = {"JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER",
                "NOVEMBER", "DECEMBER", "DEEP", "WIDE", "HIGH", "LONG", "THICK", "MM", "INCHES", "FEET", "DEGREES"}


def _counts(rs: list[dict]) -> dict | None:
    items = []
    for r in sorted(rs, key=lambda r: (r["angle"], r["box"][1], r["box"][0])):
        t = r["text"]
        if AREA_UNIT.search(t):
            continue
        m = _COUNT.search(t)
        if not m or re.search(r"[\"'’′”″]\s*$", t):
            continue
        n = [n for n in _numbers(t) if n[2] == m.start(1)]
        if not n:
            continue
        word = m.group(2).upper()
        if (1900 <= n[0][1] <= 2100 or word in _NOT_COUNTED or not word.endswith("S")
                or re.search(r"\b[Xx@]\s*$", t[: m.start(1)])):
            continue                       # dates ('2024 FEBRUARY'), sizes ('X 300 DEEP'), singular words ('5 BED')
        items.append({"label": _clean_label(t[: m.start(1)]), "value": f"{m.group(1)} {m.group(2).upper()}",
                      "boxes": _boxes([r])})
    if len(items) < 2:
        return None
    return {"id": "count_table", "kind": "count_table", "title": "Counts printed on the sheet", "items": items,
            "text": "; ".join(f"{i['label']} {i['value']}" for i in items) + "."}


def _equipment(ws: list[dict]) -> dict | None:
    found: dict[str, dict] = {}
    for w in ws:
        t = norm(str(w.get("text", ""))).strip(".,:;()_|")
        m = TAG_RX.match(t)
        if not m:
            continue
        tag = f"{m.group(1)}-{int(m.group(2))}{m.group(3)}"
        if tag not in found or w.get("conf", 0) > found[tag].get("conf", 0):
            found[tag] = w
    found = _merge_confusable(found)
    series: dict[str, list[str]] = {}
    for tag in found:
        series.setdefault(tag.split("-")[0], []).append(tag)
    items = []
    for name, tags in series.items():
        nums = {int(re.match(r"[A-Z]+-(\d+)", t).group(1)) for t in tags}
        if len(nums) < 3 or (len(name) == 1 and name != "PS"):
            continue
        ordered = sorted(tags, key=lambda t: (int(re.match(r"[A-Z]+-(\d+)", t).group(1)), t))
        items.append({"label": name, "value": f"{len(nums)} tags ({ordered[0]}..{ordered[-1]})",
                      "boxes": [list(found[t]["box"]) for t in ordered], "_n": len(nums)})
    if not items:
        return None
    items.sort(key=lambda i: (-i["_n"], i["label"]))
    for i in items:
        i.pop("_n")
    return {"id": "equipment", "kind": "equipment", "title": "Tagged equipment", "items": items,
            "text": "; ".join(f"{i['label']}: {i['value']}" for i in items) + "."}


def _inches(text: str) -> float | None:
    m = _INCH.match(norm(text).strip())
    if not m:
        return None
    s = m.group(1)
    try:
        if "/" in s:
            whole, _, frac = s.partition("-")
            num, den = frac.split("/")
            v = (float(whole) if whole else 0.0) + float(num) / float(den)
        else:
            v = float(s)
    except (ValueError, ZeroDivisionError):
        return None
    return v if 0.5 <= v <= 48 else None


def _pipes(ws: list[dict]) -> dict | None:
    sizes: dict[str, list[dict]] = {}
    for w in ws:
        t = norm(str(w.get("text", ""))).strip()
        if _inches(t) is None:
            continue
        label = t.replace("”", '"').replace("″", '"').replace(" ", "")
        sizes.setdefault(label, []).append(w)
    total = sum(len(v) for v in sizes.values())
    if total < 8 or len(sizes) < 2:
        return None
    items = [{"label": k, "value": str(len(v)), "boxes": [list(w["box"]) for w in v]}
             for k, v in sorted(sizes.items(), key=lambda kv: (-len(kv[1]), _inches(kv[0]) or 0))]
    return {"id": "pipe_sizes", "kind": "pipe_sizes", "title": "Pipe / duct sizes called out", "items": items,
            "text": "; ".join(f"{i['label']} × {i['value']}" for i in items) + "."}


def _slabs(rs: list[dict]) -> dict | None:
    hor = sorted([r for r in rs if r["angle"] == 0], key=lambda r: (r["box"][1], r["box"][0]))
    items, seen = [], set()
    for i, r in enumerate(hor):
        m = _SLAB.search(r["text"])
        if not m:
            continue
        near, cur = [r], r
        for s in hor[i + 1:]:
            if s["box"][1] - cur["box"][3] > 1.8 * max(cur["h"], 1):
                if s["box"][1] - cur["box"][3] > 4 * max(cur["h"], 1):
                    break
                continue
            if s["box"][0] < cur["box"][2] + cur["h"] and s["box"][2] > cur["box"][0] - cur["h"] and len(near) < 5:
                near.append(s)
                cur = s
        text = norm(" ".join(x["text"] for x in near))
        key = re.sub(r"\s+", " ", text).strip().upper()
        if key in seen:
            continue
        seen.add(key)
        bar = _BAR.search(text)
        el = _EL.search(text)
        parts = []
        if bar:
            parts.append(re.sub(r"\s*@\s*", " @ ", bar.group(0)).upper())
        if el:
            e = re.sub(r"\s*=\s*", " ", el.group(0)).upper()
            parts.append("top " + re.sub(r"^EL\.?\s*", "EL ", e).strip())
        label = _title(re.sub(r"\s+", " ", r["text"]).strip())
        if len(label) > 60:
            label = f"{m.group(1)} slab-on-grade"
        items.append({"label": label, "value": ", ".join(parts) if parts else f"{m.group(1)} slab",
                      "boxes": _boxes(near)})
    if not items:
        return None
    return {"id": "slab_types", "kind": "slab_types", "title": "Slab types called out", "items": items,
            "text": "; ".join(f"{i['label']}: {i['value']}" for i in items) + "."}


def _note(rs: list[dict]) -> dict | None:
    for r in sorted(rs, key=lambda r: (r["box"][1], r["box"][0])):
        m = re.match(r"\s*SCALE\b[:\s]*(.*)$", r["text"], re.I)
        if m and m.group(1).strip():
            return {"id": "note_scale", "kind": "note", "title": "Scale note",
                    "items": [{"label": "Scale", "value": m.group(1).strip(), "boxes": _boxes([r])}],
                    "text": f"Scale {m.group(1).strip()}."}
    return None


def findings(words: list[dict]) -> list[dict]:
    """Findings ordered by usefulness, at most 12; each item carries the boxes of its printed evidence."""
    try:
        ws = [w for w in (words or []) if isinstance(w, dict) and isinstance(w.get("box"), (list, tuple))
              and len(w["box"]) == 4 and w.get("text") is not None]
        if not ws:
            return []
        rs = rows(ws)
        out = [f for f in (_areas(rs), _counts(rs), _equipment(ws), _pipes(ws), _slabs(rs), _note(rs)) if f]
        return out[:12]
    except Exception:  # noqa: BLE001 - odd OCR input must never break the panel
        return []
