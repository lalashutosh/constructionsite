#!/usr/bin/env bash
# Merge every branch of a wave into the current branch (run in the MAIN checkout), then run the tests.
# Usage: scripts/merge_wave.sh w1
set -euo pipefail

WAVE="${1:?usage: merge_wave.sh w1|w2|w3}"
if [ -n "$(git status --porcelain)" ]; then echo "Main checkout not clean."; exit 1; fi

BRANCHES="$(git for-each-ref --format='%(refname:short)' "refs/heads/${WAVE}/*")"
[ -z "$BRANCHES" ] && { echo "no branches for $WAVE"; exit 1; }

for b in $BRANCHES; do
  echo "== merging $b"
  if ! git merge --no-ff --no-edit "$b"; then
    echo "CONFLICT in $b. Resolve (keep the OWNER's version of owned paths, see AGENTS.md), commit, then re-run."
    exit 2
  fi
done

echo "== tests"
if [ -x .venv/bin/python ]; then .venv/bin/python -m pytest -q || { echo "TESTS FAILED"; exit 3; }; fi
git tag -f "${WAVE}-done" >/dev/null
echo "OK: ${WAVE} merged and tagged ${WAVE}-done"
