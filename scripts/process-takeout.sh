#!/bin/bash
# process-takeout.sh
# Extracts Google Takeout archives, fixes metadata, and finds Google-only
# files not present in the iCloud export (the delta).
#
# Usage: ./scripts/process-takeout.sh [takeout-dir] [processed-dir] [icloud-export-dir] [delta-dir]

set -euo pipefail

TAKEOUT_DIR="${1:-/Volumes/HomeRAID/google-takeout}"
PROCESSED_DIR="${2:-/Volumes/HomeRAID/google-processed}"
ICLOUD_DIR="${3:-/Volumes/HomeRAID/icloud-export}"
DELTA_DIR="${4:-/Volumes/HomeRAID/google-delta}"

mkdir -p "$PROCESSED_DIR" "$DELTA_DIR"

# Step 1: Extract all zip archives
echo "Extracting archives from $TAKEOUT_DIR..."
for f in "$TAKEOUT_DIR"/*.zip; do
  echo "  Extracting $f"
  unzip -o "$f" -d "$PROCESSED_DIR"
done

# Step 2: Fix metadata with gpth (GooglePhotosTakeoutHelper)
if ! command -v gpth &>/dev/null; then
  echo "Error: gpth not found. Download from https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper/releases"
  exit 1
fi

echo "Fixing metadata with gpth..."
gpth --input "$PROCESSED_DIR/Takeout/Google Photos" \
     --output "$PROCESSED_DIR/organized"

# Step 3: Find Google-only files using czkawka
if ! command -v czkawka_cli &>/dev/null; then
  echo "Error: czkawka not found. Install with: brew install czkawka"
  exit 1
fi

echo "Finding Google-only files (not in iCloud export)..."
echo "Results will be printed — manually review and move unique files to $DELTA_DIR"
czkawka_cli duplicates \
  -d "$PROCESSED_DIR/organized" \
  -d "$ICLOUD_DIR" \
  --search-method HASH \
  --hash-type Blake3

echo "Done. Review czkawka output above."
echo "Move Google-only files to: $DELTA_DIR"
echo "Then merge $DELTA_DIR into $ICLOUD_DIR"
