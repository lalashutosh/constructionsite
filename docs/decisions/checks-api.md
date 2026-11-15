# Checks API: confidence meter + yes/no questions (2026-11-14, lead)

Goal: when the engine is unsure about something that changes numbers (scale, sheet type, which view is the plan),
it says how sure it is and asks the user ONE short yes/no question; the answer is applied and numbers recompute.

## Contract (additive; owners: scale agent = engine + API, ui-builder = web)
`GET /api/checks?path=<path>` -> `{"path": str, "items": [Check, ...]}` (most impactful first)
```
Check = {
  "id": str,                     # stable per (file sha, kind, candidate), e.g. "scale:note:1in=40ft"
  "kind": "scale" | "sheet_type" | "plan_view" | "units",
  "status": "open" | "confirmed" | "rejected" | "auto",   # auto = confident enough, no question needed
  "confidence": float,           # 0..1, what the meter shows
  "summary": str,                # plain sentence: "Scale 1\" = 40'-0\" (title block note + scale bar agree)"
  "question": str | null,        # yes/no question when status == "open": "Is the overall width 323'-4\" (98.6 m)?"
  "evidence": [{"box": [x0, y0, x1, y1], "label": str}],  # image-pixel boxes (same space as /api/image)
  "impact": str | null,          # "All areas and lengths depend on this."
  "value": dict                  # e.g. {"px_per_m": 1.853, "source": "printed_ratio", "tag": "specified"}
}
```
`POST /api/checks/answer` body `{"path": str, "id": str, "answer": "yes" | "no", "value": number | null}` ->
same shape as GET (updated). yes -> the candidate becomes a user-confirmed anchor (tag `chosen`, tight sigma);
no -> the candidate is rejected and the next candidate (if any) becomes the open question. Stored per file sha in
`cache/checks/<sha>.json`; cached answers/geometry that depend on scale must be invalidated.

Rules: a question is asked only when confidence < 0.8 or anchors disagree (> 5%); at most 3 open questions per file;
the cheapest question first (a yes/no beats typing a length). Never ask what the drawing already states clearly.
Confidence is computed, never an LLM's self-report: anchor agreement count, tag (specified > drawn > defaulted),
spread, OCR confidence.
