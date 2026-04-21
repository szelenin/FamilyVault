#!/bin/bash
# export-icloud.sh
# Full or incremental export from Photos.app (iCloud) to the RAID.
# On first run: exports everything. On subsequent runs: only new/changed photos.
#
# Fixes applied (IMP-011):
#   - Explicit --library path avoids ambiguous library detection
#   - --update-errors re-exports previously failed files
#   - --fix-orientation corrects rotation metadata
#   - --exiftool-option '-m' ignores minor exiftool errors (avoids aborts on bad metadata)
#   - Report + log files for audit trail
#
# Usage: ./scripts/export-icloud.sh [export-dir] [library-path]

set -euo pipefail

EXPORT_DIR="${1:-/Volumes/HomeRAID/icloud-export}"
LIBRARY="${2:-/Volumes/HomeRAID/Photos Library.photoslibrary}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

if [ ! -d "$EXPORT_DIR" ]; then
  echo "Error: export directory does not exist: $EXPORT_DIR"
  exit 1
fi

if [ ! -d "$LIBRARY" ]; then
  echo "Error: Photos Library not found: $LIBRARY"
  echo "Pass the correct path as second argument."
  exit 1
fi

echo "Exporting iCloud Photos to: $EXPORT_DIR"
echo "Library: $LIBRARY"
echo "Started at: $(date)"

osxphotos export "$EXPORT_DIR" \
  --library "$LIBRARY" \
  --directory "{folder_album}" \
  --exiftool \
  --exiftool-option '-m' \
  --sidecar xmp --sidecar json \
  --person-keyword --album-keyword \
  --update --update-errors \
  --touch-file \
  --fix-orientation \
  --report "$EXPORT_DIR/export-report-${TIMESTAMP}.csv" \
  --verbose \
  2>&1 | tee "$EXPORT_DIR/osxphotos-export-${TIMESTAMP}.log"

echo "Finished at: $(date)"
echo "Report: $EXPORT_DIR/export-report-${TIMESTAMP}.csv"
echo "Log:    $EXPORT_DIR/osxphotos-export-${TIMESTAMP}.log"
