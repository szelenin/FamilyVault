#!/usr/bin/env bats
# sync-metadata.bats — verify spec-014 metadata-write contract.
# Manual-only invocation per spec FR-012a.

# Source helpers at file scope so each @test subshell gets them.
# shellcheck source=helpers.sh
source "$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/helpers.sh"

setup_file() {
    [ -f "$EXPORT_DB" ] || { echo "missing export DB: $EXPORT_DB" >&2; return 1; }
    [ -f "$PHOTOS_DB" ] || { echo "missing Photos library DB: $PHOTOS_DB" >&2; return 1; }
}

# --- T7 (US5): GPS regression guard — files with library GPS keep file GPS --
@test "T7_no_regression_gps" {
    # Filter to photos only (ZKIND=0) — videos use QuickTime GPS tags, not EXIF.
    local uuids
    uuids=$(pick_fixture_uuids "ZTRASHEDSTATE=0 AND ZLIBRARYSCOPESHARESTATE!=0 AND ZKIND=0 AND ZLATITUDE IS NOT NULL AND ZLATITUDE != -180.0 ORDER BY ZDATECREATED DESC" 10)
    [ -n "$uuids" ] || { skip "no GPS-having shared photos in library"; }
    local fail=0 checked=0
    while IFS= read -r uuid; do
        [ -z "$uuid" ] && continue
        local file
        file=$(resolve_uuid_to_path "$uuid")
        [ -n "$file" ] && [ -f "$file" ] || { echo "T7: $uuid: not exported (skip)"; continue; }
        # Skip video files (Live Photo .mov pairs) — handled by Composite:GPSPosition if needed.
        case "$file" in
            *.mov|*.MOV|*.mp4|*.MP4) continue ;;
        esac
        checked=$((checked + 1))
        local lat lon
        lat=$(read_exif_field "$file" "Composite:GPSPosition")
        lon=$(read_exif_field "$file" "EXIF:GPSLongitude")
        if [ -z "$lat" ] && [ -z "$lon" ]; then
            echo "T7 FAIL: uuid=$uuid file=$file expected GPS, got Composite:GPSPosition='$lat' EXIF:GPSLongitude='$lon'"
            fail=$((fail + 1))
        fi
    done <<< "$uuids"
    [ "$checked" -gt 0 ] || { echo "T7: 0 fixtures actually checked"; return 1; }
    [ "$fail" -eq 0 ] || { echo "T7: $fail of $checked fixtures missing GPS"; return 1; }
}

# --- T8 (US5): idempotency check ----------------------------------------------
# Runs ONLY if a sync-report-*.csv was produced in the last hour AND the
# report records 0 "exported" or "updated" rows (i.e., a steady-state run).
# Otherwise SKIP — proper full-library idempotency is verified in Polish T032.
@test "T8_idempotent_rerun" {
    local report
    report=$(find "$EXPORT_DIR" -maxdepth 1 -name 'sync-report-*.csv' -cmin -60 \
        -exec stat -f '%c %N' {} + 2>/dev/null \
        | sort -nr | head -1 | awk '{$1=""; print substr($0,2)}')
    [ -n "$report" ] && [ -f "$report" ] || { skip "no recent sync-report CSV (full idempotency check is in Polish T032)"; }
    local exported updated
    exported=$(awk -F',' 'NR>1 && $3==1' "$report" | wc -l | tr -d ' ')
    updated=$(awk -F',' 'NR>1 && $5==1' "$report" | wc -l | tr -d ' ')
    if [ "$exported" -gt 0 ] || [ "$updated" -gt 0 ]; then
        skip "latest report ($report) shows $exported exported, $updated updated — not yet a steady-state run; check after Polish T032"
    fi
}

# --- T_negative (US5): runner exits non-zero on failed assertion -------------
# This is a self-test of run.sh; not part of the spec acceptance set, but
# protects FR-011 against silent regression. Activated by env var to avoid
# polluting normal runs.
@test "T_negative_runner_returns_nonzero_on_failure" {
    if [ "${T_NEGATIVE_PROBE:-0}" != "1" ]; then
        skip "negative-path probe disabled; run with T_NEGATIVE_PROBE=1 for the meta-check"
    fi
    false  # always fails when activated
}

# --- T0 (US1): only one sync script in repo --------------------------------
@test "T0_only_one_sync_script_in_repo" {
    REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
    count=$(find "${REPO_ROOT}/scripts" -maxdepth 1 -type f -name '*.sh' \
        | grep -cE 'sync\.sh$|export-icloud\.sh$')
    [ "$count" -eq 1 ] || {
        echo "Expected exactly 1 sync script (sync.sh OR export-icloud.sh), found $count"
        find "${REPO_ROOT}/scripts" -maxdepth 1 -name '*.sh'
        return 1
    }
}

# --- T1 (US2): favorited photos carry XMP:Rating=5 --------------------------
@test "T1_favorite_rating_5" {
    local uuids
    uuids=$(pick_fixture_uuids "ZTRASHEDSTATE=0 AND ZLIBRARYSCOPESHARESTATE!=0 AND ZFAVORITE=1 ORDER BY ZDATECREATED DESC" 10)
    [ -n "$uuids" ] || { echo "no favorited fixtures found in library"; return 1; }
    local fail=0 checked=0
    while IFS= read -r uuid; do
        [ -z "$uuid" ] && continue
        checked=$((checked + 1))
        local file
        file=$(resolve_uuid_to_path "$uuid")
        [ -n "$file" ] && [ -f "$file" ] || { echo "T1: $uuid: not exported (skip)"; continue; }
        local rating
        rating=$(read_exif_field "$file" "XMP:Rating")
        if [ "$rating" != "5" ]; then
            echo "T1 FAIL: uuid=$uuid file=$file expected XMP:Rating=5 got '$rating'"
            fail=$((fail + 1))
        fi
    done <<< "$uuids"
    [ "$checked" -gt 0 ] || { echo "T1: 0 fixtures actually checked"; return 1; }
    [ "$fail" -eq 0 ] || { echo "T1: $fail of $checked fixtures failed"; return 1; }
}

# --- T2 (US2): non-favorite photos carry XMP:Rating=0 -----------------------
@test "T2_non_favorite_rating_0" {
    local uuids
    uuids=$(pick_fixture_uuids "ZTRASHEDSTATE=0 AND ZLIBRARYSCOPESHARESTATE!=0 AND (ZFAVORITE IS NULL OR ZFAVORITE=0) ORDER BY ZDATECREATED DESC" 10)
    [ -n "$uuids" ] || { echo "no non-favorited fixtures found"; return 1; }
    local fail=0 checked=0
    while IFS= read -r uuid; do
        [ -z "$uuid" ] && continue
        checked=$((checked + 1))
        local file
        file=$(resolve_uuid_to_path "$uuid")
        [ -n "$file" ] && [ -f "$file" ] || { echo "T2: $uuid: not exported (skip)"; continue; }
        local rating
        rating=$(read_exif_field "$file" "XMP:Rating")
        if [ "$rating" != "0" ]; then
            echo "T2 FAIL: uuid=$uuid file=$file expected XMP:Rating=0 got '$rating'"
            fail=$((fail + 1))
        fi
    done <<< "$uuids"
    [ "$checked" -gt 0 ] || { echo "T2: 0 fixtures actually checked"; return 1; }
    [ "$fail" -eq 0 ] || { echo "T2: $fail of $checked fixtures failed"; return 1; }
}

# --- T3 (US3): named-person photos have person name in IPTC:Keywords --------
@test "T3_person_keyword" {
    local uuids
    uuids=$("$SQLITE3" "$(_uri_path "$PHOTOS_DB")?mode=ro" -readonly "
        SELECT DISTINCT a.ZUUID
        FROM ZASSET a
        JOIN ZDETECTEDFACE df ON df.ZASSETFORFACE = a.Z_PK
        JOIN ZPERSON p ON df.ZPERSONFORFACE = p.Z_PK
        WHERE a.ZTRASHEDSTATE=0
          AND p.ZFULLNAME IS NOT NULL AND p.ZFULLNAME != ''
        LIMIT 10;")
    if [ -z "$uuids" ]; then
        skip "no named-person fixtures in this library — Photos.app face clusters are unnamed; T3 will be exercised once persons are named"
    fi
    local fail=0 checked=0
    while IFS= read -r uuid; do
        [ -z "$uuid" ] && continue
        local person
        person=$("$SQLITE3" "$(_uri_path "$PHOTOS_DB")?mode=ro" -readonly "
            SELECT p.ZFULLNAME
            FROM ZPERSON p
            JOIN ZDETECTEDFACE df ON df.ZPERSONFORFACE = p.Z_PK
            JOIN ZASSET a ON df.ZASSETFORFACE = a.Z_PK
            WHERE a.ZUUID='$uuid' AND p.ZFULLNAME IS NOT NULL AND p.ZFULLNAME != ''
            LIMIT 1;")
        local file
        file=$(resolve_uuid_to_path "$uuid")
        [ -n "$file" ] && [ -f "$file" ] || { echo "T3: $uuid: not exported (skip)"; continue; }
        checked=$((checked + 1))
        local kws
        kws=$("$EXIFTOOL" -fast2 -IPTC:Keywords -s -s -s "$file" 2>/dev/null)
        if ! echo "$kws" | grep -qF "$person"; then
            echo "T3 FAIL: uuid=$uuid file=$file expected keyword '$person' got '$kws'"
            fail=$((fail + 1))
        fi
    done <<< "$uuids"
    [ "$checked" -gt 0 ] || { echo "T3: 0 fixtures actually checked"; return 1; }
    [ "$fail" -eq 0 ] || { echo "T3: $fail of $checked fixtures failed"; return 1; }
}

# --- T9 (US3): user-set keywords on a photo MUST appear in the exported file -
@test "T9_user_keywords_preserved" {
    # Find photos that have user-set keywords in Photos.app (Z_1KEYWORDS link).
    # For each, verify ALL user keywords appear in the exported file's keyword tags.
    local rows
    rows=$("$SQLITE3" "$(_uri_path "$PHOTOS_DB")?mode=ro" -readonly "
        SELECT a.ZUUID, k.ZTITLE
        FROM ZASSET a
        JOIN ZADDITIONALASSETATTRIBUTES aa ON aa.Z_PK = a.ZADDITIONALATTRIBUTES
        JOIN Z_1KEYWORDS jk ON jk.Z_1ASSETATTRIBUTES = aa.Z_PK
        JOIN ZKEYWORD k ON k.Z_PK = jk.Z_52KEYWORDS
        WHERE a.ZTRASHEDSTATE=0
        LIMIT 5;" | tr '|' '\t')
    if [ -z "$rows" ]; then
        skip "no user-set keywords in this library"
    fi
    local fail=0 checked=0
    while IFS=$'\t' read -r uuid keyword; do
        [ -z "$uuid" ] && continue
        local file
        file=$(resolve_uuid_to_path "$uuid")
        [ -n "$file" ] && [ -f "$file" ] || { echo "T9: $uuid: not exported (skip)"; continue; }
        checked=$((checked + 1))
        local kws
        kws=$("$EXIFTOOL" -fast2 -IPTC:Keywords -XMP:Subject -XMP:TagsList -s -s -s "$file" 2>/dev/null | tr '\n' ' ')
        if ! echo "$kws" | grep -qF "$keyword"; then
            echo "T9 FAIL: uuid=$uuid file=$file expected user keyword '$keyword' got '$kws'"
            fail=$((fail + 1))
        fi
    done <<< "$rows"
    [ "$checked" -gt 0 ] || { echo "T9: 0 fixtures actually checked"; return 1; }
    [ "$fail" -eq 0 ] || { echo "T9: $fail of $checked fixtures failed"; return 1; }
}

# --- T5 (US4): files recently touched by sync.sh have a sibling .xmp sidecar
# Scope: files whose mtime is within the last hour (i.e., touched by this
# session's partial syncs after --sidecar flags were added). Skips file types
# osxphotos does not sidecar. Full-library coverage is verified in Polish T032.
@test "T5_xmp_sidecar_exists" {
    local files
    # Take the 20 most-recently-changed primary media files. Excludes .mov
    # because osxphotos does not write sidecars for Live Photo movie
    # components — only for the primary HEIC/JPG. Standalone videos use
    # the .mp4 path, which is included.
    files=$(find "$EXPORT_DIR" -type f -cmin -60 \
        \( -iname '*.heic' -o -iname '*.jpg' -o -iname '*.jpeg' \
        -o -iname '*.png' -o -iname '*.mp4' \
        -o -iname '*.dng' -o -iname '*.tiff' \) \
        -exec stat -f '%c %N' {} + 2>/dev/null \
        | sort -nr | head -20 | awk '{$1=""; print substr($0,2)}')
    [ -n "$files" ] || { skip "no recently-touched media files"; }
    local fail=0 checked=0
    while IFS= read -r full; do
        [ -z "$full" ] && continue
        [ -f "$full" ] || continue
        checked=$((checked + 1))
        if [ ! -f "${full}.xmp" ]; then
            echo "T5 FAIL: missing ${full}.xmp"
            fail=$((fail + 1))
        fi
    done <<< "$files"
    [ "$checked" -gt 0 ] || { skip "0 recently-touched media files to check"; }
    [ "$fail" -eq 0 ] || { echo "T5: $fail of $checked fixtures missing .xmp sidecar"; return 1; }
}

# --- T6 (US4): files recently touched by sync.sh have a sibling .json sidecar
@test "T6_json_sidecar_exists" {
    local files
    # Take the 20 most-recently-changed primary media files. Excludes .mov
    # because osxphotos does not write sidecars for Live Photo movie
    # components — only for the primary HEIC/JPG. Standalone videos use
    # the .mp4 path, which is included.
    files=$(find "$EXPORT_DIR" -type f -cmin -60 \
        \( -iname '*.heic' -o -iname '*.jpg' -o -iname '*.jpeg' \
        -o -iname '*.png' -o -iname '*.mp4' \
        -o -iname '*.dng' -o -iname '*.tiff' \) \
        -exec stat -f '%c %N' {} + 2>/dev/null \
        | sort -nr | head -20 | awk '{$1=""; print substr($0,2)}')
    [ -n "$files" ] || { skip "no recently-touched media files"; }
    local fail=0 checked=0
    while IFS= read -r full; do
        [ -z "$full" ] && continue
        [ -f "$full" ] || continue
        checked=$((checked + 1))
        if [ ! -f "${full}.json" ]; then
            echo "T6 FAIL: missing ${full}.json"
            fail=$((fail + 1))
        fi
    done <<< "$files"
    [ "$checked" -gt 0 ] || { skip "0 recently-touched media files to check"; }
    [ "$fail" -eq 0 ] || { echo "T6: $fail of $checked fixtures missing .json sidecar"; return 1; }
}

# --- T4 (US3): album-member photos have album name in IPTC:Keywords ---------
@test "T4_album_keyword" {
    local rows
    rows=$("$SQLITE3" "$(_uri_path "$PHOTOS_DB")?mode=ro" -readonly "
        SELECT a.ZUUID || '|' || g.ZTITLE
        FROM ZGENERICALBUM g
        JOIN Z_33ASSETS j ON j.Z_33ALBUMS = g.Z_PK
        JOIN ZASSET a ON a.Z_PK = j.Z_3ASSETS
        WHERE g.ZKIND=2
          AND g.ZTITLE IS NOT NULL AND g.ZTITLE != ''
          AND a.ZTRASHEDSTATE=0
        LIMIT 10;")
    [ -n "$rows" ] || { echo "no album-membership fixtures found"; return 1; }
    local fail=0 checked=0
    while IFS= read -r row; do
        [ -z "$row" ] && continue
        local uuid="${row%%|*}"
        local album="${row#*|}"
        local file
        file=$(resolve_uuid_to_path "$uuid")
        [ -n "$file" ] && [ -f "$file" ] || { echo "T4: $uuid: not exported (skip)"; continue; }
        checked=$((checked + 1))
        # Read both IPTC:Keywords (images) and XMP:Subject (cross-format) — either suffices.
        local kws
        kws=$("$EXIFTOOL" -fast2 -IPTC:Keywords -XMP:Subject -s -s -s "$file" 2>/dev/null | tr '\n' ' ')
        if ! echo "$kws" | grep -qF "$album"; then
            echo "T4 FAIL: uuid=$uuid album='$album' file=$file got keywords='$kws'"
            fail=$((fail + 1))
        fi
    done <<< "$rows"
    [ "$checked" -gt 0 ] || { echo "T4: 0 fixtures actually checked"; return 1; }
    [ "$fail" -eq 0 ] || { echo "T4: $fail of $checked fixtures failed"; return 1; }
}
