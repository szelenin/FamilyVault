#!/bin/bash
# sync.sh
# Incremental sync — picks up new/changed photos from iCloud since last run.
# Designed to run as a daily cron job or launchd task.
#
# To schedule via cron (runs daily at 2 AM):
#   crontab -e
#   0 2 * * * /Volumes/HomeRAID/scripts/sync.sh >> /Volumes/HomeRAID/sync.log 2>&1
#
# Usage: ./scripts/sync.sh [export-dir] [library-path]

set -euo pipefail

EXPORT_DIR="${1:-/Volumes/HomeRAID/icloud-export}"
LIBRARY="${2:-/Volumes/HomeRAID/Photos Library.photoslibrary}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

if [ ! -d "$EXPORT_DIR" ]; then
  echo "$LOG_PREFIX Error: export directory does not exist: $EXPORT_DIR"
  exit 1
fi

if [ ! -d "$LIBRARY" ]; then
  echo "$LOG_PREFIX Error: Photos Library not found: $LIBRARY"
  exit 1
fi

# Check Photos.app is running (required for osxphotos)
if ! pgrep -x "Photos" > /dev/null; then
  open -a Photos
  sleep 10
fi

echo "$LOG_PREFIX Starting incremental sync to $EXPORT_DIR"

osxphotos export "$EXPORT_DIR" \
  --library "$LIBRARY" \
  --directory "{folder_album}" \
  --exiftool \
  --exiftool-option '-m' \
  --update --update-errors \
  --touch-file \
  --fix-orientation \
  --report "$EXPORT_DIR/sync-report-${TIMESTAMP}.csv" \
  --verbose \
  2>&1 | tee "$EXPORT_DIR/osxphotos-sync-${TIMESTAMP}.log"

echo "$LOG_PREFIX Sync complete"
echo "$LOG_PREFIX Report: $EXPORT_DIR/sync-report-${TIMESTAMP}.csv"
