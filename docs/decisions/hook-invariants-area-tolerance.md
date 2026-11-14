# Hook request: invariants.check vs the 2% area agreement rule

Spec (prompts/20 step 3.7): area/length/volume voters agree "within 2%". `contracts/invariants.check` requires every
voter value on a green proof to be exactly equal (`len(set(vals)) != 1`). Two area voters at 10.00 and 10.15 m2 agree
under the 2% rule but violate the invariant, so `PipelineEngine.ask` downgrades them to amber with an
"invariants: green requires voters to agree" note. Net effect: area green currently means exact agreement.

Request (contracts are frozen, so the lead decides): make the invariant tolerance-aware for kind != count
(`max(vals) - min(vals) <= 0.02 * max(vals)`). The pipeline already implements the 2% test in `compute_tier`, so no
pipeline change is needed once the invariant is relaxed.
