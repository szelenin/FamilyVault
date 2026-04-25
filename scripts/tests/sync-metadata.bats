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
