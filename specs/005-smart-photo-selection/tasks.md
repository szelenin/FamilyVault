# Tasks: Smart Photo & Video Selection

**Input**: Design documents from `/specs/005-smart-photo-selection/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: TDD is mandatory per Constitution Principle I. Test tasks precede implementation.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Project initialization, new files, shared infrastructure.

- [X] T001 Create `setup/story-engine/scripts/score_and_select.py` with empty function stubs per contracts/script-interfaces.md: `score_candidates()`, `detect_bursts()`, `detect_scenes()`, `allocate_budget()`, `select_timeline()`
- [X] T002 [P] Create `setup/story-engine/scripts/manage_project.py` with empty function stubs per contracts/script-interfaces.md: `create_project()`, `show_project()`, `set_state()`, `set_candidate_pool()`, `set_timeline()`, `swap_item()`, `remove_item()`, `reorder_items()`, `trim_video()`, `set_budget()`
- [X] T003 [P] Create `setup/story-engine/scripts/preview.py` with empty function stubs per contracts/script-interfaces.md: `fetch_thumbnail()`, `create_preview_album()`, `delete_preview_album()`
- [X] T004 [P] Create `tests/story-engine/unit/test_scoring.py` with empty test class stubs
- [X] T005 [P] Create `tests/story-engine/unit/test_project_file.py` with empty test class stubs
- [X] T006 [P] Create `tests/story-engine/unit/test_preview.py` with empty test class stubs
- [X] T007 [P] Create `tests/story-engine/integration/test_selection_pipeline.py` with empty test class stubs

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Project file format and state machine — all user stories depend on this.

**CRITICAL**: No user story work can begin until this phase is complete.

### Tests

- [X] T008 [P] Write failing unit tests for project file CRUD in `tests/story-engine/unit/test_project_file.py`: `test_create_project`, `test_show_project`, `test_set_state_forward`, `test_set_state_back_to_previewing`, `test_set_state_invalid_transition`, `test_set_candidate_pool`, `test_set_timeline`
- [X] T009 [P] Write failing unit tests for project file timeline operations in `tests/story-engine/unit/test_project_file.py`: `test_swap_item`, `test_swap_item_no_alternate`, `test_remove_item_renumbers`, `test_reorder_items`, `test_trim_video`, `test_set_budget_with_overrides`

### Implementation

- [X] T010 Implement `create_project()` and `show_project()` in `setup/story-engine/scripts/manage_project.py` — project file JSON format per data-model.md, state defaults to `searching`
- [X] T011 Implement `set_state()` in `setup/story-engine/scripts/manage_project.py` — validate state transitions: `searching → selecting → previewing → approved → generated`, plus `approved → previewing`
- [X] T012 Implement `set_candidate_pool()` and `set_timeline()` in `setup/story-engine/scripts/manage_project.py`
- [X] T013 Implement `swap_item()`, `remove_item()`, `reorder_items()`, `trim_video()`, `set_budget()` in `setup/story-engine/scripts/manage_project.py`
- [X] T014 Confirm T008–T009 tests pass: `pytest tests/story-engine/unit/test_project_file.py -v`

**Checkpoint**: Project file CRUD and state machine complete. User stories can begin.

---

## Phase 3: User Story 1 — Smart Auto-Selection (Priority: P1) MVP

**Goal**: Multi-query search, quality scoring, burst dedup, scene detection, budget allocation, and timeline selection.

**Independent Test**: Request a trip clip → verify selected photos span different moments, no near-duplicates, meet quality thresholds.

### Tests

- [X] T015 [P] [US1] Write failing unit tests for multi-query search merge in `tests/story-engine/unit/test_search.py`: `test_search_multi_merges_results`, `test_search_multi_deduplicates_by_id`, `test_search_multi_retries_on_failure`, `test_search_multi_proceeds_with_partial_results`
- [X] T016 [P] [US1] Write failing unit tests for asset enrichment in `tests/story-engine/unit/test_search.py`: `test_enrich_assets_adds_thumbhash`, `test_enrich_assets_adds_face_count`, `test_enrich_assets_adds_resolution`, `test_enrich_assets_includes_videos`
- [X] T017 [P] [US1] Write failing unit tests for scoring in `tests/story-engine/unit/test_scoring.py`: `test_score_photo_weights`, `test_score_video_weights`, `test_score_video_duration_sweet_spot`, `test_score_video_duration_penalty_short`, `test_score_must_have_bypasses_scoring`
- [X] T018 [P] [US1] Write failing unit tests for burst detection in `tests/story-engine/unit/test_scoring.py`: `test_detect_bursts_within_5_seconds`, `test_detect_bursts_keeps_highest_score`, `test_detect_bursts_stores_alternates`, `test_detect_bursts_video_preferred_over_photo`, `test_detect_bursts_photo_kept_as_alternate`
- [X] T019 [P] [US1] Write failing unit tests for scene detection and budget in `tests/story-engine/unit/test_scoring.py`: `test_detect_scenes_30min_gap`, `test_allocate_budget_proportional`, `test_allocate_budget_min_1_per_scene`, `test_allocate_budget_with_overrides`, `test_allocate_budget_cap_60`
- [X] T020 [P] [US1] Write failing unit tests for must-have extraction in `tests/story-engine/unit/test_scoring.py`: `test_must_have_guaranteed_in_timeline`, `test_must_have_fuzzy_search_variations`, `test_must_have_fallback_when_not_found`
- [X] T021 [P] [US1] Write failing unit tests for timeline selection in `tests/story-engine/unit/test_scoring.py`: `test_select_timeline_respects_budget`, `test_select_timeline_diversity_30pct_cap`, `test_select_timeline_chronological_order`, `test_select_timeline_auto_duration`
- [X] T022 [US1] Confirm T015–T021 tests fail: `pytest tests/story-engine/unit/test_search.py tests/story-engine/unit/test_scoring.py -x`

### Implementation

- [X] T023 [US1] Implement `search_multi()` in `setup/story-engine/scripts/search_photos.py` — issue multiple queries (location, date, semantic, must-have keywords), merge and deduplicate by asset_id, retry failed queries up to 3 times
- [X] T024 [US1] Implement `enrich_assets()` in `setup/story-engine/scripts/search_photos.py` — fetch `GET /api/assets/{id}` for each candidate using ThreadPoolExecutor (max 10 threads), extract thumbhash, people count, resolution, duration
- [X] T025 [US1] Implement `score_candidates()` in `setup/story-engine/scripts/score_and_select.py` — photo weights (faces 40%, relevance 30%, diversity 20%, resolution 10%), video weights (relevance 40%, duration 25%, diversity 20%, faces 15%), must-haves bypass scoring
- [X] T026 [US1] Implement `detect_bursts()` in `setup/story-engine/scripts/score_and_select.py` — group by timestamp < 5s, pick highest-scored as primary, store 2-3 alternates, prefer video over photo in same moment (keep photo as alternate)
- [X] T027 [US1] Implement `detect_scenes()` in `setup/story-engine/scripts/score_and_select.py` — split candidates at 30-minute gaps, assign scene labels
- [X] T028 [US1] Implement `allocate_budget()` in `setup/story-engine/scripts/score_and_select.py` — formula: base 10 + 5 per day, cap 60, distribute proportionally by scene candidate count, min 1 per scene, apply overrides
- [X] T029 [US1] Implement `select_timeline()` in `setup/story-engine/scripts/score_and_select.py` — pick top-scored per scene up to budget, enforce 30% diversity cap per 30-min window, insert must-haves, sort chronologically, assign positions and durations
- [X] T030 [US1] Implement must-have extraction and fuzzy search — parse prompt for quoted/comma-separated keywords, generate search variations (typo tolerance via CLIP smart search + metadata fallback), guarantee slots in timeline
- [X] T031 [US1] Implement caption generation from Immich data in `setup/story-engine/scripts/score_and_select.py` — use exifInfo.description, people names, city, scene label; fallback to filename-based caption; never hallucinate
- [X] T032 [US1] Confirm T015–T021 tests pass: `pytest tests/story-engine/unit/test_search.py tests/story-engine/unit/test_scoring.py -v`
- [ ] T033 [US1] Write and run integration test in `tests/story-engine/integration/test_selection_pipeline.py`: `test_full_selection_pipeline` — search live Immich → enrich → score → dedup → select → verify timeline has diverse, high-quality items

**Checkpoint**: Smart selection pipeline complete. Can generate high-quality timelines from any trip query.

---

## Phase 4: User Story 2 — Visual Timeline Preview (Priority: P2)

**Goal**: Immich album preview with share link, swap/remove/reorder commands.

**Independent Test**: Generate a selection → verify album created with correct items → swap an item → verify album updated.

### Tests

- [X] T034 [P] [US2] Write failing unit tests in `tests/story-engine/unit/test_preview.py`: `test_create_preview_album`, `test_delete_preview_album`, `test_create_album_cleans_old_preview`
- [X] T035 [P] [US2] Write failing unit tests in `tests/story-engine/unit/test_project_file.py`: `test_swap_updates_preview`, `test_remove_updates_preview`

### Implementation

- [X] T036 [US2] Implement `create_preview_album()` in `setup/story-engine/scripts/preview.py` — create Immich album via `POST /api/albums`, add assets via `PUT /api/albums/{id}/assets`, create share link via `POST /api/shared-links`, store album_id and share_key in project file
- [X] T037 [US2] Implement `delete_preview_album()` in `setup/story-engine/scripts/preview.py` — delete via `DELETE /api/albums/{id}`, clear preview fields in project file
- [X] T038 [US2] Implement preview cleanup in `create_preview_album()` — if project already has a preview album, delete it before creating new one (FR-009)
- [X] T039 [US2] Confirm T034–T035 tests pass: `pytest tests/story-engine/unit/test_preview.py tests/story-engine/unit/test_project_file.py -v`
- [ ] T040 [US2] Write and run integration test in `tests/story-engine/integration/test_selection_pipeline.py`: `test_preview_album_created_with_correct_assets` — create album on live Immich, verify assets present, verify share link works, clean up

**Checkpoint**: Preview albums work. User can see selected items in Immich before generation.

---

## Phase 5: User Story 4 — Video Output Quality (Priority: P2)

**Goal**: Higher bitrate (CRF 18), lossless HEIC conversion (sips quality 100), 30 fps.

**Independent Test**: Generate a clip → ffprobe confirms CRF 18, bitrate ≥ 5 Mbps, 30 fps.

### Tests

- [X] T041 [P] [US4] Write failing unit tests in `tests/story-engine/unit/test_assembly.py`: `test_ffmpeg_cmd_crf_18`, `test_ffmpeg_cmd_maxrate_10M`, `test_ffmpeg_cmd_30fps`, `test_sips_quality_100`, `test_audio_bitrate_192k`
- [X] T042 [US4] Confirm T041 tests fail: `pytest tests/story-engine/unit/test_assembly.py::test_ffmpeg_cmd_crf_18 -x`

### Implementation

- [X] T043 [US4] Update `assemble_video.py` CRF from 23 to 18, add `-maxrate 10M -bufsize 20M` in `setup/story-engine/scripts/assemble_video.py`
- [X] T044 [P] [US4] Update `assemble_video.py` frame rate from 25 to 30 fps in `setup/story-engine/scripts/assemble_video.py`
- [X] T045 [P] [US4] Update `sips_convert_cmd()` to add `-s formatOptions 100` for maximum quality JPEG output in `setup/story-engine/scripts/assemble_video.py`
- [X] T046 [P] [US4] Update audio bitrate from 128k to 192k in `setup/story-engine/scripts/assemble_video.py`
- [X] T047 [US4] Confirm T041 tests pass: `pytest tests/story-engine/unit/test_assembly.py -v`
- [ ] T048 [US4] Run e2e test to verify output quality: `IMMICH_URL=http://macmini:2283 FFMPEG_BIN=/opt/homebrew/bin/ffmpeg pytest tests/story-engine/e2e/test_full_story_flow.py -v` — verify bitrate ≥ 5 Mbps via ffprobe

**Checkpoint**: Video output quality meets SC-004 (5+ Mbps, smooth transitions).

---

## Phase 6: User Story 3 — Video Clip Inclusion (Priority: P3)

**Goal**: Videos in candidate pool and timeline, with trim support and photo-to-video transitions.

**Independent Test**: Search returns videos alongside photos → timeline includes video clips → generated output seamlessly interleaves photos and video with transitions.

### Tests

- [X] T049 [P] [US3] Write failing unit tests in `tests/story-engine/unit/test_scoring.py`: `test_video_in_candidate_pool`, `test_video_scored_with_video_weights`, `test_video_duration_in_timeline` (covered by existing tests: test_score_video_weights, test_score_video_duration_sweet_spot, test_select_timeline_auto_duration)
- [X] T050 [P] [US3] Write failing unit tests in `tests/story-engine/unit/test_assembly.py`: `test_build_ffmpeg_cmd_with_video_clip`, `test_build_ffmpeg_cmd_video_trim`, `test_build_ffmpeg_cmd_photo_to_video_transition`, `test_build_ffmpeg_cmd_video_to_photo_transition`
- [X] T051 [US3] Confirm T049–T050 tests fail

### Implementation

- [X] T052 [US3] Update `search_multi()` in `setup/story-engine/scripts/search_photos.py` to remove IMAGE-only type filter — search returns both IMAGE and VIDEO assets (done — search_multi already pops type filter)
- [X] T053 [US3] Update `enrich_assets()` to extract `duration` field for VIDEO assets in `setup/story-engine/scripts/search_photos.py` (done — enrich_assets already extracts duration)
- [X] T054 [US3] Update `assemble_video.py` to handle VIDEO type timeline items — download original video, apply trim_start/trim_end via `-ss`/`-to`, prepare as segment for filter_complex
- [X] T055 [US3] Update `assemble_video.py` filter_complex to handle photo-to-video and video-to-photo crossfade transitions — video segments retain original audio, photo segments are silent
- [X] T056 [US3] Confirm T049–T050 tests pass: `pytest tests/story-engine/unit/test_scoring.py tests/story-engine/unit/test_assembly.py -v`
- [ ] T057 [US3] Write and run e2e test with video clips: `test_full_story_flow_with_videos` in `tests/story-engine/e2e/test_full_story_flow.py` — verify output contains both still segments and video segments

**Checkpoint**: Videos fully supported in pipeline. Photos and videos interleave with transitions.

---

## Phase 7: Skill Update & Polish

**Purpose**: Update Claude Code skill, update e2e test for new project file format, documentation.

- [X] T058 Update `.claude/skills/story-engine/SKILL.md` with v2 workflow: multi-query search, must-have extraction, scoring pipeline, preview album, swap/remove/reorder/trim commands, budget adjustment
- [ ] T059 Update `tests/story-engine/e2e/test_full_story_flow.py` to use `manage_project.py` instead of `manage_scenario.py` — full pipeline: search_multi → enrich → score → select → preview album → approve → assemble → verify h264 ≥ 5 Mbps (blocked: needs Immich)
- [X] T060 [P] Update `tests/story-engine/conftest.py` with new fixtures for project file format, sample candidate pools, sample burst groups
- [X] T061 [P] Update `setup/story-engine/README.md` with v2 architecture: selection pipeline, project file format, new scripts
- [ ] T062 Run full test suite: `pytest tests/story-engine/ -v` — all unit, integration, e2e tests pass
- [ ] T063 Run quickstart.md validation — execute each command from quickstart.md against live Immich and verify expected output

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 Smart Selection)**: Depends on Phase 2
- **Phase 4 (US2 Preview)**: Depends on Phase 2, benefits from Phase 3 (uses timeline data)
- **Phase 5 (US4 Video Quality)**: Depends on Phase 2 only — can run in parallel with Phase 3
- **Phase 6 (US3 Video Clips)**: Depends on Phase 3 (scoring) and Phase 5 (assembly changes)
- **Phase 7 (Polish)**: Depends on all user stories complete

### User Story Dependencies

```
Phase 2 (Foundational)
├── Phase 3 (US1 Smart Selection) ──┐
│   └── Phase 4 (US2 Preview)       ├── Phase 7 (Polish)
└── Phase 5 (US4 Video Quality) ────┘
    └── Phase 6 (US3 Video Clips) ──┘
```

### Parallel Opportunities

- T001–T007 (Setup): All parallelizable
- T008–T009 (Foundational tests): Parallelizable
- T015–T021 (US1 tests): All parallelizable
- T034–T035 (US2 tests): Parallelizable
- Phase 3 (US1) and Phase 5 (US4) can run in parallel after Phase 2

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3)

1. Complete Setup + Foundational → project file works
2. Complete US1 (Smart Selection) → can generate high-quality timelines
3. **STOP and VALIDATE**: Test selection quality against Miami trip data
4. Iterate on scoring weights if needed

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 Smart Selection → selection quality fixed (MVP!)
3. US4 Video Quality → output quality fixed (can run parallel with US1)
4. US2 Preview → user can review before generation
5. US3 Video Clips → videos in clips
6. Polish → skill updated, all tests green

---

## Notes

- Constitution Principle I: All test tasks MUST be written and FAIL before implementation
- [P] tasks = different files, no dependencies on incomplete tasks
- Commit after each task or logical group
- Scoring weights (T025) are initial defaults — tune during integration testing (T033)
