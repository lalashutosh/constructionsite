#!/usr/bin/env bash
# Run one prompt unattended (night mode). Permissions come from .claude/settings.json (acceptEdits + allow list);
# anything not allowed is denied instead of prompting, so the run cannot hang.
# Usage: scripts/run_headless.sh prompts/21_w2_skeptic.md sonnet 80
set -euo pipefail

PROMPT="${1:?prompt file}"; MODEL="${2:-sonnet}"; TURNS="${3:-60}"
mkdir -p logs
LOG="logs/$(basename "$PROMPT" .md)-$(date +%H%M%S).log"

ARGS=(-p "$(cat "$PROMPT")" --model "$MODEL" --max-turns "$TURNS" --permission-mode acceptEdits --output-format text)
[ -n "${BUDGET:-}" ] && ARGS+=(--max-budget-usd "$BUDGET")   # only meaningful with API-key billing

claude "${ARGS[@]}" 2>&1 | tee "$LOG" | tail -40
echo "log: $LOG"
