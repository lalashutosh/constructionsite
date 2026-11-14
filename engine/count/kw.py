"""Standalone 12-keyword English intent classifier for cubicasa5k count questions.

prompts/11_w1_raster.md Step 0 said to use this until `evalkit.intents.classify` landed; it has
(evalkit/intents.py, merged). `engine.count.devcheck` now imports evalkit.intents directly. This
module is kept only as a dependency-free fallback / for unit tests that must not import evalkit.
"""
from __future__ import annotations

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "windows": ("window",),
    "floors": ("floor", "storey", "storeys"),
    "toilets": ("toilet bowl", "wc seat", "wc-istuinta"),
    "sinks": ("sink", "wash basin", "allas"),
    "showers_baths": ("shower", "bathtub"),
    "doors": ("door",),
    "saunas": ("sauna",),
    "kitchens": ("kitchen",),
    "bedrooms": ("bedroom", "makuuhuone"),
    "wc_rooms": ("separate wc", "wc-tila"),
    "bathrooms": ("bathroom", "washroom", "pesuhuone"),
    "balconies": ("balcon", "parveke"),
}


def classify(question: str) -> str:
    """Returns one of the 12 intent names, or 'unknown'. First keyword match wins; checked in an
    order that puts the more specific templates (toilets/wc_rooms/showers_baths) before the
    ones whose keywords are substrings of others (e.g. 'bathroom' vs 'bath')."""
    q = question.lower()
    order = ["toilets", "wc_rooms", "showers_baths", "sinks", "windows", "doors", "saunas",
             "kitchens", "bedrooms", "bathrooms", "balconies", "floors"]
    for name in order:
        if any(k in q for k in _KEYWORDS[name]):
            return name
    return "unknown"
