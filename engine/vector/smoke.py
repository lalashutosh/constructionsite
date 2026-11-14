"""python -m engine.vector.smoke : 20 swiss + 10 ifc + 5 schedule DEV questions through the plugin. Exit 0 when the
exact readers answer and agree with the key at the floors below; exit 1 otherwise. Runs in well under 30 s.
Also asserts the sibling-resolver contract (allow_siblings=False returns None; resolved_from is reported)."""
from __future__ import annotations

import collections
import os
import sys
import time

FLOORS = {"swiss_dwellings": 0.90, "ifc_models": 0.90, "opening_design": 0.60}
N = {"swiss_dwellings": 20, "ifc_models": 10, "opening_design": 5}


def _pick(qs, n):
    by = collections.defaultdict(list)
    for q in qs:
        by[q.intent].append(q)
    out, i = [], 0
    keys = sorted(by)
    while len(out) < n and any(by.values()):
        k = keys[i % len(keys)]
        if by[k]:
            out.append(by[k].pop(0))
        i += 1
        if i > 10000:
            break
    return out


def main() -> int:
    from evalkit.data import load_questions
    from evalkit.score import score
    from engine import registry, siblings
    from engine.vector import plugin
    t0 = time.time()
    qs = [q for q in load_questions() if q.split == "dev" and q.lang == "en" and q.type in ("count", "area", "length", "volume")]
    ok_all = True
    # resolver contract
    sw = next(q for q in qs if q.source == "swiss_dwellings")
    r = siblings.resolve(sw.path, True)
    assert r is not None and r.fmt == "dxf", "swiss pdf must resolve to its dxf sibling"
    assert siblings.resolve(sw.path, False) is None, "allow_siblings=False must bypass the resolver"
    print(f"resolver: {sw.path.split('/')[-1]} -> {r.fmt} ({r.note})")
    for src in ("swiss_dwellings", "ifc_models", "opening_design"):
        sample = _pick([q for q in qs if q.source == src], N[src])
        hit = ans = 0
        for q in sample:
            ctx = registry.Ctx(path=q.path, abs_path="", question=q.question, intent=q.intent, params=q.params,
                               kind=q.type, lang=q.lang, allow_siblings=True)
            vr = plugin.voter_primary(ctx)
            if vr is None or vr.voter.value is None:
                continue
            ans += 1
            truth = float(str(q.answer).split()[0])
            hit += bool(score(q.type, vr.voter.value, truth))
        acc = hit / max(1, len(sample))
        flag = "OK " if acc >= FLOORS[src] else "LOW"
        ok_all &= acc >= FLOORS[src]
        print(f"{flag} {src:16s} n={len(sample):2d} answered={ans:2d} correct={hit:2d} acc={acc:.2f} (floor {FLOORS[src]})")
    print(f"smoke {'PASS' if ok_all else 'FAIL'} in {time.time() - t0:.1f}s")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
