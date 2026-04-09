# Feature Specification: Smart Photo & Video Selection

**Feature Branch**: `005-smart-photo-selection`  
**Created**: 2026-04-07  
**Status**: Draft  
**Input**: User description: "Smart photo and video selection with quality scoring, deduplication, and visual timeline preview for Story Engine v2"

## Clarifications

### Session 2026-04-08

- Q: How should quality score weights be determined — fixed, prompt-driven, or hybrid? → A: Two-phase approach: AI extracts must-have items from the prompt as guaranteed slots (with fuzzy multi-query search for typo tolerance), then fills remaining slots using fixed-weight scoring (faces 40%, relevance 30%, diversity 20%, resolution 10%).
- Q: What lifecycle states should the project file support? → A: Extended forward-only: `searching → selecting → previewing → approved → generated`, with the exception that `approved` can go back to `previewing` for further refinement.
- Q: How should the system handle Immich API failures during multi-query search? → A: Silently retry failed queries up to 3 times, then proceed with whatever succeeded. Warn the user only if some queries still failed after retries.
- Q: How should default selection size be determined? → A: Budget-based with scene-aware allocation (D3). Total budget = base 10 + 5 per day of trip (capped at 60). Budget distributed proportionally across days by scene count, then within each day across scenes by candidate richness. Minimum 1 item per scene. User can adjust total budget ("make it longer/shorter") and per-scene allocation ("more boat tour, less airport").

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Smart Auto-Selection from Trip Photos (Priority: P1)

A user asks the AI to create a clip about a family trip (e.g., "make a clip of our Miami trip"). The system searches across multiple criteria (location, date range, people, semantic content), gathers all matching photos and videos into a candidate pool, scores them for quality, removes duplicates, ensures diversity across moments, and presents the top selection as a scenario.

**Why this priority**: This is the core problem — v1 returned sequential garbage photos with no quality filtering or deduplication. Fixing selection quality is the single highest-impact improvement.

**Independent Test**: Can be fully tested by requesting a trip clip and verifying the selected photos span different moments, have no near-duplicates, and meet minimum quality thresholds. Delivers immediately better clip content without any other improvements.

**Acceptance Scenarios**:

1. **Given** a user requests "make a clip of our Miami trip in March", **When** the system searches for matching content, **Then** it issues multiple search queries (by location, by date range, by semantic content) and merges results into a single candidate pool with no duplicate assets.

2. **Given** a candidate pool of 200+ photos from a trip, **When** the system scores and ranks candidates, **Then** each candidate has a quality score based on: presence of faces, image resolution, and content relevance — and the pool is sorted by score descending.

3. **Given** 10 photos taken within 5 seconds of each other (a burst), **When** the system deduplicates, **Then** it keeps the highest-scoring photo as the primary selection and stores 2-3 alternates per burst group for potential user swaps.

4. **Given** 30 beach photos and 5 restaurant photos from a week-long trip, **When** the system enforces diversity, **Then** the final selection includes photos from multiple distinct moments/scenes across different days and times, not dominated by a single scene.

5. **Given** the system has selected 15 photos and 3 video clips, **When** it creates the scenario, **Then** it auto-determines clip duration based on the number of selected items and presents the scenario to the user for review.

---

### User Story 2 - Visual Timeline Preview (Priority: P2)

After auto-selection, the user sees a visual preview of the selected photos and videos in chronological order. On desktop Claude Code, thumbnails are shown inline. On mobile, a shared Immich album link is provided. The user can approve, swap individual items, reorder, or remove items through conversation.

**Why this priority**: Users need to see actual photos before generation. In v1, the user only saw AI-generated captions that didn't reflect real content, leading to surprise at the poor result.

**Independent Test**: Can be tested by generating a selection and verifying thumbnails or album links are displayed, and that swap/remove commands update the timeline correctly.

**Acceptance Scenarios**:

1. **Given** a completed auto-selection of 15 items, **When** the user is on desktop Claude Code, **Then** the system displays a numbered timeline with inline thumbnail images, timestamps, and quality scores for each item.

2. **Given** a completed auto-selection, **When** the user is on mobile, **Then** the system creates a temporary Immich shared album containing the selected items and provides a plain-text share link.

3. **Given** the user says "replace #3", **When** the system looks up alternates for position 3, **Then** it shows 2-3 similar photos from the same burst/moment group and lets the user pick a replacement.

4. **Given** the user says "remove #7 and #8", **When** the system processes the command, **Then** those items are removed and remaining items renumber automatically.

5. **Given** the user says "make it shorter" or "only 10 photos", **When** the system adjusts, **Then** it keeps the highest-scoring items and re-presents the timeline.

---

### User Story 3 - Video Clip Inclusion (Priority: P3)

Trip videos are included alongside photos in the candidate pool and final selection. Each video clip is included at full length by default, with the ability for the user to trim via conversation.

**Why this priority**: Users shoot both photos and videos on trips. Excluding videos makes clips feel incomplete. However, smart photo selection (US1) is more critical to fix first.

**Independent Test**: Can be tested by running a search that matches trip videos and verifying they appear in the candidate pool, are scored, and appear in the generated timeline with their full duration.

**Acceptance Scenarios**:

1. **Given** a trip has both photos and videos in Immich, **When** the system builds the candidate pool, **Then** videos are included alongside photos with type clearly marked.

2. **Given** a video clip is 45 seconds long, **When** it is added to the timeline, **Then** it appears at its full duration by default.

3. **Given** the user says "trim video #4 to first 5 seconds", **When** the system processes the command, **Then** the timeline updates to show the video with start=0:00 and end=0:05.

4. **Given** a mix of 12 photos and 3 video clips in the final selection, **When** the clip is generated, **Then** the output seamlessly interleaves photos (as still frames) and video clips (with original audio) with transitions between them.

---

### User Story 4 - Video Output Quality (Priority: P2)

The generated video clip has high visual quality appropriate for phone and laptop viewing. No unnecessary lossy conversions. Adequate bitrate for smooth transitions.

**Why this priority**: The v1 output was 1 Mbps at 1080p — visibly compressed. This is a quick win that dramatically improves perceived quality alongside better selection.

**Independent Test**: Can be tested by generating a clip and measuring output bitrate, resolution, and codec settings via ffprobe. Visual quality can be spot-checked on phone and laptop.

**Acceptance Scenarios**:

1. **Given** a set of 4032x3024 iPhone photos, **When** a clip is generated for phone viewing, **Then** the output is 1080p at 5-8 Mbps with no visible compression artifacts during transitions.

2. **Given** source photos are HEIC format, **When** the assembly pipeline processes them, **Then** no intermediate lossy JPEG conversion occurs — HEIC is decoded directly or converted at maximum quality.

3. **Given** a crossfade transition between two photos, **When** the video is played on a phone, **Then** the transition is smooth with no visible blockiness or banding.

---

### Edge Cases

- What happens when a trip has fewer than 5 matching photos? System should still produce a clip with what's available, with a warning that limited content was found.
- What happens when all photos from a trip are near-identical (e.g., a photo booth)? System picks the best 3-5 and warns the user about limited diversity.
- What happens when a video clip is very long (>5 minutes)? System includes it but suggests trimming to the user.
- What happens when Immich smart search returns irrelevant results for a query? The multi-query approach (date + location + semantic) should cross-validate — items matching on multiple criteria score higher.
- What happens when the user requests a swap but no alternates exist for that slot? System informs the user and suggests running a new targeted search.
- What happens when Immich API calls fail during multi-query search? System silently retries each failed query up to 3 times, then proceeds with partial results from whichever queries succeeded. User is warned only if some queries remain failed after retries.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST issue multiple search queries per request (location, date range, people, semantic) and merge results into a deduplicated candidate pool.
- **FR-001a**: System MUST extract "must-have" items from the user's prompt (e.g., "speed boat, vizcaya garden, sunset") and run targeted searches for each. Must-have items are guaranteed slots in the final selection (best match per must-have keyword).
- **FR-001b**: For each must-have keyword, the system MUST attempt multiple search variations to handle typos and metadata mismatches (e.g., "viscaya" → also try "vizcaya", "vizcaya gardens", nearby GPS coordinates). Immich smart search (CLIP-based) provides natural fuzzy matching; the system should also try location/metadata search as a fallback.
- **FR-002**: System MUST score remaining (non-must-have) candidates using fixed-weight formulas. Photos: faces (40%), content relevance (30%), timestamp diversity (20%), resolution (10%). Videos: content relevance (40%), duration (25%, sweet spot 5-30s scores highest), diversity (20%), faces (15%). When a photo and video exist from the same moment, the video is the default primary pick but the photos are kept as alternates in the burst group for user swaps. Must-have items bypass scoring — they are selected by best match to the keyword.
- **FR-003**: System MUST detect burst groups (photos taken within 5 seconds of each other) and select only the highest-scoring photo per group.
- **FR-004**: System MUST store 2-3 alternate candidates per burst group for user swap requests.
- **FR-005**: System MUST enforce diversity in the final selection — no more than 30% of selected items from any single 30-minute window.
- **FR-006**: System MUST include both photos and videos in the candidate pool when available.
- **FR-007**: System MUST store the full candidate pool, scores, burst groups, and selected timeline as a project file on the filesystem.
- **FR-008**: System MUST create a temporary Immich shared album with the selected items as the preview mechanism. The share link MUST be provided as plain text (no markdown wrapping).
- **FR-009**: System MUST clean up old preview albums when creating a new one for the same project, to avoid album clutter.
- **FR-010**: System MUST support swap, remove, reorder, and trim commands via natural language conversation.
- **FR-011**: System MUST auto-determine selection size using a budget formula: base 10 + 5 per day of trip, capped at 60 items. Budget is distributed proportionally across days (by scene count) and within each day across scenes (by candidate richness), with a minimum of 1 item per scene. User can adjust the total budget ("make it longer") and per-scene allocation ("more boat tour photos, fewer airport").
- **FR-012**: System MUST generate video output at minimum 5 Mbps for 1080p resolution.
- **FR-013**: System MUST NOT perform lossy HEIC-to-JPEG conversion before video assembly. HEIC files must be decoded directly or converted at maximum quality.
- **FR-014**: System MUST use captions derived from actual photo content (Immich AI descriptions, EXIF data, scene detection) rather than AI-hallucinated descriptions.
- **FR-015**: System MUST support video clips in the timeline with configurable start/end trim points.

### Key Entities

- **Candidate Pool**: The full set of matching assets from multi-query search, each with quality scores and burst group assignments. Persisted as part of the project file.
- **Burst Group**: A cluster of near-identical photos (taken within 5 seconds), with one primary selection and 2-3 alternates.
- **Timeline**: The ordered sequence of selected photos and video clips with per-item metadata (position, duration, trim points, transition type).
- **Project File**: A JSON file on the filesystem containing the candidate pool, timeline, alternates, and project state. Replaces the simpler scenario.json from v1. Lifecycle states: `searching → selecting → previewing → approved → generated` (forward-only, except `approved` may return to `previewing` for refinement).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When given a trip with 200+ photos, the auto-selected photos span at least 60% of the trip's distinct days/times with no more than 2 near-duplicate photos in the final selection.
- **SC-002**: Users can preview all selected photos visually (thumbnails or album link) before approving generation.
- **SC-003**: Users can swap any individual photo with an alternate in under 2 conversation turns.
- **SC-004**: Generated video output has a bitrate of at least 5 Mbps at 1080p, with no visible compression artifacts during transitions when viewed on a phone.
- **SC-005**: The full selection pipeline (search, score, dedup, rank) completes within 60 seconds for a library of up to 100K assets.
- **SC-006**: At least 80% of auto-selected photos contain recognizable subjects (people, landmarks, activities) rather than accidental/unclear shots (sky fragments, blurred frames, blank surfaces).

## Assumptions

- Immich is the sole photo/video source and its API provides face detection, CLIP embeddings, thumbhash, and resolution metadata for all indexed assets.
- The user primarily interacts via Claude Code (desktop) or Claude mobile. Desktop supports inline image rendering; mobile does not.
- Photo libraries contain a mix of HEIC (iPhone) and JPEG images. Video formats include MOV and MP4.
- The Mac Mini running FFmpeg has sufficient processing power for video assembly at higher bitrates.
- The existing scenario.json format from v1 will be superseded by the new project file format. Backward compatibility with v1 scenarios is not required.
- Music integration is out of scope for this specification and will be addressed separately.
