"""python -m engine.skeptic.train --run latest : train the calibrator on DEV rows of an evalkit run (never HOLDOUT)."""
from __future__ import annotations

import argparse
import json
import pathlib

from engine.skeptic import calibrate


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="latest")
    a = ap.parse_args(argv)
    res = calibrate.train(a.run, pathlib.Path("docs/claims/skeptic_calibration.json"))
    print(json.dumps({k: v for k, v in res.items() if k != "reliability_cv"}, indent=1))
    for r in res.get("reliability_cv", []):
        print(r)


if __name__ == "__main__":
    main()
