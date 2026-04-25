# Feature Specification: Wife Metadata Import

**Feature Branch**: `013-wife-metadata-import`
**Created**: 2026-04-25
**Status**: Draft
**Input**: User description: "Wife metadata import: extend apply-wife-metadata.py to import GPS, favorites, ratings, titles, descriptions, keywords, and timezone from the second iCloud Photos library to matching files in icloud-export, for both photos and videos, verified end-to-end via Immich API"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Photo metadata enrichment (Priority: P1)

The user owns a self-hosted photo library on a home server. Their iCloud Shared Photo
Library contains tens of thousands of photos contributed by both spouses. The other
spouse's iCloud library — which the user can read but does not directly browse — holds
richer metadata (GPS, favorites, captions, timezones, keywords) for many of those same
photos. The user wants to bring that richer metadata into the home server's archive so
their photo app surfaces it correctly.

**Why this priority**: Photos are the dominant asset type and where richer metadata
already exists in the second library. Enriching photos first delivers immediate user
value (correct favorite status, captions, locations) and validates the matching and
write pipeline before the more complex video format support is added.

**Independent Test**: Run a dry-run that lists how many photos in the export will
receive each metadata field from the second library. Apply the changes. Read back the
metadata directly from each modified file. Confirm every field that was supposed to
change actually changed.

**Acceptance Scenarios**:

1. **Given** a photo whose copy in the second library has a favorite (heart) flag and
   the matching file in the export does not, **When** metadata import runs, **Then**
   the file in the export carries a "favorited" indicator that survives a re-read.
2. **Given** a photo whose copy in the second library has a title, description, and
   keywords, **When** metadata import runs, **Then** the file in the export contains
   that title (overwriting any prior value), that description (overwriting any prior
   value), and the union of the existing keywords with the second-library keywords.
3. **Given** a photo whose copy in the second library has GPS and the matching file
   in the export does not, **When** metadata import runs, **Then** the file in the
   export contains the GPS coordinates from the second library.
4. **Given** a photo where the second library has no GPS but does have a title,
   **When** metadata import runs, **Then** the title is still written (the absence of
   GPS does not block other field updates).
5. **Given** a successful run, **When** the user lists the backup folder, **Then**
   every modified file has an exact byte-for-byte copy that can be restored if needed.

---

### User Story 2 — Video metadata enrichment (Priority: P2)

After photo enrichment is verified, the user wants the same metadata enrichment
applied to videos in the export. Videos store metadata in a different container than
photos, so this is implemented and tested as a separate scenario, gated on photo
enrichment passing.

**Why this priority**: Videos are a smaller share of total assets and use different
metadata containers, requiring separate write logic. Sequencing after photos keeps the
risk surface small per scenario and lets the photo path validate the matching and
backup scaffolding before video write logic is exercised.

**Independent Test**: Run the import in video-only mode. Read back metadata from each
modified video file. Confirm fields appear in the locations a generic media player or
indexer would read (not only in extended sidecars).

**Acceptance Scenarios**:

1. **Given** a video whose second-library copy has GPS, title, description, keywords,
   and a favorite flag, **When** metadata import runs in video mode, **Then** all
   five fields are present when the file is re-read.
2. **Given** a successful video run, **When** the user lists the backup folder,
   **Then** every modified video has an exact byte-for-byte copy.

---

### User Story 3 — End-to-end verification through the photo app (Priority: P3)

After all file-level writes pass, the user wants confirmation that their photo app
actually surfaces the new metadata to people browsing the library — not just that it
is buried in the file. The user accepts that the photo app must be running for this
verification.

**Why this priority**: File-level reads prove the bytes are in the right place;
photo-app verification proves the indexer interprets them correctly. This is the
acceptance gate for the whole feature and bookends the work, but it depends on
Stories 1 and 2 having passed.

**Independent Test**: Start the photo app. Trigger a library re-scan. Wait for the
scan to finish. Query the photo app's data interface for a sample of modified assets
and confirm the metadata fields are present.

**Acceptance Scenarios**:

1. **Given** photo and video imports have completed and the photo app's library has
   been re-scanned, **When** the user queries a known-modified photo, **Then** the
   photo app reports the imported title, description, GPS, favorite status, and
   keywords.
2. **Given** the same conditions, **When** the user queries a known-modified video,
   **Then** the photo app reports the imported title, description, GPS, favorite
   status, and keywords on the video.

---

### User Story 4 — Safe operation with rollback (Priority: P1, supporting)

Before any destructive metadata write, the user wants every modified file backed up
in a centralized location they can throw away in one step once they are confident, or
restore from in one step if they spot a regression.

**Why this priority**: This is a quality-of-life requirement that supports Story 1
and Story 2. Without it the user does not give consent to run at scale. Marked P1
because it gates the user's willingness to proceed.

**Independent Test**: Inspect the backup folder after a partial run. Confirm every
file that was reported as "updated" has a corresponding backup. Confirm restoring a
single file from backup over the modified file produces a file identical to the
pre-run state.

**Acceptance Scenarios**:

1. **Given** the import is configured to back up before writing, **When** the import
   runs, **Then** every file the import modifies has a sibling copy in the backup
   folder, named uniquely so restoration is unambiguous.
2. **Given** a backup exists, **When** the user copies it back over the modified
   file, **Then** the file's content and metadata are restored to the pre-import
   state.
3. **Given** the user is satisfied with the results, **When** they delete the backup
   folder, **Then** all backup data is reclaimed in a single operation.

---

### User Story 5 — Pre-flight scope visibility (Priority: P2)

Before applying changes at scale, the user wants to know how many files will be
touched and per which metadata field. The exact same invocation, with a flag
indicating dry-run, must produce a count breakdown without modifying any file.

**Why this priority**: A library this size (six-figure file count) is too large for
trial-and-error. The user needs to see the magnitude of changes per field, decide
whether to scope down with a limit, and only then commit.

**Independent Test**: Run the dry-run on the full library. Confirm zero files are
modified, zero backups are written, and a clear count breakdown is produced.

**Acceptance Scenarios**:

1. **Given** dry-run mode, **When** the import is invoked, **Then** the output lists
   the number of files that would receive a GPS update, a favorite update, a title
   update, a description update, a keywords update, a rating update, and a timezone
   update — with no file modifications and no backups created.
2. **Given** dry-run mode and a per-run cap, **When** the import is invoked, **Then**
   the output reports both the full scope and the capped subset.

---

### Edge Cases

- **No match**: a record in the second library has no matching capture-time in the
  shared library. The system reports this in counts and skips silently.
- **Ambiguous match**: multiple records in the second library share a capture-time
  (burst photos). The system skips ambiguous groups for safety and reports the
  ambiguous count.
- **Field missing in source**: the second library has GPS but no title for a record.
  Only present fields are written; absent fields are not blanked in the destination.
- **Field already equal**: the destination already has the same value the second
  library would write. The system writes anyway (idempotent) but does not double-count
  in the "changed" tally.
- **Favorite removed in source**: the second library no longer has the favorite flag,
  but the destination does. The system unsets the favorite to mirror the source.
- **Keywords overlap**: the destination already has some of the keywords the second
  library wants to add. The system writes the union without duplicates.
- **Backup folder fills disk**: the system stops cleanly with a clear error and does
  not attempt further writes that would leave files unbackable.
- **Source library reads as locked**: the system reads the second library in
  read-only mode and tolerates the photo app being open.
- **Match by time tolerance**: capture times that differ by sub-second floating-point
  drift still match within a configurable tolerance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read metadata from a second photo-library database without
  requiring its originals to be downloaded locally.
- **FR-002**: System MUST match records between the second library and the user's
  archive using capture date as the bridge (because shared-library copies are
  reassigned new identifiers and direct identifier match fails).
- **FR-003**: System MUST be able to import each of these metadata fields:
  GPS coordinates, favorite flag, star rating, title, description, keywords,
  and timezone.
- **FR-004**: System MUST apply this conflict policy per field, when the second
  library and the destination disagree:
  - GPS: overwrite destination with source.
  - Favorite: mirror source state in destination (set or unset).
  - Star rating: overwrite destination with source.
  - Title: overwrite destination with source.
  - Description: overwrite destination with source.
  - Keywords: union of destination and source values.
  - Timezone: overwrite destination with source.
- **FR-005**: System MUST treat photo and video records as separate scenarios and
  expose a way to run only photos or only videos.
- **FR-006**: System MUST write metadata to videos in containers that a generic media
  player or indexer reads, not only into auxiliary sidecars.
- **FR-007**: System MUST NOT modify a file without first creating a centralized
  byte-for-byte backup of the original file.
- **FR-008**: System MUST allow the user to delete all backups in a single operation
  once they are satisfied.
- **FR-009**: System MUST provide a dry-run mode that produces a count breakdown per
  metadata field without modifying any file or creating any backup.
- **FR-010**: System MUST provide a per-run cap that limits how many files are
  modified, for incremental rollouts.
- **FR-011**: System MUST skip records flagged as ambiguous (multiple records sharing
  a capture-time within tolerance) and report the count of such records, rather than
  picking one arbitrarily.
- **FR-012**: System MUST tolerate the user's photo app being open or closed during
  metadata read.
- **FR-013**: System MUST log enough context for the user to inspect any failure
  (the file affected, the field attempted, the underlying tool's error message).
- **FR-014**: System MUST be safely re-runnable; running it again with the same data
  must not corrupt files or duplicate keywords.
- **FR-015**: System MUST NOT import face/person tags or album membership in this
  feature (out of scope; see Assumptions).
- **FR-016**: System MUST expose a verification mode that, after metadata writes,
  triggers a re-scan in the user's photo app and confirms a sample of modified assets
  surface the imported fields through the app's data interface.

### Key Entities *(include if feature involves data)*

- **Source library**: the second iCloud Photos library, in optimize-storage mode (no
  originals on disk), used only for its metadata database.
- **Bridge library**: the user's own iCloud Shared Photo Library database, used to
  resolve a capture-time from the source into the asset identifier the archive uses.
- **Archive**: the on-disk export of the user's photo library, with one file per
  asset; this is the destination of metadata writes.
- **Backup folder**: a single centralized location, separate from the archive, where
  pre-write copies of every modified file are stored under unique names.
- **Photo app**: the home-server photo application that indexes the archive in place
  (no copy) and exposes a query interface for end-to-end verification.
- **Metadata record**: a logical bundle of {GPS, favorite, rating, title, description,
  keywords, timezone} associated with a capture-time in the source library.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Photo enrichment scenario passes — every photo the system reports as
  "updated" reads back the expected value for every field that was changed, with a
  100% read-back match rate on a sample of 10 fixtures per metadata field.
- **SC-002**: Video enrichment scenario passes — same as SC-001 but on a sample of
  10 video fixtures, with metadata located in containers that the user's photo app
  surfaces (not only in auxiliary sidecars).
- **SC-003**: Backup integrity — for every file the system reports as modified, the
  user can restore the pre-modification state by copying its backup over the
  modified file, and the restored file matches the pre-modification file
  byte-for-byte.
- **SC-004**: Dry-run accuracy — the dry-run count of "files that would be updated
  per field" matches the actual modified count after the live run, within a 1%
  tolerance.
- **SC-005**: Backup cleanup — the user can reclaim 100% of backup-folder disk usage
  with a single operation after acceptance.
- **SC-006**: Photo-app verification — for each sampled modified asset, the photo
  app reports the imported title, description, GPS, favorite, rating, and keywords
  through its query interface, on a sample of 10 photos and 10 videos.
- **SC-007**: Re-runnability — running the import a second time on the same archive
  produces zero new modifications (no duplicate keywords, no flapped values).
- **SC-008**: Throughput — the import completes a full pass over the archive in
  under 3 hours of wall-clock time on the home server.

## Assumptions

- The second library is set to optimize-storage mode; this feature does not require
  its originals to be downloaded.
- The user's photo app is configured as an external library that indexes files in
  place; this means re-running a metadata write on a file is sufficient for the
  app to pick up changes on its next scan.
- Face/person tags are out of scope — the photo app's own face detection produces
  better results, and the source library has only a small number of named faces.
- Album membership is out of scope.
- The user accepts that the photo app must be running during the end-to-end
  verification phase (Story 3); during file-level scenarios it may be stopped.
- The user has read access to both the source library's database and the bridge
  library's database, in the same filesystem.
- Disk headroom of approximately 1× the size of the modified-file set must be
  available for backups; the user's RAID has terabytes of headroom and this is not
  a constraint for any realistic run.
- The IMP-011 plumbing for date-bridge matching is already in production and does
  not need to be re-derived in this feature; this feature extends that plumbing,
  it does not replace it.
- The existing prior-version script that handled GPS-only photo metadata writes
  comes under this feature's ownership and may be modified to pass the new
  scenarios.
