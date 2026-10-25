#!/usr/bin/env bash
# Polls the Claude 5-hour session usage via `orca account list --json` every
# 5 minutes and exits when it reaches the threshold (default 95%), so the agent
# is notified to stop and update the handoff files. Each check is appended to
# D:/Orca/NMS-Derelict-Probe-backups/usage-watch.log.
# Right after a reset orca can still report the previous window (its resetsAt is already in the past);
# such a reading is stale and is re-checked a minute later instead of triggering the stop.
threshold="${1:-95}"
jq=/d/Orca/Tools/jq/jq.exe
log=/d/Orca/NMS-Derelict-Probe-backups/usage-watch.log
while true; do
  json=$(timeout 60 orca account list --json 2>/dev/null)
  pct=$(printf '%s' "$json" | "$jq" -r '.result.rateLimits.claude.session.usedPercent // empty' 2>/dev/null)
  reset=$(printf '%s' "$json" | "$jq" -r '.result.rateLimits.claude.session.resetDescription // empty' 2>/dev/null)
  resets_at=$(printf '%s' "$json" | "$jq" -r '.result.rateLimits.claude.session.resetsAt // empty' 2>/dev/null)
  now_ms=$(( $(date +%s) * 1000 ))
  stale=""
  if [ -n "$resets_at" ] && [ "$resets_at" -le "$now_ms" ]; then stale=" (stale: window already reset)"; fi
  echo "$(date -u +%FT%TZ) session_used=${pct:-unknown}% resets=${reset:-?}${stale}" >> "$log"
  if [ -n "$stale" ]; then sleep 60; continue; fi
  if [ -n "$pct" ] && [ "$pct" -ge "$threshold" ]; then
    echo "USAGE THRESHOLD REACHED: session ${pct}% >= ${threshold}% (resets ${reset}). Stop and update STATUS.md, WORKSPACE_STATE.json, AI_HANDOFF.md."
    exit 0
  fi
  # Check every minute once usage passes 90% (user, 2026-10-20); every 5 minutes before that.
  if [ -n "$pct" ] && [ "$pct" -ge 90 ]; then sleep 60; else sleep 300; fi
done
