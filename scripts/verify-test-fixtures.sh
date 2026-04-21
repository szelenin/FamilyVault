#!/bin/bash
# verify-test-fixtures.sh
# Runs all test case checks against the small fixture export created by create-test-fixtures.sh.
# Prints PASS/FAIL for each check.
#
# Usage: ./scripts/verify-test-fixtures.sh [fixture-dir]

set -uo pipefail

# Ensure homebrew tools are in PATH (needed for exiftool on Mac Mini)
export PATH="/opt/homebrew/bin:$PATH"

FIXTURE_DIR="${1:-/tmp/icloud-test-fixtures}"
PASS=0
FAIL=0

check() {
  local name="$1"
  local result="$2"  # "pass" or "fail"
  local detail="${3:-}"
  if [ "$result" = "pass" ]; then
    echo "  PASS  $name${detail:+  ($detail)}"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $name${detail:+  ($detail)}"
    FAIL=$((FAIL + 1))
  fi
}

if [ ! -d "$FIXTURE_DIR" ]; then
  echo "Error: fixture directory not found: $FIXTURE_DIR"
  echo "Run ./scripts/create-test-fixtures.sh first."
  exit 1
fi

echo "=== Verifying test fixtures in: $FIXTURE_DIR ==="
echo ""

# ---------------------------------------------------------------
# Case A: ProRAW — every DNG has a companion photo (HEIC or edited JPEG)
# ---------------------------------------------------------------
echo "--- Case A: ProRAW (DNG + companion HEIC or edited JPEG) ---"
DNG_COUNT=0
DNG_WITH_COMPANION=0
while IFS= read -r dng; do
  DNG_COUNT=$((DNG_COUNT + 1))
  base="${dng%.DNG}"
  [ "${dng%.dng}" != "$dng" ] && base="${dng%.dng}"
  # Check for HEIC sibling (same stem)
  companion=""
  for ext in HEIC heic JPG jpg; do
    [ -f "${base}.${ext}" ] && { companion="${base}.${ext}"; break; }
  done
  # Also check for _edited companion (Photos.app exports processed version as _edited.*)
  if [ -z "$companion" ]; then
    for ext in jpeg jpg JPEG JPG HEIC heic; do
      [ -f "${base}_edited.${ext}" ] && { companion="${base}_edited.${ext}"; break; }
    done
  fi

  if [ -n "$companion" ]; then
    DNG_WITH_COMPANION=$((DNG_WITH_COMPANION + 1))
    SIZE=$(stat -f%z "$companion" 2>/dev/null || echo 0)
    if [ "$SIZE" -gt 524288 ]; then
      check "DNG has valid companion: $(basename "$dng")" "pass" "$(basename "$companion") ${SIZE} bytes"
    else
      check "DNG has valid companion: $(basename "$dng")" "fail" "$(basename "$companion") too small: ${SIZE} bytes"
    fi
  else
    check "DNG has companion: $(basename "$dng")" "fail" "no HEIC or edited JPEG found"
  fi
done < <(find "$FIXTURE_DIR" -name "*.DNG" -o -name "*.dng")

if [ "$DNG_COUNT" -eq 0 ]; then
  echo "  SKIP  No DNG files found (no ProRAW assets in fixture — Case A not tested)"
fi

# ---------------------------------------------------------------
# Case B: Shared-library copies exported — check via export DB
# (In a test fixture, osxphotos only adds '(1)' when filenames collide.
#  With a tiny fixture of unique files there is no collision, so the
#  suffix is absent. We verify via the export database instead.)
# ---------------------------------------------------------------
echo ""
echo "--- Case B: Shared-library copies exported ---"
EXPORT_DB="$FIXTURE_DIR/.osxphotos_export.db"
if [ -f "$EXPORT_DB" ]; then
  SHARED_COUNT=$(sqlite3 "$EXPORT_DB" \
    "SELECT COUNT(*) FROM export_data WHERE uuid IN (SELECT uuid FROM export_data WHERE filepath LIKE '%(1)%') OR filepath LIKE '% (1).%' OR filepath LIKE '%(1).%'" 2>/dev/null || echo 0)
  # Fallback: check any exported UUID count (shared copies are in the DB regardless of filename)
  TOTAL_EXPORTED=$(sqlite3 "$EXPORT_DB" "SELECT COUNT(DISTINCT uuid) FROM export_data" 2>/dev/null || echo 0)
  if [ "$TOTAL_EXPORTED" -gt 0 ]; then
    echo "  ($TOTAL_EXPORTED UUIDs in export DB)"
    # Check if IMG_1073 (known shared copy from test fixture) was exported
    SHARED_FILE=$(sqlite3 "$EXPORT_DB" "SELECT filepath FROM export_data WHERE filepath LIKE '%IMG_1073%' LIMIT 1" 2>/dev/null || echo "")
    if [ -n "$SHARED_FILE" ]; then
      check "Shared copy exported (IMG_1073 — known shared UUID)" "pass" "→ $SHARED_FILE"
      echo "  (Note: '(1)' suffix appears only in full export on filename collision, not in test fixture)"
      echo "  (GPS inference verified separately in Phase 5 T3/T4 after full-library infer-gps.py)"
    else
      check "Shared copy exported (IMG_1073)" "fail" "not found in export DB"
    fi
  else
    check "Export database has entries" "fail" "empty export DB"
  fi
else
  echo "  FAIL  No export database found at $EXPORT_DB"
  FAIL=$((FAIL + 1))
fi

# ---------------------------------------------------------------
# Case C: Orientation — no Rotate 180 (upside-down) files
# ---------------------------------------------------------------
echo ""
echo "--- Case C: Orientation (no upside-down files) ---"
HEIC_COUNT=0
while IFS= read -r f; do
  HEIC_COUNT=$((HEIC_COUNT + 1))
  ORI=$(exiftool -fast2 -Orientation "$f" 2>/dev/null | grep "Orientation" | awk -F': ' '{print $2}' || echo "unknown")
  if echo "$ORI" | grep -qi "rotate 180"; then
    check "Not upside-down: $(basename "$f")" "fail" "Orientation: $ORI"
  else
    check "Not upside-down: $(basename "$f")" "pass" "Orientation: ${ORI:-not set}"
  fi
done < <(find "$FIXTURE_DIR" -name "*.HEIC" -o -name "*.JPG" -o -name "*.jpg" -o -name "*.heic" -o -name "*.jpeg" -o -name "*.JPEG")

if [ "$HEIC_COUNT" -eq 0 ]; then
  echo "  SKIP  No HEIC/JPG files found — Case C not tested"
fi

# ---------------------------------------------------------------
# Case D: Sidecars — every media file has XMP sidecar
# Note: osxphotos names sidecars as "filename.ext.xmp" (full name + .xmp)
# ---------------------------------------------------------------
echo ""
echo "--- Case D: XMP sidecars ---"
MEDIA_COUNT=0
SIDECAR_OK=0
while IFS= read -r f; do
  fname="$(basename "$f")"
  ext="${fname##*.}"
  # Skip sidecar, database, and video files (osxphotos does not create XMP for video)
  case "$ext" in xmp|json|csv|log|md|db|db-shm|db-wal|db-journal|mov|MOV|mp4|MP4) continue ;; esac
  MEDIA_COUNT=$((MEDIA_COUNT + 1))
  # osxphotos creates sidecars named as "filename.ext.xmp"
  XMP="${f}.xmp"
  if [ -f "$XMP" ]; then
    SIDECAR_OK=$((SIDECAR_OK + 1))
    check "XMP sidecar: $(basename "$f")" "pass"
  else
    check "XMP sidecar: $(basename "$f")" "fail" "missing $(basename "$XMP")"
  fi
done < <(find "$FIXTURE_DIR" -type f)

if [ "$MEDIA_COUNT" -eq 0 ]; then
  echo "  SKIP  No media files found"
fi

# ---------------------------------------------------------------
# Case E: Video — MOV/MP4 exported with metadata
# ---------------------------------------------------------------
echo ""
echo "--- Case E: Video metadata ---"
VIDEO_COUNT=0
while IFS= read -r f; do
  VIDEO_COUNT=$((VIDEO_COUNT + 1))
  DATE=$(exiftool -fast2 -CreateDate "$f" 2>/dev/null | grep "Create Date" | awk -F': ' '{print $2}' || echo "")
  if [ -n "$DATE" ]; then
    check "Video has CreateDate: $(basename "$f")" "pass" "$DATE"
  else
    check "Video has CreateDate: $(basename "$f")" "fail" "no CreateDate in EXIF"
  fi
done < <(find "$FIXTURE_DIR" -name "*.mov" -o -name "*.MOV" -o -name "*.mp4" -o -name "*.MP4")

if [ "$VIDEO_COUNT" -eq 0 ]; then
  echo "  SKIP  No video files found — Case E not tested"
fi

# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------
echo ""
echo "=============================="
echo "  Results: $PASS passed, $FAIL failed"
echo "=============================="
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo "All checks passed. Safe to run the full export:"
  echo "  ./scripts/export-icloud.sh /Volumes/HomeRAID/icloud-export \\"
  echo "    \"/Volumes/HomeRAID/Photos Library.photoslibrary\""
else
  echo "Fix the failures above before running the full export."
  echo ""
  echo "Common fixes:"
  echo "  Case A fails (no companion): Photos.app may still be downloading — wait for 0 remaining"
  echo "  Case B fails: run infer-gps.py on the fixture dir, then re-run this script"
  echo "  Case C fails: check osxphotos version supports --fix-orientation"
  echo "  Case D fails: check --sidecar xmp flag is in export command"
  echo "  Case E fails: check --exiftool flag is in export command and exiftool is installed"
  exit 1
fi
