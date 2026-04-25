# Feature Specification: Sync Script Metadata Flags + Consolidation

**Feature Branch**: `014-sync-metadata-flags`
**Created**: 2026-04-25
**Status**: Draft
**Input**: User description: "Consolidate sync scripts into a single script with full metadata flags (favorite rating, person keywords, album keywords, XMP+JSON sidecars). Add automated tests verifying each metadata field round-trips into the export file."

> **Background**: Spec 013 research (`specs/013-wife-metadata-import/research.md`)
> proved that the iCloud Shared Library propagates ALL metadata between
> participants and that the daily incremental sync script keeps export files in
> sync — for **the metadata fields the script actually asks osxphotos to write**.
> A spot-check on five favorited+GPS photos revealed that:
>
> - GPS, capture date, title, description, and own keywords are written ✅
> - Favorite (heart) is **not** written; XMP:Rating is absent on every favorited file
> - Person/face tags as keywords are not written
> - Album names as keywords are not written
> - XMP/JSON sidecars are not produced by the daily sync
>
> The cause is not a logic bug but missing osxphotos flags in `sync.sh`. A
> sibling script `export-icloud.sh` has most (not all) of the missing flags but
> is invoked separately, and the two scripts have drifted from each other. This
> feature consolidates the two scripts into one and adds the missing flags so
> all relevant metadata reaches the export and downstream consumers
> (the home photo app, search tools).

## Clarifications

### Session 2026-04-25

- Q: For non-favorited photos, should the exported file carry a rating-zero tag, or should the rating field be absent? → A: Rating=0 explicit (osxphotos `--favorite-rating` default — favorites = 5, non-favorites = 0; no separate code path needed).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — One canonical sync script (Priority: P1)

The user has two near-identical sync scripts (`export-icloud.sh` and `sync.sh`)
that differ only in which metadata flags they pass and in operational details
(timestamped logging, auto-launching the photo app). The user wants ONE script
they invoke both ad-hoc and via the daily scheduler — eliminating the
possibility that one path produces richer metadata than the other.

**Why this priority**: drift between two scripts caused the metadata gap in
the first place. Having one canonical script prevents the same class of bug
from re-emerging.

**Independent Test**: Inspect the repository — only one sync script exists.
The launchd job and ad-hoc usage both invoke the same path. Running it
multiple times produces identical metadata coverage regardless of caller.

**Acceptance Scenarios**:

1. **Given** the consolidated state, **When** the user lists sync-related
   scripts in the repo, **Then** they see exactly one canonical script with a
   clear, current name.
2. **Given** the launchd job and ad-hoc invocations, **When** they run, **Then**
   they invoke the same script, producing the same set of metadata flags.

---

### User Story 2 — Favorites surface in the photo app (Priority: P1)

A photo the user marks as a favorite in their iCloud library should also
appear as a favorite in the home photo app. Today the favorite indicator is
present in the photo library but is not written into the exported file, so
the home app cannot detect it.

**Why this priority**: favorites are a primary curation signal. Without them
the user has to redo curation in the home app, defeating much of the value of
the cloud-sync workflow.

**Independent Test**: Pick a small set of known-favorited photos. Run the
sync. Read each exported file's metadata directly. Confirm a favorite
indicator is present.

**Acceptance Scenarios**:

1. **Given** a photo is marked favorite in the source library, **When** the
   sync runs, **Then** the corresponding exported file carries a favorite
   indicator that survives a fresh metadata read.
2. **Given** the user later removes the favorite flag in the source library,
   **When** the next sync runs, **Then** the favorite indicator on the
   exported file is removed (or set to a "not-favorite" value).

---

### User Story 3 — People and album keywords surface in search (Priority: P2)

When the user searches their archive for a person ("photos with Edgar") or
an album name ("Miami trip"), they expect the home app or any standard photo
tool to find matching photos. Today the names of people and albums known to
the source library are not propagated to the exported file's metadata, so
search-by-keyword does not work.

**Why this priority**: faces and albums are the most useful free-text
indices the user has. Without them, ML face detection in the home app has to
re-derive everything; albums are simply lost.

**Independent Test**: Pick a photo with a known named person; pick a photo
in a named album. Run the sync. Read each file's metadata. Confirm the
person's name and the album name appear in the file's keyword fields.

**Acceptance Scenarios**:

1. **Given** a photo with a named face in the library, **When** the sync
   runs, **Then** the person's name appears in the exported file's keyword
   metadata.
2. **Given** a photo in a named album, **When** the sync runs, **Then** the
   album name appears in the exported file's keyword metadata.

---

### User Story 4 — Standard sidecar files exist for interop (Priority: P2)

Some downstream tools read metadata from `.xmp` and `.json` sidecars rather
than from the embedded EXIF. The current daily sync does not produce
sidecars. The user wants sidecars produced so that any current or future
tool reading the export folder has a consistent metadata source.

**Why this priority**: it is a small operational addition that prevents
future surprises with tools that prefer sidecars. Lower priority than the
fields themselves because most consumers (the user's home app) read embedded
metadata first.

**Independent Test**: After a sync run, sample 20 exported media files and
confirm a corresponding `.xmp` and `.json` sidecar exists for each.

**Acceptance Scenarios**:

1. **Given** a sync run completes, **When** the user inspects the export
   folder, **Then** every media file has a sibling `.xmp` and `.json`
   sidecar.

---

### User Story 5 — Automated test suite catches regressions (Priority: P1, supporting)

The user does not want this metadata gap to silently re-emerge if a future
change drops a flag or alters the sync behavior. They want a small, fast
automated test suite that picks a known set of fixtures and verifies each
metadata field round-trips into the exported file.

**Why this priority**: the original gap was caught by ad-hoc spot-checking.
Without an automated test, drift will recur. Having the test in the
repository makes regressions obvious in any pre-merge check or manual
audit.

**Independent Test**: Run the test suite from a terminal. Each scenario
reports PASS / FAIL with the file paths involved and the field that was
checked. A failure clearly identifies which metadata field has regressed.

**Acceptance Scenarios**:

1. **Given** the consolidated sync has been run on a fresh fixture set,
   **When** the test suite is invoked, **Then** every scenario reports PASS
   and the suite exits with a success status.
2. **Given** a regression is introduced (a flag is removed), **When** the
   sync is re-run and the test suite is invoked, **Then** the relevant
   scenarios report FAIL and the failure message names the missing field.

---

### Edge Cases

- **Favorite removed**: a photo the user un-favorites in the library — the
  exported file's favorite indicator must be cleared, not left stale.
- **Photo with no people / no album**: person-keyword and album-keyword must
  not produce empty or junk keyword entries.
- **Photo whose only keywords come from the templates**: pre-existing user
  keywords on a photo must be preserved and not overwritten by template-only
  keywords.
- **Sidecar already exists**: an existing sidecar must be either left in
  place or refreshed with current metadata; it must not be silently
  duplicated or appended to.
- **Re-running the sync with no library changes**: must report zero
  modifications; must not touch any exported file unnecessarily.
- **Sync interrupted partway**: re-running must resume from where it left
  off, not restart from scratch.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST contain exactly one canonical incremental
  sync script for the export workflow.


- **FR-002**: The sync script MUST translate the source library's favorite
  flag into a standard rating field on the exported file: favorited photos
  receive the highest rating value; non-favorited photos receive an explicit
  zero-rating value.
- **FR-003**: The sync script MUST write named-person tags from the source
  library into the exported file's keyword metadata.
- **FR-004**: The sync script MUST write album names from the source library
  into the exported file's keyword metadata.
- **FR-005**: The sync script MUST produce an XMP sidecar and a JSON sidecar
  alongside each exported media file.
- **FR-006**: The sync script MUST be idempotent: a re-run with no library
  changes MUST produce zero file modifications.
- **FR-007**: The sync script MUST be invokable both ad-hoc by the user and
  by the scheduled background job, with the same flags and outcomes.
- **FR-008**: The scheduled background job MUST point to the canonical sync
  script (no orphaned reference to the deprecated path).
- **FR-009**: The sync script MUST log run progress with a timestamp and
  produce a CSV report of every file's outcome (skipped, exported, updated,
  error).
- **FR-010**: An automated test suite MUST exist in the repository and MUST
  verify that each of the metadata fields named in FR-002 through FR-005 is
  present in the exported file after a sync run.
- **FR-011**: The test suite MUST report PASS/FAIL per scenario and exit
  with a non-zero status if any scenario fails.
- **FR-012**: The test suite MUST be runnable without manual setup, beyond
  having an export already in place and the source library available.
- **FR-013**: The deprecated sync script MUST be removed from the
  repository as part of this feature, leaving a clean tree with only the
  canonical script.
- **FR-014**: After consolidation and flag fix, **one full re-run** of the
  canonical sync MUST be performed to backfill missing favorite / person /
  album metadata into already-exported files.

### Key Entities

- **Source library**: the user's iCloud Photos library on the home server,
  the authoritative source for all metadata fields.
- **Export folder**: the on-disk destination of exported media files; one
  file per asset, with sidecars.
- **Sync script**: the single canonical entry point that walks the library,
  detects changes, and writes them into the export folder.
- **Scheduler entry**: the operating-system-level scheduled job that
  invokes the sync script daily.
- **Export tracking record**: the persistent record (kept by the export
  tooling) that knows which files have been written and what state they were
  in, used to detect what is new or changed.
- **Test fixture**: a small, deterministic set of source-library asset
  identifiers chosen to cover each metadata field under test.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After consolidation, the repository contains exactly **1**
  sync script in the scripts directory, not 2.
- **SC-002**: After a full sync run, on a sample of **10** known-favorited
  photos picked from the library, **10/10** exported files report a
  highest-value rating when read back with a standard metadata tool.
- **SC-003**: On a sample of **10** photos with named persons, **10/10**
  exported files contain the person's name in the file's keyword field.
- **SC-004**: On a sample of **10** photos in named albums, **10/10**
  exported files contain the album's name in the file's keyword field.
- **SC-005**: On a sample of **20** exported media files, **20/20** have a
  matching `.xmp` sidecar and a matching `.json` sidecar.
- **SC-006**: Running the sync immediately after a successful run reports
  **0** new modifications (idempotency).
- **SC-007**: Across the full library, the count of source-library
  favorites and the count of exported files carrying a highest-value rating
  match within **±1%**.
- **SC-008**: The test suite completes in **under 2 minutes** on a warm
  cache.
- **SC-009**: The scheduled background job logs at least one successful run
  pointing to the canonical script after the consolidation, with no
  references to the deprecated script in any log line.

## Assumptions

- iCloud Shared Library propagates metadata between participants (proven in
  spec 013 research). Therefore, the source library is the authoritative
  metadata source for both partners' photos.
- The export tooling (osxphotos) supports writing each metadata field via
  documented flags; this feature does not require new tool development.
- A one-time full sync re-run is acceptable after the consolidation, even
  though it touches files that were already exported. This is a one-shot
  cost to backfill the missing fields.
- The scheduler entry can be safely re-pointed at the new script in one
  step, with no service interruption — the daily 2 AM run picks up the new
  script automatically.
- The user accepts that the home photo app will pick up favorite/person/
  album metadata on its next library re-scan; this is not part of this
  feature's scope.
- Tests are run on the same host where the export lives; no remote
  fixture infrastructure is required.
