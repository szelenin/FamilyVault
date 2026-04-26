#!/usr/bin/env bash
# Single-pass Google Takeout import via immich-go. Run inside tmux/screen.
set -euo pipefail

API="http://localhost:2283"
KEY_FILE="/Users/szelenin/immich-data/api-key.txt"
TAKEOUT_GLOB="/Volumes/HomeRAID/google-takeout/takeout-20260403T195541Z-3-*.zip"
LOG_FILE="/Users/szelenin/immich-data/immich-go.log"
SESSION_TAG="phase-1-google-$(date +%Y%m%d)"

if [[ ! -f "$KEY_FILE" ]]; then
  echo "API key not found at $KEY_FILE" >&2
  exit 1
fi

KEY=$(cat "$KEY_FILE")
zip_count=$(ls $TAKEOUT_GLOB 2>/dev/null | wc -l | tr -d ' ')
if [[ "$zip_count" != "49" ]]; then
  echo "Expected 49 photo-data zips matching $TAKEOUT_GLOB, found $zip_count" >&2
  exit 1
fi

echo "Starting immich-go import:"
echo "  zips:        $zip_count"
echo "  session-tag: $SESSION_TAG"
echo "  log-file:    $LOG_FILE"
echo "Hit Ctrl-C in the next 5 seconds to abort."
sleep 5

immich-go upload from-google-photos \
  --server="$API" \
  --api-key="$KEY" \
  --concurrent-tasks=4 \
  --client-timeout=60m \
  --pause-immich-jobs=true \
  --on-errors=continue \
  --session-tag="$SESSION_TAG" \
  --log-file="$LOG_FILE" \
  $TAKEOUT_GLOB

echo "immich-go finished. Resume Immich jobs with:"
echo "  curl -X PUT -H 'x-api-key: $KEY' '$API/api/jobs/{queue}/resume' (per queue)"
echo "Or via admin UI: Administration → Jobs → 'Resume All'"
