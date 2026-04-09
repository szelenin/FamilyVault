# Tasks: Smart Scene Discovery

**Input**: Design documents from `/specs/007-smart-scene-discovery/`
**Prerequisites**: plan.md, spec.md

**Tests**: TDD mandatory per Constitution Principle I.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Foundational — Project File Extension

**Purpose**: Add discovery and confirmation fields to project file.

### Tests

- [X] T001 [P] Write failing unit tests in `tests/story-engine/unit/test_project_file.py`: `test_create_project_has_discovery_field`, `test_set_discovery_result`, `test_set_scene_confirmation_include_all`, `test_set_scene_confirmation_specific_scenes`, `test_set_scene_confirmation_exclude_scenes`
- [X] T002 Confirm T001 tests fail

### Implementation

- [X] T003 Add `discovery` field (dict with `scenes`, `total_candidates`, `preview`) and `scene_confirmation` field (list of confirmed scene IDs or "all") to project file in `setup/story-engine/scripts/manage_project.py`
- [X] T004 Implement `set_discovery()` and `set_scene_confirmation()` functions in `manage_project.py`
- [X] T005 Confirm T001 tests pass

**Checkpoint**: Project file supports discovery and confirmation data.

---

## Phase 2: User Story 1 + 2 — Broad Search + Scene Discovery (Priority: P1) MVP

**Goal**: CLIP-first broad search, discover all scenes, present to user with preview album.

**Independent Test**: Search for trip → get ALL scenes listed with no budget cap → preview album with all content.

### Tests

- [X] T006 [P] [US1] Write failing unit tests in `tests/story-engine/unit/test_scoring.py`: `test_discover_scenes_returns_all`, `test_discover_scenes_no_budget_cap`, `test_discover_scenes_trip_mode`, `test_discover_scenes_groups_by_day_over_20`
- [X] T007 [P] [US2] Write failing unit tests in `tests/story-engine/unit/test_search.py`: `test_search_broad_no_city_filter`, `test_search_broad_merges_clip_and_metadata`, `test_search_broad_asks_user_over_500`
- [X] T008 Confirm T006–T007 tests fail

### Implementation

- [X] T009 [US2] Implement `search_broad()` in `setup/story-engine/scripts/search_photos.py` — CLIP search with no city filter (queries only), plus metadata search by date range only, merge and dedup. Return candidate count for threshold check.
- [X] T010 [US1] Implement `discover_scenes()` in `setup/story-engine/scripts/score_and_select.py` — wrapper around existing `detect_scenes()` that: (a) applies garbage filter, (b) enriches candidates, (c) detects scenes, (d) returns full discovery result with all scenes, item counts, cities, people per scene. No budget applied.
- [X] T011 [US1] Implement day-grouping: when scenes > 20, group by day with day-level summary (date, scene count, total items) expandable to individual scenes.
- [X] T012 [US1] Implement discovery preview: create one Immich album with ALL discovered candidates (sorted chronologically), store album_id and share_key in project's discovery field.
- [X] T013 Confirm T006–T007 tests pass

**Checkpoint**: Broad search finds all content. Scene discovery shows everything. Preview album covers all content.

---

## Phase 3: User Story 3 — Must-Have Scene Verification (Priority: P2)

**Goal**: Cross-reference user's must-have keywords against discovered scenes. Run targeted searches for missing must-haves.

### Tests

- [X] T014 [P] [US3] Write failing unit tests in `tests/story-engine/unit/test_scoring.py`: `test_verify_must_haves_all_found`, `test_verify_must_haves_missing_triggers_search`, `test_verify_must_haves_not_found_reports`
- [X] T015 Confirm T014 tests fail

### Implementation

- [X] T016 [US3] Implement `verify_must_haves()` in `setup/story-engine/scripts/score_and_select.py` — takes discovered scenes + must-have keywords, checks if each keyword matches scene content (by city, people, CLIP search match). Returns found/missing report.
- [X] T017 [US3] For missing must-haves: run targeted `search_multi()` with keyword variations, enrich results, merge into discovery as new scene or extend existing scene.
- [X] T018 Confirm T014 tests pass

**Checkpoint**: All must-have keywords verified against scenes. Missing triggers follow-up search.

---

## Phase 4: User Story 4 — Detection Mode Extension Point (Priority: P3)

**Goal**: Define detection mode enum and dispatch. Only trip mode implemented.

### Tests

- [X] T019 [P] [US4] Write failing unit tests in `tests/story-engine/unit/test_scoring.py`: `test_detect_mode_trip`, `test_detect_mode_person_timeline_raises_not_implemented`, `test_detect_mode_default_general`
- [X] T020 Confirm T019 tests fail

### Implementation

- [X] T021 [US4] Add `DETECTION_MODES` enum and `detect_mode_from_prompt()` function in `score_and_select.py` — analyzes prompt for trip keywords (location + date), person keywords (name + "grows"/"timeline"), defaults to "general". Returns mode string.
- [X] T022 [US4] Wire `discover_scenes()` to accept mode parameter and dispatch: `trip` → existing 30-min gap clustering, `person-timeline` → raise NotImplementedError, `general` → same as trip for now.
- [X] T023 Confirm T019 tests pass

**Checkpoint**: Mode detection works. Trip mode fully functional. Other modes are clean extension points.

---

## Phase 5: Skill Update & Polish

**Purpose**: Update SKILL.md with two-phase workflow. Integration tests.

- [X] T024 Update `.claude/skills/story-engine/SKILL.md` with two-phase workflow: Phase A (discover → present all scenes → preview album link) → user confirms → Phase B (score → budget → timeline → generate). Include scene confirmation commands ("include all", "include 1,3,5", "skip airport").
- [ ] T025 Write integration test in `tests/story-engine/integration/test_selection_pipeline.py`: `test_broad_search_includes_multiple_cities` — search Miami trip, verify Coconut Grove and Miami Beach assets appear.
- [ ] T026 Write integration test: `test_discover_scenes_shows_all` — run discovery against live Immich, verify all detected scenes are returned with no budget cap.
- [ ] T027 Run full test suite: `pytest tests/story-engine/ -v` — all tests pass.
- [X] T028 Commit and push.

---

## Dependencies

- **Phase 1**: No dependencies — start immediately
- **Phase 2 (US1+US2)**: Depends on Phase 1 (project file fields)
- **Phase 3 (US3)**: Depends on Phase 2 (discovery result to verify against)
- **Phase 4 (US4)**: Independent of Phase 3, depends on Phase 2
- **Phase 5**: After all user stories

## Implementation Strategy

### MVP (Phase 1 + 2): 13 tasks
Two-phase workflow with broad search and scene discovery. Biggest impact.

### Full (all phases): 28 tasks
Adds must-have verification, detection modes, skill update, integration tests.

### Parallel Opportunities
- T001 + T006 + T007 (all test writing) can run in parallel
- Phase 3 and Phase 4 can run in parallel after Phase 2
