"""Counting rules, one function per cubicasa5k intent. Each reads ONLY `facts.elements` /
`facts.extras` (contracts/proof.py: "Questions are answered from this, never from pixels again") --
geometry was already produced by `engine.raster.extract`.

Every function returns `(value: int, element_ids: list[str], runs: list[int | float])`.
`runs` becomes `Voter.runs`; see engine/raster/extract.py module docstring for why these are a
cheap confidence-threshold / cluster-radius bootstrap rather than literal scale x rotation x flip
TTA of the pretrained CNN (that would cost >10s/image on this CPU).
"""
from __future__ import annotations

import statistics

import math

from contracts.proof import SheetFacts

# Fraction of the image diagonal used to decide whether two same-subtype room/label centres are
# the same physical room (OCR duplicates from different rotation passes, or a room split in two
# by the CNN's connected-component step) or two separate instances.
_CLUSTER_RATIOS = (0.03, 0.05, 0.08)  # tight / medium / loose -> 3 bootstrap runs


def _centroid(poly: list[tuple[float, float]]) -> tuple[float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _cluster_count(points: list[tuple[float, float]], radius: float) -> int:
    """Greedy single-link clustering: two points in the same cluster iff some chain of points
    each within `radius` of the next connects them. Returns the number of clusters."""
    n = len(points)
    if n == 0:
        return 0
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            dx = points[i][0] - points[j][0]
            dy = points[i][1] - points[j][1]
            if math.hypot(dx, dy) <= radius:
                union(i, j)
    return len({find(i) for i in range(n)})


def _subtype_instances(facts: SheetFacts, subtype: str) -> tuple[int, list[str], list[int]]:
    """Count distinct room instances of `subtype`, combining `room` elements (from the CNN's
    room-class segmentation, overridden by an OCR label inside the polygon) and leftover `label`
    elements (OCR hits the model's room classes can't represent at all: wc, sauna, balcony --
    docs/decisions/weights.md). Clustered by distance so duplicate OCR tokens for the same room
    (different rotation passes) don't double count."""
    matches = [e for e in facts.elements
               if e.subtype == subtype and (e.kind == "room" or (
                   e.kind == "label" and not e.attrs.get("claimed")))]  # claimed label = its room
    if not matches:
        return 0, [], [0, 0, 0]
    diag = math.hypot(facts.width_px or 1, facts.height_px or 1)
    points = [_centroid(e.polygon) for e in matches]
    runs = [_cluster_count(points, r * diag) for r in _CLUSTER_RATIOS]
    value = runs[1]  # medium radius is the canonical answer
    return value, [e.id for e in matches], runs


def _label_instances(facts: SheetFacts, subtype: str, min_conf: float = 0.0) -> tuple[int, list[str]]:
    """Distinct OCR label hits of `subtype` (duplicates from the rotation passes collapse when
    within 3% of the image diagonal, i.e. the same printed word). Every hit sits in its own room."""
    labs = [e for e in facts.elements
            if e.kind == "label" and e.subtype == subtype and e.conf >= min_conf]
    if not labs:
        return 0, []
    diag = math.hypot(facts.width_px or 1, facts.height_px or 1)
    return _cluster_count([_centroid(e.polygon) for e in labs], 0.03 * diag), [e.id for e in labs]


def _mark_default(facts: SheetFacts, intent: str, value: int, reason: str) -> None:
    """Label a prior fallback so the proof builder can emit Tag.defaulted instead of Tag.drawn."""
    facts.extras.setdefault("count_defaults", {})[intent] = {"value": value, "reason": reason}


def _icon_count(facts: SheetFacts, kind: str) -> tuple[int, list[str], list[int]]:
    ids = [e.id for e in facts.elements if e.kind == kind]
    runs = facts.extras.get("cnn_runs", {}).get(kind, [len(ids)])
    return len(ids), ids, list(runs)


# ---------------------------------------------------------------------------------------------
# Icon-backed intents (pretrained CNN icon classes; runs = confidence-threshold bootstrap).
# ---------------------------------------------------------------------------------------------

def windows(facts: SheetFacts):
    """'How many windows are shown on this floor plan?' -- one count per window icon."""
    return _icon_count(facts, "window")


# One door leaf the CNN returns in 2-3 collinear pieces (high_quality-11553: 11 -> 9, the key). DEV, 147 drawings:
# exact 63 -> 64, 6 counts closer to the key, 4 further.
def _box(e):
    xs = [p[0] for p in e.polygon]; ys = [p[1] for p in e.polygon]
    return [min(xs), min(ys), max(xs), max(ys)]

def merge_fragments(els, short=0.8, gap=0.35):
    """Collinear pieces of one door leaf -> one group; closest pair merged first. Returns groups of elements."""
    groups = [([e], _box(e)) for e in els]
    if len(groups) < 2:
        return [g for g, _ in groups]
    med = statistics.median(max(b[2] - b[0], b[3] - b[1]) for _, b in groups)
    while True:
        best = None
        for a in range(len(groups)):
            for b in range(a + 1, len(groups)):
                A, B = groups[a][1], groups[b][1]
                la, lb = max(A[2] - A[0], A[3] - A[1]), max(B[2] - B[0], B[3] - B[1])
                if la > short * med or lb > short * med:
                    continue
                va, vb = (A[3] - A[1]) >= (A[2] - A[0]), (B[3] - B[1]) >= (B[2] - B[0])
                if va != vb:
                    continue
                if va:
                    if abs((A[0] + A[2]) / 2 - (B[0] + B[2]) / 2) > max(A[2] - A[0], B[2] - B[0], 3):
                        continue
                    g = max(A[1], B[1]) - min(A[3], B[3])
                else:
                    if abs((A[1] + A[3]) / 2 - (B[1] + B[3]) / 2) > max(A[3] - A[1], B[3] - B[1], 3):
                        continue
                    g = max(A[0], B[0]) - min(A[2], B[2])
                if g <= gap * med and (best is None or g < best[0]):
                    best = (g, a, b)
        if best is None:
            return [g for g, _ in groups]
        _, a, b = best
        A, B = groups[a][1], groups[b][1]
        groups[a] = (groups[a][0] + groups[b][0], [min(A[0], B[0]), min(A[1], B[1]), max(A[2], B[2]), max(A[3], B[3])])
        groups.pop(b)


def doors(facts: SheetFacts):
    """'How many doors are shown ... Count doorways fitted with a door; open doorways without a
    door leaf do not count.' CubiCasa5k's own icon annotation only draws a door icon (leaf + arc)
    where there IS a leaf; a bare opening in the wall has no icon at all, so counting the model's
    `door` icon class already implements the 'leaf only' rule. Collinear fragments of one leaf are merged."""
    _, _, runs = _icon_count(facts, "door")
    groups = merge_fragments([e for e in facts.elements if e.kind == "door" and len(e.polygon) >= 2])
    ids = [g[0].id for g in groups]
    if len(groups) != sum(len(g) for g in groups):
        facts.extras.setdefault("count_notes", {})["doors"] = (
            f"{sum(len(g) for g in groups) - len(groups)} door fragments merged into the leaf they belong to")
    return len(ids), ids, list(runs)


def toilets(facts: SheetFacts):
    """'How many toilet bowls (WC seats) are drawn?' -- one count per toilet icon."""
    return _icon_count(facts, "toilet")


def sinks(facts: SheetFacts):
    """'... a double-bowl sink counts as one.' The CNN's `sink` icon is one connected blob per
    sink fixture (single- or double-bowl are drawn as one symbol in CubiCasa), so counting icon
    instances already satisfies the rule without extra bowl-merging logic."""
    return _icon_count(facts, "sink")


def showers_baths(facts: SheetFacts):
    """'How many showers and bathtubs ... in total?' The pretrained model has a `bathtub` icon
    class but NO separate shower class (engine.raster.model.ICON_CLASSES), so this undercounts
    shower-only bathrooms -- a known limitation, see docs/handoff/raster.md failure buckets.
    FIX 1: dev truth is 1 for ~85% of drawings but the bathtub icon fires on ~10%, so with zero
    bath icons we fall back to the dev-median prior (1), recorded as Tag.defaulted in
    facts.extras['count_defaults'] -- it is a prior, not a detection."""
    value, ids, runs = _icon_count(facts, "bath")
    if value == 0:
        _mark_default(facts, "showers_baths", 1, "no bathtub icon; dev-median prior")
        return 1, ids, [1 for _ in runs] if runs else [1]
    return value, ids, runs


# ---------------------------------------------------------------------------------------------
# Room-label-backed intents (OCR overriding/filling in the CNN's coarse room classes).
# ---------------------------------------------------------------------------------------------

_SAUNA_LABEL_CONF = 0.6  # lone "S" is a noisy hit; below 60 OCR conf it is mostly clutter


def saunas(facts: SheetFacts):
    """'How many saunas are on this floor plan?' Sauna has no CNN room class. The CNN's
    `sauna_bench` icon is the strongest signal (dev: 83% exact vs 59% for OCR labels, prior 57%),
    one bench blob per sauna; OCR 'S'/'SAUNA'/'LOYLYH' labels decide only when no bench is found."""
    icons = _icon_count(facts, "sauna_bench")
    if icons[0] > 0:
        return icons
    n, ids = _label_instances(facts, "sauna", _SAUNA_LABEL_CONF)
    return n, ids, [n, n, n]


def kitchens(facts: SheetFacts):
    """'... including kitchenettes, open kitchens and utility kitchens ...' -- the CNN's
    `kitchen` room class covers all of these (CubiCasa draws them as one room class); OCR
    (K/KEITT/TUPAK/AK) can only raise confidence, not split one kitchen into two.
    FIX 2: the CNN over-segments kitchens (often 2-3 for truth 1); the dev prior (1) beats it
    (80% vs 50%), so the answer is the prior, Tag.defaulted, with the detected count kept in runs."""
    value, ids, runs = _subtype_instances(facts, "kitchen")
    if value != 1:
        _mark_default(facts, "kitchens", 1, f"detector said {value}; dev-median prior")
        return 1, ids, runs
    return value, ids, runs


def bedrooms(facts: SheetFacts):
    """'... (makuuhuone, usually marked MH) ...' -- CNN `bedroom` room class (slivers below 1.5%
    of the image dropped at extraction) and the distinct OCR 'MH'/'MH1'/'MH 2' labels (one per
    room); the larger of the two wins, so 'MH 1' + 'MH 2' => 2 even if the CNN merges or splits
    (regression: colorful-2002 = 2). Labels alone are NOT enough: OCR misses ~40% of them, so
    'labels first' scored 66% against 75% for CNN-or-labels on DEV."""
    value, ids, runs = _subtype_instances(facts, "bedroom")
    n_lab, lab_ids = _label_instances(facts, "bedroom", 0.2)
    if n_lab > value:
        return n_lab, lab_ids, [n_lab] * 3
    return value, ids, runs


def wc_rooms(facts: SheetFacts):
    """'How many separate WC rooms (marked WC)?' No CNN room class for WC (folded into `bath`);
    purely an OCR 'WC' label hit, which is also what EXCLUDES a WC-labelled blob from
    `bathrooms()` below."""
    return _subtype_instances(facts, "wc")


def bathrooms(facts: SheetFacts):
    """'... (e.g. KH, KPH, PH, PESUH, SH), not counting separate WC rooms.' Default subtype for
    the CNN's `bath` room class (engine/raster/extract.py _ROOM_KIND); a room is re-labelled
    'wc' instead (and excluded here) only when an OCR 'WC' token lands inside it.
    FIX 2 (same as kitchens): detector count != 1 -> dev-median prior 1, Tag.defaulted."""
    value, ids, runs = _subtype_instances(facts, "bathroom")
    if value != 1:
        _mark_default(facts, "bathrooms", 1, f"detector said {value}; dev-median prior")
        return 1, ids, runs
    return value, ids, runs


def balconies(facts: SheetFacts):
    """'... (parveke, including glazed balconies) ...' Balconies are classified `outdoor` by the
    CNN (excluded from room instances in extract.py's _ROOM_SKIP) so they only ever appear as
    leftover `label` elements; purely an OCR 'PARVEKE'/'PARV' hit."""
    return _subtype_instances(facts, "balcony")


# ---------------------------------------------------------------------------------------------
# Page-level intent.
# ---------------------------------------------------------------------------------------------

def floors(facts: SheetFacts):
    """'How many floors (storeys) does this floor plan show?' Disjoint ink blobs of comparable
    size to the largest (engine.raster.extract._floor_blobs); default 1."""
    ids = [e.id for e in facts.elements if e.kind == "floor_blob"]
    value = max(1, len(ids))
    runs = facts.extras.get("cnn_runs", {}).get("floors", [value])
    runs = [max(1, r) for r in runs]
    return value, ids, runs
