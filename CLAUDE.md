@AGENTS.md

## Claude Code specifics
- Project subagents live in `.claude/agents/`. Use them by name; independent ones in parallel.
- Single-session mode (default): the lead follows `ORCHESTRATOR.md`; run it via `scripts/overnight.sh`. Agent files pin their own model (builders sonnet, scout haiku).
- Permissions are in `.claude/settings.json` (allow list for python/pytest/npm/git/make; `.env` unreadable).
- If you hit a usage limit: stop, write progress to `docs/handoff/<agent>.md`, commit, and say what is left.
- Progress log: post a short update to GitHub issue #1 (`gh issue comment 1 -R lalashutosh/constructionsite -b "..."`) after each finished step; read it (and docs/HANDOFF.md) before starting.
