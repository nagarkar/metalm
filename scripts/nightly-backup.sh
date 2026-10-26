#!/bin/bash
# Nightly backup (launchd, 03:30; the hour lives only in the plist that `metalm-ops schedule print backup` writes).
# Steps: doctor, local copies, B2 off-site, status with alert. Every step is attempted (no set -e);
# a clean run is silent; any failure sends one SuperLM banner naming the failed steps (guidelines/scheduling.md).
# METALM_NOTIFY_CMD points the alert at a stub (tests); nothing else is overridable.
if [ -z "$METALM_CAFFEINATED" ]; then
  export METALM_CAFFEINATED=1
  exec /usr/bin/caffeinate -i -s /bin/bash "$0" "$@"
fi

HERE="$(cd "$(dirname "$0")/.." && pwd)"
OPS="$HERE/metalm-ops.sh"
NOTIFY="${METALM_NOTIFY_CMD:-$HOME/.local/bin/superlm-notify}"
LOGDIR="$HOME/.local/state/metalm/ops/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/backup-$(date +%Y%m%dT%H%M%S).log"
FAILED=()
FINISHED=0

step() {  # step <name> <command...>: run, log the exit code, remember a failure
  local name="$1"; shift
  echo "== $name: $*" >>"$LOG"
  "$@" >>"$LOG" 2>&1
  local code=$?
  echo "== $name: exit $code" >>"$LOG"
  [ "$code" -ne 0 ] && FAILED+=("$name")
  return 0
}

on_exit() {
  if [ "$FINISHED" -ne 1 ]; then FAILED+=("the run itself"); fi
  if [ "${#FAILED[@]}" -gt 0 ]; then
    local body="failed: $(IFS=,; echo "${FAILED[*]}" | sed 's/,/, /g'). Log: $LOG"
    if [ -x "$NOTIFY" ]; then
      "$NOTIFY" --repo metalm --title "nightly backup" --body "$body" >>"$LOG" 2>&1
    else
      echo "cannot alert: $NOTIFY is missing; $body" >>"$LOG"
    fi
  fi
  # Logs older than 30 days go; one file per run.
  find "$LOGDIR" -name 'backup-*.log' -mtime +30 -delete 2>/dev/null
}
trap on_exit EXIT

step doctor "$OPS" doctor
step "local copies" "$OPS" backup run
step "off-site" "$OPS" backup offsite
step status "$OPS" status --alert
FINISHED=1
