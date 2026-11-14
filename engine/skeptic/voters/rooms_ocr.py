"""rooms_ocr: count room labels via OCR (pytesseract fin+eng, rotations 0/90/180/270) against our own lexicon.

OCR-only: no geometry. Independent of the arc/line/template voters (different evidence: printed text).
"""
from __future__ import annotations

import functools
import pathlib
import re

import cv2
import numpy as np
import yaml

from engine.skeptic.prep import read_gray

NAME = "rooms_ocr"
NOTE = ("label counting only; Finnish plans often omit labels or use inconsistent abbreviations; single-letter "
        "labels (K, S) are noisy. Rotated text is retried at 90/180/270 degrees. Counts labels, not rooms: a "
        "room with two labels (e.g. 'WC/KH') counts for both intents.")
INTENTS = ("bedrooms", "bathrooms", "wc_rooms", "kitchens", "saunas", "balconies", "floors")
_LEX = pathlib.Path(__file__).resolve().parents[1] / "lexicon.yaml"


@functools.lru_cache(maxsize=1)
def lexicon():
    d = yaml.safe_load(_LEX.read_text())
    return {k: [re.compile(rf"^(?:{p})$", re.I) for p in v] for k, v in d.items()}


@functools.lru_cache(maxsize=4)
def read_tokens(path: str, rotations=(0, 90, 180, 270)):
    """[(text, cx, cy, w, h)] in ORIGINAL pixel coordinates, de-duplicated across rotations."""
    import pytesseract
    g0 = read_gray(path)
    if g0 is None:
        return None
    h0, w0 = g0.shape
    s = float(min(max(1600 / max(h0, w0), 1.0), 3.0))
    g = cv2.resize(g0, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC) if s != 1 else g0
    out = []
    for rot in rotations:
        r = np.rot90(g, rot // 90).copy()
        try:
            d = pytesseract.image_to_data(r, lang="eng+fin", config="--psm 11", output_type=pytesseract.Output.DICT,
                                          timeout=6)
        except Exception:  # noqa: BLE001
            continue
        for t, c, x, y, w, h in zip(d["text"], d["conf"], d["left"], d["top"], d["width"], d["height"]):
            t = t.strip()
            if not t or float(c) < 35:
                continue
            cx, cy = x + w / 2, y + h / 2
            # undo rotation (np.rot90 k times counter-clockwise)
            Hc, Wc = r.shape
            for _ in range((rot // 90) % 4):
                cx, cy = Hc - cy, cx          # inverse of one ccw rotation
                Hc, Wc = Wc, Hc
            out.append((t, cx / s, cy / s, w / s, h / s))
    return out


def _norm(t: str) -> list[str]:
    parts = re.split(r"[/\s,;:+\-]+", t)
    return [re.sub(r"[^\wäöåÄÖÅ]", "", p) for p in parts if p]


def count_labels(path: str, intent: str):
    toks = read_tokens(path)
    if toks is None:
        return None, []
    pats = lexicon()[intent]
    hits = []
    for t, cx, cy, w, h in toks:
        for part in _norm(t):
            if any(p.match(part) for p in pats):
                if all(abs(cx - hx) > 25 or abs(cy - hy) > 25 for _, hx, hy, _, _ in hits):
                    hits.append((part, cx, cy, w, h))
                break
    return len(hits), hits


def count_for(path: str, intent: str):
    if intent not in INTENTS:
        return None
    n, hits = count_labels(path, intent)
    if intent == "floors":
        return max(1, n)
    return n


def run(ctx):
    from contracts.proof import Element, Voter
    from engine.registry import VoterResult

    if ctx.intent not in INTENTS:
        return None
    n, hits = count_labels(ctx.abs_path, ctx.intent)
    if n is None:
        return None
    if ctx.intent == "floors":
        n = max(1, n)
    ev, ids = [], []
    for i, (t, cx, cy, w, h) in enumerate(hits):
        eid = f"lbl_{ctx.intent}_{i}"
        ids.append(eid)
        ev.append(Element(id=eid, kind="label", subtype=ctx.intent, label=t,
                          polygon=[(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2),
                                   (cx - w / 2, cy + h / 2)], conf=0.6, attrs={"method": "ocr_lexicon"}))
    return VoterResult(Voter(name=NAME, value=n, element_ids=ids, runs=[n], note=NOTE), ev)
