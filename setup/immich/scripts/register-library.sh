#!/usr/bin/env bash
set -euo pipefail

IMMICH_URL="${IMMICH_URL:-http://localhost:2283}"
API_KEY_FILE="${API_KEY_FILE:-/Volumes/HomeRAID/immich/api-key.txt}"
LIBRARY_PATH="${LIBRARY_PATH:-/usr/src/app/icloud-export}"
SCAN_CRON="${SCAN_CRON:-0 0 * * *}"

if [ ! -f "$API_KEY_FILE" ]; then
  echo "ERROR: API key file not found at $API_KEY_FILE" >&2
  exit 1
fi

API_KEY=$(cat "$API_KEY_FILE")

auth_header() {
  echo "x-api-key: $API_KEY"
}

# Check if library already registered
echo "Checking for existing external library..."
EXISTING=$(curl -sf -H "$(auth_header)" "$IMMICH_URL/api/libraries" \
  | python3 -c "
import sys, json
libs = json.load(sys.stdin)
for lib in libs:
    paths = lib.get('importPaths', [])
    if any('icloud-export' in p for p in paths):
        print(lib['id'])
        exit(0)
exit(1)
" 2>/dev/null || echo "")

if [ -n "$EXISTING" ]; then
  echo "External library already registered (id: $EXISTING) — skipping"
  exit 0
fi

echo "Registering icloud-export as external library..."
LIB_ID=$(curl -sf -X POST "$IMMICH_URL/api/libraries" \
  -H "$(auth_header)" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"EXTERNAL\",
    \"name\": \"iCloud Export\",
    \"importPaths\": [\"$LIBRARY_PATH\"],
    \"cronExpression\": \"$SCAN_CRON\",
    \"exclusionPatterns\": []
  }" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Library registered (id: $LIB_ID). Triggering initial scan..."
curl -sf -X POST "$IMMICH_URL/api/libraries/$LIB_ID/scan" \
  -H "$(auth_header)" \
  > /dev/null

echo "Library registration complete. Daily scan scheduled: $SCAN_CRON"
