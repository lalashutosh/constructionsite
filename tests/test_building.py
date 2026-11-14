from engine.building import level_from_name, organise


def test_level_from_file_names():
    assert level_from_name("talo/kellari.png")[0] == -1
    assert level_from_name("house/ground floor.jpg")[0] == 0
    assert level_from_name("1. kerros.png")[0] == 1
    assert level_from_name("plan-02-klder.pdf")[0] == 2
    assert level_from_name("OG 2.png")[0] == 2
    assert level_from_name("Dachgeschoss.pdf")[0] == 99
    assert level_from_name("second floor.png")[0] == 2
    assert level_from_name("IMG_4031.jpg") is None


def test_organise_orders_floors_and_sets_aside_non_plans():
    geos = {"a": {"check": {"views": [{"type": "floor_plan"}]}, "walls": [1]},
            "b": {"check": {"views": [{"type": "floor_plan"}]}, "walls": [1, 2]},
            "c": {"check": {"views": [{"type": "section"}]}, "walls": []},
            "d": {"check": {"views": [{"type": "floor_plan"}]}, "walls": []}}
    out = organise([{"path": "a", "name": "2nd floor.png"}, {"path": "b", "name": "kellari.png"},
                    {"path": "c", "name": "leikkaus.png"}, {"path": "d", "name": "scan.png"}], lambda p: geos[p])
    assert [f["path"] for f in out["floors"]] == ["b", "a", "d"]          # basement, 2nd, unknown last
    assert out["floors"][0]["level_source"] == "file name" and out["floors"][2]["level_source"] == "upload order"
    assert out["other"][0]["type"] == "section"


def test_same_storey_plans_are_alternatives_not_floors(tmp_path):
    from engine import building as B
    for i in range(3):
        (tmp_path / f"p{i}").write_bytes(b"x")
    files = [{"path": str(tmp_path / f"p{i}"), "name": n}
             for i, n in enumerate(["a/footing.pdf", "b/foundation.pdf", "c/floor plan.pdf"])]
    geos = {f["path"]: {"check": {"views": [{"type": "floor_plan"}]}} for f in files}

    class Fake:
        kind = "strong"

        def complete(self, system, user, max_tokens=0):
            class R:
                usd = 0.0
                text = ('{"files": [{"i": 0, "doc_type": "foundation_plan", "level": null}, '
                        '{"i": 1, "doc_type": "floor_plan", "level": null, "version": "2015-05"}, '
                        '{"i": 2, "doc_type": "floor_plan", "level": null, "version": "2015-07"}], "building": "x"}')
            return R()
    out = B.organise(files, lambda p: geos[p], abs_of=lambda p: p, thinker=Fake())
    assert len(out["floors"]) == 1 and out["floors"][0]["path"].endswith("p2")   # newest shown, nothing stacked
    assert [a["path"][-2:] for a in out["alternatives"]] == ["p1"]
    assert out["other"][0]["doc_type"] == "foundation_plan"
