"""Material quantities. Every constant used here is vibe- or user-supplied; the
caller is responsible for recording it as an `Assumption` with a `Tag` (this
module takes plain numbers, never a vibe name, so it stays a pure function).

Formulas (hand-computed in tests/takeoff/test_materials.py):
  paint:   V = n * (P*h - sum(a_open)) / c
  tiles:   N = ceil( A * (1+w) / a_tile )
  lights:  N = ceil( E * A / (F * u) )
  carpet:  strip-pack rolls along the longer axis, trim waste per strip
"""
from __future__ import annotations

import math


def paint_litres(
    perimeter_m: float, height_m: float, opening_area_m2: float, coats: int, coverage_m2_per_l: float
) -> float:
    """V = n * (P*h - sum(a_open)) / c"""
    if coverage_m2_per_l <= 0:
        raise ValueError("coverage_m2_per_l must be positive")
    net_wall_m2 = perimeter_m * height_m - opening_area_m2
    if net_wall_m2 < 0:
        raise ValueError("openings exceed the wall area")
    return coats * net_wall_m2 / coverage_m2_per_l


def tiles_count(area_m2: float, waste_frac: float, tile_area_m2: float) -> int:
    """N = ceil( A * (1+w) / a_tile )"""
    if tile_area_m2 <= 0:
        raise ValueError("tile_area_m2 must be positive")
    return math.ceil(area_m2 * (1.0 + waste_frac) / tile_area_m2)


def lights_count(area_m2: float, target_lux: float, lumens_per_fitting: float, utilisation: float) -> int:
    """N = ceil( E * A / (F * u) )"""
    if lumens_per_fitting <= 0 or utilisation <= 0:
        raise ValueError("lumens_per_fitting and utilisation must be positive")
    return math.ceil(target_lux * area_m2 / (lumens_per_fitting * utilisation))


def carpet_rolls(length_m: float, width_m: float, roll_width_m: float, waste_frac: float) -> dict:
    """Strip-pack along the longer axis: each strip runs the long side, trimmed with waste.

    Returns strip count, total roll length to buy, and the resulting area bought.
    """
    if roll_width_m <= 0:
        raise ValueError("roll_width_m must be positive")
    long_side, short_side = max(length_m, width_m), min(length_m, width_m)
    strips = math.ceil(short_side / roll_width_m)
    strip_len_m = long_side * (1.0 + waste_frac)
    total_len_m = strips * strip_len_m
    return {
        "strips": strips,
        "roll_length_m": round(total_len_m, 4),
        "total_m2": round(total_len_m * roll_width_m, 4),
    }
