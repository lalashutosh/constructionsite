import math, os, shutil, sys, json
from PIL import Image, ImageDraw, ImageFont

SL = "/mnt/user-data/uploads/constructionsite/docs/pitch/slides"
OUT = "/home/claude/pitch/frames"
W, H = 1920, 1080
SLIDE_W, SLIDE_H = 1600, 900          # slide area (scale 0.8333)
COL_X = SLIDE_W                        # stickman column starts here
PAPER = (244, 239, 230)
INK = (20, 20, 22)
TICK = 0.5                             # pose change grid (rigid, no easing)
MOUTH = 0.25                           # mouth flip grid
STEP = 0.25                            # frame state grid
WPS = 2.45                             # words per second of speech
PAUSE = 0.30                           # gap between phrases

# (slide, [phrases], pose pattern)
SEGMENTS = [
    ("02", ["Six doors. Easy, you counted them already.",
            "Now this one: an Air Force dormitory, ten thousand pixels wide.",
            "How many doors? Nobody should count that by eye."],
     ["rest", "shrug", "point", "rest", "up", "hips"]),
    ("03x", ["So people ask a chatbot.",
             "You get one confident number, and nothing to check it against.",
             "Plumb says one hundred and thirty-nine, and boxes every single door."],
     ["hips", "shrug", "rest", "shrug", "point", "up"]),
    ("05", ["Ask in plain language. Any language.",
            "More doors, or toilets and sinks? One thirty-nine against ninety-six.",
            "Every answer comes with a receipt: measured, printed, or estimated."],
     ["rest", "point", "wave", "point", "rest", "clasp"]),
    ("06", ["Every size starts with the scale, and Plumb reads it off the sheet itself.",
            "This one is a half-size print. The printed note alone would be wrong by two times.",
            "No scale at all? Click both ends of one door, and everything follows."],
     ["point", "rest", "point", "shrug", "wave", "rest"]),
    ("07", ["Then it counts what's inside: forty-eight sinks, forty-eight toilets, forty-six beds.",
            "Code counts every symbol two ways. The model only names them."],
     ["point", "up", "point", "rest", "up", "rest"]),
    ("08", ["And it turns the drawing into a build plan: concrete, hinges, pipe, cable.",
            "Services use European standards, and are labeled as estimates."],
     ["clasp", "point", "rest", "point", "shrug", "rest"]),
    ("09", ["On hard sheets, it stays honest.",
            "This piping plan prints five check valves, but only four tags are legible. Plumb says exactly that."],
     ["hips", "shrug", "point", "hips", "shrug", "rest"]),
    ("10", ["Twenty-four out of twenty-five hard questions right on Stoa's full-size sheets.",
            "Scale within two percent, on all three."],
     ["up", "rest", "up", "point", "rest", "up"]),
    ("11", ["And it's almost no LLM. Computer vision and formulas, on a laptop.",
            "Most answers cost zero tokens. Reading this whole sheet: ten cents, once."],
     ["rest", "wave", "point", "clasp", "shrug", "rest"]),
    ("12", ["The model names things. Code measures.",
            "So next year's better model makes Plumb better, not obsolete."],
     ["rest", "point", "clasp", "wave", "rest", "up"]),
    ("13", ["I'm Abhinav. This is Plumb: blueprints that show their work."],
     ["wave", "up", "wave", "rest"]),
]

def font(sz, bold=True):
    return ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-%s.otf" % ("Bold" if bold else "Regular"), sz)

# ---------- timeline ----------
def words(s): return len(s.split())
phr = []   # (seg, text, t0, t1)
t = 0.4
seg_start = []
for si, (_, ps, _) in enumerate(SEGMENTS):
    seg_start.append(t)
    for p in ps:
        d = words(p) / WPS
        phr.append((si, p, t, t + d))
        t += d + PAUSE
total_speech_end = phr[-1][3]
END = total_speech_end + 1.2
print("words:", sum(words(p[1]) for p in phr), "speech end: %.1f  video end: %.1f" % (total_speech_end, END))
if END > 120.0:
    print("TOO LONG"); sys.exit(1)

# ---------- slides ----------
def slide3_patched():
    im = Image.open(f"{SL}/slide03.png").convert("RGB")
    d = ImageDraw.Draw(im)
    d.rectangle([140, 320, 900, 880], fill=(240, 240, 240))
    f1, f2 = font(78), font(46, False)
    d.text((150, 470), "One confident", font=f1, fill=(120, 120, 120))
    d.text((150, 560), "number.", font=f1, fill=(120, 120, 120))
    d.text((150, 690), "No boxes. No working.", font=f2, fill=(150, 150, 150))
    return im

slides = {}
for k in sorted({s[0] for s in SEGMENTS}):
    im = slide3_patched() if k == "03x" else Image.open(f"{SL}/slide{k}.png").convert("RGB")
    slides[k] = im.resize((SLIDE_W, SLIDE_H), Image.LANCZOS)

# ---------- stickman ----------
UP, FO = 78, 70
def pt(p, ang, ln):
    a = math.radians(ang)
    return (p[0] + ln * math.cos(a), p[1] + ln * math.sin(a))

# angles: 0=right, 90=down, 180=left, 270=up. (upper, fore) for left arm (screen-left), right arm
POSES = {
    "rest":  ((112, 98),  (68, 82)),
    "up":    ((225, 268), (315, 272)),
    "point": ((188, 182), (68, 82)),
    "shrug": ((150, 232), (30, 308)),
    "wave":  ((112, 98),  (340, 272)),
    "hips":  ((140, 40),  (40, 140)),
    "clasp": ((105, 5),   (75, 175)),
}

SS = 4
FW, FH = 320, 520
def stick(pose, mouth_open, bounce):
    im = Image.new("RGBA", (FW * SS, FH * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = SS
    lw = 7 * s
    cx = FW // 2
    head_c = (cx, 120 + bounce)
    hr = 44
    neck = (cx, head_c[1] + hr)
    hip = (cx, neck[1] + 150)
    sh = (cx, neck[1] + 22)
    def L(a, b):
        d.line([(a[0] * s, a[1] * s), (b[0] * s, b[1] * s)], fill=INK, width=lw, joint="curve")
        for p in (a, b):
            d.ellipse([p[0]*s - lw/2, p[1]*s - lw/2, p[0]*s + lw/2, p[1]*s + lw/2], fill=INK)
    # head
    d.ellipse([(head_c[0]-hr)*s, (head_c[1]-hr)*s, (head_c[0]+hr)*s, (head_c[1]+hr)*s],
              outline=INK, width=lw, fill=PAPER)
    # eyes
    for ex in (-15, 15):
        e = (head_c[0] + ex, head_c[1] - 8)
        d.ellipse([(e[0]-4)*s, (e[1]-4)*s, (e[0]+4)*s, (e[1]+4)*s], fill=INK)
    # mouth
    m = (head_c[0], head_c[1] + 20)
    if mouth_open:
        d.ellipse([(m[0]-10)*s, (m[1]-8)*s, (m[0]+10)*s, (m[1]+8)*s], fill=INK)
    else:
        d.line([((m[0]-11)*s, m[1]*s), ((m[0]+11)*s, m[1]*s)], fill=INK, width=5*s)
    # torso + legs
    L(neck, hip)
    L(hip, (cx - 42, hip[1] + 150))
    L(hip, (cx + 42, hip[1] + 150))
    # arms
    (lu, lf), (ru, rf) = POSES[pose]
    for (ua, fa) in ((lu, lf), (ru, rf)):
        e = pt(sh, ua, UP)
        h = pt(e, fa, FO)
        L(sh, e); L(e, h)
        d.ellipse([(h[0]-10)*s, (h[1]-10)*s, (h[0]+10)*s, (h[1]+10)*s], fill=INK)
    return im.resize((FW, FH), Image.LANCZOS)

stick_cache = {}
def get_stick(pose, mo, b):
    k = (pose, mo, b)
    if k not in stick_cache: stick_cache[k] = stick(pose, mo, b)
    return stick_cache[k]

# ---------- caption band + column ----------
CAP_H = H - SLIDE_H
capfont = font(46)
def wrap(text, f, maxw):
    lines, cur = [], ""
    dd = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for w in text.split():
        trial = (cur + " " + w).strip()
        if dd.textlength(trial, font=f) <= maxw: cur = trial
        else: lines.append(cur); cur = w
    lines.append(cur)
    return lines

def caption_img(text):
    im = Image.new("RGB", (SLIDE_W, CAP_H), (16, 18, 22))
    d = ImageDraw.Draw(im)
    lines = wrap(text, capfont, SLIDE_W - 160)
    lh = 60
    y0 = (CAP_H - lh * len(lines)) // 2 - 2
    for i, ln in enumerate(lines):
        w = d.textlength(ln, font=capfont)
        d.text(((SLIDE_W - w) / 2, y0 + i * lh), ln, font=capfont, fill=(255, 255, 255))
    return im

def base_frame(slide_key):
    im = Image.new("RGB", (W, H), PAPER)
    im.paste(slides[slide_key], (0, 0))
    d = ImageDraw.Draw(im)
    # ground line under stickman
    gy = 100 + 120 + 44 + 150 + 150 + 520 - 520 + 0
    return im

cap_cache = {}
base_cache = {}
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT): os.remove(os.path.join(OUT, f))

lab = font(30)
clockf = font(34)
def clock(sec):
    return "%d:%02d" % (sec // 60, sec % 60)

def render(tm, idx):
    # which phrase / segment
    cur_p = None; seg = 0
    for p in phr:
        if p[2] - 0.0001 <= tm: seg = p[0]
        if p[2] - 0.0001 <= tm < p[3] + PAUSE * 0.9: cur_p = p
    speaking = cur_p is not None and tm < cur_p[3]
    if cur_p is not None: seg = cur_p[0]
    skey = SEGMENTS[seg][0]
    if skey not in base_cache: base_cache[skey] = base_frame(skey)
    im = base_cache[skey].copy()
    # caption band
    ctext = cur_p[1] if cur_p else ""
    if ctext not in cap_cache: cap_cache[ctext] = caption_img(ctext)
    im.paste(cap_cache[ctext], (0, SLIDE_H))
    d = ImageDraw.Draw(im)
    # column
    d.rectangle([COL_X, 0, W, H], fill=PAPER)
    d.line([(COL_X, 0), (COL_X, H)], fill=(200, 192, 178), width=3)
    # clock (discrete, whole seconds)
    d.text((COL_X + 24, 24), clock(int(tm)) + " / 2:00", font=clockf, fill=INK)
    # stickman: rigid pose by tick
    pat = SEGMENTS[seg][2]
    tick = int(tm / TICK)
    pose = pat[tick % len(pat)] if speaking else ("rest" if tick % 2 == 0 else "rest")
    mo = speaking and (int(tm / MOUTH) % 2 == 0)
    bounce = 4 if (speaking and tick % 2 == 1) else 0
    fig = get_stick(pose, bool(mo), bounce)
    fx = COL_X + (W - COL_X - FW) // 2
    fy = 190
    im.paste(fig, (fx, fy), fig)
    # floor line + name
    fy_floor = fy + 120 + 44 + 150 + 150 + 120 + bounce * 0
    d.line([(COL_X + 50, fy + 468), (W - 50, fy + 468)], fill=INK, width=5)
    nm = "abhinav"
    d.text((COL_X + (W - COL_X) // 2 - d.textlength(nm, font=lab) / 2, fy + 486), nm, font=lab, fill=INK)
    im.save(f"{OUT}/f{idx:04d}.png")

n = 0
tm = 0.0
while tm < END:
    render(tm, n)
    n += 1
    tm += STEP
print("frames", n)

# ---------- script + srt ----------
def ts(x, srt=True):
    h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60
    return "%02d:%02d:%06.3f" % (h, m, s) if srt else "%d:%02d" % (m, int(s))
srt = []
for i, (si, text, a, b) in enumerate(phr, 1):
    srt.append(f"{i}\n{ts(a).replace('.', ',')} --> {ts(b + 0.1).replace('.', ',')}\n{text}\n")
open("/home/claude/pitch/Plumb_pitch_2min.srt", "w").write("\n".join(srt))
json.dump({"n": n, "end": END, "words": sum(words(p[1]) for p in phr),
           "phr": phr, "seg_start": seg_start}, open("/home/claude/pitch/timeline.json", "w"))
