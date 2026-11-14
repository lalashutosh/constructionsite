"""Stratified smoke: N dev questions per (source, type) through the pipeline; prints accuracy, tiers, crashes."""
import collections
import sys
import time

from evalkit import score as scoring
from evalkit.data import load_questions
from engine.api import get_engine

n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
allow = (sys.argv[2] != "nosib") if len(sys.argv) > 2 else True
qs = [q for q in load_questions() if q.split == "dev"]
by = collections.defaultdict(list)
for q in qs:
    by[(q.source, q.type)].append(q)
eng = get_engine("pipeline")
for key, rows in sorted(by.items()):
    rows = rows[:: max(1, len(rows) // n)][:n]
    ok = err = 0
    tiers = collections.Counter()
    t = time.time()
    for q in rows:
        try:
            po = eng.ask(q.path, q.question, allow_siblings=allow, benchmark=True)
            ok += bool(scoring.score(q.type, po.value, q.answer))
            tiers[po.tier.value] += 1
        except Exception as e:  # noqa: BLE001
            err += 1
            print("ERR", q.path, type(e).__name__, e)
    print(key, f"acc {ok}/{len(rows)}", dict(tiers), f"err={err}", f"{(time.time() - t) / len(rows):.2f}s/q")
