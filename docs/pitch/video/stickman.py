"""Stickman presenter poses from the hand-drawn head in docs/pitch/stickman.png.
Keeps the drawn head (hair, face, eyes), redraws body/arms per pose with the same 14 px marker stroke, and makes
an open and a closed mouth for each pose. Output: docs/pitch/video/poses/<pose>_<m>.png (RGBA, 416x882)."""
import pathlib
import numpy as np
import cv2
from scipy import ndimage as ndi

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / "stickman.png"
OUT = HERE / "poses"
SS = 4          # supersampling for smooth strokes
STROKE = 14
INK = (24, 22, 22)


def head_layer():
    im = cv2.imread(str(SRC))
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    dark = g < 110
    lab, _ = ndi.label(dark)
    mouth = lab == lab[357, 190]
    # face interior: the light region around the nose point, holes (eyes, mouth) filled
    light, _ = ndi.label(~ndi.binary_dilation(dark, iterations=2))   # close small gaps in the outline
    face = ndi.binary_dilation(ndi.binary_fill_holes(light == light[320, 200]), iterations=2)
    main = lab == lab[150, 200]
    hair = ndi.binary_fill_holes(main & (np.arange(g.shape[0])[:, None] < 268)) & ~face
    band = ndi.binary_dilation(face, iterations=9)
    keep = face | hair | (band & dark)
    keep[445:] = False   # body is redrawn
    rgba = np.dstack([im, np.where(keep, 255, 0).astype(np.uint8)])
    rgba[ndi.binary_dilation(mouth, iterations=3) & face] = (255, 255, 255, 255)          # erase drawn mouth; drawn per frame
    ys, xs = np.where(face)
    return rgba, int(ys.max())


def stroke(canvas, pts, w=STROKE, jitter=0, seed=0):
    rng = np.random.default_rng(seed)
    pts = np.asarray(pts, float)
    # resample into a gentle hand-drawn polyline
    dense = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(2, int(np.hypot(*(b - a)) / 12))
        for t in np.linspace(0, 1, n, endpoint=False):
            dense.append(a + (b - a) * t)
    dense.append(pts[-1])
    dense = np.array(dense)
    if jitter:
        dense[1:-1] += rng.normal(0, jitter, dense[1:-1].shape)
        dense = cv2.GaussianBlur(dense.reshape(-1, 1, 2), (1, 5), 0).reshape(-1, 2) if len(dense) > 5 else dense
    p = (dense * SS).astype(np.int32)
    cv2.polylines(canvas, [p], False, INK + (255,), w * SS, cv2.LINE_AA)
    for q in (p[0], p[-1]):
        cv2.circle(canvas, tuple(int(v) for v in q), w * SS // 2, INK + (255,), -1, cv2.LINE_AA)


NECK, HIP = (206, 440), (210, 760)
SH = (206, 482)   # where both arms leave the body
FEET = [(HIP, (172, 812), (128, 864)), (HIP, (255, 812), (300, 860))]

POSES = {   # arm = shoulder -> elbow -> hand (left side of picture first)
    "idle":       [((206, 482), (128, 476), (82, 410)), ((206, 482), (282, 472), (330, 398))],
    "point":      [((206, 482), (110, 450), (8, 420)), ((206, 482), (262, 560), (276, 640))],
    "point_up":   [((206, 482), (120, 410), (30, 320)), ((206, 482), (262, 560), (276, 640))],
    "point_down": [((206, 482), (118, 520), (36, 590)), ((206, 482), (282, 472), (330, 398))],
    "hands_up":   [((206, 482), (96, 440), (40, 320)), ((206, 482), (316, 440), (372, 320))],
    "shrug":      [((206, 482), (140, 548), (70, 500)), ((206, 482), (272, 548), (342, 500))],
    "think":      [((206, 482), (150, 560), (176, 420)), ((206, 482), (262, 560), (276, 640))],
    "one_up":     [((206, 482), (150, 560), (140, 640)), ((206, 482), (318, 450), (366, 330))],
    "down":       [((206, 482), (160, 560), (146, 646)), ((206, 482), (252, 560), (266, 646))],
}
FINGER = {"point": ((8, 420), (-18, 412)), "point_up": ((30, 320), (12, 296)), "point_down": ((36, 590), (16, 612)),
          "one_up": ((366, 330), (376, 300))}


def render(pose, mouth_open, seed=7):
    head, chin = head_layer()
    H, W = head.shape[:2]
    pad = 70  # room for a pointing hand to the left
    big = np.zeros(((H) * SS, (W + pad) * SS, 4), np.uint8)
    off = np.array([pad, 0])
    s = seed + hash(pose) % 1000
    stroke(big, [np.add(NECK, off), np.add(HIP, off)], jitter=1.2, seed=s)
    for leg in FEET:
        stroke(big, [np.add(p, off) for p in leg], jitter=1.2, seed=s + 1)
    for k, arm in enumerate(POSES[pose]):
        stroke(big, [np.add(p, off) for p in arm], jitter=1.5, seed=s + 2 + k)
    if pose in FINGER:
        a, b = FINGER[pose]
        stroke(big, [np.add(a, off), np.add(b, off)], w=10, seed=s + 9)
    small = cv2.resize(big, (W + pad, H), interpolation=cv2.INTER_AREA)
    out = np.zeros_like(small)
    out[:, pad:][head[..., 3] > 0] = head[head[..., 3] > 0]
    # body under head: composite strokes where head is transparent
    a = small[..., 3:4] / 255.0
    base = out.astype(float)
    m = (out[..., 3] == 0)[..., None]
    comp = np.where(m, small, base)
    comp = comp.astype(np.uint8)
    # mouth
    mx, my = 190 + pad, 357
    if mouth_open:
        cv2.ellipse(comp, (mx, my + 2), (17, 11), 0, 0, 360, INK + (255,), -1, cv2.LINE_AA)
        cv2.ellipse(comp, (mx, my + 7), (9, 4), 0, 0, 360, (90, 80, 200, 255), -1, cv2.LINE_AA)
    else:
        cv2.line(comp, (mx - 22, my), (mx + 18, my - 1), INK + (255,), 7, cv2.LINE_AA)
    return comp


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    tiles = []
    for p in POSES:
        for m in (0, 1):
            img = render(p, m)
            cv2.imwrite(str(OUT / f"{p}_{m}.png"), img)
            if m == 0:
                bg = np.full(img.shape[:2] + (3,), 245, np.uint8)
                a = img[..., 3:4] / 255.0
                tiles.append((bg * (1 - a) + img[..., :3] * a).astype(np.uint8))
    sheet = np.hstack([cv2.resize(t, (t.shape[1] // 2, t.shape[0] // 2)) for t in tiles])
    cv2.imwrite(str(HERE / "poses_sheet.png"), sheet)
    print("wrote", len(POSES) * 2, "poses")
