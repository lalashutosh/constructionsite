"""A folder never fails as a whole (LLM off): bad files are listed, plans still come out."""
from engine.building import organise


def test_folder_with_bad_and_unknown_files_never_fails(tmp_path):
    good = tmp_path / "1st floor plan.png"
    good.write_bytes(b"not really a png")
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 truncated")
    (tmp_path / "model.ifc").write_bytes(b"ISO-10303-21; garbage")
    (tmp_path / "x.dwg").write_bytes(b"AC1027 garbage")
    files = [{"path": str(good), "name": "house/1st floor plan.png"},
             {"path": str(broken), "name": "house/broken.pdf"},
             {"path": str(tmp_path / "model.ifc"), "name": "house/model.ifc"},
             {"path": str(tmp_path / "x.dwg"), "name": "house/A-201 - Elevations.dwg"}]

    def geo(path, cached_only=False):
        raise RuntimeError("no geometry in this test")

    out = organise(files, geo, abs_of=lambda p: p, thinker=None)
    names = {x["name"]: x for x in out["floors"] + out["alternatives"] + out["other"]}
    assert set(names) == {f["name"] for f in files}                 # every file accounted for
    assert names["house/1st floor plan.png"]["doc_type"] == "floor_plan"
    assert names["house/model.ifc"]["doc_type"] == "bim_model"
    assert names["house/A-201 - Elevations.dwg"]["doc_type"] == "cad_drawing"


def test_missing_files_are_listed_not_invented_and_empty_folder_calls_no_llm(tmp_path):
    class Boom:
        kind = "strong"

        def complete(self, *a, **k):
            raise AssertionError("LLM must not be called")
    out = organise([], lambda p, cached_only=False: None, abs_of=lambda p: p, thinker=Boom())
    assert out["floors"] == [] and out["notes"] == ["empty folder"]
    out = organise([{"path": str(tmp_path / "nope.pdf"), "name": "nope.pdf"}], lambda p, cached_only=False: None,
                   abs_of=lambda p: p, thinker=Boom())
    assert out["other"][0]["doc_type"] == "missing"
