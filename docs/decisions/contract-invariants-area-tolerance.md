Request (integrator, hook-invariants-area-tolerance.md): green area/length/volume proofs failed `invariants.check` when voters agreed within 2% but not exactly (e.g. IFC 530.0258 vs 529.8743).
ACCEPTED by the lead 2026-11-14: additive and backwards compatible (every previously valid proof stays valid); counts still need exact agreement, other kinds agree within `AGREE_TOL = 0.02`, the scoring tolerance.
Applied in one commit with a test (tests/test_contract.py) and `scripts/check_contract.py`.
