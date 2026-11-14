"""Probe a running API (make api): health, one ask, cost."""
import json
import sys

import httpx

base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
print(httpx.get(f"{base}/health", timeout=10).json())
r = httpx.post(f"{base}/api/ask", timeout=120, json={
    "path": "data/cubicasa5k/colorful-11960.png", "question": "How many windows are shown on this floor plan?"})
d = r.json()
print(r.status_code, {k: d.get(k) for k in ("intent", "value", "tier", "refusal")}, d.get("cost"))
print(httpx.get(f"{base}/api/cost", timeout=10).json())
