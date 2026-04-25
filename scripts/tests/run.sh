#!/usr/bin/env bash
# run.sh — entrypoint for the spec-014 bats test suite.
# Manual-only invocation per spec FR-012a (daily sync does NOT trigger this).
#
# Exit codes:
#   0 — all scenarios passed
#   1 — one or more scenarios failed
#   2 — precondition missing (no export DB, no library, bats not installed)
#   3 — wall-clock SLA exceeded (>120s, per SC-008)

set -u

: "${EXPORT_DIR:=/Volumes/HomeRAID/icloud-export}"
: "${LIBRARY_PATH:=/Volumes/HomeRAID/Photos Library.photoslibrary}"
: "${BATS_BIN:=bats}"
: "${SLA_SECONDS:=120}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BATS_FILE="${SCRIPT_DIR}/sync-metadata.bats"

# Precondition checks
if ! command -v "$BATS_BIN" >/dev/null 2>&1; then
    echo "ERROR: bats not found in PATH; install via 'brew install bats-core'" >&2
    exit 2
fi
if [ ! -f "${EXPORT_DIR}/.osxphotos_export.db" ]; then
    echo "ERROR: export DB not found at ${EXPORT_DIR}/.osxphotos_export.db" >&2
    exit 2
fi
if [ ! -f "${LIBRARY_PATH}/database/Photos.sqlite" ]; then
    echo "ERROR: Photos library not found at ${LIBRARY_PATH}" >&2
    exit 2
fi
if [ ! -f "$BATS_FILE" ]; then
    echo "ERROR: bats file not found: $BATS_FILE" >&2
    exit 2
fi

export EXPORT_DIR LIBRARY_PATH

START_SECONDS=$SECONDS
"$BATS_BIN" "$BATS_FILE"
BATS_STATUS=$?
ELAPSED=$((SECONDS - START_SECONDS))

if [ "$BATS_STATUS" -ne 0 ]; then
    exit 1
fi

if [ "$ELAPSED" -gt "$SLA_SECONDS" ]; then
    echo "WARN: test suite took ${ELAPSED}s (SLA: ${SLA_SECONDS}s per SC-008)" >&2
    exit 3
fi

echo "All tests passed in ${ELAPSED}s (under SLA ${SLA_SECONDS}s)"
exit 0
