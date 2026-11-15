"""Plumb pitch deck: 13 full-slide pictures (1920x1080) drawn with the story-pitch-deck kit.
Real data only: crops of the Stoa sheets with the app's own boxes, counts from the stored deep reads
(cache/symbols), quality numbers from docs/stress-report-r9.md and the evalkit gate runs.
    .venv/bin/python docs/pitch/make_slides.py
"""
import base64
import glob
import io
import json
import pathlib
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path.home() / ".claude/skills/story-pitch-deck"))
import deck_kit as dk  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/pitch/slides"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1920, 1080
INK, GREY, BLUE, ORANGE, PANEL, TINT = dk.INK, dk.GREY, dk.BLUE, dk.ORANGE, dk.PANEL, dk.TINT
DORM = "a92115880ee3ae5eecad5e0aea0f1b8bdda46a12b7d1c173f76e1ff3135fe318"
PIPE = "b25805c1c7511e6da13ce8a59ceb70fdefd88bfd73b4aa711882b30e1c43e35b"


def deep(sha):
    return json.load(open(sorted(glob.glob(str(ROOT / f"cache/symbols/{sha}-v2[45]*.json")))[-1]))


def slide(title, kicker=None):
    fig, ax = dk.canvas(W, H)
    if kicker:
        dk.T(ax, 110, 92, kicker.upper(), 20, GREY, bold=True)
    dk.T(ax, 110, 150, title, 50, INK, bold=True)
    return fig, ax


def tag(ax, s):
    dk.T(ax, W - 60, H - 40, s, 17, GREY, ha="right")


def img(ax, rgb, x, y, w, h):
    ax.imshow(rgb, extent=(x, x + w, y + h, y), zorder=2, interpolation="lanczos")


def crop(path, box, boxes, colour, lw=4):
    """A crop of a real sheet with the app's own boxes drawn on it (RGB array)."""
    g = cv2.imread(path)
    x0, y0, x1, y1 = box
    c = g[y0:y1, x0:x1].copy()
    bgr = tuple(int(colour[i:i + 2], 16) for i in (5, 3, 1))
    for b in boxes:
        p = (np.array(b, np.float32) - [x0, y0]).astype(np.int32)
        cv2.polylines(c, [p], True, bgr, lw)
    return cv2.cvtColor(c, cv2.COLOR_BGR2RGB)


def thumb(data_url):
    raw = base64.b64decode(data_url.split(",", 1)[1])
    a = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    return cv2.cvtColor(a, cv2.COLOR_BGR2RGB)


def save(fig, n):
    dk.save(fig, OUT / f"slide{n:02d}.png", full_slide=True)


dorm, pipe = deep(DORM), deep(PIPE)
tot = {t["kind"]: t for t in dorm["totals"]}

# 1 title -----------------------------------------------------------------------------------------------------
fig, ax = dk.canvas(W, H)
dk.T(ax, 110, 430, "Plumb", 150, INK, bold=True)
dk.T(ax, 116, 560, "Blueprints that show their work", 46, BLUE, bold=True)
dk.T(ax, 116, 660, "Junction 2026  ·  Stoa: Make Blueprints Talk  ·  Abhinav Chutani", 26, GREY)
save(fig, 1)

# 2 the character --------------------------------------------------------------------------------------------
fig, ax = slide("Meet the site engineer", "the character")
dk.T(ax, 116, 300, "One dormitory floor.", 40, INK, bold=True)
dk.T(ax, 116, 360, "10,200 × 6,600 pixels.", 40, BLUE, bold=True)
dk.T(ax, 116, 450, "Every dot is a door\nto find, count and order.", 30, GREY)
dk.panel(ax, 980, 220, 830, 760, PANEL)
dk.person(ax, 1395, 330, 52, INK)
n = tot["door"]["count"]
cols = 14
for i in range(n):
    cx, cy = 1050 + (i % cols) * 50, 470 + (i // cols) * 48
    ax.add_patch(dk.Circle((cx, cy), 15, color=dk.DOT, zorder=3))
dk.T(ax, 1395, 950, f"{n} doors on this sheet", 24, GREY, ha="center")
save(fig, 2)

# 3 the problem is normal ------------------------------------------------------------------------------------
fig, ax = slide("And that is only the doors", "the problem")
rows = [("Doors", tot["door"]["count"]), ("Chairs", tot["chair"]["count"]), ("Sinks", tot["sink"]["count"]),
        ("Toilets", tot["toilet"]["count"]), ("Beds", tot["bed"]["count"])]
mx = max(v for _, v in rows)
for k, (lab, v) in enumerate(rows):
    y = 290 + k * 118
    dk.T(ax, 116, y, lab, 34, INK, bold=True)
    ax.add_patch(Rectangle((400, y - 30), 1000 * v / mx, 60, color=ORANGE if k == 0 else dk.DOT, zorder=2))
    dk.T(ax, 420 + 1000 * v / mx, y, str(v), 36, INK, bold=True)
dk.T(ax, 116, 920, "Then: hinges, pipe, cable, concrete, finishes. By hand, an engineer's afternoon, every day.", 28, GREY)
tag(ax, "counts: Plumb deep read of the A-2 dormitory sheet")
save(fig, 3)

# 4 the question ---------------------------------------------------------------------------------------------
fig, ax = slide("Can a drawing answer, and show where?", "the question")
dk.panel(ax, 760, 260, 400, 110, ORANGE, r=55)
dk.T(ax, 960, 315, "139 doors?", 40, "white", bold=True, ha="center")
for x, head, sub, col in ((260, "A guess", "general AI: nothing to check", dk.DOT), (1060, "A receipt", "every door boxed on the drawing", BLUE)):
    dk.arrow(ax, 960, 380, x + 300, 520, ORANGE)
    dk.panel(ax, x, 540, 600, 300, PANEL if col == dk.DOT else TINT)
    dk.T(ax, x + 300, 640, head, 46, INK if col == dk.DOT else BLUE, bold=True, ha="center")
    dk.T(ax, x + 300, 730, sub, 26, GREY, ha="center")
save(fig, 4)

# 5 the solution: three steps ---------------------------------------------------------------------------------
fig, ax = slide("Three steps, all checkable", "the solution")
steps = [("1  Read the sheet", "scale, outline, printed text\nfrom the drawing itself"),
         ("2  Count by code", "find every repeated symbol,\ncount each copy two ways"),
         ("3  Show the receipt", "every number boxed,\ntagged, and costed")]
for k, (h, c) in enumerate(steps):
    x = 110 + k * 600
    dk.panel(ax, x, 300, 520, 520, TINT if k == 2 else PANEL)
    dk.T(ax, x + 40, 380, h, 36, BLUE if k == 2 else INK, bold=True)
    dk.T(ax, x + 40, 520, c, 28, GREY)
    if k < 2:
        dk.arrow(ax, x + 530, 560, x + 590, 560, ORANGE)
dk.T(ax, 110, 900, "A vision model only names each kind of symbol, once. It never produces a number.", 28, INK, bold=True)
save(fig, 5)

# 6 demo: dorm with its door boxes ----------------------------------------------------------------------------
fig, ax = slide("Every door, boxed on the drawing", "demo · A-2 dormitory")
doors = [e["polygon"] for e in dorm["elements"] if e["kind"] == "door"]
img(ax, crop(str(ROOT / f"cache/uploads/{DORM}.png"), (1750, 4700, 4300, 5650), doors, BLUE, 6), 110, 230, 1100, 409)
dk.panel(ax, 1290, 230, 520, 700, PANEL)
for k, (lab, big, note, col) in enumerate([("SCALE", '1" = 40\'-0"', "half-size print caught", ORANGE),
                                           ("DOORS", f"{tot['door']['count']}", "per wing, each boxed", BLUE),
                                           ("BEDS", f"{tot['bed']['count']}", "two counts agree", BLUE)]):
    y = 310 + k * 210
    dk.T(ax, 1330, y, lab, 20, GREY, bold=True)
    dk.T(ax, 1330, y + 70, big, 54, col, bold=True)
    dk.T(ax, 1330, y + 130, note, 24, GREY)
dk.T(ax, 110, 700, "The printed note would make everything twice too big.\nThe scale bar and the dimensions outvote it.", 28, INK)
tag(ax, "real sheet, real output")
save(fig, 6)

# 7 the deep read: symbol cards ------------------------------------------------------------------------------
fig, ax = slide("The deep read: find it, count it, then name it", "creativity")
cards = [tot[k] for k in ("door", "chair", "sink", "toilet", "bed", "staircase") if k in tot]
for k, t in enumerate(cards):
    x, y = 110 + (k % 3) * 580, 260 + (k // 3) * 330
    dk.panel(ax, x, y, 540, 290, PANEL)
    if t.get("thumb"):
        img(ax, thumb(t["thumb"]), x + 30, y + 45, 200, 200)
    dk.T(ax, x + 260, y + 110, t["label"], 34, INK, bold=True)
    dk.T(ax, x + 260, y + 200, str(t["count"]), 70, BLUE, bold=True)
dk.T(ax, 110, 960, "Click a count in the app and every copy lights up in 3D.", 28, GREY)
tag(ax, "symbol pictures: cut from the sheet by the app")
save(fig, 7)

# 8 hard sheets, honest answers -------------------------------------------------------------------------------
fig, ax = slide("Hard sheets, honest answers", "accuracy · M-101A piping + S-100F foundation")
tagb = [e["polygon"] for e in pipe["elements"] if e["kind"].startswith("tag ")]
img(ax, crop(str(ROOT / f"cache/uploads/{PIPE}.png"), (2500, 1600, 6400, 4200), tagb, BLUE, 6), 110, 230, 1020, 680)
dk.panel(ax, 1210, 230, 600, 680, PANEL)
for k, (lab, big, note, col) in enumerate([("VALVES", "12", "every tag listed", BLUE),
                                           ("CHECK VALVES", "5", 'prints "TYP. OF 5";\n4 tags legible: says so', ORANGE),
                                           ("TRENCH LENGTH", "4275", "quoted from the note\n(foundation sheet S-100F)", GREY)]):
    y = 300 + k * 205
    dk.T(ax, 1250, y, lab, 20, GREY, bold=True)
    dk.T(ax, 1250, y + 60, big, 50, col, bold=True)
    dk.T(ax, 1450, y + 55, note, 22, GREY)
save(fig, 8)

# 9 proof beyond one case ------------------------------------------------------------------------------------
fig, ax = slide("Measured, not claimed", "proof")
bars = [("Harder questions, 3 full-size Stoa sheets", 24 / 25 * 100, "24 / 25"),
        ("Dataset plans, exact counts (n = 400)", 81.5, "81.5%"),
        ("Swiss dwellings, counts (n = 206)", 91.3, "91.3%")]
for k, (lab, v, s) in enumerate(bars):
    y = 320 + k * 190
    dk.T(ax, 116, y - 45, lab, 28, INK, bold=True)
    ax.add_patch(Rectangle((116, y), 1300, 50, color=PANEL, zorder=1))
    ax.add_patch(Rectangle((116, y), 13 * v, 50, color=BLUE, zorder=2))
    dk.T(ax, 1450, y + 25, s, 40, INK, bold=True)
dk.T(ax, 116, 930, "Scale read from the sheet itself: within 2% on all three Stoa sheets.", 28, ORANGE, bold=True)
tag(ax, "docs/stress-report-r9.md · evalkit gate, 2026-11-15")
save(fig, 9)

# 10 from drawing to shopping list ----------------------------------------------------------------------------
fig, ax = slide("From drawing to what to buy", "build plan")
tiles = [("Pipework", "2,023 m", "routing estimate"), ("Cable", "418 m", "HD 60364 circuits"),
         ("Supply load", "148 LU", "EN 806-3"), ("Waste flow", "8.0 l/s", "EN 12056-2")]
for k, (lab, big, sub) in enumerate(tiles):
    x = 110 + k * 440
    dk.panel(ax, x, 280, 400, 330, TINT)
    dk.T(ax, x + 36, 350, lab, 28, GREY, bold=True)
    dk.T(ax, x + 36, 450, big, 62, BLUE, bold=True)
    dk.T(ax, x + 36, 540, sub, 24, GREY)
dk.T(ax, 110, 720, "Plus concrete, walls, doors and hinges, fixtures, and floor finishes room by room.", 30, INK, bold=True)
dk.T(ax, 110, 790, "No plumbing sheet in the set? Estimated by European rules, and labelled as estimates.", 28, ORANGE)
tag(ax, "A-2 dormitory, estimates")
save(fig, 10)

# 11 low inference cost --------------------------------------------------------------------------------------
fig, ax = slide("Most answers cost nothing", "low inference cost")
dk.T(ax, 116, 430, "$0.0000", 190, BLUE, bold=True)
dk.T(ax, 124, 580, "0 tokens: geometry and code answer most questions", 32, INK, bold=True)
dk.panel(ax, 1240, 280, 570, 400, PANEL)
dk.T(ax, 1280, 360, "DEEP READ, 67-MEGAPIXEL SHEET", 20, GREY, bold=True)
dk.T(ax, 1280, 470, "about $0.10", 60, ORANGE, bold=True)
dk.T(ax, 1280, 570, "paid once per drawing;\nre-reads are free", 26, GREY)
save(fig, 11)

# 12 why it lasts --------------------------------------------------------------------------------------------
fig, ax = slide("Why next year's models won't replace it", "why it lasts")
dk.panel(ax, 110, 300, 820, 420, PANEL)
dk.T(ax, 160, 400, "Models name things", 46, INK, bold=True)
dk.T(ax, 160, 500, "what a symbol is,\nwhat a question means", 30, GREY)
dk.panel(ax, 990, 300, 820, 420, TINT)
dk.T(ax, 1040, 400, "Code measures", 46, BLUE, bold=True)
dk.T(ax, 1040, 500, "scale, counts, areas, lengths,\nwith a box for every number", 30, GREY)
dk.T(ax, 110, 840, "A better model makes Plumb better. It doesn't replace it.", 34, ORANGE, bold=True)
save(fig, 12)

# 13 thank you -----------------------------------------------------------------------------------------------
fig, ax = dk.canvas(W, H)
dk.T(ax, 110, 420, "Can a drawing answer, and show where?", 54, INK, bold=True)
dk.T(ax, 110, 540, "Yes. Every number, boxed on the drawing.", 54, BLUE, bold=True)
dk.T(ax, 116, 680, "Plumb  ·  Abhinav Chutani  ·  Junction 2026", 28, GREY)
save(fig, 13)

dk.contact_sheet(sorted(OUT.glob("slide*.png")), OUT / "contact_sheet.png")
print("wrote", len(list(OUT.glob("slide*.png"))), "slides to", OUT)
