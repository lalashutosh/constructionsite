"""Build web/public/claims.json from evaluation reports only (AGENTS.md rule 9: no hand-typed numbers).
    .venv/bin/python scripts/make_claims.py [--with <report dir>] [--nosib <report dir>]
Defaults: the newest evalkit/out/*w2-dev and *w2-dev-nosib runs."""
import argparse, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "evalkit" / "out"


def newest(suffix):
    runs = sorted(p for p in OUT.iterdir() if p.is_dir() and p.name.endswith(suffix))
    return runs[-1] if runs else None


def parse(report: pathlib.Path) -> dict:
    t = (report / "report.md").read_text()
    m = re.search(r"\*\*dev\*\*: ([\d.]+)% \[([\d.]+)%, ([\d.]+)%\] \(n=(\d+)\)", t)
    out = {"run": report.name, "dev_pct": float(m.group(1)), "ci": [float(m.group(2)), float(m.group(3))],
           "n": int(m.group(4)), "by_source": {}}
    for src, typ, pct, n in re.findall(r"^\| (\w+) \| (\w+) \| ([\d.]+)% \[[^\]]*\] \(n=(\d+)\) \|$", t, re.M):
        out["by_source"].setdefault(src, {})[typ] = {"pct": float(pct), "n": int(n)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with", dest="w")
    ap.add_argument("--nosib")
    a = ap.parse_args()
    w = pathlib.Path(a.w) if a.w else newest("w2-dev")
    ns = pathlib.Path(a.nosib) if a.nosib else newest("w2-dev-nosib")
    claims = {"source": "evalkit/out reports (DEV split; holdout never used)",
              "with_siblings": parse(w) if w else None, "no_siblings": parse(ns) if ns else None}
    for f in ("integrator.json", "skeptic_calibration.json"):
        p = ROOT / "docs" / "claims" / f
        if p.exists():
            d = json.loads(p.read_text())
            if "router_lolo" in d:
                claims["router_leave_one_language_out"] = d["router_lolo"]
            if "n_dev_rows" in d:
                claims["calibrator_trained_on"] = d["n_dev_rows"]
    led = ROOT / "logs" / "verda_cost.jsonl"
    if led.exists():
        rows = [json.loads(l) for l in led.read_text().splitlines() if l.strip()]
        claims["llm_ledger"] = {"calls": len(rows), "usd": round(sum(r.get("usd", 0) for r in rows), 4)}
    (OUT / "summary_claims.json").write_text(json.dumps(claims, indent=1) + "\n")   # merged by web/scripts/copy-fixtures.mjs
    dst = ROOT / "web" / "public" / "claims.json"
    base = {}
    latest = OUT / "latest" / "claims.json"
    if latest.exists():
        base = {k: v for k, v in json.loads(latest.read_text()).items() if k not in ("run", "commit", "reliability_cv")}
    dst.write_text(json.dumps({**base, **claims}, indent=1) + "\n")
    print(f"wrote {dst.relative_to(ROOT)}: with siblings {claims['with_siblings'] and claims['with_siblings']['dev_pct']}%,"
          f" no siblings {claims['no_siblings'] and claims['no_siblings']['dev_pct']}%")


if __name__ == "__main__":
    main()
