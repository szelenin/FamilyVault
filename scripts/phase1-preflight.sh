#!/usr/bin/env bash
# Pre-flight checks before kicking off the Phase 1 import.
# Exits 0 only if every check passes.
set -euo pipefail

API="http://localhost:2283"
KEY_FILE="/Users/szelenin/immich-data/api-key.txt"
TAKEOUT_DIR="/Volumes/HomeRAID/google-takeout"
MANIFEST="docs/architecture/google-takeout-manifest.json"

fail=0
log() { printf "%-40s %s\n" "$1" "$2"; }

# 1. RAID free space ≥ 3 TB
raid_avail_gb=$(df -g /Volumes/HomeRAID | awk 'NR==2{print $4}')
if (( raid_avail_gb >= 3000 )); then
  log "RAID free space:" "${raid_avail_gb} GB OK"
else
  log "RAID free space:" "${raid_avail_gb} GB FAIL (need ≥3000)"; fail=1
fi

# 2. Internal SSD free space ≥ 200 GB
int_avail_gb=$(df -g /Users/szelenin | awk 'NR==2{print $4}')
if (( int_avail_gb >= 200 )); then
  log "Internal SSD free space:" "${int_avail_gb} GB OK"
else
  log "Internal SSD free space:" "${int_avail_gb} GB FAIL (need ≥200)"; fail=1
fi

# 3. Immich responds with photos=0 videos=0
if [[ ! -f "$KEY_FILE" ]]; then
  log "Immich API key:" "MISSING ($KEY_FILE)"; fail=1
else
  KEY=$(cat "$KEY_FILE")
  resp=$(curl -sfm 5 -H "x-api-key: $KEY" "$API/api/server/statistics" || echo "")
  if [[ -z "$resp" ]]; then
    log "Immich API health:" "FAIL (no response)"; fail=1
  else
    p=$(echo "$resp" | jq -r .photos)
    v=$(echo "$resp" | jq -r .videos)
    if [[ "$p" == "0" && "$v" == "0" ]]; then
      log "Immich starting state:" "photos=0 videos=0 OK"
    else
      log "Immich starting state:" "photos=$p videos=$v FAIL (must be 0/0)"; fail=1
    fi
  fi
fi

# 4. immich-go installed
if command -v immich-go >/dev/null; then
  log "immich-go:" "$(immich-go --version 2>&1 | head -1) OK"
else
  log "immich-go:" "NOT INSTALLED FAIL"; fail=1
fi

# 5. Exactly 49 takeout zips on disk (the -3-NNN pattern, excluding metadata zip)
zip_count=$(find "$TAKEOUT_DIR" -name 'takeout-*-3-*.zip' -type f | wc -l | tr -d ' ')
if [[ "$zip_count" == "49" ]]; then
  log "Takeout zips on disk:" "49 OK"
else
  log "Takeout zips on disk:" "$zip_count FAIL (expected 49 photo-data zips, plus 1 metadata zip not counted)"; fail=1
fi

# 6. Manifest present
if [[ -f "$MANIFEST" ]]; then
  total=$(jq -r .total_files_in_html "$MANIFEST")
  log "Manifest present:" "$total entries OK"
else
  log "Manifest present:" "MISSING ($MANIFEST) FAIL"; fail=1
fi

# 7. Video transcoding disabled (best-effort — try to read system config)
if [[ -n "${KEY:-}" ]]; then
  conf=$(curl -sfm 5 -H "x-api-key: $KEY" "$API/api/system-config" 2>/dev/null || echo "{}")
  policy=$(echo "$conf" | jq -r '.ffmpeg.transcode // "unknown"')
  if [[ "$policy" == "disabled" ]]; then
    log "Video transcoding policy:" "disabled OK"
  else
    log "Video transcoding policy:" "$policy WARN (recommended: disabled)"
  fi
fi

if (( fail == 0 )); then
  echo "ALL CHECKS PASSED."
else
  echo "PRE-FLIGHT FAILED — fix issues above before starting import." >&2
  exit 1
fi
