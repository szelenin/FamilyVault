#!/usr/bin/env bash
set -euo pipefail

RAID_PATH="${RAID_PATH:-/Volumes/HomeRAID}"
RAID_TIMEOUT="${RAID_TIMEOUT:-60}"
RAID_POLL_INTERVAL="${RAID_POLL_INTERVAL:-5}"

elapsed=0
echo "Waiting for RAID mount at $RAID_PATH (timeout: ${RAID_TIMEOUT}s)..."

while [ "$elapsed" -lt "$RAID_TIMEOUT" ]; do
  if [ -d "$RAID_PATH" ]; then
    echo "RAID mounted at $RAID_PATH"
    exit 0
  fi
  echo "  ...waiting ($elapsed/${RAID_TIMEOUT}s)"
  sleep "$RAID_POLL_INTERVAL"
  elapsed=$(( elapsed + RAID_POLL_INTERVAL ))
done

echo "ERROR: RAID not mounted at $RAID_PATH after ${RAID_TIMEOUT}s timeout. Aborting." >&2
exit 1
