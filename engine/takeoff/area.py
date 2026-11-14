"""Area takeoff: shoelace via shapely, room / apartment totals, and the interval scale propagates.

Formula (hand-computed in tests/takeoff/test_area.py):
  A = shoelace(polygon) / px_per_m**2
  dA/A ~= 2 * ds/s   (s = px_per_m), combined in quadrature with any polygon
  measurement error, since A ~ 1/s**2 so a small relative error ds/s in s
  gives a relative error of 2*ds/s in A (first-order Taylor).
"""
from __future__ import annotations

import math
from typing import Iterable

from shapely.geometry import Polygon

from contracts.proof import Element

EXCLUDED_SUBTYPES = {"balcony", "loggia", "terrace"}


def _closed(polygon: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return polygon if polygon[0] == polygon[-1] else [*polygon, polygon[0]]


def polygon_area_px(polygon: list[tuple[float, float]]) -> float:
    """Shoelace area in squared pixels (via shapely)."""
    if len(polygon) < 3:
        return 0.0
    return Polygon(_closed(polygon)).area


def polygon_perimeter_px(polygon: list[tuple[float, float]]) -> float:
    if len(polygon) < 2:
        return 0.0
    return Polygon(_closed(polygon)).length


def room_area_m2(room: Element, px_per_m: float) -> float:
    if px_per_m <= 0:
        raise ValueError("px_per_m must be positive")
    return polygon_area_px(room.polygon) / (px_per_m ** 2)


def room_perimeter_m(room: Element, px_per_m: float) -> float:
    if px_per_m <= 0:
        raise ValueError("px_per_m must be positive")
    return polygon_perimeter_px(room.polygon) / px_per_m


def apartment_total_m2(
    rooms: Iterable[Element], px_per_m: float, exclude: set[str] = EXCLUDED_SUBTYPES
) -> float:
    """Sum of net room areas, excluding balconies / loggias / terraces (apartment total, not gross)."""
    total = 0.0
    for r in rooms:
        if r.kind != "room":
            continue
        if (r.subtype or "").lower() in exclude:
            continue
        total += room_area_m2(r, px_per_m)
    return total


def area_interval(area_m2: float, scale_rel_sigma: float, polygon_rel_sigma: float = 0.0) -> tuple[float, float]:
    """1-sigma-ish interval for an area derived through a scale with the given relative sigma.

    dA/A ~= 2 * ds/s, combined in quadrature with a polygon-tracing error term.
    """
    if area_m2 < 0:
        raise ValueError("area_m2 must be non-negative")
    combined_rel = math.sqrt((2.0 * scale_rel_sigma) ** 2 + polygon_rel_sigma ** 2)
    lo = area_m2 * (1.0 - combined_rel)
    hi = area_m2 * (1.0 + combined_rel)
    return max(0.0, lo), hi
