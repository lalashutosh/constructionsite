"""OCR of Finnish room-label abbreviations. Pytesseract output is a HYPOTHESIS:
engine/count/devcheck.py is what confirms a mapping is worth trusting (AGENTS.md rule 2),
not what the abbreviation "should" mean in Finnish.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np
import pytesseract
import yaml

_LEXICON_PATH = pathlib.Path(__file__).with_name("lexicon_fi.yaml")
_TOKEN_CLEAN = re.compile(r"[^A-ZÅÄÖ0-9]")
_TRAILING_DIGITS = re.compile(r"[0-9]+$")


@dataclass
class OcrToken:
    text: str               # raw OCR text
    clean: str               # cleaned, uppercased, trailing-digit-stripped
    category: str | None     # lexicon category, or None if no match
    bbox: tuple[float, float, float, float]  # x, y, w, h in the ORIGINAL image (pixels)
    conf: float


@lru_cache(maxsize=1)
def _lexicon() -> dict[str, set[str]]:
    raw = yaml.safe_load(_LEXICON_PATH.read_text())
    return {cat: {tok.upper() for tok in toks} for cat, toks in raw.items()}


def clean_token(text: str) -> str:
    t = _TOKEN_CLEAN.sub("", text.upper())
    t = _TRAILING_DIGITS.sub("", t)
    return t


def categorize(text: str) -> str | None:
    clean = clean_token(text)
    if not clean:
        return None
    for cat, toks in _lexicon().items():
        if clean in toks:
            return cat
    return None


def ocr_tokens(img_rgb: np.ndarray, *, upscale_to: int = 1200, min_conf: float = 40.0,
                rotations: tuple[int, ...] = (0, 1, 2, 3)) -> list[OcrToken]:
    """Run tesseract fin+eng at the given quarter-turn rotations of the (upscaled) image,
    return tokens with bbox mapped back to ORIGINAL (un-upscaled, un-rotated) pixel coords.
    `rotations` defaults to all 4 (0/90/180/270); engine.raster.extract passes a smaller set to
    stay inside the per-image CPU budget (docs/decisions/weights.md)."""
    h, w = img_rgb.shape[:2]
    scale = max(1.0, upscale_to / max(h, w))
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    up = cv2.resize(gray, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_LANCZOS4)
    up = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    out: list[OcrToken] = []
    uh, uw = up.shape
    for k in rotations:
        if k == 0:
            rot = up
        elif k == 1:
            rot = cv2.rotate(up, cv2.ROTATE_90_CLOCKWISE)
        elif k == 2:
            rot = cv2.rotate(up, cv2.ROTATE_180)
        else:
            rot = cv2.rotate(up, cv2.ROTATE_90_COUNTERCLOCKWISE)
        rh, rw = rot.shape
        try:
            data = pytesseract.image_to_data(rot, lang="fin+eng", config="--psm 11",
                                              output_type=pytesseract.Output.DICT)
        except pytesseract.TesseractError:
            continue
        n = len(data["text"])
        for i in range(n):
            text = data["text"][i].strip()
            if not text:
                continue
            conf = float(data["conf"][i])
            if conf < min_conf:
                continue
            x, y, bw, bh = (data["left"][i], data["top"][i], data["width"][i], data["height"][i])
            # map the 4 box corners from the rotated-upscaled frame back to upscaled-frame (k=0),
            # then down by `scale` to the ORIGINAL image.
            corners = [(x, y), (x + bw, y), (x, y + bh), (x + bw, y + bh)]
            un = [_unrotate(px, py, k, rw, rh) for px, py in corners]
            xs = [p[0] / scale for p in un]
            ys = [p[1] / scale for p in un]
            bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            out.append(OcrToken(text=text, clean=clean_token(text), category=categorize(text),
                                 bbox=bbox, conf=conf))
    return out


def _unrotate(x: float, y: float, k: int, rw: float, rh: float) -> tuple[float, float]:
    """Inverse of cv2.rotate(..., 90*k clockwise) applied to a point, rw/rh = rotated image dims.
    Same convention as engine.raster.prep._rotate_matrix; verified numerically in
    tests/test_raster_prep.py-style round trips (see test_ocr.py)."""
    if k == 0:
        return x, y
    if k == 1:
        return y, rw - x
    if k == 2:
        return rw - x, rh - y
    # k == 3
    return rh - y, x
