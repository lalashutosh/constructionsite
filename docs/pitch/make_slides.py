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
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
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
DORM_PNG = str(ROOT / f"cache/uploads/{DORM}.png")
PIPE_PNG = str(ROOT / f"cache/uploads/{PIPE}.png")
SMALL = str(pathlib.Path.home() / "Downloads/junction-dataset-preview/data/cubicasa5k/colorful-2002.png")
plan = json.load(open(ROOT / "docs/pitch/dorm_plan.json"))
CHATBOT = ROOT / "docs/pitch/chatbot.png"


def fit(rgb, w, h):
    """Scale an RGB image to fit w x h (keeps aspect). Returns (img, w2, h2)."""
    s_ = min(w / rgb.shape[1], h / rgb.shape[0])
    return cv2.resize(rgb, (int(rgb.shape[1] * s_), int(rgb.shape[0] * s_)), interpolation=cv2.INTER_AREA), \
        int(rgb.shape[1] * s_), int(rgb.shape[0] * s_)


def full(path):
    return cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)


def boxes_of(kinds):
    return [e["polygon"] for e in dorm["elements"] if e["kind"] in kinds]


# 1 title -----------------------------------------------------------------------------------------------------
fig, ax = dk.canvas(W, H)
dk.T(ax, 110, 430, "Plumb", 150, INK, bold=True)
dk.T(ax, 116, 560, "Blueprints that show their work", 46, BLUE, bold=True)
dk.T(ax, 116, 660, "Junction 2026  ·  Stoa: Make Blueprints Talk  ·  Abhinav Chutani", 26, GREY)
save(fig, 1)

# 2 hook: 6 doors vs a 10,200 px sheet -----------------------------------------------------------------------
fig, ax = slide("Six doors is easy. This isn't.", "the problem")
from engine.api import get_engine  # noqa: E402
small_doors = [e.polygon for e in get_engine("pipeline").analyze(SMALL).elements if e.kind == "door"]
im, w2, h2 = fit(crop(SMALL, (0, 0, cv2.imread(SMALL).shape[1], cv2.imread(SMALL).shape[0]), small_doors, BLUE, 3), 560, 600)
img(ax, im, 110, 260, w2, h2)
dk.T(ax, 110, 260 + h2 + 50, f"{len(small_doors)} doors: count them in ten seconds", 26, INK, bold=True)
im, w2, h2 = fit(full(DORM_PNG), 1000, 640)
img(ax, im, 810, 250, w2, h2)
dk.T(ax, 810, 250 + h2 + 40, "Air Force dormitory, 10,200 × 6,600 px", 26, INK, bold=True)
tag(ax, "real sheets: CubiCasa5k colorful-2002 · Stoa dataset A-2")
save(fig, 2)

# 3 chatbot vs Plumb -----------------------------------------------------------------------------------------
fig, ax = slide("A guess you can't check, or a receipt", "general AI vs Plumb")
dk.panel(ax, 110, 230, 820, 720, PANEL)
dk.T(ax, 150, 290, "GENERAL AI CHATBOT", 22, GREY, bold=True)
if CHATBOT.exists():
    im, w2, h2 = fit(full(str(CHATBOT)), 740, 300)
    img(ax, im, 150, 340, w2, h2)
    dk.T(ax, 150, 760, "104 doors", 60, ORANGE, bold=True)
    dk.T(ax, 150, 830, "after 1 min 10 s of thinking", 26, GREY)
else:
    dk.T(ax, 520, 600, "[ your ChatGPT screenshot:\n docs/pitch/chatbot.png ]", 30, ORANGE, bold=True, ha="center")
dk.T(ax, 150, 920, "one number, nothing to check", 26, INK, bold=True)
dk.panel(ax, 990, 230, 820, 720, TINT)
dk.T(ax, 1030, 290, "PLUMB", 22, BLUE, bold=True)
# the app's own count tiles (a whole-sheet view, no close-up of individual door boxes)
tiles = full(str(ROOT / "docs/pitch/video/cap/doors/f000.png"))[958:1395, 2340:3134]
im, w2, h2 = fit(tiles, 740, 300)
img(ax, im, 1030, 340, w2, h2)
dk.T(ax, 1030, 760, f"{tot['door']['count']} doors", 60, BLUE, bold=True)
dk.T(ax, 1030, 830, "each one listed per wing", 26, GREY)
dk.T(ax, 1030, 920, "every one boxed on the drawing", 26, INK, bold=True)
save(fig, 3)

# 4 how it works ---------------------------------------------------------------------------------------------
fig, ax = slide("Read the sheet. Count by code. Show the receipt.", "how it works")
steps = [("1  Read", "scale, outline, printed text,\nfrom the drawing itself"),
         ("2  Count by code", "every repeated symbol,\ncounted two ways"),
         ("3  Show the receipt", "every number boxed,\ntagged: measured, printed\nor estimated")]
for k, (h_, c_) in enumerate(steps):
    x = 110 + k * 600
    dk.panel(ax, x, 280, 520, 440, TINT if k == 2 else PANEL)
    dk.T(ax, x + 40, 360, h_, 38, BLUE if k == 2 else INK, bold=True)
    dk.T(ax, x + 40, 500, c_, 28, GREY)
    if k < 2:
        dk.arrow(ax, x + 530, 500, x + 590, 500, ORANGE)
dk.T(ax, 110, 850, "An AI model only names what each symbol is. It never produces a number.", 32, ORANGE, bold=True)
save(fig, 4)

# 5 ask anything, see why ------------------------------------------------------------------------------------
fig, ax = slide("Ask anything. See why.", "reasoning a human can verify")
dk.panel(ax, 110, 230, 1700, 120, PANEL)
dk.T(ax, 150, 290, "Are there more doors or toilets and sinks?", 34, INK, bold=True)
dk.T(ax, 1770, 290, "Doors 139 vs 96 (48 + 48)", 34, BLUE, bold=True, ha="right")
both = crop(DORM_PNG, (2100, 4750, 3300, 5480), [], BLUE, 6)
tsk = [ (np.array(b, np.float32) - [2100, 4750]).astype(np.int32) for b in boxes_of(("toilet", "sink"))]
bgr = cv2.cvtColor(both, cv2.COLOR_RGB2BGR)
for p_ in tsk:
    cv2.polylines(bgr, [p_], True, (26, 122, 255), 6)
im, w2, h2 = fit(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), 1000, 560)
img(ax, im, 110, 390, w2, h2)
dk.T(ax, 110, 390 + h2 + 40, "orange: toilets and sinks · each one a box you can click", 24, GREY)
dk.T(ax, 1180, 420, "SAME QUESTION, ANY LANGUAGE", 20, GREY, bold=True)
for k, (q, a) in enumerate([("How many bedrooms?", "2"), ("Montako makuuhuonetta?", "2"), ("Wie viele Schlafzimmer?", "2"),
                            ("¿Cuántos dormitorios hay?", "2"), ("Mitu magamistuba on?", "2")]):
    dk.T(ax, 1180, 490 + k * 72, q, 28, INK)
    dk.T(ax, 1780, 490 + k * 72, a, 32, BLUE, bold=True, ha="right")
dk.T(ax, 1180, 880, "$0.0000 each", 28, ORANGE, bold=True)
save(fig, 5)

# 6 the scale ------------------------------------------------------------------------------------------------
fig, ax = slide("The scale, read from the sheet. Or from one length.", "creativity")
from engine.scale import sheet_scale as S2  # noqa: E402
from engine import cache as C2  # noqa: E402
st = S2.sheet_state(DORM_PNG, C2.sha256_file(DORM_PNG))
sb = [b for c in st["cons"]["winner"]["items"] for b in c["boxes"]]
quads = [[[b[0] - 20, b[1] - 20], [b[2] + 20, b[1] - 20], [b[2] + 20, b[3] + 20], [b[0] - 20, b[3] + 20]] for b in sb]
im, w2, h2 = fit(crop(DORM_PNG, (7400, 5850, 8800, 6400), quads, ORANGE, 6), 900, 400)
img(ax, im, 110, 260, w2, h2)
dk.T(ax, 110, 260 + h2 + 50, "Note, scale bar and dimensions agree: 49.2 px per metre.\nA half-size print caught: the note alone would be 2× wrong.", 26, INK)
dk.panel(ax, 1110, 250, 700, 640, TINT)
dk.T(ax, 1150, 320, "NO SCALE ON THE DRAWING?", 20, GREY, bold=True)
dk.T(ax, 1150, 410, "Measure one door.", 46, BLUE, bold=True)
dk.T(ax, 1150, 560, "Click its two ends, type 0.9 m:\nevery room, wall and area on\nthe sheet follows.", 30, INK)
dk.T(ax, 1150, 760, "One known length → all dimensions", 28, ORANGE, bold=True)
save(fig, 6)

# 7 the deep read --------------------------------------------------------------------------------------------
fig, ax = slide("Every bed, chair and staircase, found and counted", "creativity · the deep read")
cards = [tot[k] for k in ("door", "chair", "sink", "toilet", "bed", "staircase") if k in tot]
for k, t in enumerate(cards):
    x, y = 110 + (k % 3) * 580, 260 + (k // 3) * 330
    dk.panel(ax, x, y, 540, 290, PANEL)
    if t.get("thumb"):
        img(ax, thumb(t["thumb"]), x + 30, y + 45, 200, 200)
    dk.T(ax, x + 260, y + 110, t["label"], 34, INK, bold=True)
    dk.T(ax, x + 260, y + 200, str(t["count"]), 70, BLUE, bold=True)
dk.T(ax, 110, 960, "Code finds every repeated symbol; a model names each kind once. Click a count: every copy lights up in 3D.", 26, GREY)
save(fig, 7)

# 8 building: build plan + service runs ----------------------------------------------------------------------
fig, ax = slide("From drawing to what to buy", "creativity · the build plan")
sm = plan.get("services_map") or {}
g0 = cv2.imread(DORM_PNG, cv2.IMREAD_GRAYSCALE)
ol = np.array(sm.get("outline") or [[0, 0]], np.float32)
x0, y0 = ol.min(0).astype(int) - 60
x1, y1 = ol.max(0).astype(int) + 60
bg = cv2.cvtColor(255 - ((255 - g0[y0:y1, x0:x1]) // 4), cv2.COLOR_GRAY2BGR)
for lines_, col in ((sm.get("piping", []), (235, 130, 59)), (sm.get("electrical", []), (11, 158, 245))):
    for l in lines_:
        cv2.polylines(bg, [(np.array(l, np.float32) - [x0, y0]).astype(np.int32)], False, col, 14)
im, w2, h2 = fit(cv2.cvtColor(bg, cv2.COLOR_BGR2RGB), 820, 700)
img(ax, im, 110, 240, w2, h2)
dk.T(ax, 110, 240 + h2 + 36, "blue: pipe runs · amber: circuits (estimated, European rules)", 22, GREY)
q = {c["item"]: c for c in plan["checklist"]}
rows = [("Foundation concrete", q.get("Foundation concrete")), ("Hinges", q.get("Hinges")),
        ("Light fittings (EN 12464-1)", q.get("Light fittings")),
        ("Pipework", q.get("Pipework (supply + waste runs)")), ("Cable", q.get("Cable (lighting + power circuits)"))]
for k, (lab, c_) in enumerate(rows):
    if not c_:
        continue
    y = 290 + k * 128
    dk.panel(ax, 1010, y - 50, 800, 105, TINT if lab in ("Pipework", "Cable") else PANEL)
    dk.T(ax, 1045, y, lab, 28, INK, bold=True)
    v = c_["qty"]
    dk.T(ax, 1780, y, f"{v:,.0f} {c_['unit']}" if isinstance(v, (int, float)) else str(v), 36, BLUE, bold=True, ha="right")
dk.T(ax, 1010, 950, "Plus walls, doors, fixtures, finishes.\nEstimates are labelled.", 24, GREY)
save(fig, 8)

# 9 accuracy: honest on hard sheets --------------------------------------------------------------------------
fig, ax = slide("Hard sheets, honest answers", "accuracy · M-101A piping + S-100F foundation")
tagb = [e["polygon"] for e in pipe["elements"] if e["kind"].startswith("tag ")]
img(ax, crop(PIPE_PNG, (2500, 1600, 6400, 4200), tagb, BLUE, 6), 110, 230, 1020, 680)
dk.panel(ax, 1210, 230, 600, 680, PANEL)
for k, (lab, big, note, col) in enumerate([("VALVES", "12", "every tag listed", BLUE),
                                           ("CHECK VALVES", "5", 'prints "TYP. OF 5";\n4 tags legible: says so', ORANGE),
                                           ("TRENCH LENGTH", "4275", "quoted from the note\n(foundation sheet)", GREY)]):
    y = 300 + k * 205
    dk.T(ax, 1250, y, lab, 20, GREY, bold=True)
    dk.T(ax, 1250, y + 60, big, 50, col, bold=True)
    dk.T(ax, 1450, y + 55, note, 22, GREY)
save(fig, 9)

# 10 accuracy: measured ---------------------------------------------------------------------------------------
fig, ax = slide("Measured, not claimed", "accuracy")
bars = [("Harder questions, 3 full-size Stoa sheets", 24 / 25 * 100, "24 / 25"),
        ("Dataset plans, exact counts (n = 400)", 81.5, "81.5%"),
        ("Swiss dwellings, counts (n = 206)", 91.3, "91.3%")]
for k, (lab, v, s_) in enumerate(bars):
    y = 320 + k * 190
    dk.T(ax, 116, y - 45, lab, 28, INK, bold=True)
    ax.add_patch(Rectangle((116, y), 1300, 50, color=PANEL, zorder=1))
    ax.add_patch(Rectangle((116, y), 13 * v, 50, color=BLUE, zorder=2))
    dk.T(ax, 1450, y + 25, s_, 40, INK, bold=True)
dk.T(ax, 116, 930, "Scale read from the sheet itself: within 2% on all three Stoa sheets.", 28, ORANGE, bold=True)
tag(ax, "docs/stress-report-r9.md · evalkit gate, 2026-11-15")
save(fig, 10)

# 11 low inference cost --------------------------------------------------------------------------------------
fig, ax = slide("Computer vision and formulas, on a laptop", "low inference cost")
dk.panel(ax, 110, 250, 1100, 560, TINT)
dk.T(ax, 150, 320, "RUNS LOCALLY, NO MODEL CALLS", 20, GREY, bold=True)
for k, s_ in enumerate(["Scale from notes, bars and dimension lines", "Symbols found and counted by computer vision",
                        "Areas, lengths, perimeters: geometry", "Pipe, cable, lights: fixed engineering formulas",
                        "Every answer boxed and tagged"]):
    dk.tick(ax, 165, 400 + k * 80, 20, BLUE)
    dk.T(ax, 205, 400 + k * 80, s_, 30, INK, bold=True)
dk.panel(ax, 1260, 250, 550, 260, PANEL)
dk.T(ax, 1300, 320, "AN LLM, ONLY TO NAME THINGS", 20, GREY, bold=True)
dk.T(ax, 1300, 400, "'this symbol is a bed'", 28, INK)
dk.T(ax, 1300, 460, "once per symbol type", 24, GREY)
dk.T(ax, 1270, 620, "$0.0000", 80, BLUE, bold=True)
dk.T(ax, 1275, 700, "most answers: 0 tokens", 26, INK, bold=True)
dk.T(ax, 1275, 770, "whole sheet: about $0.10, once", 26, ORANGE, bold=True)
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

# 13 close ---------------------------------------------------------------------------------------------------
fig, ax = dk.canvas(W, H)
dk.T(ax, 110, 420, "Ask a drawing anything.", 60, INK, bold=True)
dk.T(ax, 110, 540, "Get the answer, and see where it came from.", 54, BLUE, bold=True)
dk.T(ax, 116, 680, "Plumb  ·  blueprints that show their work  ·  Junction 2026", 28, GREY)
save(fig, 13)

dk.contact_sheet(sorted(OUT.glob("slide*.png")), OUT / "contact_sheet.png")
print("wrote", len(list(OUT.glob("slide*.png"))), "slides to", OUT)
