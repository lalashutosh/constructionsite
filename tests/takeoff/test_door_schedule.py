from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.proof import Element, Provenance, ScaleInfo, SheetFacts
from engine.scale import anchors as scale
from engine.takeoff import door_schedule

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def _room(id_, x0, y0, x1, y1, subtype="living"):
    return Element(
        id=id_, kind="room", subtype=subtype,
        polygon=[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
    )


def _door(id_, x, y, width_px=90.0):
    return Element(
        id=id_, kind="door",
        polygon=[(x, y), (x + width_px, y), (x + width_px, y + 12.0), (x, y + 12.0), (x, y)],
        attrs={"width_px": width_px},
    )


def _facts(elements) -> SheetFacts:
    return SheetFacts(provenance=Provenance(file="test.png"), sheet_type="floor_plan", elements=list(elements))


# ---------------------------------------------------------------------------
# two distinct rooms either side of a door
# ---------------------------------------------------------------------------


def test_door_between_two_rooms_resolves_both_sides():
    living = _room("living", 0, 0, 200, 200)
    bedroom = _room("bedroom", 200, 0, 400, 200)
    door = _door("d0", 195, 50)  # centroid near x=240, straddling the shared wall
    facts = _facts([living, bedroom, door])
    rows = door_schedule.build(facts, scale=ScaleInfo(px_per_m=100.0, rel_sigma=0.02, widths_relative=False))
    assert len(rows) == 1
    row = rows[0]
    assert {row.from_room, row.to_room} == {"living", "bedroom"}
    # 90 px / 100 px/m = 0.9 m
    assert row.width_m == pytest.approx(0.9)
    assert row.width_px_relative is None
    assert row.open_decisions == []


def test_door_with_single_room_assumes_exterior_and_flags_decision():
    living = _room("living", 0, 0, 200, 200)
    door = _door("d0", 10, 190)
    facts = _facts([living, door])
    rows = door_schedule.build(facts, scale=ScaleInfo(px_per_m=100.0, rel_sigma=0.02, widths_relative=False))
    row = rows[0]
    assert row.from_room == "living"
    assert row.to_room == "exterior"
    assert any("exterior" in d for d in row.open_decisions)


def test_door_with_no_rooms_at_all():
    door = _door("d0", 10, 10)
    facts = _facts([door])
    rows = door_schedule.build(facts, scale=None)
    row = rows[0]
    assert row.from_room is None and row.to_room is None
    assert any("unknown" in d for d in row.open_decisions)


# ---------------------------------------------------------------------------
# circularity: scale.widths_relative=True -> never report a metres width
# ---------------------------------------------------------------------------


def test_widths_relative_scale_reports_px_not_metres():
    living = _room("living", 0, 0, 200, 200)
    door = _door("d0", 10, 190, width_px=77.0)
    facts = _facts([living, door])
    relative_scale = ScaleInfo(px_per_m=100.0, rel_sigma=0.12, widths_relative=True, needs_user=True)
    rows = door_schedule.build(facts, scale=relative_scale)
    row = rows[0]
    assert row.width_m is None
    assert row.width_px_relative == pytest.approx(77.0)
    assert any("circular" in d.lower() for d in row.open_decisions)


def test_no_scale_at_all_reports_px_not_metres():
    living = _room("living", 0, 0, 200, 200)
    door = _door("d0", 10, 190)
    facts = _facts([living, door])
    rows = door_schedule.build(facts, scale=None)
    assert rows[0].width_m is None
    assert rows[0].width_px_relative is not None


# ---------------------------------------------------------------------------
# to_csv
# ---------------------------------------------------------------------------


def test_to_csv_has_header_and_one_row_per_door():
    living = _room("living", 0, 0, 200, 200)
    bedroom = _room("bedroom", 200, 0, 400, 200)
    doors = [_door("d0", 195, 50), _door("d1", 195, 150)]
    facts = _facts([living, bedroom, *doors])
    rows = door_schedule.build(facts, scale=ScaleInfo(px_per_m=100.0, rel_sigma=0.02, widths_relative=False))
    csv_text = door_schedule.to_csv(rows)
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("id,from_room,to_room")
    assert len(lines) == 1 + len(doors)


# ---------------------------------------------------------------------------
# on the frozen sample fixture
# ---------------------------------------------------------------------------


def test_door_schedule_on_sample_fixture():
    facts = SheetFacts.model_validate(json.loads((FIXTURES / "sample_facts.json").read_text()))
    info = scale.solve(facts)
    rows = door_schedule.build(facts, scale=info)
    # 7 door elements in the fixture
    assert len(rows) == 7
    assert all(r.from_room == "room1" for r in rows)
    assert all(r.to_room == "exterior" for r in rows)  # only one room polygon on this sheet
    # scale solves to a real (non-relative) px_per_m via printed_area + door_prior
    assert info.widths_relative is False
    assert all(r.width_m is not None for r in rows)
