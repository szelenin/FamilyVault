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
