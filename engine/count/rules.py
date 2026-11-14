"""Counting rules, one function per cubicasa5k intent. Each reads ONLY `facts.elements` /
`facts.extras` (contracts/proof.py: "Questions are answered from this, never from pixels again") --
geometry was already produced by `engine.raster.extract`.

Every function returns `(value: int, element_ids: list[str], runs: list[int | float])`.
`runs` becomes `Voter.runs`; see engine/raster/extract.py module docstring for why these are a
cheap confidence-threshold / cluster-radius bootstrap rather than literal scale x rotation x flip
TTA of the pretrained CNN (that would cost >10s/image on this CPU).
"""
from __future__ import annotations

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
               if e.subtype == subtype and e.kind in ("room", "label")]
    if not matches:
        return 0, [], [0, 0, 0]
    diag = math.hypot(facts.width_px or 1, facts.height_px or 1)
    points = [_centroid(e.polygon) for e in matches]
    runs = [_cluster_count(points, r * diag) for r in _CLUSTER_RATIOS]
    value = runs[1]  # medium radius is the canonical answer
    return value, [e.id for e in matches], runs


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


def doors(facts: SheetFacts):
    """'How many doors are shown ... Count doorways fitted with a door; open doorways without a
    door leaf do not count.' CubiCasa5k's own icon annotation only draws a door icon (leaf + arc)
    where there IS a leaf; a bare opening in the wall has no icon at all, so counting the model's
    `door` icon class already implements the 'leaf only' rule -- no extra filtering needed."""
    return _icon_count(facts, "door")


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
    shower-only bathrooms -- a known limitation, see docs/handoff/raster.md failure buckets."""
    return _icon_count(facts, "bath")


# ---------------------------------------------------------------------------------------------
# Room-label-backed intents (OCR overriding/filling in the CNN's coarse room classes).
# ---------------------------------------------------------------------------------------------

def saunas(facts: SheetFacts):
    """'How many saunas ...?' Sauna has no CNN room class; purely an OCR 'S'/'SAUNA' label hit
    (engine/raster/lexicon_fi.yaml)."""
    return _subtype_instances(facts, "sauna")


def kitchens(facts: SheetFacts):
    """'... including kitchenettes, open kitchens and utility kitchens ...' -- the CNN's
    `kitchen` room class covers all of these (CubiCasa draws them as one room class); OCR
    (K/KEITT/TUPAK/AK) can only raise confidence, not split one kitchen into two."""
    return _subtype_instances(facts, "kitchen")


def bedrooms(facts: SheetFacts):
    """'... (makuuhuone, usually marked MH) ...' -- CNN `bedroom` room class, OCR 'MH' confirms."""
    return _subtype_instances(facts, "bedroom")


def wc_rooms(facts: SheetFacts):
    """'How many separate WC rooms (marked WC)?' No CNN room class for WC (folded into `bath`);
    purely an OCR 'WC' label hit, which is also what EXCLUDES a WC-labelled blob from
    `bathrooms()` below."""
    return _subtype_instances(facts, "wc")


def bathrooms(facts: SheetFacts):
    """'... (e.g. KH, KPH, PH, PESUH, SH), not counting separate WC rooms.' Default subtype for
    the CNN's `bath` room class (engine/raster/extract.py _ROOM_KIND); a room is re-labelled
    'wc' instead (and excluded here) only when an OCR 'WC' token lands inside it."""
    return _subtype_instances(facts, "bathroom")


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
