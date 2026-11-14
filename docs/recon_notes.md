# Recon notes

Full recon in `docs/recon.md` (319 lines: questions by source×type, templates, answer distributions). Key facts:
- Root `/tmp/mockds`, 7990 rows. cubicasa5k 4270 (png count) · swiss_dwellings 2358 (pdf+dxf+png) · ifc_models 1049 · ifc_bench 249 (text) · opening_design 64.
- Types: count 6076 · area 1599 · text 265 · volume 34 · length 16.
- Scoring: counts exact; area/length/volume ±2%; text free-form.
- Siblings present for swiss_dwellings (.dxf 25/25 sampled).
