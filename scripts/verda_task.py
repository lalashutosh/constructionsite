#!/usr/bin/env python3
"""Verda worker: a cheap model writes ONE file for a tightly scoped task, code checks it, errors go back, it retries.

Claude (Opus lead / sonnet builders) writes the spec and reviews the result; Verda does the typing.
Output is STAGED under cache/verda/staged/<task>/ and never written into the repo unless --apply is given, so a
Claude reviewer always looks at the diff first (`diff -u <target> <staged>`).

Usage:
  .venv/bin/python scripts/verda_task.py --task cache/verda/tasks/<name>.md --target engine/x/y.py \
      [--context a.py b.py ...] [--check "DATASET_ROOT=... .venv/bin/python -m pytest -q tests/test_y.py"] \
      [--model fast|strong] [--tries 3] [--apply]

The task file should state: goal, the exact file to produce, interfaces to use (pass them via --context), constraints
(no network, deterministic, tests to satisfy), and what NOT to change. The target's current content (if any) is sent
as context so the model edits it instead of starting over. During the check the staged file is swapped into place
and the original is ALWAYS restored afterwards (unless --apply and the check passed).
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "bin" / "python")
LOG = ROOT / "logs" / "verda_tasks.jsonl"

SYSTEM = ("You are a careful senior engineer. Output ONLY the complete content of the requested file inside one "
          "fenced code block. No explanation before or after. Keep existing public names and behaviour unless the "
          "task says otherwise. Deterministic code, no network calls, no secrets.")


def extract(text: str) -> str:
    blocks = re.findall(r"```[a-zA-Z0-9_+-]*\n(.*?)```", text, re.S)
    return (max(blocks, key=len) if blocks else text).rstrip() + "\n"


def syntax_error(path: Path, code: str) -> str | None:
    if path.suffix == ".py":
        try:
            ast.parse(code)
        except SyntaxError as e:
            return f"SyntaxError line {e.lineno}: {e.msg}"
    if path.suffix == ".json":
        try:
            json.loads(code)
        except ValueError as e:
            return f"JSON error: {e}"
    return None


def run_check(cmd: str, target: Path, staged: str) -> tuple[bool, str]:
    backup = target.with_suffix(target.suffix + ".verda_bak") if target.exists() else None
    if backup:
        shutil.copy2(target, backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(staged)
    try:
        r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True, timeout=600)
        out = (r.stdout + r.stderr)[-3500:]
        return r.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "check timed out after 600 s"
    finally:
        if backup:
            shutil.move(backup, target)
        else:
            target.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--context", nargs="*", default=[])
    ap.add_argument("--check")
    ap.add_argument("--model", choices=["fast", "strong"], default="fast")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=12000)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--think", action="store_true", help="let the model reason first (strong model, hard tasks)")
    a = ap.parse_args()

    target = ROOT / a.target
    name = Path(a.task).stem
    stage = ROOT / "cache" / "verda" / "staged" / name
    stage.mkdir(parents=True, exist_ok=True)
    spec = (ROOT / a.task).read_text()
    ctx = list(a.context) + ([a.target] if target.exists() else [])
    feedback, ok, code, t0 = "", False, "", time.time()
    for attempt in range(1, a.tries + 1):
        prompt = (f"{spec}\n\nProduce the full content of `{a.target}`."
                  + (f"\n\nYour previous attempt failed this check; fix it:\n```\n{feedback}\n```" if feedback else ""))
        pf = stage / f"prompt_{attempt}.md"
        pf.write_text(prompt)
        raw = stage / f"raw_{attempt}.md"
        r = subprocess.run([PY, "scripts/verda.py", "--model", a.model, "--prompt-file", str(pf.relative_to(ROOT)),
                            "--system", SYSTEM, "--max-tokens", str(a.max_tokens), "--out", str(raw.relative_to(ROOT)),
                            *([] if a.think else ["--no-think"]),
                            "--context", *ctx], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0 or not raw.exists():
            print(f"[verda_task] attempt {attempt}: verda call failed: {(r.stdout + r.stderr)[-400:]}")
            return 5
        code = extract(raw.read_text())
        (stage / target.name).write_text(code)
        err = syntax_error(target, code)
        if err:
            feedback = err
        elif a.check:
            ok, feedback = run_check(a.check, target, code)
        else:
            ok = True
        print(f"[verda_task] attempt {attempt}/{a.tries}: {'PASS' if ok else 'FAIL'}"
              + ("" if ok else f" -> {feedback.strip().splitlines()[-1][:160] if feedback.strip() else ''}"))
        if ok:
            break
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({"t": time.time(), "task": a.task, "target": a.target, "model": a.model, "ok": ok,
                            "attempts": attempt, "s": round(time.time() - t0, 1)}) + "\n")
    staged = stage / target.name
    if ok and a.apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code)
        print(f"[verda_task] applied to {a.target} — review with `git diff -- {a.target}`")
    else:
        print(f"[verda_task] staged: {staged.relative_to(ROOT)} — review with "
              f"`diff -u {a.target if target.exists() else '/dev/null'} {staged.relative_to(ROOT)}`")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
