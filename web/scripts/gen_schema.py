import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from contracts.proof import ProofObject, SheetFacts  # noqa: E402

OUT = ROOT / "web" / "scripts" / "_schemas"
OUT.mkdir(exist_ok=True)

(OUT / "ProofObject.json").write_text(json.dumps(ProofObject.model_json_schema(), indent=2))
(OUT / "SheetFacts.json").write_text(json.dumps(SheetFacts.model_json_schema(), indent=2))
print("wrote schemas to", OUT)
