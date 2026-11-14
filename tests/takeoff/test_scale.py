from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from contracts.proof import Element, Provenance, SheetFacts, Tag
from engine.scale import anchors as scale

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def _door(id_, x, width_px=90.0):
    return Element(
        id=id_, kind="door",
        polygon=[(x, 560.0), (x + width_px, 560.0), (x + width_px, 572.0), (x, 572.0), (x, 560.0)],
        attrs={"width_px": width_px},
    )


def _room(id_, x0, y0, x1, y1, subtype="living", label=None):
    return Element(
        id=id_, kind="room", subtype=subtype,
        polygon=[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
        label=label,
    )


def _facts(elements, printed_areas=(), extras=None, width_px=480, height_px=620) -> SheetFacts:
    return SheetFacts(
        provenance=Provenance(file="test.png"), sheet_type="floor_plan",
        width_px=width_px, height_px=height_px,
        elements=list(elements), printed_areas=list(printed_areas), extras=extras or {},
    )


# ---------------------------------------------------------------------------
# parse_dimension: hand-computed
# ---------------------------------------------------------------------------


def test_parse_dimension_grouped_mm():
    # "3 600" is architectural shorthand for 3600 mm = 3.6 m
    assert scale.parse_dimension("3 600") == pytest.approx(3.6)


def test_parse_dimension_meters():
    assert scale.parse_dimension("3.60 m") == pytest.approx(3.60)
    assert scale.parse_dimension("12m") == pytest.approx(12.0)


def test_parse_dimension_mm_explicit():
    assert scale.parse_dimension("3600mm") == pytest.approx(3.6)


def test_parse_dimension_feet_inches():
    # 12'-6" = 12*12 + 6 = 150 inches; 150 * 0.0254 = 3.81 m
    assert scale.parse_dimension("12'-6\"") == pytest.approx(150 * 0.0254)


def test_parse_dimension_unrecognised_returns_none():
    assert scale.parse_dimension("not a dimension") is None
    assert scale.parse_dimension("") is None


# ---------------------------------------------------------------------------
# door_prior only -> circular evidence
# ---------------------------------------------------------------------------


def test_door_prior_only_sets_widths_relative_and_needs_user():
    # median width 90 px / 0.9 m assumed = 100 px/m; only anchor present.
    doors = [_door(f"d{i}", 60 + i * 50) for i in range(4)]
    facts = _facts(doors)
    info = scale.solve(facts)
    assert info.px_per_m == pytest.approx(100.0)
    assert info.widths_relative is True
    assert info.needs_user is True
    assert {a.kind for a in info.anchors} == {"door_prior"}


def test_no_anchors_at_all_needs_user():
    facts = _facts([])
    info = scale.solve(facts)
    assert info.px_per_m is None
    assert info.needs_user is True


# ---------------------------------------------------------------------------
# printed_area + door_prior combine, agree -> not circular
# ---------------------------------------------------------------------------


def test_printed_area_plus_door_prior_combine_and_agree():
    room = _room("room1", 40, 40, 440, 540, label="OH")  # 400x500 px = 200000 px^2
    doors = [_door(f"d{i}", 60 + i * 50) for i in range(4)]  # median width 90 px -> 100 px/m
    printed_areas = [{"text": "20.0 m2", "value_m2": 20.0, "polygon": [(200, 260), (280, 260), (280, 280), (200, 280)]}]
    facts = _facts([room, *doors], printed_areas=printed_areas)
    info = scale.solve(facts)
    # sqrt(200000/20) = sqrt(10000) = 100 px/m: both anchors agree exactly.
    assert info.px_per_m == pytest.approx(100.0, rel=1e-6)
    assert info.widths_relative is False
    assert info.needs_user is False
    kinds = {a.kind for a in info.anchors}
    assert kinds == {"printed_area", "door_prior"}
    # combining two agreeing anchors must not be worse than the best single one
    best_single_sigma = min(a.rel_sigma for a in info.anchors)
    assert info.rel_sigma <= best_single_sigma


def test_sample_facts_fixture_solves():
    facts = SheetFacts.model_validate(json.loads((FIXTURES / "sample_facts.json").read_text()))
    info = scale.solve(facts)
    assert info.px_per_m == pytest.approx(100.0, rel=1e-6)
    assert info.widths_relative is False


# ---------------------------------------------------------------------------
# outlier rejection
# ---------------------------------------------------------------------------


def test_outlier_anchor_is_rejected_and_noted():
    room = _room("room1", 40, 40, 440, 540)
    doors = [_door(f"d{i}", 60 + i * 50) for i in range(4)]  # -> 100 px/m, rel_sigma 0.12
    # an independent dimension string that agrees with the doors: 100 px over 1 m -> 100 px/m
    dim = Element(id="dim0", kind="dimension", polygon=[(0.0, 0.0), (100.0, 0.0)], label="1 m")
    # a wildly wrong printed_area claim: forces px_per_m to ~1000 (10x off the other two, >> 3 sigma)
    bad_printed_areas = [{"text": "0.2 m2", "value_m2": 0.2, "polygon": [(200, 260), (280, 260), (280, 280), (200, 280)]}]
    facts = _facts([room, dim, *doors], printed_areas=bad_printed_areas)
    info = scale.solve(facts)
    # the two agreeing anchors (door_prior, dimension) both say 100 px/m; the bad printed_area is excluded.
    assert info.px_per_m == pytest.approx(100.0, rel=1e-3)
    rejected = [a for a in info.anchors if a.note and "OUTLIER" in a.note]
    assert len(rejected) == 1
    assert rejected[0].kind == "printed_area"
    survivors = {a.kind for a in info.anchors if not (a.note and "OUTLIER" in a.note)}
    assert survivors == {"door_prior", "dimension"}
    assert info.widths_relative is False  # a non-door_prior anchor survived: not circular


# ---------------------------------------------------------------------------
# scale_bar / dimension anchor
# ---------------------------------------------------------------------------


def test_dimension_string_anchor():
    dim = Element(id="dim0", kind="dimension", polygon=[(0.0, 0.0), (360.0, 0.0)], label="3 600")
    facts = _facts([dim])
    info = scale.solve(facts)
    # 360 px over 3.6 m -> 100 px/m
    assert info.px_per_m == pytest.approx(100.0)
    assert info.anchors[0].tag == Tag.drawn


# ---------------------------------------------------------------------------
# printed_ratio + paper size
# ---------------------------------------------------------------------------


def test_printed_ratio_with_explicit_dpi():
    facts = _facts([], extras={"printed_ratio": "1:100", "dpi": 254.0})
    info = scale.solve(facts)
    # px/mm paper = 254/25.4 = 10; px/m real = 10*1000/100 = 100
    assert info.px_per_m == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# user anchor (chosen, rel_sigma 0.01) overrides/combines cleanly
# ---------------------------------------------------------------------------


def test_user_anchor_combines_and_is_tagged_chosen():
    doors = [_door(f"d{i}", 60 + i * 50) for i in range(4)]
    facts = _facts(doors)
    info = scale.solve(facts, user_anchors=({"px_per_m": 100.0, "note": "user tapped a door"},))
    assert info.widths_relative is False
    assert info.needs_user is False
    user_anchor = next(a for a in info.anchors if a.kind == "user")
    assert user_anchor.tag == Tag.chosen
    # the user anchor is far more precise, so the combined sigma should be close to its own
    assert info.rel_sigma < 0.05


# ---------------------------------------------------------------------------
# next_question
# ---------------------------------------------------------------------------


def test_next_question_empty_when_scale_is_resolved():
    room = _room("room1", 40, 40, 440, 540)
    doors = [_door(f"d{i}", 60 + i * 50) for i in range(4)]
    printed_areas = [{"text": "20.0 m2", "value_m2": 20.0, "polygon": [(200, 260), (280, 260), (280, 280), (200, 280)]}]
    facts = _facts([room, *doors], printed_areas=printed_areas)
    info = scale.solve(facts)
    assert scale.next_question(facts, info) == []


def test_next_question_order_and_reduction_when_needs_user():
    doors = [_door(f"d{i}", 60 + i * 50) for i in range(4)]
    facts = _facts(doors)
    info = scale.solve(facts)
    qs = scale.next_question(facts, info)
    assert len(qs) == 3
    assert "tap a door" in qs[0].question
    assert "draw a line" in qs[1].question
    assert "printed scale" in qs[2].question
    # each candidate must shrink (or at worst hold) the sigma relative to the current 0.12
    for q in qs:
        assert q.expected_rel_sigma <= info.rel_sigma
        assert q.expected_interval_reduction_pct >= 0.0
    # tapping a door (rel_sigma 0.01) should win out over typing the printed scale (0.03)
    assert qs[0].expected_rel_sigma <= qs[2].expected_rel_sigma
