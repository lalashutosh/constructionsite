"""Scale solving: turn a SheetFacts (+ optional user taps) into a ScaleInfo.

Anchors, best first:
  1. scale_bar / dimension string matched to a measured pixel segment
  2. printed_ratio + paper size (+ sheet DPI from facts.extras if present)
  3. printed_area label matched to the room polygon it sits inside
  4. door_prior: median detected door leaf width assumed 0.9 m (tag defaulted)
  5. user: a tap or drawn line with a typed length (tag chosen)

All anchors are combined by inverse-variance weighting *in log space* (a
scale factor is always positive and anchor errors are relative, so this is
the natural space to average in). Anchors more than 3 sigma from the
weighted mean are rejected as outliers and the reason is recorded on the
anchor's `note`. If the ONLY anchor that survives is `door_prior`, the
result is circular evidence: `widths_relative=True`, `needs_user=True` --
door widths must never be reported as "measured" when the only reason we
know the scale is that we assumed doors are 0.9 m wide.
"""
from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from typing import Any, Optional

from shapely.geometry import Point, Polygon

from contracts.proof import Element, ScaleAnchor, ScaleInfo, SheetFacts, Tag

DOOR_PRIOR_M = 0.9
DOOR_PRIOR_REL_SIGMA = 0.12
OUTLIER_SIGMA = 3.0

# ---------------------------------------------------------------------------
# dimension string parsing
# ---------------------------------------------------------------------------

_FEET_INCHES_RE = re.compile(r"""^\s*(\d+)\s*'\s*-?\s*(\d+(?:\.\d+)?)?\s*"?\s*$""")
_METERS_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*m\b", re.IGNORECASE)
_MM_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*mm\b", re.IGNORECASE)
_GROUPED_MM_RE = re.compile(r"^\s*(\d{1,2})\s+(\d{3})\s*$")  # "3 600" -> 3600 mm
_RATIO_RE = re.compile(r"^\s*1\s*:\s*(\d+(?:\.\d+)?)\s*$")

# ISO 216 (long edge mm, short edge mm)
PAPER_MM = {
    "A0": (1189.0, 841.0),
    "A1": (841.0, 594.0),
    "A2": (594.0, 420.0),
    "A3": (420.0, 297.0),
    "A4": (297.0, 210.0),
    "A5": (210.0, 148.0),
}

DEFAULT_DPI = 300.0


def parse_dimension(text: str) -> Optional[float]:
    """Parse a dimension string (scale-bar label / dimension string) to metres.

    Supports "3 600" (space-grouped mm), "3.60 m", "3600 mm", "12'-6\"".
    Returns None if the string is not recognised (never guesses).
    """
    if not text:
        return None
    t = text.strip()
    m = _FEET_INCHES_RE.match(t)
    if m:
        feet = float(m.group(1))
        inches = float(m.group(2)) if m.group(2) else 0.0
        return (feet * 12.0 + inches) * 0.0254
    m = _METERS_RE.match(t)
    if m:
        return float(m.group(1).replace(",", "."))
    m = _MM_RE.match(t)
    if m:
        return float(m.group(1).replace(",", ".")) / 1000.0
    m = _GROUPED_MM_RE.match(t)
    if m:
        return float(m.group(1) + m.group(2)) / 1000.0
    return None


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def _closed(polygon: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return polygon if polygon[0] == polygon[-1] else [*polygon, polygon[0]]


def _bbox_extent_px(polygon: list[tuple[float, float]]) -> float:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return max(max(xs) - min(xs), max(ys) - min(ys))


def _area_px(polygon: list[tuple[float, float]]) -> float:
    return Polygon(_closed(polygon)).area


def _centroid(polygon: list[tuple[float, float]]) -> Point:
    return Polygon(_closed(polygon)).centroid


# ---------------------------------------------------------------------------
# anchor extraction
# ---------------------------------------------------------------------------


def _scale_bar_and_dimension_anchors(facts: SheetFacts) -> list[ScaleAnchor]:
    out: list[ScaleAnchor] = []
    for e in facts.elements:
        if e.kind not in ("scale_bar", "dimension"):
            continue
        meters = None
        if "length_m" in e.attrs:
            meters = float(e.attrs["length_m"])
        elif e.label:
            meters = parse_dimension(e.label)
        if meters is None or meters <= 0:
            continue
        px = _bbox_extent_px(e.polygon)
        if px <= 0:
            continue
        out.append(
            ScaleAnchor(
                kind=e.kind if e.kind in ("scale_bar",) else "dimension",
                px_per_m=px / meters,
                rel_sigma=0.02,
                tag=Tag.drawn,
                note=f"{e.kind} '{e.label}' = {meters:.3f} m over {px:.1f} px",
                element_ids=[e.id],
            )
        )
    return out


def _printed_ratio_anchor(facts: SheetFacts) -> Optional[ScaleAnchor]:
    ratio_str = facts.extras.get("printed_ratio")
    if not ratio_str:
        return None
    m = _RATIO_RE.match(str(ratio_str))
    if not m:
        return None
    ratio = float(m.group(1))

    dpi = facts.extras.get("dpi")
    if dpi:
        dpi = float(dpi)
        tag, rel_sigma, note = Tag.specified, 0.03, f"printed ratio 1:{ratio:g}, dpi {dpi:g} from extras"
    else:
        paper_size = facts.extras.get("paper_size")
        if paper_size in PAPER_MM and facts.width_px and facts.height_px:
            long_mm, _short_mm = PAPER_MM[paper_size]
            long_px = max(facts.width_px, facts.height_px)
            dpi = long_px / long_mm * 25.4
            tag, rel_sigma = Tag.defaulted, 0.06
            note = f"printed ratio 1:{ratio:g} on {paper_size}, dpi inferred from sheet size assuming full bleed"
        else:
            dpi = DEFAULT_DPI
            tag, rel_sigma = Tag.defaulted, 0.10
            note = f"printed ratio 1:{ratio:g}, dpi assumed {DEFAULT_DPI:g} (no paper size / dpi given)"

    px_per_mm_paper = dpi / 25.4
    px_per_m_real = px_per_mm_paper * 1000.0 / ratio
    return ScaleAnchor(kind="printed_ratio", px_per_m=px_per_m_real, rel_sigma=rel_sigma, tag=tag, note=note)


def _printed_area_anchors(facts: SheetFacts) -> list[ScaleAnchor]:
    out: list[ScaleAnchor] = []
    rooms = [e for e in facts.elements if e.kind == "room"]
    if not rooms:
        return out
    for pa in facts.printed_areas:
        value_m2 = pa.get("value_m2")
        poly = pa.get("polygon")
        if not value_m2 or value_m2 <= 0 or not poly:
            continue
        label_centroid = _centroid(poly)
        best_room, best_dist = None, None
        for r in rooms:
            d = label_centroid.distance(Polygon(_closed(r.polygon)))
            if best_dist is None or d < best_dist:
                best_room, best_dist = r, d
        if best_room is None:
            continue
        area_px = _area_px(best_room.polygon)
        if area_px <= 0:
            continue
        px_per_m = math.sqrt(area_px / value_m2)
        out.append(
            ScaleAnchor(
                kind="printed_area",
                px_per_m=px_per_m,
                rel_sigma=0.02,
                tag=Tag.specified,
                note=f"printed '{pa.get('text')}' matches room {best_room.id} at {px_per_m:.2f} px/m",
                element_ids=[best_room.id],
            )
        )
    return out


def _door_prior_anchor(facts: SheetFacts) -> Optional[ScaleAnchor]:
    doors = [e for e in facts.elements if e.kind == "door"]
    if not doors:
        return None
    widths = []
    for d in doors:
        if "width_px" in d.attrs:
            widths.append(float(d.attrs["width_px"]))
        else:
            widths.append(_bbox_extent_px(d.polygon))
    widths.sort()
    n = len(widths)
    median = widths[n // 2] if n % 2 else (widths[n // 2 - 1] + widths[n // 2]) / 2.0
    if median <= 0:
        return None
    return ScaleAnchor(
        kind="door_prior",
        px_per_m=median / DOOR_PRIOR_M,
        rel_sigma=DOOR_PRIOR_REL_SIGMA,
        tag=Tag.defaulted,
        note=f"median of {n} detected door leaves = {median:.1f} px, assumed {DOOR_PRIOR_M} m",
        element_ids=[d.id for d in doors],
    )


def _user_anchor(ua: dict[str, Any]) -> ScaleAnchor:
    if "px_per_m" in ua:
        px_per_m = float(ua["px_per_m"])
    else:
        px_per_m = float(ua["px_length"]) / float(ua["length_m"])
    return ScaleAnchor(
        kind="user",
        px_per_m=px_per_m,
        rel_sigma=float(ua.get("rel_sigma", 0.01)),
        tag=Tag.chosen,
        note=ua.get("note", "user-supplied scale reference"),
        element_ids=list(ua.get("element_ids", [])),
    )


# ---------------------------------------------------------------------------
# combination
# ---------------------------------------------------------------------------


@dataclass
class _Combined:
    px_per_m: Optional[float]
    rel_sigma: Optional[float]
    used: list[ScaleAnchor]


def _weighted_log_mean(anchors: list[ScaleAnchor], idxs: list[int]) -> tuple[float, float]:
    logs = [math.log(anchors[i].px_per_m) for i in idxs]
    weights = [1.0 / (anchors[i].rel_sigma ** 2) for i in idxs]
    sw = sum(weights)
    mean_log = sum(w * l for w, l in zip(weights, logs)) / sw
    return mean_log, sw


def _combine(anchors: list[ScaleAnchor]) -> _Combined:
    """Inverse-variance combination in log space, with a 3-sigma outlier test.

    The outlier test compares each anchor to the unweighted MEDIAN of all
    logs, not the inverse-variance weighted mean: an overconfident (small
    rel_sigma) but wrong anchor would otherwise drag the weighted mean onto
    itself and never look like an outlier by its own yardstick. The median
    only fails when outliers are the majority by count, which we accept.
    """
    if not anchors:
        return _Combined(None, None, [])
    logs = [math.log(a.px_per_m) for a in anchors]
    idxs = list(range(len(anchors)))
    if len(anchors) > 1:
        median_log = statistics.median(logs)
        keep = []
        for i in idxs:
            z = abs(logs[i] - median_log) / anchors[i].rel_sigma
            if z > OUTLIER_SIGMA:
                reason = f"{z:.1f} sigma from the median of all anchors ({math.exp(median_log):.2f} px/m): rejected as outlier"
                anchors[i].note = f"{anchors[i].note}; OUTLIER: {reason}" if anchors[i].note else f"OUTLIER: {reason}"
            else:
                keep.append(i)
        idxs = keep if keep else idxs  # never end up with zero anchors
    mean_log, sw = _weighted_log_mean(anchors, idxs)
    rel_sigma = math.sqrt(1.0 / sw)
    return _Combined(math.exp(mean_log), rel_sigma, [anchors[i] for i in idxs])


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def _printed_dims_anchor(facts: SheetFacts) -> Optional[ScaleAnchor]:
    """Opening sizes printed on raster plans (engine/scale/printed_dims.py); None for vector files / no labels."""
    try:
        import pathlib
        from engine import cache as facts_cache
        from engine.pipeline import _abs
        from engine.scale import printed_dims
        if "vector" in facts.extras or not facts.provenance.file:
            return None
        ap = _abs(facts.provenance.file)
        if pathlib.Path(ap).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"):
            return None
        return printed_dims.anchor(facts, ap, facts.provenance.sha256 or facts_cache.sha256_file(ap))
    except Exception:  # noqa: BLE001  (an unreadable label never breaks scale solving)
        return None


def _sheet_anchors(facts: SheetFacts) -> tuple[list[ScaleAnchor], bool]:
    """Anchors read from the sheet's own notes / scale bar / dimension strings (engine/scale/sheet_scale.py)."""
    try:
        import pathlib
        from engine import cache as facts_cache
        from engine.pipeline import _abs
        from engine.scale import sheet_scale
        if "vector" in facts.extras or not facts.provenance.file:
            return [], False
        ap = _abs(facts.provenance.file)
        if pathlib.Path(ap).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".pdf"):
            return [], False
        if max(facts.width_px or 0, facts.height_px or 0) < 700 and pathlib.Path(ap).suffix.lower() != ".pdf":
            return [], False                      # small floor-plan scans: handled by printed_dims / label areas
        out, st = sheet_scale.anchors_for(ap, facts.provenance.sha256 or facts_cache.sha256_file(ap))
        return out, bool(st["cons"]["winner"] or st["users"])
    except Exception:  # noqa: BLE001
        return [], False


def label_area_candidates(facts: SheetFacts) -> list[dict]:
    """Room areas printed in the room labels ('MH 10.5', 'TUPA 18.5'), as read by the vision label reader
    (cache/labels/<sha>.json; no network here). Each label inside exactly one room polygon gives
    px_per_m = sqrt(polygon px^2 / printed m^2)."""
    import json as _json
    import math as _math
    import pathlib
    import re as _re
    sha = facts.provenance.sha256
    if not sha or not facts.width_px or not facts.height_px:
        return []
    f = pathlib.Path(__file__).resolve().parents[2] / "cache" / "labels" / f"{sha}.json"
    if not f.exists():
        return []
    try:
        labels = _json.loads(f.read_text())
        from shapely.geometry import Point, Polygon
    except Exception:  # noqa: BLE001
        return []
    rooms = []
    for e in facts.elements:
        if e.kind == "room" and len(e.polygon) >= 3:
            try:
                P = Polygon(e.polygon)
                if P.is_valid and P.area > 0:
                    rooms.append((e, P))
            except Exception:  # noqa: BLE001
                pass
    out = []
    for l in labels:
        m = _re.search(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:m2|m²|m\^2)?\s*$", str(l.get("text", "")))
        if not m or not isinstance(l.get("x"), (int, float)) or not isinstance(l.get("y"), (int, float)):
            continue
        if not _re.search(r"[A-Za-zÄÖÅäöå]", l["text"]):          # a bare number is a dimension, not a room area
            continue
        a = float(m.group(1).replace(",", "."))
        raw = m.group(0)
        unit = bool(_re.search(r"m2|m²|m\^2", raw))
        decimal = bool(_re.search(r"\d[.,]\d", raw))
        if not (unit or decimal or a >= 4):
            continue                      # 'MH 1', 'MAKUUHUONE 2': a room NUMBER, not an area
        if not (0.8 <= a <= 400):
            continue
        pt = Point(l["x"] / 100 * facts.width_px, l["y"] / 100 * facts.height_px)
        hit = [(e, P) for e, P in rooms if P.contains(pt)]
        if len(hit) != 1:
            continue
        e, P = hit[0]
        typ = f"{e.subtype or ''} {l['text']}".lower()
        floor_m2 = 5.0 if _re.search(r"bed|makuu|mh\b|sov|living|olohuone|oh\b|kitchen|keitti", typ) else 1.5
        if a < floor_m2:
            continue                      # a 1 m2 bedroom is a misread, not a scale anchor
        out.append({"px_per_m": _math.sqrt(P.area / a), "text": l["text"], "id": e.id, "m2": a})
    return out


def _label_area_anchor(facts: SheetFacts) -> Optional[ScaleAnchor]:
    """Printed room areas that agree (>= 2 rooms within 15%) -> one 'printed_area' anchor, tag specified."""
    import statistics as _st
    c = label_area_candidates(facts)
    if len(c) < 2:
        return None
    best = []
    for v in sorted(x["px_per_m"] for x in c):
        grp = [x for x in c if abs(x["px_per_m"] / v - 1) <= 0.15]
        if len(grp) > len(best):
            best = grp
    if len(best) < 2 or len(best) < 0.34 * len(c):
        return None
    pv = _st.median(x["px_per_m"] for x in best)
    spread = max(x["px_per_m"] for x in best) / min(x["px_per_m"] for x in best) - 1
    return ScaleAnchor(kind="printed_area", px_per_m=pv, rel_sigma=max(0.03, spread / 2), tag=Tag.specified,
                       note=f"room areas printed on the drawing ({', '.join(x['text'] for x in best)}) agree within "
                            f"{spread:.0%} across {len(best)} rooms; {len(c) - len(best)} rooms disagreed "
                            "(merged or split outlines)",
                       element_ids=[x["id"] for x in best])


def solve(facts: SheetFacts, user_anchors: tuple[dict[str, Any], ...] = ()) -> ScaleInfo:
    """Combine every scale anchor derivable from `facts` (+ optional user taps) into one ScaleInfo."""
    anchors: list[ScaleAnchor] = []
    anchors += _scale_bar_and_dimension_anchors(facts)
    pr = _printed_ratio_anchor(facts)
    if pr is not None:
        anchors.append(pr)
    anchors += _printed_area_anchors(facts)
    pd = _printed_dims_anchor(facts)
    if pd is not None:
        anchors.append(pd)
    la = _label_area_anchor(facts)
    if la is not None:
        anchors.append(la)
    sa, has_sheet = _sheet_anchors(facts)
    anchors += sa
    dp = _door_prior_anchor(facts)
    # a measurement printed on the drawing beats the 0.9 m door guess; the guess is kept only as a fallback
    if dp is not None and pd is None and la is None and not has_sheet:
        anchors.append(dp)
    for ua in user_anchors:
        anchors.append(_user_anchor(ua))

    live = [a for a in anchors if "REJECTED:" not in (a.note or "")]   # sheet consensus rejects stay on the receipt only
    users = [a for a in live if a.kind == "user"]
    if users:                                   # a length the user measured decides; the rest stays on the receipt
        u = users[-1]
        for a in anchors:
            if a.kind != "user" and "REJECTED" not in (a.note or ""):
                a.note = (a.note or a.kind) + "; not used: your measurement decides"
        return ScaleInfo(px_per_m=u.px_per_m, rel_sigma=u.rel_sigma, anchors=anchors, widths_relative=False,
                         needs_user=False)
    combined = _combine(live)
    if combined.px_per_m is None:
        return ScaleInfo(px_per_m=None, rel_sigma=None, anchors=[], widths_relative=False, needs_user=True)

    kinds_used = {a.kind for a in combined.used}
    only_prior = kinds_used == {"door_prior"}
    return ScaleInfo(
        px_per_m=combined.px_per_m,
        rel_sigma=combined.rel_sigma,
        anchors=anchors,
        widths_relative=only_prior,
        needs_user=only_prior,
    )


@dataclass
class NextQuestion:
    anchor_kind: str
    question: str
    expected_rel_sigma: float
    expected_interval_reduction_pct: float


# fixed priority order: cheapest-for-the-user first
_CANDIDATES = [
    ("user", "tap a door: is it 0.9 m wide?", 0.01),
    ("user", "draw a line over something you know the length of and type it", 0.01),
    ("printed_ratio", "type the printed scale (e.g. 1:100)", 0.03),
]


def next_question(facts: SheetFacts, info: ScaleInfo) -> list[NextQuestion]:
    """The cheapest-first list of questions that would resolve `info.needs_user`.

    Each entry reports the rel_sigma the scale would have if that answer were
    added, and the resulting drop in the AREA interval's relative half-width
    (dA/A = 2 ds/s), i.e. "how much tighter would the answer become".
    """
    if not info.needs_user:
        return []
    current_sigma = info.rel_sigma if info.rel_sigma is not None else 1.0
    out: list[NextQuestion] = []
    for kind, question, new_sigma in _CANDIDATES:
        if info.rel_sigma is None:
            combined_sigma = new_sigma
        else:
            w1 = 1.0 / (current_sigma ** 2)
            w2 = 1.0 / (new_sigma ** 2)
            combined_sigma = math.sqrt(1.0 / (w1 + w2))
        reduction_pct = max(0.0, (2.0 * current_sigma - 2.0 * combined_sigma) * 100.0)
        out.append(NextQuestion(kind, question, combined_sigma, reduction_pct))
    return out
