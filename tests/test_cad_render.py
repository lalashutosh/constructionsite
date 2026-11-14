"""DXF / IFC uploaded without a sibling image: we draw them ourselves and the 3D data comes from their entities."""
import glob
import os

import pytest

from engine.vector.dxf_render import ascii_label

ROOT = os.environ.get("DATASET_ROOT", "")


def test_ascii_label():
    assert ascii_label("Küche 7.54 m²") == "Kuche 7.54 m2"
    assert ascii_label("ELUTUBA+KÖÖK") == "ELUTUBA+KOOK"


def _first(pattern):
    hits = sorted(glob.glob(os.path.join(ROOT, pattern))) if ROOT else []
    if not hits:
        pytest.skip("dataset not available")
    return hits[0]


def test_dxf_geometry_matches_reader(tmp_path):
    from engine.vector import dxf, dxf_render
    f = _first("data/swiss_dwellings/*.dxf")
    g = dxf_render.geometry(f, 1400)
    plan = dxf.load(f)
    assert len(g["doors"]) == len(plan.door_frames) and len(g["windows"]) == len(plan.window_polys)
    assert g["walls"] and g["px_per_m"] > 0
    for w in g["walls"]:                                   # everything inside the image
        assert all(0 <= x <= g["width"] and 0 <= y <= g["height"] for x, y in w["outer"])
    out = tmp_path / "r.png"
    fr = dxf_render.render(f, str(out), 1400)
    assert out.stat().st_size > 0 and (fr.width, fr.height) == (g["width"], g["height"])


def test_ifc_empty_model_says_why():
    from engine.vector import ifc_render
    f = _first("data/ifc_models/resbim-388_model.ifc")
    with pytest.raises(ValueError, match="no building elements"):
        ifc_render.geometry(f, 800)
