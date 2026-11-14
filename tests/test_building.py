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
