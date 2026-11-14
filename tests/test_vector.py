"""Vector plugin tests: resolver contract, name matching, fixture rules, schedule parsing, SVG/IFC helpers."""
from __future__ import annotations

import os
import pathlib

import pytest

from engine import registry, siblings
from engine.vector import dxf_query, ifc, schedule, svgvec


def _touch(p: pathlib.Path, data: bytes = b"x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def test_resolver_priority_and_bypass(tmp_path):
    d = tmp_path / "data" / "swiss_dwellings"
    for ext in ("pdf", "dxf", "png"):
        _touch(d / f"a.{ext}")
    r = siblings.resolve("data/swiss_dwellings/a.pdf", True, related=False, root=tmp_path)
    assert r is not None and r.fmt == "dxf" and r.path.endswith("a.dxf")
    assert siblings.resolve("data/swiss_dwellings/a.pdf", False, root=tmp_path) is None   # bypass is total
    # png never resolves to a worse format, dxf has no better sibling
    assert siblings.resolve("data/swiss_dwellings/a.dxf", True, related=False, root=tmp_path) is None
    r2 = siblings.resolve("data/swiss_dwellings/a.png", True, related=False, root=tmp_path)
    assert r2 is not None and r2.fmt == "dxf"


def test_resolver_ifc_over_svg_and_related_is_opt_in(tmp_path):
    d = tmp_path / "data" / "ifc_models"
    _touch(d / "model.ifc")
    _touch(d / "model_plan-01.pdf")
    _touch(d / "model_plan-01.svg")
    p = "data/ifc_models/model_plan-01.pdf"
    r = siblings.resolve(p, True, related=False, root=tmp_path)
    assert r is not None and r.fmt == "svg"                      # same-stem sibling only
    r = siblings.resolve(p, True, related=True, root=tmp_path)
    assert r is not None and r.fmt == "ifc" and "RELATED" in (r.note or "")
    assert siblings.resolve(p, False, related=True, root=tmp_path) is None


def test_norm_nfkc_casefold_whitespace():
    assert ifc.norm("  1.  KORRUS ") == ifc.norm("1. korrus")
    assert ifc.norm("Ｋælder") == ifc.norm("kælder")             # full-width K via NFKC
    assert ifc.norm("STRASSE") == ifc.norm("Straße")             # casefold, not lower


def test_quoted_names_and_element_words():
    assert ifc.quoted_names("Kui suur on ruumi „KORIDOR (119)“ netopõrandapind korrusel „1.korrus“ (m²)?") == [
        "KORIDOR (119)", "1.korrus"]
    assert ifc.quoted_names("net floor area of the room 'Depot (Rum nr. K08)' on 'Kælder'") == ["Depot (Rum nr. K08)", "Kælder"]
    assert ifc.element_class_from_text("Mitu seina on näidatud korruse „1.korrus“ plaanil?") == "IfcWall"
    assert ifc.element_class_from_text("Hvor mange søjler er vist på plantegningen for 'Kælder'?") == "IfcColumn"
    assert ifc.element_class_from_text("Wie viele Träger enthält das Modell „X“?") == "IfcBeam"
    assert ifc.element_class_from_text("x", "rooms (spaces)") == "IfcSpace"


def test_fixture_rules():
    wc = dict(nC=0, nP=2, L=0.6, S=0.45)
    tub = dict(nC=1, nP=2, L=1.7, S=0.75)
    basin = dict(nC=1, nP=2, L=0.55, S=0.4)
    shower = dict(nC=1, nP=2, L=0.9, S=0.88)
    kitchen = dict(nC=4, nP=1, L=2.0, S=0.6)
    assert [dxf_query.classify_fixture(c) for c in (wc, tub, basin, shower, kitchen)] == [
        "toilets", "bathtubs", "washbasins", "showers", None]


def test_schedule_dimension_strings():
    assert schedule._cell_dim(["0\"", "-", "8'", "3/16\"", "11", "-", "2'"]) == ["8'-0\"", "2'-11 3/16\""]
    assert schedule.DOOR_NO.match("118.A1") and not schedule.DOOR_NO.match("118")
    assert schedule.MATL.match("AL-1/GL-1") and schedule.MATL.match("STL-2")


def test_svg_path_even_odd_area():
    poly = svgvec._poly("M0,0 L10,0 L10,10 L0,10 L0,0 M2,2 L4,2 L4,4 L2,4 L2,2")
    assert abs(poly.area - 96.0) < 1e-9                           # ring with a hole


def test_plugin_registers_resolver_and_voters():
    registry.reset()
    from engine.vector import plugin
    plugin.register()
    assert any(n == "vector_siblings" for n, _ in registry.resolvers())
    assert len(registry.voters_for("count")) == 3 and len(registry.voters_for("area")) == 3
    registry.reset()


@pytest.mark.skipif(not __import__("evalkit.data", fromlist=["dataset_root"]).dataset_root().joinpath("questions.jsonl").exists(), reason="dataset not available")
def test_real_dxf_and_ifc_round_trip():
    from evalkit.data import load_questions
    from engine.vector import plugin
    qs = [q for q in load_questions() if q.lang == "en" and q.split == "dev"]
    q = next(q for q in qs if q.source == "swiss_dwellings" and q.intent == "doors")
    ctx = registry.Ctx(path=q.path, abs_path="", question=q.question, intent=q.intent, params=q.params, kind="count")
    vr = plugin.voter_primary(ctx)
    assert vr is not None and vr.exact and vr.voter.value == int(q.answer)
    ctx.allow_siblings = False                                    # PDF given file: still the vector text/paths
    vr2 = plugin.voter_primary(ctx)
    assert vr2 is not None and vr2.voter.name == "pdf_vector" and vr2.voter.value == int(q.answer)
    q = next(q for q in qs if q.source == "ifc_models" and q.intent == "room_net_area" and q.path.endswith(".ifc"))
    ctx = registry.Ctx(path=q.path, abs_path="", question=q.question, intent=q.intent, params=q.params, kind="area")
    vr = plugin.voter_primary(ctx)
    assert vr is not None and abs(vr.voter.value - float(str(q.answer).split()[0])) / float(str(q.answer).split()[0]) < 0.02


def test_credit_lookup_table_and_all_files(tmp_path):
    from engine.vector import credits
    d = tmp_path / "data"
    (d / "ifc_models").mkdir(parents=True)
    (d / "ifc_models" / "LICENSE.md").write_text(
        "| file | title | licence | credit | source |\n|---|---|---|---|---|\n| m.ifc | M | MIT | (c) X | http://x |\n")
    (d / "swiss_dwellings").mkdir()
    (d / "swiss_dwellings" / "LICENSE.md").write_text("intro\n\nAll files: CC-BY-4.0. Credit: Swiss Dwellings v3.0.0, CC BY 4.0.\n")
    assert credits.lookup(tmp_path, "data/ifc_models/m.ifc") == ("MIT", "(c) X")
    assert credits.lookup(tmp_path, "data/swiss_dwellings/a.dxf") == ("CC-BY-4.0", "Swiss Dwellings v3.0.0, CC BY 4.0.")
    assert credits.lookup(tmp_path, "data/ifc_models/unknown.ifc") == (None, None)


def test_extract_gives_sheet_facts_not_raster(monkeypatch, tmp_path):
    """The pipeline looks for engine.vector.plugin.extract; without it vector files fell through to the raster
    extractor and every swiss/ifc answer was capped at amber (product mode: refused)."""
    from engine.vector import plugin
    d = tmp_path / "data" / "swiss_dwellings"
    _touch(d / "a.dxf", b"0\nEOF\n")
    (d / "LICENSE.md").write_text("All files: CC-BY-4.0. Credit: SD credit.\n")
    monkeypatch.setattr(siblings, "dataset_root", lambda: tmp_path)
    f = plugin.extract("data/swiss_dwellings/a.dxf", allow_siblings=True)
    assert f.legible and f.sheet_type == "floor_plan" and f.provenance.fmt == "dxf"
    assert f.provenance.credit == "SD credit." and f.provenance.license == "CC-BY-4.0"
    with pytest.raises(FileNotFoundError):
        plugin.extract("data/swiss_dwellings/missing.dxf")
