#!/usr/bin/env bash
# Best-effort snapshot of pre-wipe Immich state.
# For the record only — not used for restore. Tolerant of Immich being down.
set -euo pipefail

OUT="${1:-/tmp/immich-pre-wipe-state.json}"
API="http://localhost:2283"
KEY_FILE="/Volumes/HomeRAID/immich/api-key.txt"

echo "Writing snapshot to $OUT"

# Capture disk usage of old Immich paths (always works regardless of container state)
disk_usage=$(du -sh /Volumes/HomeRAID/immich/* 2>&1 | jq -Rs .)

# Capture container state
docker_ps=$(docker ps --format '{{.Names}}\t{{.Status}}' 2>&1 | grep -i immich | jq -Rs .)

# Capture API state if Immich responds
api_stats="null"
api_libraries="null"
if [[ -f "$KEY_FILE" ]]; then
  KEY=$(cat "$KEY_FILE")
  if curl -sfm 5 -H "x-api-key: $KEY" "$API/api/server/statistics" > /tmp/_stats.json 2>/dev/null; then
    api_stats=$(cat /tmp/_stats.json)
  fi
  if curl -sfm 5 -H "x-api-key: $KEY" "$API/api/libraries" > /tmp/_libs.json 2>/dev/null; then
    api_libraries=$(cat /tmp/_libs.json)
  fi
  rm -f /tmp/_stats.json /tmp/_libs.json
fi

cat <<EOF > "$OUT"
{
  "snapshot_taken": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "disk_usage": $disk_usage,
  "docker_immich_containers": $docker_ps,
  "api_server_statistics": $api_stats,
  "api_libraries": $api_libraries
}
EOF

echo "Snapshot written."
cat "$OUT" | jq . || cat "$OUT"
