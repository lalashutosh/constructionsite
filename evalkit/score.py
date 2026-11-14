"""Scoring rules (from the dataset README) and Wilson confidence intervals.

count: exact match after int(round(x)). area/length/volume: relative error <= 2% (truth 0 -> need exact).
text: normalised exact match, reported separately, excluded from the headline number.
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional

TOLERANCE = 0.02


def _to_number(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def score_count(pred: Any, truth: Any) -> bool:
    p, t = _to_number(pred), _to_number(truth)
    if p is None or t is None:
        return False
    return int(round(p)) == int(round(t))


def score_quantity(pred: Any, truth: Any, tolerance: float = TOLERANCE) -> bool:
    """area / length / volume: relative error <= tolerance. truth == 0 requires an exact match."""
    p, t = _to_number(pred), _to_number(truth)
    if p is None or t is None:
        return False
    if t == 0:
        return p == 0
    return abs(p - t) / abs(t) <= tolerance


_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")


def normalize_text(s: Any) -> str:
    s = "" if s is None else str(s)
    s = s.strip().lower()
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


def score_text(pred: Any, truth: Any) -> bool:
    return normalize_text(pred) == normalize_text(truth)


def score(kind: str, pred: Any, truth: Any, tolerance: float = TOLERANCE) -> bool:
    """Dispatch by question `type`. `kind` is one of count/area/length/volume/text/other."""
    if kind == "count":
        return score_count(pred, truth)
    if kind in ("area", "length", "volume"):
        return score_quantity(pred, truth, tolerance)
    if kind == "text":
        return score_text(pred, truth)
    return False


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% (default) confidence interval for k successes out of n trials. (0, 0) if n == 0."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    lo = (centre - margin) / denom
    hi = (centre + margin) / denom
    return (max(0.0, lo), min(1.0, hi))


def wilson_str(k: int, n: int, z: float = 1.96) -> str:
    if n == 0:
        return "n/a"
    lo, hi = wilson(k, n, z)
    return f"{k / n:.1%} [{lo:.1%}, {hi:.1%}] (n={n})"
