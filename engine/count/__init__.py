"""`count(intent, facts) -> (value, element_ids, runs)` -- the only entry point other agents call
(Definition of done in prompts/11_w1_raster.md). `runs` is what `Voter.runs` gets set to upstream.
"""
from __future__ import annotations

from contracts.proof import SheetFacts
from engine.count import rules

_DISPATCH = {
    "windows": rules.windows,
    "floors": rules.floors,
    "toilets": rules.toilets,
    "sinks": rules.sinks,
    "showers_baths": rules.showers_baths,
    "doors": rules.doors,
    "saunas": rules.saunas,
    "kitchens": rules.kitchens,
    "bedrooms": rules.bedrooms,
    "wc_rooms": rules.wc_rooms,
    "bathrooms": rules.bathrooms,
    "balconies": rules.balconies,
}

INTENTS = tuple(_DISPATCH)


def count(intent: str, facts: SheetFacts) -> tuple[int, list[str], list[int]]:
    fn = _DISPATCH.get(intent)
    if fn is None:
        raise KeyError(f"engine.count: no rule for intent {intent!r} (known: {INTENTS})")
    value, element_ids, runs = fn(facts)
    return int(value), element_ids, runs
