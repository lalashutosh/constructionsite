"""Environment + dataset sanity check. stdlib only, so it runs before `make setup`.
Exit 1 on hard failures (python, dataset). Warns on soft ones (tesseract langs, node).
"""
from __future__ import annotations

import collections
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
hard: list[str] = []
soft: list[str] = []


def load_env() -> None:
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$", line)
            if m and not line.lstrip().startswith("#"):
                os.environ.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout + ""
    except Exception as exc:  # noqa: BLE001
        return f"ERR {exc}"


def main() -> int:
    load_env()
    print(f"python  {sys.version.split()[0]}")
    if sys.version_info < (3, 10):
        hard.append("Python >= 3.10 required")

    for tool in ("git", "node", "npm"):
        p = shutil.which(tool)
        print(f"{tool:7} {p or 'MISSING'}")
        if not p:
            (hard if tool == "git" else soft).append(f"{tool} not found")

    sys.path.insert(0, str(ROOT))
    import engine  # noqa: F401  (puts a repo-local tesseract on PATH when none is installed system-wide)
    t = shutil.which("tesseract")
    if t:
        langs = set(run(["tesseract", "--list-langs"]).split())
        print(f"tesseract langs: {sorted(langs & {'eng', 'fin', 'swe', 'est', 'deu', 'fra'})}")
        for need in ("eng", "fin"):
            if need not in langs:
                soft.append(f"tesseract language '{need}' missing (macOS: brew install tesseract-lang)")
    else:
        soft.append("tesseract missing (macOS: brew install tesseract tesseract-lang)")

    root = os.environ.get("DATASET_ROOT", "")
    if not root:
        hard.append("DATASET_ROOT not set (copy .env.example to .env)")
    else:
        d = pathlib.Path(root).expanduser()
        q = d / "questions.jsonl"
        if not q.exists():
            hard.append(f"{q} not found; DATASET_ROOT must contain questions.jsonl and data/")
        else:
            rows = [json.loads(l) for l in q.read_text().splitlines() if l.strip()]
            by_src = collections.defaultdict(list)
            for r in rows:
                by_src[r["path"].split("/")[1]].append(r["path"])
            print(f"questions: {len(rows)} rows")
            for src, paths in sorted(by_src.items()):
                sample = list(dict.fromkeys(paths))[:25]
                ok = sum((d / p).exists() for p in sample)
                sib = ""
                if src == "swiss_dwellings":
                    s = sum((d / p).with_suffix(".dxf").exists() for p in sample)
                    sib = f", .dxf siblings {s}/{len(sample)}"
                print(f"  {src:16} {len(paths):5} Qs; files present {ok}/{len(sample)}{sib}")
                if ok < len(sample):
                    soft.append(f"{src}: {len(sample) - ok}/{len(sample)} sampled files missing under DATASET_ROOT")

    for s in soft:
        print(f"WARN  {s}")
    for h in hard:
        print(f"FAIL  {h}")
    print("RESULT", "FAIL" if hard else "OK")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
