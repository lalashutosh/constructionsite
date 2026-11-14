#!/usr/bin/env bash
# Create one git worktree per agent for a wave and print the exact commands to start each Claude Code session.
# Usage: scripts/launch_wave.sh w1 | w2 | w3        (run from the main checkout, clean git state)
set -euo pipefail

WAVE="${1:?usage: launch_wave.sh w1|w2|w3}"
REPO="$(git rev-parse --show-toplevel)"
BASE="$(basename "$REPO")"

case "$WAVE" in
  w1) TABLE=(
        "evaluator|evaluator|prompts/10_w1_evaluator.md"
        "raster|raster-extractor|prompts/11_w1_raster.md"
        "takeoff|takeoff|prompts/12_w1_takeoff.md"
        "ui|ui-builder|prompts/13_w1_ui.md"
      ) ;;
  w2) TABLE=(
        "integrator|integrator|prompts/20_w2_integrator.md"
        "skeptic|skeptic|prompts/21_w2_skeptic.md"
        "vector|vector|prompts/22_w2_vector.md"
      ) ;;
  w3) TABLE=(
        "wow-ui|ui-builder|prompts/30_w3_wow_ui.md"
        "wow-engine|takeoff|prompts/31_w3_wow_engine.md"
        "a2a|integrator|prompts/32_w3_a2a.md"
      ) ;;
  *) echo "unknown wave $WAVE"; exit 1 ;;
esac


if [ -n "$(git status --porcelain)" ]; then
  echo "Commit or stash first: worktrees branch from HEAD, uncommitted files would be missing."; exit 1
fi

echo "Branching from $(git rev-parse --short HEAD)"
for row in "${TABLE[@]}"; do
  IFS='|' read -r NAME AGENT PROMPT <<<"$row"
  DIR="$REPO/../${BASE}-wt-${NAME}"
  BRANCH="${WAVE}/${NAME}"
  if [ ! -d "$DIR" ]; then
    git worktree add -b "$BRANCH" "$DIR" HEAD >/dev/null
  fi
  [ -f "$REPO/.env" ] && [ ! -f "$DIR/.env" ] && cp "$REPO/.env" "$DIR/.env" || true
  [ -d "$REPO/.venv" ] && [ ! -e "$DIR/.venv" ] && ln -s "$REPO/.venv" "$DIR/.venv" || true
  echo
  echo "# --- $NAME (agent: $AGENT) ---"
  echo "cd \"$DIR\" && claude --agent $AGENT --permission-mode acceptEdits \"\$(cat $PROMPT)\""
done
echo
echo "When agents report done:  cd \"$REPO\" && scripts/merge_wave.sh $WAVE"
