#!/usr/bin/env bash
# Polls Immich every 60s during the Phase 1 import, logs to a file.
# Run in a separate tmux window/pane from the import.
set -euo pipefail

API="http://localhost:2283"
KEY_FILE="/Users/szelenin/immich-data/api-key.txt"
LOG="${1:-/Users/szelenin/immich-data/import-progress.log}"

KEY=$(cat "$KEY_FILE")
prev_total=0
prev_ts=$(date +%s)

echo "Monitoring Immich at $API; logging to $LOG"
echo "timestamp,photos,videos,total,delta_per_min,meta_waiting,thumb_waiting,smart_waiting,face_waiting" > "$LOG"

while true; do
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  now=$(date +%s)

  stats=$(curl -sfm 5 -H "x-api-key: $KEY" "$API/api/server/statistics" 2>/dev/null || echo "{}")
  jobs=$(curl -sfm 5 -H "x-api-key: $KEY" "$API/api/jobs" 2>/dev/null || echo "{}")

  p=$(echo "$stats" | jq -r '.photos // 0')
  v=$(echo "$stats" | jq -r '.videos // 0')
  total=$(( p + v ))

  meta=$(echo "$jobs" | jq -r '.metadataExtraction.jobCounts.waiting // 0')
  thumb=$(echo "$jobs" | jq -r '.thumbnailGeneration.jobCounts.waiting // 0')
  smart=$(echo "$jobs" | jq -r '.smartSearch.jobCounts.waiting // 0')
  face=$(echo "$jobs" | jq -r '.faceDetection.jobCounts.waiting // 0')

  dt=$(( now - prev_ts ))
  if (( dt > 0 )); then
    delta_per_min=$(( (total - prev_total) * 60 / dt ))
  else
    delta_per_min=0
  fi

  echo "$ts,$p,$v,$total,$delta_per_min,$meta,$thumb,$smart,$face" >> "$LOG"
  printf "[%s] photos=%d videos=%d total=%d (%+d/min) | meta_q=%d thumb_q=%d smart_q=%d face_q=%d\n" \
    "$ts" "$p" "$v" "$total" "$delta_per_min" "$meta" "$thumb" "$smart" "$face"

  prev_total=$total
  prev_ts=$now
  sleep 60
done
