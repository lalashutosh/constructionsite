"""What the SHEET ITSELF prints, read back with a receipt (no LLM, no network).

Big construction sheets answer many questions in print: notes ("MOTOR CONTROL CENTER TRENCH LENGTH - 4275"),
schedules / area tables ("TOTAL WEST WING = 7,009 SF", "SECOND FLOOR = 48 DORMS"), equipment tags (FP-1 .. FP-5) and
overall dimension strings (27000, 323'-4"). This module finds them in the OCR / PDF text layer
(engine/scale/sheet_text.words) and returns the value WITH the boxes of the printed words, tagged `specified`.

  lookup(abs_path, sha, question)          -> best matching printed row(s) for a free question, or None
  tag_count(abs_path, sha, question)       -> 'how many fuel pumps' -> distinct FP-n tags (+ targeted re-read of gaps)
  printed_total_area(abs_path, sha)        -> the largest 'TOTAL ... = n SF / m2' row
  overall_dims(abs_path, sha, ppm)         -> largest printed dimension per direction, verified (line length at the
                                              solved scale, or equal to the sum of a printed dimension chain)
Every result carries `boxes` (original image px) and `rows` (the printed text) for the proof view."""
from __future__ import annotations

import itertools
import re
from typing import Any, Optional

import numpy as np

from engine.scale import sheet_scale as S
from engine.scale import sheet_text as T

SQFT_M2 = 0.09290304
STOP = set("""how many much what which is are was were the a an of on in at to for this that these those there does do
did be by with and or from all every each sheet printed written shown where located location find show say says
said mention mentioned noted note drawing plan blueprint shown show tell me please its it as per give find value big
large size number total""".split())
KEEP_IN_TOTAL = {"total"}            # 'total' is a stopword for matching, but a row that says TOTAL is preferred
AREA_CUE = re.compile(r"\b(area|square|footage|sq\.?\s*(ft|m)|sf|m2|m²|floor\s*space)\b", re.I)
AREA_UNIT = re.compile(r"\b(SF|S\.F\.|SQ\.?\s*FT\.?|SQFT|M2|M²|SQ\.?\s*M)\b", re.I)
NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w])")
DONE = re.compile(r"(\d|\b(?:SF|MM|M2|M²|DORMS?|EA|TYP\.?)|\))\s*\.?$", re.I)
PROPERTY = {"thick", "thickness", "deep", "depth", "long", "length", "wide", "width", "high", "height", "tall", "big",
            "large", "size", "dimension", "elevation", "level", "diameter", "spacing", "far", "distance", "area"}
LENGTH_Q = re.compile(r"\b(how\s+long|length|how\s+wide|width|how\s+far|distance)\b", re.I)
ORD = {"FIRST": 1, "1ST": 1, "GROUND": 1, "SECOND": 2, "2ND": 2, "THIRD": 3, "3RD": 3, "FOURTH": 4, "4TH": 4,
       "FIFTH": 5, "5TH": 5, "BASEMENT": 0}
GLOSSARY = {   # common drawing abbreviations; the sheet's own '(ABBR)' definitions are tried first
    "fuel pump": "FP", "check valve": "CV", "filter separator": "FS", "pipe support": "PS", "pressure gauge": "PG",
    "exhaust fan": "EF", "air handling unit": "AHU", "air handler": "AHU", "fan coil": "FCU", "variable air volume": "VAV",
    "fire extinguisher": "FE", "pump": "P", "valve": "V", "column": "C", "footing": "F", "beam": "B",
    "unit heater": "UH", "water heater": "WH", "manual air vent": "MAV", "transmitter": "PIT", "control valve": "CV",
}


# --------------------------------------------------------------------------- text rows / blocks
def _words(abs_path: str, sha: str) -> list[dict]:
    return T.words(abs_path, sha)


def rows(ws: list[dict], gap_h: float = 12.0) -> list[dict]:
    """Words on one baseline, allowing the wide gaps of a table ('TOTAL WEST WING =      7,009 SF')."""
    out = []
    for ang in (0, 90):
        items = [w for w in ws if w.get("angle", 0) == ang]
        ax = (lambda b: (b[0], b[2], (b[1] + b[3]) / 2, b[3] - b[1])) if ang == 0 else \
             (lambda b: (b[1], b[3], (b[0] + b[2]) / 2, b[2] - b[0]))
        lines: list[list[dict]] = []
        ends: list[float] = []
        for w in sorted(items, key=lambda w: ax(w["box"])[0]):
            a0, a1, c, h = ax(w["box"])
            best, bd = None, None
            for k, ln in enumerate(lines):
                _, _, lc, lh = ax(ln[-1]["box"])
                hh = max(h, lh)
                gap = a0 - ends[k]
                wide_ok = bool(re.match(r"^[=\d(]|^(SF|S\.F\.|SQ|M2|M²|MM|FT)\b", S.norm(w["text"]), re.I))
                lim = (gap_h if wide_ok else 2.2) * min(h, lh)       # table value columns may sit far right
                if abs(lc - c) < 0.45 * hh and -0.5 * h < gap < lim and 0.6 < h / max(lh, 1) < 1.7:
                    if bd is None or abs(lc - c) < bd:
                        best, bd = k, abs(lc - c)
            if best is None:
                lines.append([w])
                ends.append(a1)
            else:
                lines[best].append(w)
                ends[best] = max(ends[best], a1)
        for ln in lines:
            xs0 = [w["box"][0] for w in ln]; ys0 = [w["box"][1] for w in ln]
            xs1 = [w["box"][2] for w in ln]; ys1 = [w["box"][3] for w in ln]
            hs = [ax(w["box"])[3] for w in ln]
            out.append({"text": S.norm(" ".join(w["text"] for w in ln)), "box": [min(xs0), min(ys0), max(xs1), max(ys1)],
                        "angle": ang, "h": float(np.median(hs)), "words": ln})
    return out


def blocks(rs: list[dict]) -> list[dict]:
    """A row plus the rows directly under it that continue the same note (left edges close, small line gap)."""
    hor = sorted([r for r in rs if r["angle"] == 0], key=lambda r: (r["box"][1], r["box"][0]))
    out = []
    for i, r in enumerate(hor):
        blk = [r]
        cur = r
        for s in hor[i + 1:]:
            if s["box"][1] - cur["box"][3] > 1.8 * cur["h"]:
                if s["box"][1] - cur["box"][3] > 4 * cur["h"]:
                    break
                continue
            if DONE.search(cur["text"]):           # 'TRENCH LENGTH - 4275' / '= 26,562 SF' ends a statement
                break
            if (abs(s["box"][0] - cur["box"][0]) < 3.0 * cur["h"] or
                    (s["box"][0] < cur["box"][2] and s["box"][2] > cur["box"][0] and len(cur["text"]) <= 12)) and 0.7 < s["h"] / cur["h"] < 1.4 and s["box"][1] > cur["box"][1]:
                blk.append(s)
                cur = s
                if len(blk) >= 4:
                    break
        out.append({"text": " ".join(b["text"] for b in blk), "rows": blk, "h": r["h"],
                    "box": [min(b["box"][0] for b in blk), min(b["box"][1] for b in blk),
                            max(b["box"][2] for b in blk), max(b["box"][3] for b in blk)]})
    return out + [{"text": r["text"], "rows": [r], "h": r["h"], "box": r["box"]} for r in rs if r["angle"] == 90]


def _stem(w: str) -> str:
    w = w.lower().strip(".,:;()'\"-/")
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def keywords(question: str) -> list[str]:
    toks = re.findall(r"[A-Za-z][A-Za-z\-]+", question)
    out = []
    for t in toks:
        for part in t.split("-"):
            s = _stem(part)
            if len(s) >= 3 and s not in STOP and s not in PROPERTY and s not in out and not AREA_CUE.fullmatch(part):
                out.append(s)
    return out


def _tok_match(kw: str, text: str) -> bool:
    for tok in re.findall(r"[A-Za-z]+", text):
        t = _stem(tok)
        if t == kw or (len(kw) >= 4 and t.startswith(kw)) or (len(t) >= 4 and kw.startswith(t)):
            return True
    return False


def this_floor(rs: list[dict]) -> Optional[int]:
    """Floor of the sheet from its title ('SECOND FLOOR PLAN'): the tallest such row that is not a table row."""
    best = None
    for r in rs:
        m = re.search(r"\b(FIRST|1ST|GROUND|SECOND|2ND|THIRD|3RD|FOURTH|4TH|FIFTH|5TH|BASEMENT)\s+FLOOR\b", r["text"].upper())
        if m and "=" not in r["text"] and "PLAN" in r["text"].upper():
            if best is None or r["h"] > best[0]:
                best = (r["h"], ORD[m.group(1)])
    return best[1] if best else None


def _numbers(text: str) -> list[tuple[str, float, int]]:
    return [(m.group(1), float(m.group(1).replace(",", "")), m.start()) for m in NUM.finditer(text)]


# --------------------------------------------------------------------------- free lookup
def lookup(abs_path: str, sha: str, question: str) -> Optional[dict]:
    """Rows whose words cover the question's content words. Returns {value, kind, text, rows, boxes, coverage, unit}."""
    kws = keywords(question)
    if not kws:
        return None
    ws = _words(abs_path, sha)
    rs = rows(ws)
    floor = this_floor(rs) if re.search(r"\bthis\s+(floor|level|storey|story)\b", question, re.I) else None
    want_area = bool(AREA_CUE.search(question))
    want_count = bool(re.search(r"\bhow\s+many\b|\bnumber\s+of\b|\bcount\b", question, re.I))
    want_total = bool(re.search(r"\btotal\b", question, re.I))
    want_length = bool(LENGTH_Q.search(question)) and not want_area
    props = [_stem(w) for w in re.findall(r"[A-Za-z]+", question) if _stem(w) in PROPERTY]
    scored = []
    for b in blocks(rs):
        t = b["text"]
        hit = [k for k in kws if _tok_match(k, t)]
        if not hit:
            continue
        cov = len(hit) / len(kws)
        nums = _numbers(t)
        if not nums:
            continue
        sc = cov + 0.02 * len(hit)
        if want_area and not AREA_UNIT.search(t):
            continue                                            # an area question needs a printed area
        if want_length and AREA_UNIT.search(t):
            continue                                            # ... and a length question is not answered by one
        if any(_tok_match(pw, t) for pw in props):
            sc += 0.1
        if want_total and "TOTAL" in t.upper():
            sc += 0.15
        if floor is not None:
            m = re.search(r"\b(FIRST|1ST|GROUND|SECOND|2ND|THIRD|3RD|FOURTH|4TH|FIFTH|5TH|BASEMENT)\b", t.upper())
            if m:
                sc += 0.4 if ORD[m.group(1)] == floor else -0.4
        if not want_total and re.match(r"\s*TOTAL\b", t.upper()):
            sc -= 0.1
        sc -= 0.01 * max(0, len(t) / 40 - 2)                     # a long paragraph matches anything a little
        scored.append((sc, cov, b, hit))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    top_sc, cov, b, hit = scored[0]
    need = 0.5 if len(kws) >= 3 else (0.99 if len(kws) == 2 else 1.0)
    if cov < need:
        return None
    t = b["text"]
    nums = _numbers(t)
    kind, unit, value = "text", None, t
    if want_area and AREA_UNIT.search(t):
        m = AREA_UNIT.search(t)
        before = [n for n in nums if n[2] < m.start()]
        n = before[-1] if before else nums[-1]
        u = m.group(1).upper()
        kind, unit = "area", "m2"
        value = n[1] * SQFT_M2 if ("F" in u) else n[1]
        printed = f"{n[0]} {'SF' if 'F' in u else 'm²'}"
    elif want_count:
        # only a number printed AS a count: '48 DORMS', '(TYP. OF 5)', 'QTY 3', '= 12 EA' (not the pipe size '2"')
        n = _printed_count(t, hit)
        if n is None:
            return None
        kind, value, printed = "count", n, str(n)
    else:
        printed = t
        if _garbled(t):                                     # OCR lost part of the note: re-read just that box
            rr = reread_box(abs_path, b["box"], b["h"])
            if rr and len(re.findall(r"\d", rr)) > len(re.findall(r"\d", t)):
                printed = value = t = rr
    alts = [s for s in scored[1:4] if s[0] >= top_sc - 0.05 and s[2]["text"] != t]
    return {"value": value, "kind": kind, "unit": unit, "printed": printed, "text": t, "coverage": round(cov, 2),
            "rows": [r["text"] for r in b["rows"]], "boxes": [r["box"] for r in b["rows"]], "keywords": kws, "hit": hit,
            "floor": floor, "alts": [{"text": a[2]["text"], "box": a[2]["box"]} for a in alts]}


def _printed_count(t: str, hit: list[str]) -> Optional[int]:
    m = re.search(r"\bTYP(?:ICAL|\.)?\s*(?:OF\s*)?\(?(\d{1,3})\)?", t, re.I) or re.search(r"\bQTY\.?\s*:?\s*(\d{1,4})\b", t, re.I) \
        or re.search(r"\b(\d{1,4})\s*(?:EA|EACH|NOS?\.?|PCS)\b", t, re.I)
    if m:
        return int(m.group(1))
    for mm in re.finditer(r"(?<![\d.,'\"])(\d{1,4})\s+([A-Za-z]+)", t):
        if any(_tok_match(k, mm.group(2)) for k in hit):
            return int(mm.group(1))
    return None


def _garbled(t: str) -> bool:
    """A note that starts or ends mid-expression ('SUMP X 300 DEEP', '600 X')."""
    return bool(re.search(r"(?:^|[A-Z]{3,}\s+)[Xx@]\s+\d|\d\s*[Xx@]\s*$|\b[Xx]\s+[Xx]\b", t))


def reread_box(abs_path: str, box: list[float], h: float) -> Optional[str]:
    """Second OCR of one note box at 2x, as a block of text (psm 6). Raster sheets only."""
    import cv2
    import pytesseract
    g = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)
    if g is None:
        return None
    H, W = g.shape
    x0, y0 = max(0, int(box[0] - 3 * h)), max(0, int(box[1] - 1.5 * h))
    x1, y1 = min(W, int(box[2] + 3 * h)), min(H, int(box[3] + 1.5 * h))
    crop = cv2.resize(g[y0:y1, x0:x1], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    try:
        txt = pytesseract.image_to_string(crop, config="--psm 6", timeout=20)
    except Exception:  # noqa: BLE001
        return None
    lines = [ln.strip() for ln in txt.splitlines() if re.search(r"[A-Za-z0-9]{2,}", ln)]
    return S.norm(" ".join(lines)) or None


# --------------------------------------------------------------------------- equipment tags
def _noun(question: str) -> Optional[str]:
    m = re.search(r"\bhow\s+many\s+(.+?)(?:\s+(?:are|is|do|does|can|there|on|in|shown|exist|appear)\b|\?|$)", question, re.I)
    if not m:
        m = re.search(r"\bnumber\s+of\s+(.+?)(?:\s+(?:are|is|on|in|shown)\b|\?|$)", question, re.I)
    return m.group(1).strip().lower() if m else None


TAG_RX = re.compile(r"^([A-Z]{1,4})-?(\d{1,3})([A-Z]?)$")


def _prefixes(noun: str, rs: list[dict]) -> list[tuple[str, str]]:
    """Candidate tag prefixes for a noun: the sheet's own '(CV)' definitions, initials, glossary. [(prefix, why)]"""
    words = [_stem(w) for w in re.findall(r"[a-z]+", noun) if w not in STOP]
    out: list[tuple[str, str]] = []
    for r in rs:                                        # 'NON-SURGE CHECK VALVE (CV) W/ ...'
        for m in re.finditer(r"\(([A-Z]{1,4})\)", r["text"]):
            pre = r["text"][: m.start()]
            if words and all(_tok_match(w, pre[-60:]) for w in words):
                out.append((m.group(1), f"the sheet defines ({m.group(1)}) as '{pre[-40:].strip()}'"))
    if len(words) >= 2:
        out.append(("".join(w[0] for w in words).upper(), f"initials of '{noun}'"))
    key = " ".join(words)
    for k, v in GLOSSARY.items():
        if " ".join(_stem(x) for x in k.split()) == key:
            out.append((v, f"standard abbreviation {v} = {k}"))
    seen, uniq = set(), []
    for p, why in out:
        if p not in seen:
            seen.add(p)
            uniq.append((p, why))
    return uniq


def _tags(ws: list[dict], prefix: str) -> dict[str, dict]:
    """Distinct tags PREFIX[+1 letter]-n read on the sheet -> {tag: word}."""
    out: dict[str, dict] = {}
    for w in ws:
        t = S.norm(w["text"]).strip(".,:;()_|")
        m = TAG_RX.match(t)
        if not m:
            continue
        letters = m.group(1)
        if letters == prefix or (letters.startswith(prefix) and len(letters) == len(prefix) + 1):
            tag = f"{letters}-{int(m.group(2))}{m.group(3)}"
            if tag not in out or w.get("conf", 0) > out[tag].get("conf", 0):
                out[tag] = w
    return out


def _reread_bands(abs_path: str, ws_found: list[dict]) -> list[dict]:
    """Targeted second OCR of the rows where a tag series was found (2x upscale): underlined / small tags."""
    import cv2
    g = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)
    if g is None:
        return []
    H, W = g.shape
    out = []
    bands = []
    for w in ws_found:
        y0, y1 = w["box"][1], w["box"][3]
        h = y1 - y0
        if not any(abs(b[0] - y0) < h for b in bands):
            bands.append((y0, y1, h))
    xs = [w["box"][0] for w in ws_found] + [w["box"][2] for w in ws_found]
    x0, x1 = max(0, int(min(xs) - 0.15 * W)), min(W, int(max(xs) + 0.15 * W))
    for (y0, y1, h) in bands[:6]:
        a, b = max(0, int(y0 - 1.5 * h)), min(H, int(y1 + 1.5 * h))
        crop = cv2.resize(g[a:b, x0:x1], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        for t, x, y, ww, hh, c in T._tess(crop, timeout=30):
            out.append({"text": t, "box": [x0 + x / 2, a + y / 2, x0 + (x + ww) / 2, a + (y + hh) / 2], "conf": c, "angle": 0})
    return out


_CONF = [set("IL1T"), set("O0DQ"), set("S5"), set("B8"), set("Z2")]


def _merge_confusable(found: dict[str, dict]) -> dict[str, dict]:
    """FSL-2 next to FSI-1/FSI-4/FSI-5 is FSI-2 misread: series whose names differ only in OCR-confusable letters
    are merged into the most frequent spelling."""
    series: dict[str, list[str]] = {}
    for tg in found:
        series.setdefault(tg.split("-")[0], []).append(tg)
    names = sorted(series, key=lambda n: -len(series[n]))
    canon: dict[str, str] = {}
    for n in names:
        tgt = next((c for c in canon.values() if len(c) == len(n) and c != n and all(
            a == b or any(a in g and b in g for g in _CONF) for a, b in zip(c, n))), None)
        canon[n] = tgt or n
    out: dict[str, dict] = {}
    for tg, w in found.items():
        name, num = tg.split("-", 1)
        out.setdefault(f"{canon[name]}-{num}", w)
    return out


# ISA-5.1 instrument tags: succeeding letters say what the device IS (FCV flow control valve, PIT pressure indicating
# transmitter, PG pressure gauge). Used only when neither the sheet nor the glossary defines the series.
ISA_FUNC = [("CV", "control valve"), ("V", "valve"), ("IT", "indicating transmitter"), ("T", "transmitter"),
            ("G", "gauge"), ("I", "indicator"), ("S", "switch"), ("E", "element"), ("C", "controller"), ("R", "recorder")]


def _sheet_defs(rs: list[dict]) -> dict[str, str]:
    """'NON-SURGE CHECK VALVE (CV) W/ ...' -> {'CV': 'non-surge check valve'} (the words before the brackets)."""
    out: dict[str, str] = {}
    for r in rs:
        for m in re.finditer(r"\(([A-Z]{1,5})\)", r["text"]):
            pre = re.sub(r"[^A-Za-z /-]", " ", r["text"][: m.start()]).split()
            if pre:
                out.setdefault(m.group(1), " ".join(pre[-4:]).lower())
    return out


_DICT: Optional[set] = None


def _english(w: str) -> bool:
    """Is this an ordinary word (SWING, MUST) rather than a device tag (BPCV)? System word list when present."""
    global _DICT
    if _DICT is None:
        try:
            _DICT = {x.strip().lower() for x in open("/usr/share/dict/words", encoding="utf-8", errors="ignore") if len(x) <= 8}
        except OSError:
            _DICT = set()
    w = w.lower()
    return any(x in _DICT for x in (w, w[:-3], w[:-3] + "e", w[:-1], w[:-2], w[:-2] + "e")
               if len(x) >= 3 and x != w[:-1] or x == w)       # using -> use, swings -> swing


def expand(series: str, defs: dict[str, str], numbered: bool = True) -> tuple[str, str]:
    """What a tag series means and where that meaning comes from: the sheet, the glossary, or ISA-5.1 letters."""
    if series in defs:
        return defs[series], f"the sheet defines ({series}) as '{defs[series]}'"
    for k, v in GLOSSARY.items():
        if v == series:
            return k, f"standard abbreviation {series} = {k}"
    if len(series) < 3 or (not numbered and _english(series)):
        return "", ""                                      # 'AV', 'SWING': not an instrument tag
    for suf, name in ISA_FUNC:
        if series.endswith(suf) and len(series) > len(suf):
            return name, f"ISA-5.1 tag letters: {series} ends in '{suf}' = {name}"
    return "", ""


def class_count(abs_path: str, sha: str, noun: str) -> Optional[dict]:
    """'how many valves': every tag series on the sheet whose MEANING is a valve (check valves CV-n, control valves
    FSCV-n, a single BPCV ...). Distinct numbered tags + unnumbered tag words. Returns a breakdown per series."""
    words = [_stem(w) for w in re.findall(r"[a-z]+", noun.lower()) if w not in STOP]
    if len(words) != 1:
        return None
    cls = words[0]
    ws = _words(abs_path, sha)
    rs = rows(ws)
    defs = _sheet_defs(rs)
    numbered: dict[str, dict] = {}
    plain: dict[str, list] = {}
    for w in ws:
        t = S.norm(w["text"]).strip(".,:;()_|")
        m = TAG_RX.match(t)
        if m and len(m.group(1)) >= 2:
            numbered.setdefault(f"{m.group(1)}-{int(m.group(2))}{m.group(3)}", w)
        elif re.fullmatch(r"[A-Z]{2,5}", t):
            plain.setdefault(t, []).append(w)
    numbered = _merge_confusable(numbered)
    series: dict[str, list[str]] = {}
    for tg in numbered:
        series.setdefault(tg.split("-")[0], []).append(tg)
    groups = []
    for name in sorted(set(series) | set(plain)):
        meaning, why = expand(name, defs, numbered=name in series)
        if not meaning or not any(_tok_match(cls, x) for x in meaning.split()):
            continue
        if series.get(name):                 # small / underlined tags: re-read the rows of this series once
            try:
                extra = _merge_confusable(_tags(_reread_bands(abs_path, [numbered[t] for t in series[name]]), name))
                for k, v in extra.items():
                    if k.split("-")[0] == name and k not in numbered:
                        numbered[k] = v
                        series[name].append(k)
            except Exception:  # noqa: BLE001
                pass
        tags = sorted(series.get(name, []), key=lambda t: int(re.sub(r"\D", "", t.split("-")[1]) or 0))
        if tags:
            boxes = [numbered[t]["box"] for t in tags]
            n = len(tags)
        elif name in defs or name in GLOSSARY.values() or len(plain.get(name, [])) <= 3:
            boxes = [w["box"] for w in plain.get(name, [])]   # an unnumbered device drawn once or twice (BPCV)
            n = len(boxes)
        else:
            continue
        typ = next((_printed_count(r["text"], []) for r in rs if f"({name})" in r["text"]
                    and re.search(r"\bTYP", r["text"], re.I)), None)
        if typ and typ > n:                   # 'CHECK VALVE (CV) ... (TYP. OF 5)': the sheet states the quantity
            why += f"; the sheet says TYP. OF {typ} ({n} tags legible)"
            n = typ
        groups.append({"series": name, "meaning": meaning, "why": why, "n": n, "tags": tags, "boxes": boxes})
    if not groups:
        return None
    return {"noun": noun, "total": sum(g["n"] for g in groups), "groups": sorted(groups, key=lambda g: -g["n"])}


def tag_count(abs_path: str, sha: str, question: str) -> Optional[dict]:
    noun = _noun(question)
    if not noun:
        return None
    ws = _words(abs_path, sha)
    rs = rows(ws)
    for prefix, why in _prefixes(noun, rs):
        found = _tags(ws, prefix)
        if len(found) < 1:
            continue
        read_first = len(found)
        try:                               # small / underlined tags: re-read the rows where the series was found
            extra = _tags(_reread_bands(abs_path, list(found.values())), prefix)
            for k, v in extra.items():
                found.setdefault(k, v)
        except Exception:  # noqa: BLE001
            pass
        found = _merge_confusable(found)
        # series with gaps (FSI-1, FSI-4, FSI-5): re-read their rows before inferring anything
        series: dict[str, list[int]] = {}
        for tg in found:
            m = re.match(r"([A-Z]+)-(\d+)", tg)
            series.setdefault(m.group(1), []).append(int(m.group(2)))
        gaps = any(max(v) > len(set(v)) for v in series.values())
        if gaps:
            try:
                extra = _tags(_reread_bands(abs_path, list(found.values())), prefix)
                for k, v in extra.items():
                    m = re.match(r"([A-Z]+)-(\d+)", k)
                    if m.group(1) in series or len(m.group(1)) == len(prefix) + 1:
                        found.setdefault(k, v)
            except Exception:  # noqa: BLE001
                pass
            series = {}
            for tg in found:
                m = re.match(r"([A-Z]+)-(\d+)", tg)
                series.setdefault(m.group(1), []).append(int(m.group(2)))
        numbered = sum(max(v) for v in series.values())
        missing = [f"{s}-{i}" for s, v in series.items() for i in range(1, max(v) + 1) if i not in v]
        return {"prefix": prefix, "why": why, "noun": noun, "tags": sorted(found, key=lambda t: (t.split("-")[0], int(re.sub(r"\D", "", t.split("-")[1]) or 0))),
                "boxes": [found[t]["box"] for t in found], "read": len(found), "read_first_pass": read_first,
                "numbered": numbered, "missing": missing}
    return None


# --------------------------------------------------------------------------- printed totals
def printed_total_area(abs_path: str, sha: str) -> Optional[dict]:
    """Largest 'TOTAL ... <n> SF|m2' row (area tables on architectural sheets)."""
    best = None
    for r in rows(_words(abs_path, sha)):
        t = r["text"]
        if not re.search(r"\bTOTAL\b", t.upper()):
            continue
        m = AREA_UNIT.search(t)
        if not m:
            continue
        nums = [n for n in _numbers(t) if n[2] < m.start()]
        if not nums:
            continue
        n = nums[-1]
        u = m.group(1).upper()
        m2 = n[1] * SQFT_M2 if "F" in u else n[1]
        if best is None or m2 > best["m2"]:
            best = {"m2": m2, "printed": f"{n[0]} {'SF' if 'F' in u else 'm²'}", "text": t, "box": r["box"]}
    return best


# --------------------------------------------------------------------------- overall dimensions
def overall_dims(abs_path: str, sha: str, ppm: Optional[float]) -> Optional[dict]:
    """Largest verified printed dimension per direction (0 = width, 90 = depth). A dimension is VERIFIED when its own
    dimension line measures true at the solved scale (within 6%) or when it equals the sum of 2-4 other printed
    dimensions of the same direction (a dimension chain, within 0.5%). Returns {w, d} entries {m, text, box, how}."""
    res = S.analyze(abs_path, sha)
    ws = _words(abs_path, sha)
    metric = any(n["system"] == "metric" for n in res["notes"]) and not any(n["system"] == "imperial" for n in res["notes"])
    toks: dict[int, list[dict]] = {0: [], 90: []}
    for w in ws:
        r = S.parse_dim(w["text"])
        if not r:
            continue
        k = r[0]["kind"]
        if metric and k != "mm":
            continue
        if not metric and k not in ("ftin",):
            continue
        toks[w.get("angle", 0)].append({"text": S.norm(w["text"]), "m": r[0]["m"], "box": w["box"]})
    measured = {}
    for d in res["dims"]:
        ok = [d["ppm"]] + [a["ppm"] for a in d.get("alts", [])]
        if ppm and any(abs(p / ppm - 1) <= 0.06 for p in ok):
            measured[(round(d["box"][0]), round(d["box"][1]))] = True
    W = max(res["w"], res["h"])
    out = {}
    B = None
    for ang, name in ((0, "w"), (90, "d")):
        cand = sorted(toks[ang], key=lambda t: -t["m"])
        vals = [t["m"] for t in toks[ang]]
        for t in cand[:8]:
            if ppm and (t["m"] * ppm > 1.02 * W or t["m"] * ppm < 0.15 * W):   # longer than the sheet / a detail
                continue
            how = None
            if (round(t["box"][0]), round(t["box"][1])) in measured:
                how = "its dimension line measures true at the solved scale"
            else:
                others = [v for v in vals if v < t["m"] * 0.98]
                for n in (2, 3, 4):
                    for combo in itertools.combinations(sorted(set(others), reverse=True)[:14], n):
                        if abs(sum(combo) - t["m"]) <= 0.005 * t["m"]:
                            how = "it equals the printed chain " + " + ".join(_fmt(c, metric) for c in combo)
                            break
                    if how:
                        break
                if how is None:     # chain may repeat a segment (133'-10" + 55'-8" + 133'-10")
                    for a, b in itertools.combinations_with_replacement(sorted(set(others), reverse=True)[:10], 2):
                        for c in sorted(set(others))[:10]:
                            if abs(a + b + c - t["m"]) <= 0.005 * t["m"] and len({a, b, c}) < 3:
                                how = "it equals the printed chain " + " + ".join(_fmt(x, metric) for x in (a, c, b))
                                break
                        if how:
                            break
            if how is None and ppm:
                if B is None:
                    g, _ = S.load_gray(abs_path, 2000)
                    B = S.ink_mask(g)
                if _line_beside(B, t["box"], ang, t["m"] * ppm):
                    how = "a drawn dimension line of that length (at the solved scale) runs beside it"
            if how:
                out[name] = {"m": t["m"], "text": t["text"], "box": t["box"], "how": how}
                break
    return out or None


def _line_beside(B: np.ndarray, box: list[float], angle: int, want_px: float) -> bool:
    """Is there a straight ink run of ~want_px (within 4%) passing beside the text box, parallel to it?"""
    if angle == 90:
        B = B.T
        box = [box[1], box[0], box[3], box[2]]
    H, W = B.shape
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    h = max(4, y1 - y0)
    g = max(3, int(0.6 * h))
    for y in range(max(0, y0 - 3 * h), min(H, y1 + 3 * h)):
        row = B[y]
        L = S._runs(row, max(0, x0 - 1), -1, g, W) if row[max(0, x0 - 1)] or row[max(0, x0 - g):x0].any() else None
        R = S._runs(row, min(W - 1, x1 + 1), 1, g, W) if row[min(W - 1, x1 + 1)] or row[x1:x1 + g].any() else None
        if L is None or R is None:
            continue
        if abs((R - L) - want_px) <= 0.04 * want_px:
            return True
    return False


def _fmt(m: float, metric: bool) -> str:
    if metric:
        return f"{m * 1000:.0f}"
    inches = round(m / S.M_PER_IN)
    return f"{inches // 12}'-{inches % 12}\""


def element_boxes(prefix: str, boxes: list[list[float]], label: str) -> list[Any]:
    """Printed words as Elements (kind 'label') so the proof view can pin them."""
    from contracts.proof import Element
    out = []
    for i, b in enumerate(boxes):
        x0, y0, x1, y1 = [float(v) for v in b]
        out.append(Element(id=f"{prefix}_{i}", kind="label", polygon=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                           label=label if isinstance(label, str) else None, conf=0.9, attrs={"printed": True}))
    return out
