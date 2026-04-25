# Contract: `scripts/tests/run.sh` CLI

**Date**: 2026-04-25 | **Feature**: `014-sync-metadata-flags`

This contract documents the test runner used to validate spec 014. Manual
invocation per Q1 clarification — the daily sync does not call this.

## Invocation

```sh
./scripts/tests/run.sh
```

No arguments. The runner uses default paths from sync.sh.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `EXPORT_DIR` | `/Volumes/HomeRAID/icloud-export` | Where to look for exported files and `.osxphotos_export.db`. |
| `LIBRARY_PATH` | `/Volumes/HomeRAID/Photos Library.photoslibrary` | Source library to query for fixture UUIDs. |
| `BATS_BIN` | `bats` (from PATH) | bats binary location. |

## Side effects

None. The runner reads only — it never modifies files in the export.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All scenarios passed. |
| 1 | One or more scenarios failed. |
| 2 | Precondition missing (no export DB, no library, bats not installed). |

## Stdout

Standard bats TAP output — one line per `@test` block, plus a summary at
the end:

```text
1..8
ok 1 T1_favorite_rating_5
ok 2 T2_non_favorite_rating_0
ok 3 T3_person_keyword
ok 4 T4_album_keyword
ok 5 T5_xmp_sidecar_exists
ok 6 T6_json_sidecar_exists
ok 7 T7_no_regression_gps
ok 8 T8_idempotent_rerun

8 tests, 0 failures
```

A failure is reported with the offending file path and the field that was
missing/wrong:

```text
not ok 1 T1_favorite_rating_5
# (in test file scripts/tests/sync-metadata.bats, line 23)
#   `assert_field_value "$file" "XMP:Rating" "5"' failed
# expected: 5
# actual:   (empty)
# file:     /Volumes/HomeRAID/icloud-export/2024/Birthday/IMG_2910.HEIC
# UUID:     ABCDEF12-3456-7890-ABCD-EF1234567890
```

## Failure semantics

The runner exits with a non-zero status if **any** scenario fails. There is
no per-scenario tolerance and no partial-pass mode. This matches FR-011.

## Performance budget

The full suite must complete in under 2 minutes on a warm cache (SC-008).
Each scenario picks 10 fixtures × 1 exiftool read = ~80 exiftool invocations
total, each well under 1 second.
