# Decision: workspace trust gate blocks all execution (2026-11-14 12:40)

**Problem:** Every Bash call that runs an interpreter/exec (`python`, `.venv/bin/python`,
`pytest`, `make`, `npm`, even `git --version`) is denied with "this workspace has not
been trusted — run Claude Code interactively here once and accept the trust dialog".
Only read-only tools (Read/Grep in cwd, ls/cat via Bash) work. `~/.claude.json` is
outside the allowed search root, so the trust flag can't be inspected or edited from here.

**Why not self-fix:** Flipping `hasTrustDialogAccepted:true` bypasses a security consent
control the user set up. Not an agent's call. Treated like the tesseract/DATASET_ROOT
human-only blockers in ORCHESTRATOR.

**Fallback:** Both P1 resume agents (raster-extractor, ui-builder) hit this wall and did
no real work; ui-builder stopped to save quota. STATUS set BLOCKED. Human must accept the
trust dialog (run `claude` interactively in /home/ashutosh/Downloads/plumb once), then
restart overnight.sh. All prior committed code is intact; nothing lost.
