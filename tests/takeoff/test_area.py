from __future__ import annotations

import math
import random
import statistics

import pytest

from contracts.proof import Element
from engine.takeoff import area


def _square_room(id_, side_px, subtype="living", x0=0.0, y0=0.0):
    return Element(
        id=id_, kind="room", subtype=subtype,
        polygon=[(x0, y0), (x0 + side_px, y0), (x0 + side_px, y0 + side_px), (x0, y0 + side_px), (x0, y0)],
    )


# ---------------------------------------------------------------------------
# polygon_area_px: hand-computed shoelace
# ---------------------------------------------------------------------------


def test_polygon_area_px_square():
    # 10x10 px square -> area 100 px^2
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    assert area.polygon_area_px(square) == pytest.approx(100.0)


def test_polygon_area_px_triangle():
    # right triangle legs 6, 4 -> area = 0.5*6*4 = 12
    tri = [(0.0, 0.0), (6.0, 0.0), (0.0, 4.0)]
    assert area.polygon_area_px(tri) == pytest.approx(12.0)


def test_polygon_perimeter_px_square():
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    assert area.polygon_perimeter_px(square) == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# room_area_m2 / room_perimeter_m: fixture numbers
# ---------------------------------------------------------------------------


def test_room_area_m2_matches_sample_fixture():
    # room1 in contracts/fixtures/sample_facts.json: 400x500 px, px_per_m = 100
    # -> 4 m x 5 m -> 20 m^2
    room = Element(
        id="room1", kind="room", subtype="living",
        polygon=[(40.0, 40.0), (440.0, 40.0), (440.0, 540.0), (40.0, 540.0), (40.0, 40.0)],
    )
    assert area.room_area_m2(room, px_per_m=100.0) == pytest.approx(20.0)


def test_room_area_m2_rejects_non_positive_scale():
    room = _square_room("r", 100.0)
    with pytest.raises(ValueError):
        area.room_area_m2(room, px_per_m=0.0)


# ---------------------------------------------------------------------------
# apartment_total_m2: excludes balconies/loggias/terraces
# ---------------------------------------------------------------------------


def test_apartment_total_excludes_balcony():
    living = _square_room("living", 200.0, subtype="living", x0=0, y0=0)       # 2x2 m = 4 m^2 at 100 px/m
    balcony = _square_room("balcony", 100.0, subtype="balcony", x0=500, y0=0)  # excluded
    total = area.apartment_total_m2([living, balcony], px_per_m=100.0)
    assert total == pytest.approx(4.0)


def test_apartment_total_sums_multiple_rooms():
    a_room = _square_room("a", 100.0, x0=0, y0=0)     # 1 m^2
    b_room = _square_room("b", 200.0, x0=500, y0=0)   # 4 m^2
    total = area.apartment_total_m2([a_room, b_room], px_per_m=100.0)
    assert total == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# area_interval: analytic dA/A = 2 ds/s
# ---------------------------------------------------------------------------


def test_area_interval_hand_computed():
    # A=20, scale_rel_sigma=0.1 -> dA/A = 0.2 -> [16, 24]
    lo, hi = area.area_interval(20.0, scale_rel_sigma=0.1)
    assert lo == pytest.approx(16.0)
    assert hi == pytest.approx(24.0)


def test_area_interval_combines_polygon_error_in_quadrature():
    # scale_rel_sigma=0.1 (-> 0.2) combined with polygon_rel_sigma=0.15 in quadrature:
    # sqrt(0.2^2 + 0.15^2) = sqrt(0.04+0.0225) = sqrt(0.0625) = 0.25
    lo, hi = area.area_interval(20.0, scale_rel_sigma=0.1, polygon_rel_sigma=0.15)
    assert hi - lo == pytest.approx(2 * 20.0 * 0.25)


def test_area_interval_lo_never_negative():
    lo, _hi = area.area_interval(1.0, scale_rel_sigma=10.0)
    assert lo >= 0.0


# ---------------------------------------------------------------------------
# Monte Carlo (seed 7, n=2000): confirm the analytic dA/A = 2 ds/s propagation
# ---------------------------------------------------------------------------


def test_area_interval_monte_carlo_matches_analytic():
    rng = random.Random(7)
    rel_sigma = 0.10
    base_px_per_m = 100.0
    area_px = 200000.0  # same as the sample fixture's room1

    samples = []
    for _ in range(2000):
        # scale factors are positive and their errors are relative: lognormal perturbation
        s = base_px_per_m * math.exp(rng.gauss(0.0, rel_sigma))
        samples.append(area_px / (s ** 2))

    mean_area = statistics.mean(samples)
    std_area = statistics.pstdev(samples)
    empirical_rel_sigma = std_area / mean_area
    analytic_rel_sigma = 2.0 * rel_sigma

    assert empirical_rel_sigma == pytest.approx(analytic_rel_sigma, rel=0.15)

    # and the analytic interval should bracket the empirical 1-sigma band reasonably
    nominal_area = area_px / (base_px_per_m ** 2)
    lo, hi = area.area_interval(nominal_area, scale_rel_sigma=rel_sigma)
    assert lo < mean_area < hi
