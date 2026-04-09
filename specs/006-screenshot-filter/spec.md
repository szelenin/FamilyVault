# Feature Specification: Screenshot & Garbage Filtering

**Feature Branch**: `006-screenshot-filter`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "IMP-009: Screenshot and garbage filtering for Story Engine selection pipeline"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Screenshot Exclusion (Priority: P1)

When the system searches for trip photos, screenshots (screen captures, app exports, screen recordings) are automatically excluded from the candidate pool. The user never sees screenshots in their timeline unless they explicitly request them.

**Why this priority**: Screenshots appeared in every test run (e.g., IMG_7280.PNG, "Screenshot 2024-11-14"). They're the most common garbage type and the easiest to detect.

**Independent Test**: Run a search that includes assets with screenshot characteristics → verify none appear in the candidate pool.

**Acceptance Scenarios**:

1. **Given** a library containing photos and screenshots, **When** the system searches for trip content, **Then** assets with "Screenshot" in the filename are excluded from the candidate pool.
2. **Given** a PNG file with no camera EXIF data (no make/model), **When** the system evaluates candidates, **Then** it is flagged as a likely screenshot and excluded.
3. **Given** an image with resolution matching known screen dimensions (e.g., 1170x2532 for iPhone 13 Pro), **When** the system evaluates candidates, **Then** it is flagged as a likely screenshot and excluded.
4. **Given** a legitimate photo that happens to be PNG format but has camera EXIF data, **When** the system evaluates candidates, **Then** it is NOT excluded (false positive prevention).

---

### User Story 2 - Story Engine Generated Clip Exclusion (Priority: P1)

Previously generated story engine clips uploaded to Immich are automatically excluded from search results, preventing the system from including its own output in new clips.

**Why this priority**: In testing, the v1 generated clip (output.mp4, deviceId=story-engine) appeared as a candidate. This creates a feedback loop of including old clips in new ones.

**Independent Test**: Upload a clip with deviceId=story-engine → run a search → verify it does not appear in results.

**Acceptance Scenarios**:

1. **Given** a video asset with `deviceId=story-engine` in Immich, **When** the system searches for content, **Then** that asset is excluded from the candidate pool.
2. **Given** a user-uploaded video (deviceId != story-engine), **When** the system searches, **Then** it is included normally.

---

### User Story 3 - Non-Photo Content Filtering (Priority: P2)

Screen recordings, app-generated images (camphoto_* files), and other non-camera content are detected and excluded from the candidate pool.

**Why this priority**: Less common than screenshots but still appeared in testing (camphoto_959030623.jpg with no faces, no location). Lower priority because these are harder to detect reliably.

**Independent Test**: Include known non-photo files in a candidate pool → verify they are filtered out.

**Acceptance Scenarios**:

1. **Given** a file with "camphoto_" prefix in the filename, **When** the system evaluates candidates, **Then** it is excluded as app-generated content.
2. **Given** a video file named "RPReplay_" (screen recording), **When** the system evaluates candidates, **Then** it is excluded.
3. **Given** an asset with no GPS coordinates, no city, no camera make/model, and no faces detected, **When** the system evaluates candidates, **Then** it receives a low confidence score and is deprioritized (not hard-excluded, since some legitimate photos lack metadata).

---

### Edge Cases

- What if a user intentionally screenshots a photo to share? It should still be excluded — the original photo should be in the library.
- What if a photo has no EXIF because it was edited in a third-party app? Don't hard-exclude — deprioritize it via low score instead.
- What if screen dimensions change with new iPhone models? The known-dimensions list should be configurable and easy to extend.
- What if a user wants to include a screenshot in their clip? The filter should be bypassable via explicit request ("include screenshots").

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST exclude assets with "Screenshot" (case-insensitive) in the filename from the candidate pool.
- **FR-002**: System MUST exclude assets with `deviceId=story-engine` from the candidate pool.
- **FR-003**: System MUST flag assets as likely screenshots when ALL of: (a) no camera make/model in EXIF, (b) image resolution matches a known screen dimension, (c) no GPS coordinates.
- **FR-004**: System MUST maintain a configurable list of known screen resolutions (iPhone, iPad) for screenshot detection.
- **FR-005**: System MUST exclude assets with known non-photo filename patterns: `camphoto_*`, `RPReplay_*`, `Simulator Screen Shot*`.
- **FR-006**: System MUST NOT hard-exclude assets that have camera EXIF data, even if they match other screenshot signals (false positive prevention).
- **FR-007**: The garbage filter MUST run as part of the `enrich_assets()` pipeline, after metadata is fetched but before scoring.
- **FR-008**: System MUST log filtered assets (count and reason) so the user can be informed: "Filtered 12 screenshots, 1 generated clip."
- **FR-009**: System MUST allow the user to override the filter via explicit request (e.g., "include screenshots").

### Key Entities

- **Garbage Filter**: A function that evaluates each enriched candidate and returns a keep/exclude decision with a reason string. Applied between enrichment and scoring in the pipeline.
- **Screen Dimensions List**: A configurable list of known screen resolutions (width x height) used for screenshot detection. Stored as a constant in the filter module.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero screenshots appear in any auto-generated timeline when the filter is active.
- **SC-002**: Zero story-engine generated clips appear in search results.
- **SC-003**: No legitimate camera photos are incorrectly filtered (zero false positives for assets with camera EXIF data).
- **SC-004**: The filter adds less than 1 second to the selection pipeline for 500 candidates.

## Assumptions

- Screenshots in the library primarily come from iPhones/iPads with known screen resolutions.
- The `deviceId` field on Immich assets reliably identifies story-engine generated content.
- Camera EXIF make/model is present on all legitimate photos taken with a phone or camera.
- The filter runs locally on already-enriched candidate data — no additional Immich API calls needed.
