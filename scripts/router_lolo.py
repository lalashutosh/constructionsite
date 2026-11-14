"""Leave-one-language-out router report. Writes docs/claims/integrator.json (router_lolo)."""
import json
import pathlib

from engine.router import lolo_accuracy

r = lolo_accuracy()
print(json.dumps(r, indent=1))
out = pathlib.Path(__file__).resolve().parents[1] / "docs" / "claims" / "integrator.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"router_lolo": r["overall"]}) + "\n")
