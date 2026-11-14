from __future__ import annotations

import pytest

from engine.takeoff import materials


# ---------------------------------------------------------------------------
# paint: V = n * (P*h - sum(a_open)) / c
# ---------------------------------------------------------------------------


def test_paint_litres_hand_computed():
    # perimeter 20 m, height 2.5 m -> gross wall 50 m^2, minus 5 m^2 openings = 45 m^2
    # 2 coats / 9 m^2 per litre -> V = 2*45/9 = 10 litres
    v = materials.paint_litres(perimeter_m=20.0, height_m=2.5, opening_area_m2=5.0, coats=2, coverage_m2_per_l=9.0)
    assert v == pytest.approx(10.0)


def test_paint_litres_rejects_openings_bigger_than_wall():
    with pytest.raises(ValueError):
        materials.paint_litres(perimeter_m=4.0, height_m=2.0, opening_area_m2=100.0, coats=1, coverage_m2_per_l=8.0)


# ---------------------------------------------------------------------------
# tiles: N = ceil(A*(1+w)/a_tile)
# ---------------------------------------------------------------------------


def test_tiles_count_hand_computed():
    # 20 m^2 * 1.1 waste = 22 m^2; tile 0.09 m^2 (0.3x0.3) -> 22/0.09 = 244.44 -> ceil 245
    n = materials.tiles_count(area_m2=20.0, waste_frac=0.10, tile_area_m2=0.3 * 0.3)
    assert n == 245


def test_tiles_count_exact_division_no_overcounting():
    # 9 m^2 * 1.0 / 1 m^2 tiles = 9 exactly -> ceil(9) = 9, not 10
    n = materials.tiles_count(area_m2=9.0, waste_frac=0.0, tile_area_m2=1.0)
    assert n == 9


# ---------------------------------------------------------------------------
# lights: N = ceil(E*A/(F*u))
# ---------------------------------------------------------------------------


def test_lights_count_hand_computed():
    # E=300 lux, A=20 m^2 -> 6000; F=1500 lm, u=0.6 -> F*u=900; 6000/900=6.67 -> ceil 7
    n = materials.lights_count(area_m2=20.0, target_lux=300.0, lumens_per_fitting=1500.0, utilisation=0.6)
    assert n == 7


# ---------------------------------------------------------------------------
# carpet: strip-pack along the longer axis with trim waste
# ---------------------------------------------------------------------------


def test_carpet_rolls_hand_computed():
    # room 5 m x 3.2 m, roll width 4 m, waste 0.10
    # long side=5, short side=3.2 -> strips = ceil(3.2/4) = 1
    # strip length = 5 * 1.10 = 5.5 m; total length = 1*5.5 = 5.5 m; total area = 5.5*4 = 22 m^2
    out = materials.carpet_rolls(length_m=5.0, width_m=3.2, roll_width_m=4.0, waste_frac=0.10)
    assert out["strips"] == 1
    assert out["roll_length_m"] == pytest.approx(5.5)
    assert out["total_m2"] == pytest.approx(22.0)


def test_carpet_rolls_needs_multiple_strips():
    # room 5 m x 9 m, roll width 4 m -> short side=5 -> strips=ceil(5/4)=2
    # strip length = 9 * 1.0 = 9; total length = 18; total area = 18*4 = 72
    out = materials.carpet_rolls(length_m=5.0, width_m=9.0, roll_width_m=4.0, waste_frac=0.0)
    assert out["strips"] == 2
    assert out["roll_length_m"] == pytest.approx(18.0)
    assert out["total_m2"] == pytest.approx(72.0)
