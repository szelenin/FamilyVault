#!/usr/bin/env bash
# helpers.sh — shared utilities for sync-metadata.bats
#
# Provides:
#   pick_fixture_uuids "$predicate_sql" "$count" — query Photos.sqlite for N UUIDs
#   resolve_uuid_to_path "$uuid" — UUID → exported file absolute path
#   read_exif_field "$file" "$tag" — read a single tag via exiftool
#   assert_field_value "$file" "$tag" "$expected" — bats assertion with file path on failure
#   keywords_set "$file" — read IPTC:Keywords as space-delimited; useful for subset checks

# Defaults; override via env.
: "${EXPORT_DIR:=/Volumes/HomeRAID/icloud-export}"
: "${LIBRARY_PATH:=/Volumes/HomeRAID/Photos Library.photoslibrary}"
: "${EXIFTOOL:=/opt/homebrew/bin/exiftool}"
: "${SQLITE3:=/usr/bin/sqlite3}"

EXPORT_DB="${EXPORT_DIR}/.osxphotos_export.db"
PHOTOS_DB="${LIBRARY_PATH}/database/Photos.sqlite"

# Encode a path with spaces for sqlite URI mode.
_uri_path() {
    printf 'file:%s' "$(echo "$1" | sed 's/ /%20/g')"
}

pick_fixture_uuids() {
    local predicate_sql="$1"
    local count="${2:-10}"
    "$SQLITE3" "$(_uri_path "$PHOTOS_DB")?mode=ro" -readonly \
        "SELECT ZUUID FROM ZASSET WHERE $predicate_sql LIMIT $count;"
}

resolve_uuid_to_path() {
    local uuid="$1"
    local rel
    rel=$("$SQLITE3" "$EXPORT_DB" \
        "SELECT filepath FROM export_data WHERE uuid='$uuid' LIMIT 1;" 2>/dev/null) || rel=""
    if [ -n "$rel" ]; then
        printf '%s/%s' "$EXPORT_DIR" "$rel"
    fi
    return 0
}

read_exif_field() {
    local file="$1"
    local tag="$2"
    "$EXIFTOOL" -fast2 "-${tag}" -s -s -s "$file" 2>/dev/null
}

assert_field_value() {
    local file="$1"
    local tag="$2"
    local expected="$3"
    local actual
    actual=$(read_exif_field "$file" "$tag")
    if [ "$actual" != "$expected" ]; then
        printf 'FAIL: %s: expected %s=%s, got %q (file: %s)\n' \
            "$tag" "$tag" "$expected" "$actual" "$file" >&2
        return 1
    fi
}

# Read IPTC:Keywords as a newline-delimited list. exiftool returns "kw1, kw2, kw3" — normalize.
keywords_set() {
    local file="$1"
    "$EXIFTOOL" -fast2 -IPTC:Keywords -s -s -s "$file" 2>/dev/null \
        | tr ',' '\n' | sed 's/^ *//; s/ *$//' | grep -v '^$'
}
