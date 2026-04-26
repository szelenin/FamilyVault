# Phase 1 Data Model: Sync Script Metadata Flags + Consolidation

**Date**: 2026-04-25 | **Branch**: `014-sync-metadata-flags`

This feature is a CLI tool with no persistent service, no database schema
changes, and no API. The "data model" here is the in-memory entities the
test runner constructs while it executes. They are documented for clarity
and to make the test architecture concrete.

---

## Test Fixture

A test fixture is a row produced by querying Photos.sqlite at test time.
Each fixture binds a scenario to a concrete file on disk.

| Field | Type | Source | Purpose |
|-------|------|--------|---------|
| `scenario_id` | string | constant per `@test` block | Identifies which assertion this fixture serves (e.g. `T1_favorite`). |
| `uuid` | string | `Photos.sqlite ZASSET.ZUUID` | Photos.app asset UUID. |
| `expected_field` | string | hardcoded per scenario | The metadata tag we expect to read back (e.g. `XMP:Rating`). |
| `expected_value` | string | derived from library | The value we expect (e.g. `5` for favorites). |
| `file_path` | string | `.osxphotos_export.db.export_data.filepath` | Resolved exported file location. |

**Identity**: `(scenario_id, uuid)` is unique per test run — fixtures are
discarded after the bats run completes; nothing persists.

**Lifecycle**: discovered → asserted → discarded. No state transitions.

---

## Scenario Definition

A scenario is the in-bats representation of one acceptance test (T1–T8 from
spec.md User Story 5).

| Field | Type | Purpose |
|-------|------|---------|
| `id` | string | Stable name like `T1_favorite_rating_5`. |
| `description` | string | One-line human-readable purpose. |
| `predicate_sql` | string | SQL that picks fixture UUIDs from Photos.sqlite (e.g. `WHERE ZFAVORITE=1 AND ZLIBRARYSCOPESHARESTATE!=0 LIMIT 10`). |
| `assertion` | shell function | Reads back the metadata field via `exiftool` and asserts the expected value. |
| `count` | integer | Number of fixtures to sample (10 per spec.md SC-002 to SC-005). |

The bats file declares one `@test` block per scenario; the helper functions
in `helpers.sh` factor out the fixture-discovery and assertion patterns so
each `@test` reads as one declarative call.

---

## Test Result

Per-fixture result captured by the bats runner.

| Field | Type | Purpose |
|-------|------|---------|
| `scenario_id` | string | Matches the `@test` name. |
| `uuid` | string | Which library asset was checked. |
| `file_path` | string | Which file on disk was checked. |
| `status` | enum (`PASS`, `FAIL`, `SKIP`) | Outcome. |
| `actual_value` | string | What `exiftool` returned (empty if FAIL due to missing tag). |
| `message` | string | Human-readable explanation, useful when status=FAIL. |

bats's TAP output captures the {scenario, status, message} triple natively;
`actual_value` and `file_path` go into the failure message so a regression
points directly at the file.

---

## Sync Run Report (osxphotos-generated, not a project entity)

osxphotos already produces a CSV report per run (`sync-report-<timestamp>.csv`)
with one row per asset processed. This is **not** part of this feature's data
model — it is consumed as-is. The bats tests do not parse it. It exists for
audit-trail purposes (FR-009).

---

## What's NOT in the data model

- **No persistent test database**: tests are stateless; each run discovers
  fixtures fresh.
- **No fixture cache file**: the predicate_sql is the source of truth.
- **No API contract data**: this is a CLI tool, not a web service.
- **No user accounts, sessions, auth**: local single-user.
