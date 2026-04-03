#!/bin/bash
# export-icloud.sh
# Full or incremental export from Photos.app (iCloud) to the RAID.
# On first run: exports everything. On subsequent runs: only new/changed photos.
#
# Usage: ./scripts/export-icloud.sh /Volumes/HomeRAID/icloud-export

set -euo pipefail

EXPORT_DIR="${1:-/Volumes/HomeRAID/icloud-export}"

if [ ! -d "$EXPORT_DIR" ]; then
  echo "Error: export directory does not exist: $EXPORT_DIR"
  exit 1
fi

echo "Exporting iCloud Photos to: $EXPORT_DIR"
echo "Started at: $(date)"

osxphotos export "$EXPORT_DIR" \
  --directory "{folder_album}" \
  --exiftool \
  --sidecar xmp --sidecar json \
  --person-keyword --album-keyword \
  --update --ramdb \
  --export-edited --export-live --export-raw --export-bursts \
  --touch-file \
  --verbose

echo "Finished at: $(date)"
