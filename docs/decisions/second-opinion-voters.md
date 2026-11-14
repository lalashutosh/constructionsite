Skeptic pixel voters (doors_arc 12%, windows_lines 3% on DEV150) are far weaker than the raster detector (57%, 40%), but with two voters the median tie went to the voter with the smaller TTA spread, i.e. the weak one.
Decision: skeptic voters set `VoterResult.second_opinion=True`; `pick_value` takes the value from primary voters only (falls back to all when no primary has a value); the tier still requires agreement of all voters.
Measured effect is recorded in docs/handoff/skeptic.md (DEV, with vs without the skeptic voters).
