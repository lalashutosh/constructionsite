"""Builds the pitch video: real app captures (cap/<scene>/ from capture.mjs) in a window with smooth 60 fps camera
moves and a synthetic cursor, the stickman presenter beside it (instant pose swaps, mouth driven by the voice),
captions and the judging criterion on screen.

  .venv/bin/python docs/pitch/video/build_video.py            # uses docs/pitch/video/voice.* if present, else a draft TTS
Output: docs/pitch/video/Plumb_pitch.mp4 (1920x1080, 60 fps). Hard limit 2:00 is checked."""
import json
import pathlib
import random
import re
import subprocess
import sys
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CAP = HERE / "cap"
POSES = HERE / "poses"
SLIDES = ROOT / "docs/pitch/slides"
OUT = HERE / "Plumb_pitch.mp4"
FONT = str(pathlib.Path.home() / ".claude/skills/story-pitch-deck/fonts/Figtree-Bold.ttf")
FPS, W, H = 60, 1920, 1080
WX, WY, WW, WH = 36, 84, 1440, 810          # app window on the frame
SW, SH = 3200, 1800                         # every source normalised to this (CSS 1600x900 at 2x)
PAPER = (244, 241, 234)
INK = (24, 22, 22)
TEAL = (15, 118, 110)
random.seed(7)

# ------------------------------------------------------------------------------------------------ the voiceover
PARAS = [p.strip().replace("\n", " ") for p in (ROOT / "docs/pitch/VOICEOVER.md").read_text().split("---", 1)[1].split("\n\n") if p.strip()]
assert len(PARAS) == 17, len(PARAS)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def voice():
    """(wav path, [(start, end)] per paragraph)."""
    work = HERE / "work"
    work.mkdir(exist_ok=True)
    mine = [p for p in HERE.glob("voice.*") if p.suffix.lower() in (".m4a", ".wav", ".mp3", ".aac", ".mov", ".mp4")]
    wav = work / "voice.wav"
    if mine:
        raw = work / "voice_raw.wav"
        run(["ffmpeg", "-y", "-i", str(mine[0]), "-af", "highpass=f=70,loudnorm=I=-16:TP=-1.5", "-ac", "1", "-ar", "48000", str(raw)])
        spans = split_by_pauses(raw)
        # tighten the pauses between paragraphs to 0.45 s (nothing inside a paragraph is cut)
        x, sr = load_pcm(raw)
        pad, gap = 0.12, 0.45
        out, new, t = [np.zeros(int(0.25 * sr), np.float32)], [], 0.25
        for s, e in spans:
            a, b = max(0, int((s - pad) * sr)), min(len(x), int((e + pad) * sr))
            new.append((t + pad, t + (b - a) / sr - pad))
            out += [x[a:b], np.zeros(int(gap * sr), np.float32)]
            t += (b - a) / sr + gap
        y = (np.clip(np.concatenate(out), -1, 1) * 32767).astype(np.int16)
        with wave.open(str(wav), "w") as f:
            f.setnchannels(1), f.setsampwidth(2), f.setframerate(sr), f.writeframes(y.tobytes())
        return wav, new
    # draft: macOS TTS, one file per paragraph, 0.45 s gaps
    parts, spans, t = [], [], 0.25
    for i, p in enumerate(PARAS):
        a = work / f"p{i:02d}.aiff"
        run(["say", "-v", "Daniel", "-r", "182", "-o", str(a), p])
        w = work / f"p{i:02d}.wav"
        run(["ffmpeg", "-y", "-i", str(a), "-ac", "1", "-ar", "48000", str(w)])
        with wave.open(str(w)) as f:
            d = f.getnframes() / f.getframerate()
        spans.append((t, t + d))
        parts.append((t, w))
        t += d + 0.45
    total = t + 0.6
    pcm = np.zeros(int(total * 48000), np.int16)
    for s, w in parts:
        with wave.open(str(w)) as f:
            x = np.frombuffer(f.readframes(f.getnframes()), np.int16)
        i = int(s * 48000)
        pcm[i:i + len(x)] = x[: len(pcm) - i]
    with wave.open(str(wav), "w") as f:
        f.setnchannels(1), f.setsampwidth(2), f.setframerate(48000), f.writeframes(pcm.tobytes())
    return wav, spans


def load_pcm(wav):
    with wave.open(str(wav)) as f:
        return np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768, f.getframerate()


def split_by_pauses(wav):
    """Paragraph spans from the pauses in a real recording: the 16 longest pauses split it into 17 paragraphs."""
    x, sr = load_pcm(wav)
    hop = sr // 100
    rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, "same")[::hop])
    thr = max(0.012, np.percentile(rms, 30) * 1.8)
    talk = rms > thr
    idx = np.where(talk)[0]
    start, end = idx[0] / 100, idx[-1] / 100
    gaps, i = [], idx[0]
    while i < idx[-1]:
        if not talk[i]:
            j = i
            while j < len(talk) and not talk[j]:
                j += 1
            gaps.append((j - i, i / 100, j / 100))
            i = j
        else:
            i += 1
    words = [len(p.split()) for p in PARAS]
    if len(gaps) < 16:   # fall back to word-count proportions
        tot, acc, spans = sum(words), start, []
        for n in words:
            d = (end - start) * n / tot
            spans.append((acc, acc + d))
            acc += d
        return spans
    cut = sorted(sorted(gaps, reverse=True)[:16], key=lambda g: g[1])
    edges = [start] + [c for g in cut for c in (g[1], g[2])] + [end]
    return [(edges[2 * k], edges[2 * k + 1]) for k in range(17)]


# ------------------------------------------------------------------------------------------------ sources
_img_cache = {}


def src(key):
    """Normalised 3200x1800 RGB image for a capture frame 'scene/fNNN.png', a slide 'slide10', or 'chatbot'."""
    if key in _img_cache:
        return _img_cache[key]
    if key.startswith("slide"):
        im = cv2.cvtColor(cv2.imread(str(SLIDES / f"{key}.png")), cv2.COLOR_BGR2RGB)
        im = cv2.resize(im, (SW, SH), interpolation=cv2.INTER_CUBIC)
    elif key == "chatbot":
        c = cv2.cvtColor(cv2.imread(str(ROOT / "docs/pitch/chatbot.png")), cv2.COLOR_BGR2RGB)
        im = np.full((SH, SW, 3), c[5, 5], np.uint8)
        s = 2900 / c.shape[1]
        c = cv2.resize(c, (2900, int(c.shape[0] * s)), interpolation=cv2.INTER_CUBIC)
        y0 = (SH - c.shape[0]) // 2
        im[y0:y0 + c.shape[0], 150:150 + c.shape[1]] = c
    else:
        im = cv2.cvtColor(cv2.imread(str(CAP / key)), cv2.COLOR_BGR2RGB)
        if im.shape[:2] != (SH, SW):
            im = cv2.resize(im, (SW, SH), interpolation=cv2.INTER_AREA)
    pyr = [im]
    for _ in range(3):
        pyr.append(cv2.resize(pyr[-1], (pyr[-1].shape[1] // 2 + pyr[-1].shape[1] // 4, pyr[-1].shape[0] // 2 + pyr[-1].shape[0] // 4), interpolation=cv2.INTER_AREA))
    if len(_img_cache) > 40:
        _img_cache.pop(next(iter(_img_cache)))
    _img_cache[key] = pyr
    return pyr


def view(pyr, cam):
    """Render the camera box (CSS px: x, y, w; h = w*9/16) of a source into the window size."""
    x, y, w = cam
    h = w * 9 / 16
    scale_css = WW / w                       # output px per CSS px
    s0 = scale_css / 2                       # output px per source px at level 0
    lvl, f = 0, 1.0
    while lvl + 1 < len(pyr) and s0 / (f * 0.75) <= 1.0:
        lvl, f = lvl + 1, f * 0.75
    im = pyr[lvl]
    k = s0 / f                               # output px per level px
    sx, sy = 2 * x * f, 2 * y * f
    M = np.float32([[k, 0, -sx * k], [0, k, -sy * k]])
    return cv2.warpAffine(im, M, (WW, WH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(16, 20, 27))


def fit_box(r, pad=1.25, minw=360):
    """Camera (x, y, w) showing rect r = (x, y, w, h) with padding, 16:9, inside the 1600x900 page."""
    x, y, w, h = r
    cx, cy = x + w / 2, y + h / 2
    cw = max(w * pad, h * pad * 16 / 9, minw)
    cw = min(cw, 1600)
    ch = cw * 9 / 16
    return (min(max(cx - cw / 2, 0), 1600 - cw), min(max(cy - ch / 2, 0), 900 - ch), cw)


FULL = (0, 0, 1600)
meta_cache = {}


def meta(scene):
    if scene not in meta_cache:
        m = json.loads((CAP / scene / "meta.json").read_text())
        seen = {}
        for e in m:      # 'answer', 'answer#1', ...
            n = seen.get(e["tag"], 0)
            seen[e["tag"]] = n + 1
            e["key"] = e["tag"] if n == 0 else f"{e['tag']}#{n}"
        meta_cache[scene] = m
    return meta_cache[scene]


def idx(scene, key):
    for i, e in enumerate(meta(scene)):
        if e["key"] == key:
            return i
    raise KeyError(f"{scene}: {key} not in {[e['key'] for e in meta(scene)]}")


def cam_of(spec, scene=None, frame=None):
    if spec == "full":
        return FULL
    if isinstance(spec, tuple) and spec[0] == "rect":
        _, name, pad = spec[:3]
        r = meta(scene)[frame]["rects"].get(name)
        if not r:
            return FULL
        if len(spec) > 3:          # sub-rect: fractions of the element (fx, fy, fw, fh)
            fx, fy, fw, fh = spec[3]
            r = (r[0] + r[2] * fx, r[1] + r[3] * fy, r[2] * fw, r[3] * fh)
        return fit_box(r, pad)
    if isinstance(spec, tuple) and spec[0] == "cursor":
        c = meta(scene)[frame]["cursor"]
        return fit_box((c["x"] - 1, c["y"] - 1, 2, 2), 1, spec[1])
    if isinstance(spec, tuple) and spec[0] == "box":
        return fit_box(spec[1:], 1.0, 100)
    return FULL


# ------------------------------------------------------------------------------------------------ the edit
def seq(scene, a, b, cam_a="full", cam_b=None, w=1.0, ref=None):
    """Play capture frames a..b (keys); camera eases from cam_a to cam_b (specs resolved on frame 'ref' or the last)."""
    return dict(scene=scene, a=a, b=b, cam_a=cam_a, cam_b=cam_b or cam_a, w=w, ref=ref)


def still(key, cam_a="full", cam_b=None, w=1.0):
    return dict(image=key, cam_a=cam_a, cam_b=cam_b or cam_a, w=w)


ANS = ("rect", "answer", 1.15)
SHEET = ("rect", "sheet", 1.05)
CANVAS = ("rect", "canvas", 1.0)
SECTIONS = ["The problem"] * 4 + ["Reasoning you can check"] * 2 + ["Creativity"] * 5 + ["Accuracy"] * 2 + ["Low inference cost"] * 2 + ["Why it lasts"] * 2
BEATS = [
    [seq("small", "open", "answer", "full", ANS, 1.0), seq("small", "move:proof", "proof", ("rect", "sheet", 1.0, (0, 0, 1, 0.55)), w=0.7)],
    [seq("dorm_open", "top", "top", ("box", 330, 420, 280, 158), CANVAS, 1.2), seq("dorm_open", "3d", "3d", CANVAS, ("box", 300, 180, 700, 394), 0.8)],
    [still("chatbot", "full", ("box", 40, 420, 700, 394), 1.0)],
    [seq("doors", "top", "lit", CANVAS, CANVAS, 0.8), seq("doors", "lit", "lit", ("box", 1150, 470, 440, 248), ("box", 1150, 480, 300, 169), 1.0)],
    [seq("lang", "type", "answer", "full", ANS, 1.0), seq("lang", "answer", "answer#1", ANS, ANS, 0.9, ref="answer#1")],
    [seq("dorm_ask", "type#5", "answer#1", ("rect", "ask", 1.1), ANS, 1.0, ref="answer#1"), seq("dorm_ask", "move:proof#1", "proof_cmp", SHEET, ("rect", "sheet", 1.0, (0, 0, 1, 0.5)), 1.0)],
    [seq("scale", "badge", "badge", "full", ("rect", "badge", 1.3), 0.8), seq("scale", "move:where", "pins", ("rect", "badge", 1.3), CANVAS, 1.0, ref="pins")],
    [seq("measure", "before", "move:set", "full", "full", 0.6), seq("measure", "pt", "typed", ("cursor", 640), ("cursor", 520), 1.2, ref="pt"),
     seq("measure", "move:setsize", "payoff", ("rect", "measure", 1.2), CANVAS, 1.0, ref="payoff")],
    [seq("threed", "orbit", "orbit#69", CANVAS, CANVAS, 1.2), seq("threed", "move:Furniture", "layer:Electrical", CANVAS, CANVAS, 1.3)],
    [seq("threed", "move:Beds", "ck:Stair", "full", "full", 1.0)],
    [seq("plan", "move:plan", "end", "full", ("rect", "right", 1.02), 1.0)],
    [seq("pipe", "open", "answer", "full", ANS, 1.2), seq("pipe", "move:proof", "proof", SHEET, ("rect", "sheet", 1.0, (0, 0, 1, 0.5)), 0.9)],
    [still("slide10", "full", ("box", 60, 140, 1480, 832), 1.0)],
    [still("slide11", "full", ("box", 40, 100, 1520, 855), 1.0)],
    [seq("small", "answer", "answer", ("rect", "answer", 1.05, (0, 0.35, 0.7, 0.4)), w=0.5), seq("dorm_open", "top", "top", ("box", 60, 590, 440, 248), w=0.5)],
    [still("slide12", "full", ("box", 60, 100, 1480, 832), 1.0)],
    [still("slide13", "full", ("box", 40, 80, 1520, 855), 1.0)],
]
POSE_PLAN = [["point", "one_up", "shrug"], ["hands_up", "point", "think"], ["think", "shrug"], ["point", "hands_up"],
             ["one_up", "point"], ["think", "point", "one_up"], ["point_up", "point"], ["one_up", "point_down", "hands_up"],
             ["hands_up", "point"], ["point", "one_up"], ["point", "point_down", "idle"], ["think", "point", "shrug"],
             ["hands_up"], ["shrug", "point"], ["one_up", "point_down"], ["think", "one_up"], ["hands_up", "idle"]]
assert len(BEATS) == len(POSE_PLAN) == len(SECTIONS) == 17


def frame_weight(e):
    if e.get("frame"):
        return 0.35
    if e.get("hold"):
        return 4.0
    if e["tag"] == "type":
        return 0.5
    if e.get("click"):
        return 1.6
    return 1.0


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def timeline(spans, total):
    """Per-beat: (t0, t1, beat). Each paragraph's beats share its time (plus the pause after it)."""
    out = []
    for k, beats in enumerate(BEATS):
        t0 = spans[k][0] if k else 0.0
        t1 = spans[k + 1][0] if k + 1 < len(spans) else total
        ws = sum(b["w"] for b in beats)
        t = t0
        for b in beats:
            d = (t1 - t0) * b["w"] / ws
            out.append((t, t + d, k, b))
            t += d
    return out


def beat_state(b, u):
    """(source key, camera, cursor CSS (x, y) or None, click ripple 0..1 or None) at fraction u of beat b."""
    if "image" in b:
        return b["image"], lerp(cam_of(b["cam_a"]), cam_of(b["cam_b"]), ease(u)), None, None
    sc = b["scene"]
    i0, i1 = idx(sc, b["a"]), idx(sc, b["b"])
    fr = meta(sc)[i0:i1 + 1]
    ws = np.array([frame_weight(e) for e in fr])
    if len(fr) > 1:
        ws[-1] = max(ws[-1], 3.0)
    cum = np.concatenate([[0], np.cumsum(ws)]) / ws.sum()
    j = int(np.clip(np.searchsorted(cum, u, side="right") - 1, 0, len(fr) - 1))
    lu = (u - cum[j]) / max(cum[j + 1] - cum[j], 1e-6)
    ref = idx(sc, b["ref"]) if b.get("ref") else i1
    ca, cb = cam_of(b["cam_a"], sc, ref if b["cam_a"] != b["cam_b"] or b.get("ref") else i0 + j), cam_of(b["cam_b"], sc, ref)
    if b["cam_a"] == ("rect", "answer", 1.15) and b["cam_b"] == b["cam_a"]:
        ca = cb = cam_of(b["cam_a"], sc, ref)
    cam = lerp(ca, cb, ease(u))
    e = fr[j]
    prev = meta(sc)[i0 + j - 1]["cursor"] if i0 + j > 0 else e["cursor"]
    c0, c1 = (prev["x"], prev["y"]), (e["cursor"]["x"], e["cursor"]["y"])
    cur = lerp(c0, c1, ease(lu / 0.6)) if e.get("click") or e["tag"] in ("pt",) else c1
    click = (lu - 0.6) / 0.4 if e.get("click") and lu > 0.6 else None
    return f"{sc}/{e['f']}", cam, cur, click


# ------------------------------------------------------------------------------------------------ drawing
def rounded_mask(w, h, r):
    m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (r, 0), (w - r, h), 255, -1)
    cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
    for cx, cy in ((r, r), (w - r, r), (r, h - r), (w - r, h - r)):
        cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return m.astype(np.float32)[..., None] / 255


WMASK = rounded_mask(WW, WH, 18)


def base_frame():
    bg = np.full((H, W, 3), PAPER, np.float32)
    sh = np.zeros((H, W), np.float32)
    cv2.rectangle(sh, (WX + 6, WY + 16), (WX + WW - 6, WY + WH + 14), 1.0, -1)
    sh = cv2.GaussianBlur(sh, (0, 0), 18) * 0.28
    bg *= (1 - sh[..., None])
    return bg.astype(np.uint8)


BASE = base_frame()
F_CAP = ImageFont.truetype(FONT, 38)
F_SEC = ImageFont.truetype(FONT, 26)


def caption_chunks(text, n_words_max=16):
    words = text.split()
    chunks, cur = [], []
    for w_ in words:
        cur.append(w_)
        if len(cur) >= n_words_max or (len(cur) >= 7 and re.search(r"[.?!:;]$", w_)):
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def wrap(draw, text, font, maxw):
    lines, cur = [], ""
    for w_ in text.split():
        t = (cur + " " + w_).strip()
        if draw.textlength(t, font=font) > maxw and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = t
    return lines + [cur]


_text_cache = {}


def text_layer(section, caption):
    key = (section, caption)
    if key in _text_cache:
        return _text_cache[key]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    tw = d.textlength(section.upper(), font=F_SEC)
    d.rounded_rectangle((WX, 26, WX + tw + 40, 68), 21, fill=TEAL + (255,))
    d.text((WX + 20, 47), section.upper(), font=F_SEC, fill=(255, 255, 255, 255), anchor="lm")
    if caption:
        lines = wrap(d, caption, F_CAP, WW - 40)[:2]
        y = WY + WH + 30
        for ln in lines:
            d.text((WX + 8, y), ln, font=F_CAP, fill=INK + (255,))
            y += 50
    a = np.array(im)
    _text_cache[key] = (a[..., :3].astype(np.float32), a[..., 3:4].astype(np.float32) / 255)
    if len(_text_cache) > 60:
        _text_cache.pop(next(iter(_text_cache)))
    return _text_cache[key]


def load_poses():
    out = {}
    for p in POSES.glob("*.png"):
        a = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        s = 0.86
        a = cv2.resize(a, (int(a.shape[1] * s), int(a.shape[0] * s)), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(a[..., :3], cv2.COLOR_BGR2RGB).astype(np.float32)
        out[p.stem] = (rgb, a[..., 3:4].astype(np.float32) / 255)
    return out


POSE_IMG = load_poses()


def paste(dst, rgb, alpha, x, y):
    h, w = alpha.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    r = dst[y0:y1, x0:x1].astype(np.float32)
    a = alpha[y0 - y:y1 - y, x0 - x:x1 - x]
    dst[y0:y1, x0:x1] = (r * (1 - a) + rgb[y0 - y:y1 - y, x0 - x:x1 - x] * a).astype(np.uint8)


def draw_cursor(img, x, y, click):
    if click is not None and 0 <= click <= 1:
        r = int(10 + 34 * click)
        ov = img.copy()
        cv2.circle(ov, (int(x), int(y)), r, (45, 212, 191), 4, cv2.LINE_AA)
        cv2.addWeighted(ov, 1 - click, img, click, 0, img)
    pts = np.array([[0, 0], [0, 26], [7, 20], [12, 31], [17, 29], [12, 18], [21, 18]], np.float32)
    p = (pts + [x, y]).astype(np.int32)
    cv2.fillPoly(img, [p], (255, 255, 255), cv2.LINE_AA)
    cv2.polylines(img, [p], True, (10, 10, 10), 2, cv2.LINE_AA)


def pose_schedule(spans, total):
    """[(t, pose)] instant swaps: each paragraph's poses spread over it with a little randomness."""
    out = [(0.0, "idle")]
    for k, (s, e) in enumerate(spans):
        poses = POSE_PLAN[k]
        n = len(poses)
        for j, p in enumerate(poses):
            t = s + (e - s) * j / n + (random.uniform(-0.15, 0.25) if j else -0.1)
            out.append((max(t, out[-1][0] + 0.4), p))
    return out


def main():
    wav, spans = voice()
    x, sr = load_pcm(wav)
    total = len(x) / sr + 0.2
    if total > 119.5:
        print(f"WARNING: voice is {total:.1f} s, over the 2:00 limit")
    hop = sr // FPS
    env = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(int(total * FPS) + 2)])
    thr = max(0.01, np.percentile(env, 35) * 1.6)
    beats = timeline(spans, total)
    poses = pose_schedule(spans, total)
    caps = []   # (t0, t1, text)
    for k, (s, e) in enumerate(spans):
        ch = caption_chunks(PARAS[k])
        nw = [len(c.split()) for c in ch]
        t = s
        for c, n in zip(ch, nw):
            d = (e - s) * n / sum(nw)
            caps.append((t, t + d + (0.35 if c == ch[-1] else 0), c))
            t += d
    nfr = int(total * FPS)
    stills = [float(v) for v in sys.argv[sys.argv.index("--still") + 1].split(",")] if "--still" in sys.argv else None
    want = {int(v * FPS) for v in stills} if stills else None
    tmp = HERE / "work" / "video_noaudio.mp4"
    ff = None if want else subprocess.Popen(["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS), str(tmp)],
                          stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    prev_win, prev_key, fade = None, None, 0
    bi = 0
    for fi in range(nfr):
        t = fi / FPS
        if want is not None and not any(0 <= w_ - fi <= 0 for w_ in want):
            if fi > max(want):
                break
            continue
        while bi + 1 < len(beats) and t >= beats[bi + 1][0]:
            bi += 1
        t0, t1, k, b = beats[bi]
        u = (t - t0) / max(t1 - t0, 1e-6)
        key, cam, cur, click = beat_state(b, u)
        win = view(src(key), cam)
        beat_key = id(b)
        if prev_key is not None and beat_key != prev_key:
            fade = 12
            fade_from = prev_win
        if fade > 0:
            a = fade / 12
            win = (win.astype(np.float32) * (1 - a) + fade_from.astype(np.float32) * a).astype(np.uint8)
            fade -= 1
        prev_win, prev_key = win, beat_key
        frame = BASE.copy()
        region = frame[WY:WY + WH, WX:WX + WW].astype(np.float32)
        frame[WY:WY + WH, WX:WX + WW] = (region * (1 - WMASK) + win.astype(np.float32) * WMASK).astype(np.uint8)
        if cur is not None:
            cx = WX + (cur[0] - cam[0]) / cam[2] * WW
            cy = WY + (cur[1] - cam[1]) / (cam[2] * 9 / 16) * WH
            if WX <= cx <= WX + WW and WY <= cy <= WY + WH:
                draw_cursor(frame, cx, cy, click)
        cap = next((c for (a_, b_, c) in caps if a_ <= t < b_), "")
        trgb, ta = text_layer(SECTIONS[k], cap)
        frame = (frame.astype(np.float32) * (1 - ta) + trgb * ta).astype(np.uint8)
        pose = [p for (tt, p) in poses if tt <= t][-1]
        talking = env[min(fi, len(env) - 1)] > thr
        mouth = 1 if talking and (fi // 5) % 2 == 0 else 0
        rgb, al = POSE_IMG[f"{pose}_{mouth}"]
        bob = -4 if any(0 <= t - tt < 0.07 for tt, _ in poses) else 0
        paste(frame, rgb, al, W - rgb.shape[1] - 14, H - rgb.shape[0] - 8 + bob)
        if want is not None:
            Image.fromarray(frame).save(HERE / "work" / f"still_{t:06.2f}.png")
            continue
        ff.stdin.write(frame.tobytes())
        if fi % 600 == 0:
            print(f"{t:6.1f}s / {total:.1f}s", flush=True)
    if want is not None:
        print("stills in", HERE / "work")
        return
    ff.stdin.close()
    ff.wait()
    run(["ffmpeg", "-y", "-i", str(tmp), "-i", str(wav), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(OUT)])
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(OUT)],
                             capture_output=True, text=True).stdout)
    print(f"wrote {OUT}  {d:.2f} s  ({'OK' if d <= 120 else 'OVER 2:00'})")


if __name__ == "__main__":
    main()   # --still 3.0,12.5  renders just those times to work/still_*.png
