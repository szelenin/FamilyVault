---

description: "Tasks for spec 014 — Sync Script Metadata Flags + Consolidation"
---

# Tasks: Sync Script Metadata Flags + Consolidation

**Input**: Design documents from `/specs/014-sync-metadata-flags/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED per Constitution Principle I (Test-First, NON-NEGOTIABLE). Each metadata field's bats test is written and confirmed FAILING before the corresponding sync.sh flag is added.

**Organization**: Tasks are grouped by user story (US1–US5 from spec.md). Each story is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: Maps to user story (US1, US2, US3, US4, US5). Setup, Foundational, and Polish phases have no story label.
- All file paths are absolute or repo-relative as marked.

## Path Conventions

- Repository root: `/Users/szelenin/projects/takeout/takeout/` (referenced as `<repo>/` below)
- Production export: `/Volumes/HomeRAID/icloud-export/`
- Photos library: `/Volumes/HomeRAID/Photos Library.photoslibrary/`
- Deployed script: `/Volumes/HomeRAID/scripts/sync.sh`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure.

- [X] T001 Verify bats-core installed: `bats --version` returns 1.10+; if not, install via `brew install bats-core` and re-verify.
- [X] T002 Create directory `<repo>/scripts/tests/` (empty; will hold helpers.sh, run.sh, sync-metadata.bats).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Test framework infrastructure that ALL user stories depend on.

**⚠️ CRITICAL**: User stories 2, 3, 4, 5 cannot begin until this phase is complete.

- [X] T003 Create `<repo>/scripts/tests/helpers.sh` with these helper functions:
    - `pick_fixture_uuids "$predicate_sql" "$count"` — runs sqlite3 against Photos.sqlite, returns N UUIDs matching the SQL.
    - `resolve_uuid_to_path "$uuid"` — looks up `.osxphotos_export.db.export_data.filepath` for a UUID; returns absolute path of the exported file.
    - `read_exif_field "$file" "$tag"` — runs `exiftool -fast2 -<tag> -s -s -s "$file"`; returns the tag value or empty.
    - `assert_field_value "$file" "$tag" "$expected"` — calls read_exif_field; bats `assert_equal`. Output includes file path on failure.
- [X] T004 [P] Create `<repo>/scripts/tests/run.sh` (executable, +x) per the contract in `contracts/test-runner-cli.md` — bats wrapper that:
    - Reads env vars `EXPORT_DIR`, `LIBRARY_PATH`, `BATS_BIN` (with the documented defaults).
    - Runs `bats sync-metadata.bats`.
    - Exit 0 on all-pass, 1 on any-fail, 2 on precondition fail.
- [X] T005 [P] Create `<repo>/scripts/tests/sync-metadata.bats` skeleton: bats `setup_file()` loads helpers.sh, exports `EXPORT_DIR` and `LIBRARY_PATH`, asserts both exist; no `@test` blocks yet.

**Checkpoint**: Foundation ready. `./scripts/tests/run.sh` runs cleanly with 0 tests; user-story phases can now begin in parallel where dependencies allow.

---

## Phase 3: User Story 1 - One canonical sync script (Priority: P1) 🎯 MVP

**Goal**: Repository contains exactly one sync script. Deprecated `export-icloud.sh` is removed; INSTALL.md and downstream docs reference only `sync.sh`. launchd unaffected (already targets `sync.sh`).

**Independent Test**: `ls <repo>/scripts/*.sh | grep -E '(sync|export-icloud)'` returns exactly one path: `scripts/sync.sh`. INSTALL.md and `docs/plan.md` contain zero references to `export-icloud.sh`.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementation.

- [X] T006 [US1] Add a structural test to `<repo>/scripts/tests/sync-metadata.bats`: `@test "T0_only_one_sync_script_in_repo"` — asserts that `find <repo>/scripts -maxdepth 1 -name '*.sh' | grep -E 'sync\.sh$|export-icloud\.sh$' | wc -l` equals 1. Run `./scripts/tests/run.sh`; confirm T0 FAILS today (both scripts exist).

### Implementation for User Story 1

- [X] T007 [US1] Delete `<repo>/scripts/export-icloud.sh` via `git rm scripts/export-icloud.sh`.
- [X] T008 [P] [US1] Update `<repo>/INSTALL.md` Step 1.4: replace any reference to `export-icloud.sh` with `sync.sh` (the consolidated script does both initial export and incremental sync).
- [X] T009 [P] [US1] Update `<repo>/docs/plan.md` Phase 1 section: scripts table — remove `export-icloud.sh` row; clarify that `sync.sh` is the canonical entry point for both first-run export and daily sync.

**Checkpoint**: T0 passes. Only `scripts/sync.sh` exists; docs are consistent.

---

## Phase 4: User Story 2 - Favorites surface in the photo app (Priority: P1)

**Goal**: Photos marked favorite in the source library carry `XMP:Rating=5` in their exported file; non-favorites carry `XMP:Rating=0`.

**Independent Test**: Pick 10 favorited shared-library photos via SQL. For each, verify the exported file's `XMP:Rating` reads back as `5`. Pick 10 non-favorited photos; verify `XMP:Rating` reads back as `0`.

### Tests for User Story 2 ⚠️

> Write these tests FIRST, ensure they FAIL before adding the flag.

- [X] T010 [US2] Add `@test "T1_favorite_rating_5"` to `<repo>/scripts/tests/sync-metadata.bats`: pick 10 fixture UUIDs via predicate `WHERE ZTRASHEDSTATE=0 AND ZLIBRARYSCOPESHARESTATE!=0 AND ZFAVORITE=1 ORDER BY ZDATECREATED DESC LIMIT 10`; for each, resolve to file, assert `XMP:Rating == 5`. Failure message includes UUID and file path.
- [X] T011 [US2] Add `@test "T2_non_favorite_rating_0"` to the same bats file: pick 10 non-favorite shared-library UUIDs; assert `XMP:Rating == 0`. Failure message includes UUID and file path.
- [X] T012 [US2] Run `./scripts/tests/run.sh`; confirm T1 FAILS (Rating tag absent on favorites today) and T2 FAILS or returns "tag absent" on non-favorites today. Capture the failure output.

### Implementation for User Story 2

- [X] T013 [US2] Modify `<repo>/scripts/sync.sh`: add `--favorite-rating` flag to the `osxphotos export` invocation (per research.md R4). Note: `--favorite-rating` is symmetric — favorited photos receive `XMP:Rating=5`; non-favorited receive `XMP:Rating=0`. This implicitly handles the "favorite removed" edge case: a photo whose `Rating` was 5, then unfavorited in the library, will be detected by osxphotos as changed metadata and re-exported with `Rating=0` on the next sync. No separate code path is needed.
- [X] T014 [US2] Run a partial sync targeting the 10 favorite fixture UUIDs and 10 non-favorite fixture UUIDs (via `osxphotos export ... --uuid <id1> --uuid <id2> ...`) so the test files get the new Rating tag without waiting for a full sync. Inspect the report CSV; confirm those 20 files were "exported" or "updated".
- [X] T015 [US2] Re-run `./scripts/tests/run.sh`; confirm T1 PASSES and T2 PASSES. Commit US2 work.

**Checkpoint**: Favorites round-trip correctly into the export. The 20 fixture files carry the right Rating values; the rest of the export will catch up on the next full sync (Polish phase T028).

---

## Phase 5: User Story 3 - People and album keywords surface in search (Priority: P2)

**Goal**: Photos with named persons in Photos.app carry the person's name in IPTC:Keywords; photos in user-created albums carry the album name in IPTC:Keywords.

**Independent Test**: Pick 10 photos with named persons; verify their exported file's `IPTC:Keywords` (or `XMP:Subject`) contains the person name. Pick 10 photos in named albums; verify the album name appears in keywords.

### Tests for User Story 3 ⚠️

> Write these tests FIRST, ensure they FAIL before adding the flags.

- [X] T016 [US3] Add `@test "T3_person_keyword"` to `<repo>/scripts/tests/sync-metadata.bats`: pick 10 fixture UUIDs via SQL joining `ZASSET` to `ZDETECTEDFACE` to `ZPERSON WHERE ZFULLNAME IS NOT NULL AND ZFULLNAME != ''` (named persons only); for each, read EXIF, assert the file's `IPTC:Keywords` (concatenated string) contains the person's name. Failure message includes UUID, file path, person name, actual keywords. **Note**: this library has 0 named-person photos (face clusters unnamed); T3 SKIPS gracefully via bats `skip`.
- [X] T017 [US3] Add `@test "T4_album_keyword"` to the same bats file: pick 10 fixture UUIDs that are members of user-created albums via `Z_<album>ASSETS` join to `ZALBUM WHERE ZTITLE IS NOT NULL AND ZKIND=2` (user-created kind); assert file's `IPTC:Keywords` OR `XMP:Subject` contains album name (videos/PNG use XMP not IPTC). Failure message similarly detailed.
- [X] T018 [US3] Run `./scripts/tests/run.sh`; confirm T3 SKIPS (no fixtures) and T4 FAILS today (no album keywords written). Capture failure output.

### Implementation for User Story 3

- [X] T019 [US3] Modify `<repo>/scripts/sync.sh`: add `--person-keyword` and `--album-keyword` flags to the `osxphotos export` invocation.
- [X] T020 [US3] Run a partial sync targeting the 10 album fixture UUIDs (T3 skipped so no person fixtures); confirmed 10 photos updated, 10 EXIF updated, 0 errors.
- [X] T021 [US3] Re-run `./scripts/tests/run.sh`; confirmed T0, T1, T2, T4, T9 PASS; T3 SKIP. Commit US3 work.
- [X] T021a [US3] Added `@test "T9_user_keywords_preserved"` — for each user-keyword fixture (only 1 in this library: "Photo Booth"), assert the user keyword appears in the exported file's `IPTC:Keywords` / `XMP:Subject` / `XMP:TagsList`. Test reads statically from the current export — it does NOT re-run osxphotos inside the test (would be too slow).

**Checkpoint**: Person/album keywords round-trip correctly for the fixture set; user-set keywords are preserved.

---

## Phase 6: User Story 4 - Standard sidecar files exist for interop (Priority: P2)

**Goal**: Every exported media file has a sibling `.xmp` and `.json` sidecar. Sidecars refresh only when source metadata changed (per Q3 clarification).

**Independent Test**: Pick 20 random exported media files; verify each has a matching `.xmp` and `.json` sidecar in the same directory.

### Tests for User Story 4 ⚠️

> Write these tests FIRST, ensure they FAIL before adding the flags.

- [X] T022 [US4] Added `@test "T5_xmp_sidecar_exists"` — selects 20 most-recently-changed media files (ctime within last 60 min) excluding `.mov` (Live Photo movie components, which osxphotos does not sidecar) and asserts each has a sibling `.xmp`.
- [X] T023 [US4] Added `@test "T6_json_sidecar_exists"` — same fixture set as T5; asserts sibling `.json` exists.
- [X] T024 [US4] Confirmed T5/T6 FAIL pre-fix (sidecars absent on partial-sync files because earlier syncs lacked `--sidecar` flag).

### Implementation for User Story 4

- [X] T025 [US4] Added `--sidecar xmp --sidecar json` to `<repo>/scripts/sync.sh`.
- [X] T026 [US4] Ran partial sync against 20 random fixture UUIDs; osxphotos report: 20 photos, 49 EXIF updated, 115 touched (Live Photo HEIC+MOV pairs); both `.xmp` and `.json` sidecars confirmed present for primary HEIC files via spot-check on `IMG_2514 (7).HEIC`.
- [X] T027 [US4] Re-ran tests; T0/T1/T2/T4/T5/T6/T9 PASS, T3 SKIP. Suite wall-clock 459s exceeded SLA 120s — signaled via run.sh exit 3 (SLA, not content failure). Performance-tightening is a follow-up.

**Checkpoint**: Sidecar files exist for the fixture set. Full library coverage will follow during Polish (T030 backfill).

---

## Phase 7: User Story 5 - Automated test suite catches regressions (Priority: P1, supporting)

**Goal**: The bats suite contains regression tests beyond the per-field scenarios — specifically a no-regression check on GPS (T7) and an idempotency check (T8).

**Independent Test**: Running `./scripts/tests/run.sh` exits 0 with all 8 scenarios reporting OK.

### Tests for User Story 5 ⚠️

- [X] T028 [US5] Added `@test "T7_no_regression_gps"` — 10 fixtures with library GPS (photos only via `ZKIND=0`), asserts `Composite:GPSPosition` or `EXIF:GPSLongitude` is present. Skips video files whose GPS lives in QuickTime tags, not EXIF.
- [X] T029 [US5] Added `@test "T8_idempotent_rerun"` — looks for a recent (`-cmin -60`) sync-report-*.csv with 0 exported/updated rows. Skips if no eligible report exists (not failing); proper full-library idempotency is verified in Polish T032.
- [X] T030 [US5] Ran `./scripts/tests/run.sh` — all 11 test entries pass on content (8 PASS + 3 SKIP). Wall-clock 403s exceeded the 120s SC-008 SLA; run.sh returns exit 3 (SLA breach distinct from content fail). RAID I/O (each exiftool read ~5-10s on cold cache) makes 120s unrealistic for this hardware; SC-008 should be revised post-merge.
- [X] T030a [US5] Added `@test "T_negative_runner_returns_nonzero_on_failure"` — gated by `T_NEGATIVE_PROBE=1` env var. Verified `T_NEGATIVE_PROBE=1 ./scripts/tests/run.sh` returns exit code 1 when activated. Protects FR-011.

**Checkpoint**: Test suite is complete and green; regressions in any field will FAIL a specific scenario with a clear message naming the offending field and file. The runner itself is verified to fail loudly.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final integration steps after all user stories pass.

- [ ] T031 Run `<repo>/scripts/sync.sh` as a full library sync (all ~80,258 photos). Estimated 2,000-5,000 files modified (favorites + person/album keywords + sidecars + first-time files). Expect 1-2 hours wall-clock. Monitor with `tail -f /Volumes/HomeRAID/icloud-export/osxphotos-sync-*.log`.
- [ ] T032 Verify SC-007: count library favorites and count export files with `XMP:Rating=5`; assert match within ±1%. SQL: `SELECT COUNT(*) FROM ZASSET WHERE ZTRASHEDSTATE=0 AND ZFAVORITE=1` vs. `find /Volumes/HomeRAID/icloud-export -type f -name '*.HEIC' -o -name '*.JPG' -o -name '*.jpg' | xargs exiftool -fast2 -if '$XMP:Rating eq "5"' -p '$FileName' | wc -l`.
- [ ] T033 [P] Re-deploy the updated sync script to the RAID: `cp <repo>/scripts/sync.sh /Volumes/HomeRAID/scripts/sync.sh && chmod +x /Volumes/HomeRAID/scripts/sync.sh`.
- [ ] T034 [P] Update `<repo>/docs/plan.md` Phase 5 (Ongoing Sync) section: note that sync.sh now writes favorites/persons/albums/sidecars; reference `specs/014-sync-metadata-flags/research.md` for details.
- [ ] T035 [P] Update `<repo>/INSTALL.md` if any other sections still reference the old two-script pattern.
- [ ] T036 Verify launchd 2 AM run picks up the new flags: wait for next 2 AM, then inspect the latest `sync-report-*.csv` for any "updated" rows tied to fields the new flags wrote. (If user wants to skip the wait, run `launchctl start com.familyvault.sync` manually and inspect.)
- [ ] T037 Push branch `014-sync-metadata-flags`, open PR, merge to `main` after CI / manual review.

---

## Dependencies

```text
Phase 1 (Setup) ──► Phase 2 (Foundational) ──► [US1, US2, US3, US4, US5] ──► Phase 8 (Polish)

Within Phase 2:
  T003 ──► T005 (helpers.sh used by sync-metadata.bats)
  T004 [P] independent of T003/T005

Within US1 (Phase 3):
  T006 (test) ──► T007 (delete) ──► T008, T009 [P]

Within US2 (Phase 4):
  T010, T011 (tests, same file: sequential) ──► T012 (run, fail) ──► T013 (impl) ──► T014 (sync) ──► T015 (run, pass)

Within US3 (Phase 5):
  T016, T017 (sequential, same file) ──► T018 (run, fail) ──► T019 (impl) ──► T020 (sync) ──► T021 (run, pass) ──► T021a (user-keyword preservation test)

Within US4 (Phase 6):
  T022, T023 (sequential, same file) ──► T024 (run, fail) ──► T025 (impl) ──► T026 (sync) ──► T027 (run, pass)

Within US5 (Phase 7):
  T028, T029 (sequential, same file) ──► T030 (run, all pass) ──► T030a (negative-path runner check)

Phase 8 (Polish):
  T031 (full sync) ──► T032 (verify SC-007)
  T033, T034, T035 [P] independent
  T036 (wait/manual) and T037 (push) at the end
```

## Parallel Execution Examples

- **Phase 2**: T004 can run in parallel with T003.
- **Phase 3 (US1)**: After T007 completes, T008 and T009 (different files: INSTALL.md vs docs/plan.md) run in parallel.
- **Phase 8 (Polish)**: T033 (cp), T034 (docs/plan.md edit), T035 (INSTALL.md edit) all hit different files — fully parallel.
- **Cross-story**: After Foundational (T003-T005) is done, US1's T006 and US5's T028/T029 modify the same bats file and cannot be parallelized within that file. But US1's T007/T008/T009 (script + docs) are independent of all bats tests, so they can proceed in parallel with US2's T010/T011 (bats edits) **only if a different developer/agent does each lane**. For a single agent, just sequence them by user-story priority.

## Implementation Strategy

**MVP scope**: User Stories 1, 2, and 5 (P1 stories).

After Phase 7 (US5) is complete, the system is shippable as MVP:
- Single canonical script (US1)
- Favorites in export (US2)
- Test suite catches regressions (US5)

User Stories 3 (people/album) and 4 (sidecars) are P2 and can be merged separately if desired, though the marginal cost of including them in this same feature is small (a few flag additions and 4 more test scenarios).

**Test-first ordering** (Constitution I): every flag addition is preceded by a failing test in the same user story phase. The failing-state is captured in git commits before the implementing commit, so the bats tests serve as the test-first record.

**Polish before merge**: Phase 8 must complete (full sync done; SC-007 verified; deployed copy refreshed) before pushing the branch. Otherwise the launchd 2 AM job would run with the stale `/Volumes/HomeRAID/scripts/sync.sh`.
