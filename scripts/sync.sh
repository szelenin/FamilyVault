#!/bin/bash
# sync.sh
# Incremental sync — picks up new/changed photos from iCloud since last run.
# Designed to run as a daily cron job or launchd task.
#
# To schedule via cron (runs daily at 2 AM):
#   crontab -e
#   0 2 * * * /Volumes/HomeRAID/scripts/sync.sh >> /Volumes/HomeRAID/sync.log 2>&1
#
# Usage: ./scripts/sync.sh [export-dir]

set -euo pipefail

EXPORT_DIR="${1:-/Volumes/HomeRAID/icloud-export}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

if [ ! -d "$EXPORT_DIR" ]; then
  echo "$LOG_PREFIX Error: export directory does not exist: $EXPORT_DIR"
  exit 1
fi

# Check Photos.app is running (required for osxphotos)
if ! pgrep -x "Photos" > /dev/null; then
  open -a Photos
  sleep 10
fi

echo "$LOG_PREFIX Starting incremental sync to $EXPORT_DIR"

osxphotos export "$EXPORT_DIR" \
  --directory "{folder_album}" \
  --exiftool \
  --update --ramdb \
  --export-edited --export-live --export-raw \
  --touch-file

echo "$LOG_PREFIX Sync complete"
