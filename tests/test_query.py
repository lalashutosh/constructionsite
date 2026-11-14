import copy
import glob
import json
import pathlib

import pytest

from contracts.proof import Element, Provenance, SheetFacts
from engine import query
from engine.query import SpecError, run, spec_for, validate

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _room(i, sub, x, label=None, storey="EG", w=10, **attrs):
    return Element(id=f"r{i}", kind="room", subtype=sub, label=label, attrs={"storey": storey, **attrs},
                   polygon=[(x, 0), (x + w, 0), (x + w, 10), (x, 10)])


def _facts():
    els = [_room(0, "bedroom", 0, "Zi"), _room(1, "bathroom", 10, "Bad"), _room(2, "balcony", 20, "Bal"),
           _room(3, "bedroom", 40, "Zi", storey="OG"),
           Element(id="d0", kind="door", polygon=[(9, 4), (11, 4), (11, 6), (9, 6)]),
           Element(id="d1", kind="door", attrs={"leaf": False}, polygon=[(0, 0), (1, 0), (1, 1), (0, 1)]),
           Element(id="s1", kind="sink", polygon=[(11, 1), (13, 1), (13, 3), (11, 3)]),
           Element(id="s2", kind="sink", polygon=[(13, 1), (15, 1), (15, 3), (13, 3)])]
    return SheetFacts(provenance=Provenance(file="x"), elements=els, width_px=100, height_px=100)


def test_spec_validation_rejects_unknown_fields():
    for bad in ({"select": "door", "aggregate": "count", "value": 3},
                {"select": "door", "aggregate": "median"},
                {"select": "door", "aggregate": "count", "where": {"colour": "red"}},
                {"select": "door", "aggregate": "count", "rules": ["make_it_up"]},
                {"aggregate": "count"}):
        with pytest.raises(SpecError):
            validate(bad)
    with pytest.raises(SpecError):
        validate({"select": "dragon", "aggregate": "count"}, known_kinds={"door", "room"})
    validate({"select": "door", "aggregate": "count"}, known_kinds={"door", "room"})


def test_basic_aggregates_and_rules():
    f = _facts()
    assert run({"select": "door", "aggregate": "count", "rules": ["door_requires_leaf"]}, f).value == 1
    assert run({"select": "door", "aggregate": "count"}, f).value == 2
    assert run({"select": "sink", "aggregate": "count", "rules": ["double_bowl_one_sink"]}, f).value == 1
    r = run({"select": "room", "aggregate": "sum_area", "rules": ["exclude_outdoor"]}, f, px_per_m=1.0)
    assert r.value == 300.0 and "exclude_outdoor" in r.rule_applied
    assert run({"select": "room", "aggregate": "sum_area"}, f).value is None  # needs scale
    g = run({"select": "room", "group_by": "storey", "aggregate": "count"}, f)
    assert g.groups == {"EG": 3, "OG": 1}
    adj = run({"select": "room", "where": {"adjacent_to": {"room_type": "bathroom"}}, "aggregate": "count"}, f)
    assert adj.value == 2  # bedroom r0 and balcony r2 touch the bathroom
    has = run({"select": "room", "where": {"has": {"kind": "sink"}}, "aggregate": "count"}, f)
    assert has.value == 1


def test_real_unit_area_attr_needs_no_scale():
    f = SheetFacts(provenance=Provenance(file="x"), elements=[_room(0, "bedroom", 0, area_m2=12.5),
                                                              _room(1, "bedroom", 20, area_m2=7.5)])
    assert run({"select": "room", "aggregate": "sum_area"}, f).value == 20.0


def test_fixed_specs_valid_and_params():
    s = spec_for("room_net_area", {"room": "Kitchen", "storey": "EG"})
    validate(s)
    assert s["where"] == {"label": "Kitchen", "storey": "EG"}
    assert spec_for("count_on_storey", {"element": "IfcDoor", "storey": "EG"})["select"] == "door"
    assert spec_for("nonsense") is None


def test_execute_plan_combines_in_code():
    f = _facts()
    specs = [{"select": "door", "aggregate": "count"}, {"select": "sink", "aggregate": "count"}]
    assert query.execute_plan(specs, "sum", f).value == 4


def test_apartments_graph_groups():
    from engine.query.graph import count_apartments
    f = _facts()
    assert count_apartments(f) >= 1


def test_fixed_specs_equal_intent_path_on_cached_facts():
    from engine.count import INTENTS, count
    files = sorted(glob.glob(str(ROOT / "cache" / "raster" / "*.json")))[:25]
    if not files:
        pytest.skip("no cached raster facts")
    for fn in files:
        facts = SheetFacts.model_validate_json(open(fn).read())
        for it in INTENTS:
            a = count(it, copy.deepcopy(facts))[0]
            b = run(spec_for(it, {}, "cubicasa5k"), copy.deepcopy(facts)).value
            assert a == b, (fn, it, a, b)


def test_fixed_specs_equal_intent_path_on_synthetic_fixture():
    from engine.count import INTENTS, count
    f = _facts()
    f.elements += [Element(id="w1", kind="window", polygon=[(0, 0), (2, 0), (2, 2), (0, 2)]),
                   Element(id="fb", kind="floor_blob", polygon=[(0, 0), (9, 0), (9, 9), (0, 9)])]
    for it in INTENTS:
        assert count(it, copy.deepcopy(f))[0] == run(spec_for(it, {}, "cubicasa5k"), copy.deepcopy(f)).value, it


def test_argmax_area_names_the_room_and_avg_area():
    from contracts.proof import Element, Provenance, SheetFacts
    from engine.query.run import run
    sq = lambda x, s: [(x, 0.0), (x + s, 0.0), (x + s, s), (x, s)]
    f = SheetFacts(provenance=Provenance(file="f"), elements=[
        Element(id="r1", kind="room", label="Bad", polygon=sq(0, 2), attrs={"area_m2": 4.0}),
        Element(id="r2", kind="room", label="Wohnen", polygon=sq(5, 5), attrs={"area_m2": 25.0})])
    r = run({"select": "room", "aggregate": "argmax_area"}, f)
    assert r.value == "Wohnen, 25.0 m²" and r.evidence_ids == ["r2"]
    assert run({"select": "room", "aggregate": "avg_area"}, f).value == 14.5


def test_difference_combine():
    from contracts.proof import Element, Provenance, SheetFacts
    from engine.query import execute_plan
    f = SheetFacts(provenance=Provenance(file="f"), elements=[
        Element(id=f"w{i}", kind="window", polygon=[(i, 0), (i, 1)]) for i in range(3)] + [
        Element(id="d0", kind="door", polygon=[(0, 0), (0, 1)])])
    r = execute_plan([{"select": "window", "aggregate": "count"}, {"select": "door", "aggregate": "count"}],
                     "difference", f)
    assert r.value == 2 and r.groups == {"part1": 3, "part2": 1}


def test_a_room_with_a_toilet_is_a_bathroom_even_if_unnamed():
    from contracts.proof import Element, Provenance, SheetFacts
    from engine.query.run import run
    sq = lambda x, s: [(x, 0.0), (x + s, 0.0), (x + s, s), (x, s)]
    f = SheetFacts(provenance=Provenance(file="f"), elements=[
        Element(id="r1", kind="room", subtype="sauna", label="S", polygon=sq(0, 10), attrs={"area_m2": 4.0}),
        Element(id="r2", kind="room", subtype="living", polygon=sq(20, 30), attrs={"area_m2": 30.0}),
        Element(id="t1", kind="toilet", polygon=sq(3, 2))])
    r = run({"select": "room", "where": {"room_type": "bathroom"}, "aggregate": "sum_area"}, f)
    assert r.value == 4.0 and r.evidence_ids == ["r1"] and any("toilet" in n for n in r.notes)
