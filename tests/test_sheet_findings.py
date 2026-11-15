"""engine/sheet_findings.py: findings of a big sheet come from what it prints (synthetic OCR words, no files)."""
from engine.sheet_findings import findings


def W(t, x, y, w=None, h=30, ang=0):
    w = w or 18 * len(t)
    return {"text": t, "box": [x, y, x + w, y + h], "conf": 90.0, "angle": ang}


def row(words_txt, x, y):
    out, cx = [], x
    for t in words_txt.split():
        out.append(W(t, cx, y))
        cx += 18 * len(t) + 15
    return out


def test_area_and_count_tables():
    ws = []
    ws += row("WEST WING DORMITORY = 6,095 SF", 100, 100)
    ws += row("EAST WING DORMITORY = 6,092 SF", 100, 150)
    ws += row("TOTAL SECOND FLOOR = 26,562 SF", 100, 200)
    ws += row("FIRST FLOOR = 48 DORMS", 100, 400)
    ws += row("SECOND FLOOR = 48 DORMS", 100, 450)
    ws += row("TOTAL = 144 DORMS", 100, 500)
    f = {x["kind"]: x for x in findings(ws)}
    assert "area_table" in f and len(f["area_table"]["items"]) == 3
    assert f["area_table"]["items"][0]["value"].replace(" ", "") == "6,095SF"
    assert "West Wing" in f["area_table"]["items"][0]["label"]
    assert "count_table" in f and any(i["value"].startswith("144") for i in f["count_table"]["items"])
    assert all(i["boxes"] for i in f["area_table"]["items"])


def test_equipment_and_pipes_and_nothing_zero():
    ws = [W(f"FP-{i}", 100 + 200 * i, 100) for i in range(1, 6)]
    ws += [W(t, 100 + 200 * i, 300) for i, t in enumerate(["FSI-1", "FSL-2", "FSI-3", "FSI-4"])]
    ws += [W(t, 50 * i, 900) for i, t in enumerate(['8"', '6"', '8"', '12"', '2"', '8"', '6"', '16"', '8"'])]
    f = {x["kind"]: x for x in findings(ws)}
    eq = {i["label"]: i["value"] for i in f["equipment"]["items"]}
    assert eq["FP"].startswith("5") and eq["FSI"].startswith("4")
    assert "pipe_sizes" in f
    for x in findings(ws):
        for i in x["items"]:
            assert not str(i["value"]).startswith("0")


def test_slab_types_and_empty():
    ws = row("300 SLAB-ON-GRADE W/ D16 @ 300 TOP OF SLAB EL. = 9400", 100, 100)
    ws += row("150 SLAB-ON-GRADE W/", 100, 600) + row("D13 @ 300", 100, 640)
    f = {x["kind"]: x for x in findings(ws)}
    vals = " ".join(i["value"] for i in f["slab_types"]["items"])
    assert "D16" in vals and "D13" in vals
    assert findings([]) == []
