#!/bin/bash
# download-takeout.sh
# Downloads Google Takeout archives from Google Drive using rclone.
# Requires rclone configured with a Google Drive remote (run: rclone config).
#
# Usage: ./scripts/download-takeout.sh [rclone-remote-name] [local-destination]
# Example: ./scripts/download-takeout.sh gdrive /Volumes/HomeRAID/google-takeout

set -euo pipefail

REMOTE="${1:-gdrive}"
DEST="${2:-/Volumes/HomeRAID/google-takeout}"

if ! command -v rclone &>/dev/null; then
  echo "Error: rclone not found. Install with: brew install rclone"
  exit 1
fi

if ! rclone lsd "${REMOTE}:" 2>/dev/null | grep -q "Takeout"; then
  echo "Error: No 'Takeout' folder found in ${REMOTE}:"
  echo "Make sure your Google Takeout export is complete and delivered to Google Drive."
  exit 1
fi

mkdir -p "$DEST"

echo "Downloading Google Takeout from ${REMOTE}:Takeout to $DEST"
echo "Started at: $(date)"

rclone copy "${REMOTE}:Takeout" "$DEST" \
  --progress \
  --transfers 4 \
  --checkers 8 \
  --drive-chunk-size 128M \
  --retries 10 \
  --low-level-retries 20

echo "Finished at: $(date)"
echo "Downloaded to: $DEST"
