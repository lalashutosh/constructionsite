#!/usr/bin/env python3
"""Dataset reconnaissance -> docs/recon.md. Pure stdlib (+Pillow if present). Deterministic.

Usage: python scripts/recon.py [DATASET_ROOT]   (falls back to env / .env)
"""
from __future__ import annotations
import collections, json, os, pathlib, random, re, statistics, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def dataset_root(argv):
    if len(argv) > 1:
        return pathlib.Path(argv[1]).expanduser()
    if os.environ.get("DATASET_ROOT"):
        return pathlib.Path(os.environ["DATASET_ROOT"]).expanduser()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DATASET_ROOT="):
                return pathlib.Path(line.split("=", 1)[1].strip().strip('"\'')).expanduser()
    sys.exit("DATASET_ROOT not set (env, .env, or argv[1])")


def norm(q: str) -> str:
    return re.sub(r"\d+(?:[.,]\d+)?", "#", q)


def main():
    root = dataset_root(sys.argv)
    qf = root / "questions.jsonl"
    if not qf.exists():
        sys.exit(f"{qf} not found")
    rows = [json.loads(l) for l in qf.open(encoding="utf-8") if l.strip()]
    out = ["# Dataset reconnaissance", "", f"Root: `{root}`  ·  rows: {len(rows)}", ""]

    by_src_type = collections.Counter((r["path"].split("/")[1], r["type"]) for r in rows)
    out += ["## Questions by source x type", "", "| source | type | n |", "|---|---|---|"]
    for (s, t), n in sorted(by_src_type.items()):
        out.append(f"| {s} | {t} | {n} |")
    out.append("")

    ext = collections.Counter(pathlib.Path(r["path"]).suffix for r in rows)
    out += ["## File extensions of question paths", "", ", ".join(f"{k or '(none)'}: {v}" for k, v in ext.most_common()), ""]

    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r["path"].split("/")[1], r["type"], norm(r["question"]))].append(r)
    out += ["## Question templates (digits -> #), most frequent first, per source", ""]
    for src in sorted({k[0] for k in groups}):
        out += [f"### {src}", "", "| n | type | template | answers min / median / max | share 0 |", "|---|---|---|---|---|"]
        items = sorted(((k, v) for k, v in groups.items() if k[0] == src), key=lambda kv: -len(kv[1]))[:60]
        for (s, t, q), rs in items:
            nums = [r["answer"] for r in rs if isinstance(r["answer"], (int, float))]
            if nums:
                med = statistics.median(nums)
                stat = f"{min(nums)} / {med} / {max(nums)}"
                z = f"{sum(1 for x in nums if x == 0) / len(nums):.0%}"
            else:
                stat, z = "(text)", ""
            out.append(f"| {len(rs)} | {t} | {q[:140].replace('|', '/')} | {stat} | {z} |")
        out.append("")

    # sibling presence + image sizes (only if files exist)
    rnd = random.Random(7)
    paths = sorted({r["path"] for r in rows})
    present = [p for p in paths if (root / p).exists()]
    out += ["## Files", "", f"distinct question paths: {len(paths)} · present on disk: {len(present)}", ""]
    sib = collections.Counter()
    for p in rnd.sample(present, min(300, len(present))):
        pp = root / p
        for sibling in pp.parent.glob(pp.stem + ".*"):
            if sibling != pp:
                sib[(p.split("/")[1], pathlib.Path(p).suffix, sibling.suffix)] += 1
    if sib:
        out += ["Sibling formats found next to question files (sample of 300):", ""]
        for (s, e, se), n in sorted(sib.items()):
            out.append(f"- {s}: {e} has sibling {se} ({n})")
        out.append("")
    try:
        from PIL import Image
        sizes = collections.defaultdict(list)
        pngs = [p for p in present if p.lower().endswith((".png", ".jpg", ".jpeg"))]
        for p in rnd.sample(pngs, min(200, len(pngs))):
            with Image.open(root / p) as im:
                sizes[p.split("/")[1]].append(im.size)
        if sizes:
            out += ["## Raster image sizes (sample of up to 200)", ""]
            for s, v in sorted(sizes.items()):
                w = [a for a, _ in v]; h = [b for _, b in v]
                out.append(f"- {s}: n={len(v)} width {min(w)}–{statistics.median(w):.0f}–{max(w)}, height {min(h)}–{statistics.median(h):.0f}–{max(h)}")
            out.append("")
    except ImportError:
        out.append("(Pillow missing: image-size stats skipped)")

    dest = ROOT / "docs" / "recon.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {dest} ({len(out)} lines)")


if __name__ == "__main__":
    main()
