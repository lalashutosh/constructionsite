from engine.sheetfloor import asked_floor, pick

FL = [{"label": "1. KERROS", "level": 0, "box": [0, 0, 10, 10]}, {"label": "2. KERROS", "level": 1, "box": [11, 0, 20, 10]}]


def test_asked_floor_forms():
    assert asked_floor("How many bedrooms on floor 2?") == ("index", 2)
    assert asked_floor("Montako makuuhuonetta 2. kerroksessa?") == ("index", 2)
    assert asked_floor("How many doors on the second floor?") == ("index", 2)
    assert asked_floor("How many windows upstairs?") == ("top", -1)
    assert asked_floor("How many doors on the ground floor?") == ("ground", 0)
    assert asked_floor("How many doors are there?") is None


def test_pick():
    assert pick(FL, ("index", 2))["label"] == "2. KERROS"
    assert pick(FL, ("ground", 0))["label"] == "1. KERROS"
    assert pick(FL, ("top", -1))["label"] == "2. KERROS"
    assert pick(FL, ("index", 3)) is None
