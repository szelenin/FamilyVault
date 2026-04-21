#!/bin/bash
# create-test-fixtures.sh
# Cherry-picks representative assets from the Photos Library for each export test case
# and exports them to a small, isolated test directory.
#
# Run this on Mac Mini BEFORE the full export to validate the export command is correct.
#
# Test cases covered:
#   Case A: ProRAW photo  — DNG exported WITH processed HEIC sibling
#   Case B: Shared copy   — "(1)" file without GPS gets GPS inferred
#   Case C: Portrait      — Orientation EXIF is correct after --fix-orientation
#   Case D: Sidecars      — XMP + JSON sidecars created for every asset
#   Case E: Video         — MOV/MP4 exported with metadata
#
# Usage: ./scripts/create-test-fixtures.sh [library-path] [output-dir]

set -euo pipefail

LIBRARY="${1:-/Volumes/HomeRAID/Photos Library.photoslibrary}"
OUT_DIR="${2:-/tmp/icloud-test-fixtures}"
N_PER_CASE=2  # how many assets to pick per test case

if [ ! -d "$LIBRARY" ]; then
  echo "Error: Photos Library not found: $LIBRARY"
  echo "Pass the correct path as first argument."
  exit 1
fi

mkdir -p "$OUT_DIR"
echo "=== Creating test fixtures in: $OUT_DIR ==="
echo "Library: $LIBRARY"
echo ""

# ---------------------------------------------------------------
# Step 1: Query UUIDs for each test case
# ---------------------------------------------------------------

echo "--- Finding test assets via osxphotos query ---"

# Case A: ProRAW photos (has a paired RAW file in Photos.app)
echo "Case A: ProRAW photos..."
UUID_PRORAW=$(osxphotos query --library "$LIBRARY" --json --has-raw 2>/dev/null \
  | python3 -c "import sys,json; data=json.load(sys.stdin); [print(d['uuid']) for d in data[:$N_PER_CASE]]" 2>/dev/null || true)

if [ -z "$UUID_PRORAW" ]; then
  echo "  WARNING: No ProRAW photos found. Case A will be skipped."
else
  echo "  Found UUIDs: $(echo "$UUID_PRORAW" | tr '\n' ' ')"
fi

# Case B: Shared-library copies without GPS — MUST have "(1)" in filename.
# infer-gps.py only processes files with "(1)" suffix; other GPS-less files won't be touched.
echo "Case B: Shared-library copies (filename contains '(1)') without GPS..."
UUID_NO_GPS=$(osxphotos query --library "$LIBRARY" --json --no-location 2>/dev/null \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
shared = [d for d in data if '(1)' in d.get('original_filename', '')]
[print(d['uuid']) for d in shared[:$N_PER_CASE]]
" 2>/dev/null || true)

# Fallback: if no "(1)" files found without GPS, pick any "(1)" file (even with GPS) to
# confirm osxphotos exports shared copies at all — and mark GPS test as SKIP
if [ -z "$UUID_NO_GPS" ]; then
  echo "  WARNING: No GPS-less '(1)' files found. Trying any '(1)' file..."
  UUID_NO_GPS=$(osxphotos query --library "$LIBRARY" --json 2>/dev/null \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
shared = [d for d in data if '(1)' in d.get('original_filename', '')]
[print(d['uuid']) for d in shared[:$N_PER_CASE]]
" 2>/dev/null || true)
  [ -n "$UUID_NO_GPS" ] && echo "  NOTE: These '(1)' files may already have GPS — Case B GPS check may SKIP"
fi

if [ -z "$UUID_NO_GPS" ]; then
  echo "  WARNING: No GPS-less photos found. Case B will be skipped."
else
  echo "  Found UUIDs: $(echo "$UUID_NO_GPS" | tr '\n' ' ')"
fi

# Case C: Portrait photos (height > width — likely need orientation fix)
echo "Case C: Portrait photos..."
UUID_PORTRAIT=$(osxphotos query --library "$LIBRARY" --json --portrait 2>/dev/null \
  | python3 -c "import sys,json; data=json.load(sys.stdin); [print(d['uuid']) for d in data[:$N_PER_CASE]]" 2>/dev/null || true)

if [ -z "$UUID_PORTRAIT" ]; then
  # Fallback: shared-library "(1)" photos are most likely to have had orientation issues
  echo "  Fallback: picking shared-library '(1)' photos for Case C orientation check..."
  UUID_PORTRAIT=$(osxphotos query --library "$LIBRARY" --json 2>/dev/null \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
shared = [d for d in data if '(1)' in d.get('original_filename', '') and d.get('media_type') == 'image']
[print(d['uuid']) for d in shared[:$N_PER_CASE]]
" 2>/dev/null || true)
fi

if [ -z "$UUID_PORTRAIT" ]; then
  echo "  WARNING: Could not find portrait or '(1)' photos. Case C will be SKIPPED."
else
  echo "  Found UUIDs: $(echo "$UUID_PORTRAIT" | tr '\n' ' ')"
fi

# Case E: Videos
echo "Case E: Videos..."
UUID_VIDEO=$(osxphotos query --library "$LIBRARY" --json --only-movies 2>/dev/null \
  | python3 -c "import sys,json; data=json.load(sys.stdin); [print(d['uuid']) for d in data[:$N_PER_CASE]]" 2>/dev/null || true)

if [ -z "$UUID_VIDEO" ]; then
  echo "  WARNING: No videos found. Case E will be skipped."
else
  echo "  Found UUIDs: $(echo "$UUID_VIDEO" | tr '\n' ' ')"
fi

# Combine all UUIDs (deduplicated)
ALL_UUIDS=$(echo -e "$UUID_PRORAW\n$UUID_NO_GPS\n$UUID_PORTRAIT\n$UUID_VIDEO" \
  | sort -u | grep -v '^$' | tr '\n' ' ')

if [ -z "$ALL_UUIDS" ]; then
  echo "ERROR: No assets found for any test case. Check that osxphotos can access the library."
  exit 1
fi

TOTAL_UUIDS=$(echo "$ALL_UUIDS" | wc -w | tr -d ' ')
echo ""
echo "Total unique assets to export: $TOTAL_UUIDS"
echo ""

# ---------------------------------------------------------------
# Step 2: Export the cherry-picked assets
# ---------------------------------------------------------------

echo "--- Exporting test fixtures ---"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# shellcheck disable=SC2086
osxphotos export "$OUT_DIR" \
  --library "$LIBRARY" \
  --uuid $ALL_UUIDS \
  --directory "{folder_album}" \
  --exiftool \
  --exiftool-option '-m' \
  --sidecar xmp --sidecar json \
  --person-keyword --album-keyword \
  --touch-file \
  --fix-orientation \
  --report "$OUT_DIR/fixture-report-${TIMESTAMP}.csv" \
  --verbose

echo ""
echo "=== Export complete ==="
echo "Output: $OUT_DIR"
echo ""

# ---------------------------------------------------------------
# Step 3: Print a summary of what was exported
# ---------------------------------------------------------------

echo "--- Files exported ---"
find "$OUT_DIR" -type f | sort | while read -r f; do
  ext="${f##*.}"
  echo "  [$ext] $(basename "$f")"
done

echo ""
echo "--- Test asset map ---"
echo "Case A (ProRAW): look for .DNG files and their .HEIC siblings above"
echo "Case B (no GPS): look for filenames ending in ' (1)' above"
echo "Case C (portrait): any HEIC/JPG file — check orientation in Immich or Preview"
echo "Case D (sidecars): look for .xmp and .json files alongside each media file"
echo "Case E (video): look for .mov or .mp4 files above"
echo ""
echo "Next step: run ./scripts/verify-test-fixtures.sh $OUT_DIR"
