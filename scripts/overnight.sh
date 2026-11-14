#!/usr/bin/env bash
# Overnight supervisor for the single-session build.
# Starts one Claude Code session (the orchestrator, ORCHESTRATOR.md). Whenever it stops (usage limit, turn cap,
# crash), the supervisor waits if needed and starts a fresh session that continues from git + docs/STATE.md.
# Ends when STATE says DONE or BLOCKED, at STOP_AT, or when several cycles in a row make no progress.
#
# Usage (from the repo folder):  bash scripts/overnight.sh
# Options (env): STOP_AT="09:30"   wall-clock stop time, today or tomorrow (default 09:00)
#                ORCH_MODEL=opus   orchestrator model; falls back to sonnet if opus is not available on the plan
#                TURNS=400         max turns per session
#                LIMIT_WAIT=900    seconds to wait after a usage-limit message before retrying (default 15 min)
#                MAX_IDLE=4        stop after this many cycles with no new commit and no STATE change
set -uo pipefail

if [ -z "${AWAKE:-}" ]; then
  if command -v systemd-inhibit >/dev/null 2>&1; then
    exec systemd-inhibit --what=idle:sleep --who=plumb --why="overnight build" env AWAKE=1 bash "$0" "$@"
  elif command -v caffeinate >/dev/null 2>&1; then
    exec caffeinate -dimsu env AWAKE=1 bash "$0" "$@"
  fi
fi

cd "$(dirname "$0")/.."
STOP_AT="${STOP_AT:-09:00}"; ORCH_MODEL="${ORCH_MODEL:-opus}"; TURNS="${TURNS:-400}"
LIMIT_WAIT="${LIMIT_WAIT:-900}"; MAX_IDLE="${MAX_IDLE:-4}"; IDLE_SLEEP="${IDLE_SLEEP:-120}"
L=logs/overnight; mkdir -p "$L"; S="$L/SUPERVISOR.md"
note() { echo "- $(date '+%H:%M') $*" | tee -a "$S"; }

if [ -n "${ANTHROPIC_API_KEY:-}" ] && [ -z "${ALLOW_API_BILLING:-}" ]; then
  echo "ANTHROPIC_API_KEY is set in this shell: Claude Code would bill the API instead of your subscription."
  echo "Run 'unset ANTHROPIC_API_KEY', or set ALLOW_API_BILLING=1 on purpose."; exit 1
fi
command -v claude >/dev/null || { echo "claude CLI not found"; exit 1; }

STOP_EPOCH="$(date -d "$STOP_AT" +%s 2>/dev/null || date -j -f %H:%M "$STOP_AT" +%s)"
[ "$STOP_EPOCH" -le "$(date +%s)" ] && STOP_EPOCH=$((STOP_EPOCH + 86400))

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  git init -q -b main && git add -A && git commit -qm "w0: add plumb pack (single-session)"
fi
if [ "$(git rev-parse --show-toplevel)" != "$(pwd -P)" ]; then
  echo "refusing: git repo root is $(git rev-parse --show-toplevel), not $(pwd -P)."
  echo "plumb must be its own repo (run 'git init' here), or 'git add' would sweep the parent folder."; exit 1
fi
git checkout -q main 2>/dev/null || true

state_sig() { { git rev-parse HEAD; md5sum docs/STATE.md 2>/dev/null || md5 -q docs/STATE.md; } | tr -d '\n'; }
first_line() { head -1 docs/STATE.md 2>/dev/null; }

note "supervisor start, stop at $(date -d "@$STOP_EPOCH" '+%a %H:%M' 2>/dev/null || echo "$STOP_AT"), model $ORCH_MODEL"
cycle=0; idle=0
while :; do
  case "$(first_line)" in
    "STATUS: DONE")    note "STATE says DONE. Read docs/MORNING.md."; exit 0 ;;
    "STATUS: BLOCKED") note "STATE says BLOCKED. Read docs/MORNING.md."; exit 3 ;;
  esac
  now=$(date +%s)
  [ "$now" -ge "$STOP_EPOCH" ] && { note "stop time reached"; exit 0; }
  cycle=$((cycle + 1)); log="$L/cycle-$(printf %03d $cycle).log"; before="$(state_sig)"
  header="Current time: $(date '+%Y-%m-%d %H:%M'). Stop time: $(date -d "@$STOP_EPOCH" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "$STOP_AT"). Minutes left: $(( (STOP_EPOCH - now) / 60 )). Cycle: $cycle."
  note "cycle $cycle start ($ORCH_MODEL)"
  claude -p "$header"$'\n\n'"$(cat ORCHESTRATOR.md)" --model "$ORCH_MODEL" --max-turns "$TURNS" \
    --permission-mode acceptEdits --output-format text >"$log" 2>&1
  rc=$?
  git add -A . >/dev/null 2>&1 && git commit -qm "supervisor: wip after cycle $cycle" >/dev/null 2>&1 || true
  note "cycle $cycle end rc=$rc | $(tail -3 "$log" | tr '\n' ' ' | cut -c1-240)"

  if [ "$ORCH_MODEL" != "sonnet" ] && tail -20 "$log" | grep -qiE "model.*(not (available|found|supported)|invalid)|not available on your plan|does not have access" ; then
    note "model $ORCH_MODEL not available: switching orchestrator to sonnet"; ORCH_MODEL=sonnet; continue
  fi
  if tail -20 "$log" | grep -qiE "usage limit|session limit|limit reached|rate limit|resets|try again later|overloaded"; then
    wait_s="$LIMIT_WAIT"
    # "resets 7:10am" -> sleep until then (+2 min), never past stop time
    rt="$(tail -20 "$log" | grep -oiE 'resets( at)? [0-9]{1,2}(:[0-9]{2})? ?(am|pm)?' | tail -1 | sed -E 's/resets( at)? //I')"
    if [ -n "$rt" ] && re="$(date -d "$rt" +%s 2>/dev/null)"; then
      [ "$re" -le "$(date +%s)" ] && re=$((re + 86400))
      wait_s=$(( re - $(date +%s) + 120 ))
    fi
    left=$(( STOP_EPOCH - $(date +%s) )); [ "$wait_s" -gt "$left" ] && wait_s="$left"
    [ "$wait_s" -lt 60 ] && wait_s=60
    note "usage limit or overload${rt:+ (resets $rt)}: waiting $((wait_s / 60)) min"; sleep "$wait_s"; idle=0; continue
  fi
  if [ "$(state_sig)" = "$before" ]; then
    idle=$((idle + 1)); note "no progress this cycle ($idle/$MAX_IDLE)"
    [ "$idle" -ge "$MAX_IDLE" ] && { note "STOP: no progress for $MAX_IDLE cycles, see $log"; exit 4; }
    sleep "$IDLE_SLEEP"
  else
    idle=0; sleep 20
  fi
done
