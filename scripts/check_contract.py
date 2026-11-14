"""Validate every fixture against the contract + invariants. Exit 1 on any problem."""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts import invariants  # noqa: E402
from contracts.proof import ProofObject, SheetFacts  # noqa: E402


def main() -> int:
    failed = 0
    for p in sorted((ROOT / "contracts" / "fixtures").glob("*.json")):
        data = json.loads(p.read_text())
        try:
            if p.name.startswith("sample_facts"):
                SheetFacts.model_validate(data)
                print(f"OK   {p.name}")
            else:
                po = ProofObject.model_validate(data)
                problems = invariants.check(po)
                if problems:
                    failed += 1
                    print(f"FAIL {p.name}: {problems}")
                else:
                    print(f"OK   {p.name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {p.name}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
