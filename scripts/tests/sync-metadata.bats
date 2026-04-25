#!/usr/bin/env bats
# sync-metadata.bats — verify spec-014 metadata-write contract.
# Manual-only invocation per spec FR-012a.

setup_file() {
    SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
    # shellcheck source=helpers.sh
    source "${SCRIPT_DIR}/helpers.sh"

    # Validate environment.
    [ -f "$EXPORT_DB" ] || { echo "missing export DB: $EXPORT_DB" >&2; return 1; }
    [ -f "$PHOTOS_DB" ] || { echo "missing Photos library DB: $PHOTOS_DB" >&2; return 1; }
}

# @test blocks for T0..T9 will be added by US1, US2, US3, US4, US5 phases.
# This skeleton ensures the runner can be exercised before any scenarios exist.
