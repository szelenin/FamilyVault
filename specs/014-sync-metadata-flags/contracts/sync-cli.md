# Contract: `scripts/sync.sh` CLI

**Date**: 2026-04-25 | **Feature**: `014-sync-metadata-flags`

This contract documents the CLI surface the canonical `sync.sh` exposes. Any
change here is a breaking change for either the user (ad-hoc invocation) or
the launchd plist (scheduled invocation).

## Invocation

```sh
./scripts/sync.sh [export-dir] [library-path]
```

## Arguments (positional, both optional)

| Position | Name | Default | Purpose |
|----------|------|---------|---------|
| 1 | `export-dir` | `/Volumes/HomeRAID/icloud-export` | Destination directory for exported media + sidecars + reports + log. |
| 2 | `library-path` | `/Volumes/HomeRAID/Photos Library.photoslibrary` | Source `Photos.photoslibrary` to read assets and metadata from. |

## Environment

The script does not require any environment variables. It uses absolute
paths to all tools (`/opt/homebrew/bin/osxphotos`, `/opt/homebrew/bin/exiftool`)
to remain robust under launchd's reduced PATH.

## Side effects on the filesystem

| Path | Effect |
|------|--------|
| `<export-dir>/<folder>/<album>/...` | Media files + sidecars created or updated. |
| `<export-dir>/.osxphotos_export.db` | osxphotos's tracking DB; written every run. |
| `<export-dir>/sync-report-<TIMESTAMP>.csv` | One row per asset processed. |
| `<export-dir>/osxphotos-sync-<TIMESTAMP>.log` | Verbose log of the run. |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Sync completed successfully. Some files may have had per-file errors; these are reported in the CSV but do not fail the run. |
| 1 | Hard precondition failed (export dir missing, library missing, osxphotos not found). |
| 130 | User-interrupted (SIGINT). |
| Other non-zero | osxphotos itself failed (e.g., out of disk). |

## Stdout/stderr behavior

- All stdout from osxphotos is `tee`'d to the log file in `<export-dir>`.
- Script-level status lines (Starting / Sync complete / Report) are written
  to stdout AND into the log via `tee`.
- No quiet mode; the script is verbose by design (`--verbose` is passed to
  osxphotos).

## Idempotency

A re-run with no library changes since the previous run MUST report 0
modifications. This is enforced by FR-006 and validated by SC-006.

## Idempotency caveat (one-time)

The first run after this feature lands will modify many files (FR-014
backfill — favorites, person/album keywords, sidecars). This is the
expected one-shot cost. Subsequent runs return to zero-modifications
behavior.

## Compatibility

- **launchd** invokes the deployed copy `/Volumes/HomeRAID/scripts/sync.sh`,
  which is a `cp` of this script. The contract is identical.
- **Photos.app** must be installed on the host (osxphotos depends on it).
  The script attempts to launch Photos.app if not running (`open -a Photos`).
- **macOS Sequoia** is the target; older macOS may work but is not tested.
