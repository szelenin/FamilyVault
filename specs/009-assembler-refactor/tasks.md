# Tasks: Assembler Refactor

**Input**: Design documents from `/specs/009-assembler-refactor/`
**Prerequisites**: plan.md (required), spec.md (required)

**Tests**: TDD mandatory — this is Python code, not AI reasoning.

**Organization**: Tasks grouped by user story.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Foundational — Assembly Config + v2 Support

**Purpose**: Add assembly config to project.json and make assembler read v2 format.

### Tests

- [X] T001 [P] Write failing unit tests in `tests/story-engine/unit/test_project_file.py`: `test_create_project_has_assembly_config`, `test_set_assembly_config_orientation`, `test_set_assembly_config_resolution`, `test_set_assembly_config_padding`
- [X] T002 [P] Write failing unit tests in `tests/story-engine/unit/test_assembly.py`: `test_build_ffmpeg_cmd_from_project`, `test_build_ffmpeg_cmd_portrait_resolution`, `test_build_ffmpeg_cmd_reads_assembly_config`
- [X] T003 Confirm T001-T002 tests fail

### Implementation

- [X] T004 Add `assembly_config` field to `create_project()` in `setup/story-engine/scripts/manage_project.py` — default: `{"orientation": "portrait", "resolution": "1080x1920", "crf": 18, "fps": 30, "padding": "black"}`
- [X] T005 Add `set_assembly_config(project_id, config, stories_dir)` function in `manage_project.py`
- [X] T006 Refactor `assemble_video.py` to add new `assemble_v2(project_id, stories_dir, immich_url, api_key_file, ffmpeg_bin)` entry point that reads `project.json` timeline and assembly_config. Keep old `assemble()` for backward compat.
- [X] T007 Confirm T001-T002 tests pass

**Checkpoint**: Assembler can read v2 project.json with assembly config.

---

## Phase 2: User Story 2 — DNG/RAW Support (Priority: P1)

**Goal**: DNG files converted to JPEG without crashing.

### Tests

- [X] T008 [P] [US2] Write failing unit tests in `tests/story-engine/unit/test_assembly.py`: `test_sips_convert_dng_to_jpeg`, `test_detect_dng_by_extension`, `test_detect_dng_by_mime`, `test_dng_conversion_failure_skips_item`
- [X] T009 Confirm T008 tests fail

### Implementation

- [X] T010 [US2] Update `detect_heic()` to `detect_format()` in `assemble_video.py` — returns format type: "heic", "dng", "jpeg", "png", "video". Checks extension and mime type.
- [X] T011 [US2] Update `sips_convert_cmd()` to handle DNG: `sips -s format jpeg -s formatOptions 100 input.DNG --out output.jpg`. Same pattern as HEIC but explicit format for DNG.
- [X] T012 [US2] Add resilience: wrap download+convert in try/except per item. On failure: log warning with filename, skip item, continue. Count and report skipped items.
- [X] T013 Confirm T008 tests pass

**Checkpoint**: DNG files convert to JPEG. Failed items don't crash assembly.

---

## Phase 3: User Story 3 — Video Clip Inclusion (Priority: P1)

**Goal**: Videos play as video segments with audio, not still images.

### Tests

- [X] T014 [P] [US3] Write failing unit tests in `tests/story-engine/unit/test_assembly.py`: `test_download_video_no_conversion`, `test_video_trim_flags`, `test_build_ffmpeg_cmd_mixed_photo_video`, `test_audio_handling_video_to_photo`
- [X] T015 Confirm T014 tests fail

### Implementation

- [X] T016 [US3] Update asset download in `assemble_v2()`: VIDEO items download as-is (no sips conversion). Detect by `type` field from timeline item, not just mime type.
- [X] T017 [US3] Update FFmpeg input construction: for VIDEO items, add `-ss trim_start -to trim_end` before `-i` flag. For IMAGE items, no trim flags.
- [X] T018 [US3] Pass `input_types` list to `build_filter_complex()` based on timeline item types. Already partially implemented — wire it into `assemble_v2()`.
- [X] T019 [US3] Handle audio: VIDEO items contribute audio, IMAGE items are silent. Add `anullsrc` for photo segments. Audio fades during crossfade transitions via `afade` filter.
- [X] T020 Confirm T014 tests pass

**Checkpoint**: Videos play with audio. Transitions between photos and videos are smooth.

---

## Phase 4: User Story 4 — Smart Orientation & No-Crop (Priority: P2)

**Goal**: AI-driven resolution, photos never cropped.

### Tests

- [X] T021 [P] [US4] Write failing unit tests in `tests/story-engine/unit/test_assembly.py`: `test_scale_pad_portrait`, `test_scale_pad_no_crop_landscape_in_portrait`, `test_scale_pad_no_crop_portrait_in_landscape`
- [X] T022 Confirm T021 tests fail

### Implementation

- [X] T023 [US4] Update `scale_pad_filter()` to accept any resolution string and always use `force_original_aspect_ratio=decrease` + `pad` — guarantees no crop, full photo content visible.
- [X] T024 [US4] Update SKILL.md: add assembly config guidance — AI determines orientation/resolution based on target platform, writes to project.json via `set_assembly_config()`. Include platform reference table (Instagram Reels: 1080×1920, YouTube: 1920×1080, phone: 1080×1920).
- [X] T025 Confirm T021 tests pass

**Checkpoint**: Portrait video for phone, landscape for YouTube. No cropping ever.

---

## Phase 5: E2E Test + Polish

**Purpose**: End-to-end test with real Immich data, SKILL.md update, regression check.

- [ ] T026 Update `tests/story-engine/e2e/test_full_story_flow.py` to use `assemble_v2()` with v2 project.json. Verify output has correct resolution and codec.
- [ ] T027 E2E test: Run full pipeline against live Immich with mixed HEIC + DNG + video timeline → verify output.mp4 is generated, valid h264, correct resolution.
- [ ] T028 Run full unit test suite: `pytest tests/story-engine/unit/ -v` — all tests pass, no regressions.

---

## Phase 6: v1 Cleanup

**Purpose**: Analyze and clean up v1 code.

- [ ] T029 Analyze v1 dependencies: grep for all imports/usages of `manage_scenario` across the codebase. List files that still reference it.
- [ ] T030 Migrate or remove v1 tests: tests that test manage_scenario.py and old assemble() interface — either migrate to v2 or remove with justification.
- [ ] T031 If no remaining v1 dependencies: delete `manage_scenario.py`. If dependencies remain: document what still uses it and why.
- [ ] T032 Commit cleanup with clear message explaining what was removed and why.

---

## Dependencies & Execution Order

- **Phase 1**: No dependencies — start immediately
- **Phase 2 (DNG)**: Depends on Phase 1 (needs assemble_v2 entry point)
- **Phase 3 (Video)**: Depends on Phase 1, can run parallel with Phase 2
- **Phase 4 (Orientation)**: Depends on Phase 1
- **Phase 5 (E2E)**: Depends on Phases 1-4
- **Phase 6 (Cleanup)**: After Phase 5 — only clean up after everything works

### Parallel Opportunities

- T001 + T002 (tests for different files) can run in parallel
- T008 + T014 (DNG tests + video tests) can run in parallel
- Phase 2 and Phase 3 can run in parallel after Phase 1

---

## Implementation Strategy

### MVP (Phase 1 + 2): 13 tasks
v2 project support + DNG handling. Fixes the crash.

### Full (all phases): 32 tasks
Adds video clips, orientation, E2E test, v1 cleanup.

---

## Notes

- TDD mandatory for this feature — actual Python code
- `assemble_v2()` is a new entry point, not a replacement of old `assemble()` — until cleanup
- The old `assemble()` stays for backward compat until Phase 6 confirms nothing uses it
- Assembly config is the bridge between AI decisions (SKILL.md) and Python execution
