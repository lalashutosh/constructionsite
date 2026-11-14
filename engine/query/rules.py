"""Named convention rules for the query engine. Each is a pure function
`(elements, facts) -> (elements, note)` applied after selection and before aggregation.
They are the ONLY place convention knowledge lives, so the planner (LLM) can only name them, never invent them."""
from __future__ import annotations

import math
from typing import Callable

from contracts.proof import Element, SheetFacts

OUTDOOR = {"balcony", "terrace", "loggia", "outdoor", "garden", "veranda", "patio"}
KITCHEN_ALIASES = {"kitchen", "kitchenette", "open_kitchen", "utility_kitchen", "kitchen_diner"}
BALCONY_ALIASES = {"balcony", "glazed_balcony", "loggia"}


def _centroid(poly) -> tuple[float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def door_requires_leaf(els, facts):
    """A doorway only counts when a door leaf is drawn (attrs.leaf is not False)."""
    kept = [e for e in els if not (e.kind == "door" and e.attrs.get("leaf") is False)]
    return kept, "door requires leaf" if len(kept) != len(els) else None


def double_bowl_one_sink(els, facts):
    """Sink elements whose centres are closer than 1.2x their own larger extent are one fixture."""
    sinks = [e for e in els if e.kind in ("sink", "fixture") and (e.subtype in (None, "sink", "washbasin"))]
    others = [e for e in els if e not in sinks]
    merged: list[Element] = []
    for e in sinks:
        c = _centroid(e.polygon)
        ext = max(max(p[0] for p in e.polygon) - min(p[0] for p in e.polygon),
                  max(p[1] for p in e.polygon) - min(p[1] for p in e.polygon), 1e-9)
        for m in merged:
            mc = _centroid(m.polygon)
            if math.hypot(c[0] - mc[0], c[1] - mc[1]) < 1.2 * ext:
                break
        else:
            merged.append(e)
    return others + merged, "double bowl = 1 sink" if len(merged) != len(sinks) else None


def separate_wc_not_bathroom(els, facts):
    """A room labelled only WC is not a bathroom."""
    kept = [e for e in els if not (e.subtype in ("bathroom", "bath") and (e.label or "").strip().lower() in ("wc", "w.c."))]
    return kept, "separate WC is not a bathroom" if len(kept) != len(els) else None


def exclude_outdoor(els, facts):
    kept = [e for e in els if (e.subtype or "").lower() not in OUTDOOR]
    return kept, "outdoor rooms excluded from net area" if len(kept) != len(els) else None


def cluster_count(els, facts) -> int:
    """Distinct instances: single-link clusters at 5% of the image diagonal (OCR duplicates, split rooms).
    Same function the detector path uses, so the fixed specs equal engine.count.rules."""
    from engine.count.rules import _cluster_count
    diag = math.hypot(facts.width_px or 1, facts.height_px or 1)
    return _cluster_count([_centroid(e.polygon) for e in els], 0.05 * diag) if els else 0


def cluster_instances(els, facts):
    return els, None  # the count itself is computed by run() via cluster_count()


def min_one(els, facts):
    return els, None  # handled in run(): value = max(1, n)


def prior_fallback_1(els, facts):
    return els, None  # handled in run(): value = 1 when detector says 0 (showers_baths)


def _reader(els, facts):
    return els, None  # handled in run(): the value comes from that intent's reader in engine.count.rules


RULES: dict[str, Callable] = {
    "reader_saunas": _reader,
    "reader_doors": _reader,
    "reader_bedrooms": _reader,
    "reader_kitchens": _reader,
    "reader_wc_rooms": _reader,
    "door_requires_leaf": door_requires_leaf,
    "double_bowl_one_sink": double_bowl_one_sink,
    "separate_wc_not_bathroom": separate_wc_not_bathroom,
    "exclude_outdoor": exclude_outdoor,
    "cluster_instances": cluster_instances,
    "min_one": min_one,
    "prior_fallback_1": prior_fallback_1,
    "prior_fallback_not1": prior_fallback_1,
    "kitchenettes_count": lambda els, facts: (els, None),    # alias expansion at select time
    "glazed_balconies_count": lambda els, facts: (els, None),
}
