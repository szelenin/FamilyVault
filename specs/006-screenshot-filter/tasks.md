# Tasks: Screenshot & Garbage Filtering

**Input**: Design documents from `/specs/006-screenshot-filter/`
**Prerequisites**: plan.md, spec.md

**Tests**: TDD mandatory per Constitution Principle I.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

**Purpose**: No new files needed — modifying existing scripts.

- [X] T001 No setup needed — filter goes into existing `score_and_select.py`

---

## Phase 2: Foundational

**Purpose**: Enrich deviceId field so the filter can use it.

- [X] T002 Update `enrich_assets()` in `setup/story-engine/scripts/search_photos.py` to extract `deviceId` field from asset detail response and add to candidate dict

---

## Phase 3: User Story 1 + 2 — Screenshot & Story-Engine Exclusion (Priority: P1) MVP

**Goal**: Filter out screenshots (filename, resolution, missing EXIF) and story-engine clips (deviceId).

**Independent Test**: Search returns candidates → filter removes screenshots and generated clips → none appear in timeline.

### Tests

- [X] T003 [P] [US1] Write failing unit tests in `tests/story-engine/unit/test_scoring.py`: `test_filter_screenshot_by_filename`, `test_filter_screenshot_by_resolution`, `test_filter_screenshot_no_exif`, `test_filter_keeps_camera_photo_png`, `test_filter_keeps_photo_with_exif`
- [X] T004 [P] [US2] Write failing unit tests in `tests/story-engine/unit/test_scoring.py`: `test_filter_story_engine_clip`, `test_filter_keeps_user_video`
- [X] T005 Confirm T003–T004 tests fail

### Implementation

- [X] T006 Implement `filter_garbage()` in `setup/story-engine/scripts/score_and_select.py` — takes list of enriched candidates, returns (kept, filtered) tuple with reason strings. Checks: filename contains "Screenshot" (case-insensitive), deviceId == "story-engine", resolution matches known screen dimensions + no EXIF make/model + no GPS.
- [X] T007 Add `KNOWN_SCREEN_DIMENSIONS` constant in `score_and_select.py` — set of (width, height) tuples for iPhone/iPad screens.
- [X] T008 Confirm T003–T004 tests pass
- [X] T009 [US1] Wire `filter_garbage()` into the pipeline: call it after `enrich_assets()` and before `score_candidates()` in the skill workflow. Update SKILL.md with filter step.

**Checkpoint**: Screenshots and story-engine clips excluded. Camera photos preserved.

---

## Phase 4: User Story 3 — Non-Photo Content (Priority: P2)

**Goal**: Filter camphoto_*, RPReplay_*, and deprioritize metadata-poor assets.

### Tests

- [X] T010 [P] [US3] Write failing unit tests in `tests/story-engine/unit/test_scoring.py`: `test_filter_camphoto`, `test_filter_rpreplay`, `test_filter_no_metadata_deprioritized`
- [X] T011 Confirm T010 tests fail

### Implementation

- [X] T012 [US3] Add filename pattern checks to `filter_garbage()`: `camphoto_*`, `RPReplay_*`, `Simulator Screen Shot*`
- [X] T013 [US3] Add metadata-poor deprioritization: assets with no GPS, no city, no EXIF make, no faces get kept but deprioritized
- [X] T014 Confirm T010 tests pass

**Checkpoint**: All garbage types filtered. Metadata-poor assets deprioritized.

---

## Phase 5: Polish

- [X] T015 Add filter logging: `filter_garbage()` returns summary dict with counts per reason (e.g., `{"screenshot_filename": 5, "story_engine": 1, "camphoto": 2}`)
- [ ] T016 Write integration test in `tests/story-engine/integration/test_selection_pipeline.py`: `test_no_screenshots_in_pipeline` — run full pipeline against live Immich, verify zero screenshots in timeline
- [X] T017 Run full test suite: `pytest tests/story-engine/ -v` — 127 unit tests pass
- [X] T018 Update `setup/story-engine/scripts/score_and_select.py` docstring and SKILL.md with filter documentation

---

## Dependencies

- **Phase 2**: Must complete before Phase 3 (deviceId field needed)
- **Phase 3**: MVP — can stop here for immediate value
- **Phase 4**: Independent of Phase 3 implementation, just extends filter_garbage()
- **Phase 5**: After all user stories

## Implementation Strategy

### MVP (Phase 2 + 3): 8 tasks
Filters screenshots and story-engine clips. Biggest impact.

### Full (+ Phase 4 + 5): 18 tasks total
Adds non-photo filtering, logging, integration test.
