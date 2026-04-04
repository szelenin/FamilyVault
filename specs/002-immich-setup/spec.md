# Feature Specification: Immich Setup

**Feature Branch**: `002-immich-setup`
**Created**: 2026-04-04
**Status**: Draft
**Downstream dependency**: `001-ai-story-engine` requires this to be complete.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Immich Running and Accessible (Priority: P1)

Immich is deployed on the Mac Mini via Docker and is accessible via a web
browser on the local network. The service starts automatically when the Mac
Mini boots and recovers automatically if a container crashes.

**Why this priority**: Everything else depends on Immich being up. Without a
running instance, no indexing, no browsing, no Story Engine.

**Independent Test**: Can be fully tested by opening `http://macmini.local:2283`
in a browser on any device on the local network and seeing the Immich login
screen. Restart the Mac Mini and verify Immich comes back up without manual
intervention.

**Acceptance Scenarios**:

1. **Given** the Mac Mini has booted, **When** a browser navigates to
   `http://macmini.local:2283`, **Then** the Immich web UI loads and an admin
   account can be created or logged into.

2. **Given** Immich is running, **When** a Docker container is manually stopped,
   **Then** it restarts automatically within 30 seconds without manual
   intervention.

3. **Given** the Mac Mini is rebooted, **When** it finishes starting up, **Then**
   Immich is accessible within 2 minutes without any manual steps.

---

### User Story 2 — External Library Indexed (Priority: P2)

The iCloud photo export at `/Volumes/HomeRAID/icloud-export` is configured as
an Immich external library. Immich indexes the files in place — no copying or
moving — and makes them browsable by date, location, and person.

**Why this priority**: The core value of Immich for this project is browsing
the existing photo library. Without the external library configured and indexed,
Immich is an empty shell.

**Independent Test**: Can be tested by opening Immich, navigating to the library,
and verifying that photos from the icloud-export folder appear with correct dates,
locations, and thumbnail previews. Verify no files were copied or moved from
their original location.

**Acceptance Scenarios**:

1. **Given** the external library is configured, **When** Immich completes its
   initial scan, **Then** the photo count in Immich matches the file count in
   `/Volumes/HomeRAID/icloud-export` (within 1% tolerance for unsupported formats).

2. **Given** osxphotos adds new files to `/Volumes/HomeRAID/icloud-export` via
   the nightly sync, **When** the next scheduled library scan runs, **Then** the
   new files appear in Immich without manual intervention.

3. **Given** a photo in the external library, **When** viewed in Immich, **Then**
   it displays the correct capture date, GPS location (if available), and is
   shown in the correct position in the timeline.

---

### User Story 3 — Face Recognition and Search Enabled (Priority: P3)

Immich's face recognition and CLIP-based semantic search are enabled and
processing the library. People can be named, and photos can be found by
searching natural language descriptions.

**Why this priority**: Face recognition and semantic search are the data layer
the AI Story Engine depends on to find relevant content. Without them, the
Story Engine cannot identify who is in photos or find content by description.

**Independent Test**: Can be tested by searching "birthday cake" in Immich and
verifying relevant photos appear, and by confirming that face clusters are
generated and can be assigned names.

**Acceptance Scenarios**:

1. **Given** the library has been indexed, **When** a user searches "beach" or
   "birthday", **Then** Immich returns visually relevant results using semantic
   understanding (not just filename matching).

2. **Given** the library contains photos of the same person across multiple years,
   **When** face recognition completes, **Then** those photos are grouped into a
   single person cluster that can be given a name.

3. **Given** a named person in Immich, **When** a user filters by that person,
   **Then** only photos containing that person are shown.

---

### Edge Cases

- What if the RAID is not mounted when Immich starts? Immich MUST log an error
  and the external library MUST show as unavailable — no crash, no data loss.
- What if the icloud-export folder is empty at first start (download still in
  progress)? Immich MUST start successfully with an empty library and pick up
  files as they appear during subsequent scans.
- What if Docker is not installed? Setup MUST fail with a clear error message
  pointing to the installation step.
- What if port 2283 is already in use on the Mac Mini? Setup MUST detect the
  conflict and report it clearly before attempting to start.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Immich MUST be deployed via Docker Compose on the Mac Mini and
  accessible at `http://macmini.local:2283` on the local network.
- **FR-002**: All Immich containers MUST be configured to restart automatically
  on failure and on Mac Mini boot (restart policy: `unless-stopped`).
- **FR-003**: Immich data (database, thumbnails, config) MUST be stored on
  `/Volumes/HomeRAID/immich` — not on the Mac Mini's internal drive.
- **FR-004**: `/Volumes/HomeRAID/icloud-export` MUST be configured as an Immich
  external library — files are indexed in place, never copied.
- **FR-005**: The external library MUST be scanned automatically on a schedule
  (at minimum daily) to pick up new files from the nightly osxphotos sync.
- **FR-006**: Face recognition MUST be enabled and run automatically as new
  photos are indexed.
- **FR-007**: CLIP-based semantic search MUST be enabled so photos are findable
  by natural language description.
- **FR-008**: Immich MUST expose its REST API at `http://macmini.local:2283/api`
  for use by the AI Story Engine and ImmichMCP.
- **FR-009**: Setup MUST be repeatable and documented — running the setup process
  again on a clean Mac Mini MUST produce the same result.

### Key Entities

- **Immich Instance**: The running Docker Compose stack — web server, background
  workers, machine learning service, PostgreSQL, Redis.
- **External Library**: A mount point in Immich pointing at
  `/Volumes/HomeRAID/icloud-export`. Read-only from Immich's perspective —
  source files are owned by osxphotos.
- **Library Scan**: A scheduled job that detects new/changed/deleted files in
  the external library and updates Immich's index.
- **Person Cluster**: A group of faces Immich has determined belong to the same
  individual, optionally assigned a name by the user.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Immich web UI is accessible at `http://macmini.local:2283` within
  2 minutes of Mac Mini boot, with no manual steps required.
- **SC-002**: 100% of JPEG, HEIC, and MP4 files in the icloud-export folder
  appear in Immich after the initial library scan completes.
- **SC-003**: A semantic search query ("birthday", "beach", "snow") returns
  visually relevant results — at least 80% of top-10 results are genuinely
  relevant to the query.
- **SC-004**: Face recognition groups the same person's photos together with
  fewer than 5% false positives across a sample of 100 photos.
- **SC-005**: The Immich REST API responds to a health-check request within
  500ms under normal operating conditions.
- **SC-006**: New files added to icloud-export appear in Immich within 24 hours
  without manual intervention.

## Assumptions

- Docker Desktop for Mac is not used — Docker is installed via Homebrew or
  OrbStack to avoid licensing restrictions and reduce overhead on a headless
  server.
- The Mac Mini remains powered on 24/7 as a home server.
- The RAID at `/Volumes/HomeRAID` is mounted before Docker starts; a boot-time
  check ensures this ordering.
- Immich version pinned at setup time; upgrades are a separate operation and
  out of scope for this spec.
- The icloud-export folder may be empty or partially populated at first setup —
  the full iCloud download may still be in progress.
- Network access to Immich from outside the home network (remote access) is
  out of scope for v1.
- This spec is a prerequisite for `001-ai-story-engine` (Story Engine) and
  `003-immich-mcp` (ImmichMCP integration).
