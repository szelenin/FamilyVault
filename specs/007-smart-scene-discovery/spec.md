# Feature Specification: Smart Scene Discovery

**Feature Branch**: `007-smart-scene-discovery`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "IMP-006: Two-phase scene discovery with prompt-aware detection, broad search, and scene-first workflow"

## Clarifications

### Session 2026-04-09

- Q: What format should each scene be presented in during Phase A? → A: Rich format: scene number, auto-label (city + time-of-day), time range, photo count, video count. Plus one preview album containing ALL discovered content (single share link), with scenes indicated by position ranges ("Scene 3 Vizcaya starts at photo 15").
- Q: How to handle broad search returning too many candidates? → A: No silent cap. If search returns more than 500 candidates, inform the user with the count and ask: proceed with all content, or refine criteria (add date range, person filter, additional keywords). User decides whether to narrow or go with everything.
- Q: How should scene labels be generated? → A: Dynamically by the AI skill, not a static template. The AI uses the user's prompt as the primary labeling hint (match scene content to prompt keywords: "speedboat" cluster → "Speedboat tour"). For unmatched scenes, use richest metadata available (city + faces + CLIP descriptions). Scripts provide raw scene data; the AI crafts labels in conversation context.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Two-Phase Scene Discovery for Trips (Priority: P1)

When a user asks for a trip clip (e.g., "make a clip of our Miami trip"), the system first discovers ALL scenes from the trip and presents them to the user — with no budget limits. The user sees every detected scene with item counts, time ranges, and sample content. Only after the user reviews and confirms which scenes to include does the system apply scoring and budget to build the final timeline.

**Why this priority**: The current one-pass approach misses scenes entirely (Coconut Grove walk was invisible because city filter excluded it). Users need to see all content before the system decides what to include.

**Independent Test**: Request a trip clip → verify ALL scenes are listed with no budget cap → user confirms → final timeline reflects only confirmed scenes with budget applied.

**Acceptance Scenarios**:

1. **Given** a user requests "make a clip of our Miami trip in March", **When** the system runs Phase A (Scene Discovery), **Then** it shows ALL detected scenes in chronological order with: scene name/label, time range, total items (photos + videos), and sample content identifiers.

2. **Given** the system detected 24 scenes from a trip, **When** presenting to the user, **Then** no scenes are hidden or excluded by budget — the user sees all 24 with item counts.

3. **Given** the user says "include scenes 1, 3, 5, 8, 12" or "skip the airport scenes", **When** the system runs Phase B (Selection), **Then** it applies scoring and budget only to the confirmed scenes and builds the timeline.

4. **Given** the user says "looks good, include all", **When** the system runs Phase B, **Then** all scenes are included with budget distributed proportionally.

5. **Given** photos exist in Coconut Grove (a Miami neighborhood) during the trip dates, **When** the system searches broadly, **Then** those photos appear as a scene even though the Immich city field says "Coconut Grove" not "Miami".

---

### User Story 2 - Broad Search Without Exact City Filtering (Priority: P1)

The system searches broadly using CLIP semantic search as the primary method, without restricting to exact city names in metadata. Metadata city search is used as an additional signal, not a hard filter. Nearby neighborhoods, suburbs, and landmarks are included.

**Why this priority**: The narrow city filter caused the biggest miss in testing — an entire evening walk scene was invisible. This is directly tied to US1's scene discovery quality.

**Independent Test**: Search for "Miami trip" → verify results include assets from Coconut Grove, Miami Beach, Coral Gables, and other nearby areas — not just assets with city="Miami".

**Acceptance Scenarios**:

1. **Given** assets in Immich with city metadata "Coconut Grove", "Miami Beach", "Coral Gables", and "Miami", **When** the system searches for a Miami trip, **Then** all four cities' assets appear in the candidate pool.

2. **Given** a CLIP search for "miami trip" returns assets with no city metadata but relevant content, **When** the system evaluates candidates, **Then** those assets are included (not filtered out for missing city).

3. **Given** a CLIP search returns an asset from New York with no relation to Miami, **When** the system evaluates candidates, **Then** it is deprioritized by low relevance score but not hard-excluded (the scoring pipeline handles ranking).

---

### User Story 3 - Must-Have Scene Verification (Priority: P2)

When the user mentions specific scenes they expect ("speedboat, vizcaya garden, sunset walk, passport"), the system verifies that each expected scene appears in the discovered scene list. Missing scenes trigger additional targeted searches.

**Why this priority**: Users know what happened on their trip. If they mention a scene and the system can't find it, that's a critical gap. But this builds on top of US1/US2 — broad search should find most content, and this is the safety net.

**Independent Test**: Request a clip with must-have keywords → verify each keyword maps to at least one detected scene → if missing, system runs targeted search and reports.

**Acceptance Scenarios**:

1. **Given** the user says "speedboat, vizcaya garden, sunset walk, passport must have", **When** the system finishes Scene Discovery, **Then** it cross-references each keyword against scene content and reports: "Found: speedboat (Scene 8), vizcaya (Scene 12), sunset (Scene 14), passport (Scene 10)".

2. **Given** the keyword "vizcaya garden" doesn't match any scene by name, **When** the system runs targeted search for "vizcaya", **Then** it finds matching assets and either creates a new scene or merges them into an existing scene at the same time range.

3. **Given** the keyword "parasailing" matches zero assets in the library, **When** the system reports, **Then** it tells the user: "Could not find content matching 'parasailing'. Did you mean something else?"

---

### User Story 4 - Prompt-Aware Scene Detection Modes (Priority: P3)

Different types of requests use different scene detection strategies. A trip clip uses location+date clustering. A "how my son grows" request uses person+time clustering. The system evaluates the prompt and selects the appropriate mode.

**Why this priority**: This enables future use cases beyond trip clips. However, the trip mode (US1-US3) must work well first before adding other modes. This story defines the extension points without requiring full implementation of all modes.

**Independent Test**: Submit different prompt types → verify the system selects the correct detection mode and applies appropriate clustering.

**Acceptance Scenarios**:

1. **Given** the user says "make a clip of our Miami trip", **When** the system evaluates the prompt, **Then** it selects "trip" mode: search by location + date range, cluster scenes by 30-minute time gaps within the trip.

2. **Given** the user says "make a clip of how Edgar grows up", **When** the system evaluates the prompt, **Then** it selects "person-timeline" mode: search by person name across all dates, cluster scenes by significant time intervals (months/years).

3. **Given** the system doesn't recognize the prompt type, **When** it defaults, **Then** it uses "general" mode: broad CLIP search with time-based scene clustering, and asks the user for clarification on date range.

---

### Edge Cases

- What if a trip spans multiple cities (e.g., Miami → Key West → Fort Lauderdale)? Each city should form its own scenes, all included in the discovery list.
- What if no scenes are detected for a date range? System informs user and suggests expanding the date range or trying different search terms.
- What if a must-have keyword matches content outside the trip date range? System asks user: "Found vizcaya photos from 2024. Include those too?"
- What if the user confirms 0 scenes (says "none of these")? System asks what they're looking for and tries a different search approach.
- What if there are 100+ scenes? Group by day and show day-level summary first, with ability to expand individual days.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement a two-phase workflow: Phase A (Scene Discovery) discovers and presents all scenes; Phase B (Selection) applies budget after user confirmation.
- **FR-002**: Phase A MUST show all detected scenes with: auto-generated scene label (city + time-of-day), time range, photo count, video count. One Immich preview album MUST be created containing all discovered content (single share link), with scene boundaries indicated by position ranges in the scene list.
- **FR-003**: System MUST NOT apply budget limits during Phase A — all scenes are shown regardless of count.
- **FR-004**: System MUST search broadly using CLIP semantic search as primary method, without hard-filtering by city name in metadata. If search returns more than 500 candidates, the system MUST inform the user with the count and offer to proceed with all content or refine criteria (add dates, person filter, keywords). No silent capping.
- **FR-005**: System MUST also run metadata search (by date range, known cities) as a supplementary signal and merge results with CLIP search.
- **FR-006**: Scene detection MUST group candidates by 30-minute time gaps for trip mode (existing algorithm).
- **FR-007**: Scene labels MUST be generated dynamically by the AI skill using the user's prompt as primary context. Prompt keywords are matched to scene content first (e.g., "speedboat" cluster → "Speedboat tour"). Unmatched scenes are labeled from the richest available metadata (city, people names, CLIP descriptions, time of day). Scripts provide raw scene data (timestamps, cities, face names, descriptions); the AI crafts human-readable labels. No hardcoded label templates.
- **FR-008**: System MUST extract must-have keywords from the user's prompt and verify each maps to at least one detected scene after Phase A. Missing must-haves trigger targeted follow-up searches.
- **FR-009**: System MUST support a "confirm" step between Phase A and Phase B where the user selects which scenes to include (all, specific list, or exclude specific ones).
- **FR-010**: Phase B MUST apply scoring, dedup, and budget allocation only to confirmed scenes.
- **FR-011**: System MUST apply garbage filtering (screenshots, story-engine clips) automatically during Phase A before scene detection.
- **FR-012**: System MUST support a "trip" detection mode (location+date clustering) as the default for trip-related prompts.
- **FR-013**: System MUST define an extension point for future detection modes (person-timeline, pet-timeline, general) without requiring them to be fully implemented now.
- **FR-014**: When scenes exceed 20, the system MUST group them by day and show a day-level summary first, expandable to individual scenes.

### Key Entities

- **Scene Discovery Result**: The output of Phase A — a list of all detected scenes with metadata, item counts, and sample content. Stored in the project file under a `discovery` field.
- **Detection Mode**: An enumeration of scene detection strategies: `trip` (location+date), `person-timeline` (person+time), `general` (broad CLIP+time). Selected based on prompt analysis.
- **Scene Confirmation**: The user's selection of which scenes to include/exclude. Stored in the project file. Drives Phase B.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When given a trip with content in multiple nearby cities (e.g., Miami + Coconut Grove + Miami Beach), all cities' content appears in Scene Discovery results.
- **SC-002**: Scene Discovery shows 100% of detected scenes — zero scenes hidden by budget or filtering (except garbage).
- **SC-003**: All user-specified must-have keywords are either matched to a scene or explicitly reported as not found within 2 conversation turns.
- **SC-004**: The Phase A → confirm → Phase B workflow completes in under 3 conversation turns for a typical trip request.
- **SC-005**: Scene Discovery (Phase A) completes within 90 seconds for a library of 100K assets and a trip of 200+ photos.

## Assumptions

- The existing `detect_scenes()` function (30-minute gap clustering) works well for trips and can be reused for Phase A.
- CLIP semantic search provides good enough recall to find trip content across nearby cities without exact city filtering.
- Scene labels can be auto-generated from city + time-of-day without custom ML models.
- Only "trip" detection mode needs full implementation now. Other modes (person-timeline, general) are extension points defined but not built.
- The garbage filter from IMP-009 (006-screenshot-filter) is already in the pipeline and applied before scene detection.
