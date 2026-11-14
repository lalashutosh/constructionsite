from contracts.proof import Element, Provenance, SheetFacts
from engine.plan.build import plan


def _facts(apartments=("A", "B")):
    sq = lambda x, s: [(x, 0.0), (x + s, 0.0), (x + s, s), (x, s)]
    els = []
    for i, a in enumerate(apartments):
        els += [Element(id=f"k{i}", kind="room", subtype="kitchen", label="Küche", polygon=sq(10 * i, 3),
                        attrs={"area_m2": 9.0, "apartment": a}),
                Element(id=f"b{i}", kind="room", subtype="bathroom", label="Bad", polygon=sq(10 * i + 4, 2),
                        attrs={"area_m2": 4.0, "apartment": a})]
    els += [Element(id="d0", kind="door", polygon=[(0, 0), (1, 0)])]
    return SheetFacts(provenance=Provenance(file="f"), elements=els)


def test_apartment_building_checklist_and_order():
    P = plan(_facts(), "standard")
    assert P["building"]["type"] == "apartment_building" and P["building"]["confidence"] == "high"
    ids = [s["id"] for s in P["steps"]]
    assert ids.index("foundation") < ids.index("floor_slab") < ids.index("structure") < ids.index("roof")
    doors = next(c for c in P["checklist"] if c["id"] == "doors")
    assert (doors["qty"], doors["tag"]) == (1, "drawn")
    found = next(c for c in P["checklist"] if c["id"] == "concrete_found")
    assert found["tag"] == "defaulted" and found["qty"] > 0          # a rate assumption entered the number


def test_vibe_changes_quantities_and_missing_scale_is_open():
    a = {c["id"]: c["qty"] for c in plan(_facts(), "budget")["checklist"]}
    b = {c["id"]: c["qty"] for c in plan(_facts(), "premium")["checklist"]}
    assert b["sockets"] > a["sockets"] and b["paint"] > a["paint"]
    raster = SheetFacts(provenance=Provenance(file="f"), elements=[
        Element(id="r", kind="room", subtype="kitchen", polygon=[(0, 0), (90, 0), (90, 90), (0, 90)])])
    P = plan(raster, "standard", px_per_m=None)
    assert next(c for c in P["checklist"] if c["id"] == "paint")["qty"] is None and "paint_l" in P["open_inputs"]
