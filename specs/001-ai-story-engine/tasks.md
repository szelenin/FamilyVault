# Tasks: AI Story Engine

**Input**: Design documents from `/specs/001-ai-story-engine/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tech Stack**: Python 3.13 + Bash | FFmpeg + sips + Immich REST API v2.6.3 | pytest
**Test approach**: TDD mandatory (Constitution Principle I) — every test task precedes its implementation task.

---

## Phase 1: Setup

**Purpose**: Project structure, dependencies, configuration.

- [ ] T001 Create directory structure: `setup/story-engine/scripts/`, `setup/story-engine/music/{upbeat,calm,sentimental}/`, `tests/story-engine/unit/`, `tests/story-engine/integration/`, `tests/story-engine/e2e/`
- [ ] T002 Create `setup/story-engine/config.sh` with env var defaults: `IMMICH_URL`, `IMMICH_API_KEY_FILE`, `STORIES_DIR`, `FFMPEG_BIN`, `IMAGE_DURATION`, `FADE_DURATION`, `OUTPUT_RESOLUTION`, `TRANSITION`
- [ ] T003 Verify FFmpeg on Mac Mini: `ssh macmini "brew list ffmpeg || brew install ffmpeg"` and confirm `ffmpeg -version`
- [ ] T004 Create stories directory: `ssh macmini "mkdir -p /Volumes/HomeRAID/stories"`
- [ ] T005 Create `tests/story-engine/conftest.py` with shared pytest fixtures: mock Immich API responses, temp `STORIES_DIR`, sample scenario JSON

---

## Phase 2: Foundational (Immich API Client)

**Purpose**: Shared HTTP client used by all three scripts. Must be complete before US1–US4.

**Independent test**: `python3 -m pytest tests/story-engine/unit/test_search.py::test_build_smart_search_request -x` passes with no network access.

- [ ] T006 Write failing unit tests in `tests/story-engine/unit/test_search.py`: `test_build_smart_search_request` (correct JSON body), `test_person_name_to_id_found`, `test_person_name_to_id_not_found`, `test_parse_asset_response_fields`, `test_search_returns_empty_list_on_zero_results`
- [ ] T007 Confirm T006 tests fail: `python3 -m pytest tests/story-engine/unit/test_search.py -x` → ImportError or AttributeError expected
- [ ] T008 Implement `setup/story-engine/scripts/search-photos.py`: argument parser (`--query`, `--person`, `--after`, `--before`, `--city`, `--country`, `--type`, `--limit`, `--format`), Immich HTTP client helpers (auth header from `IMMICH_API_KEY_FILE`, person name→ID lookup, smart search request builder, metadata search fallback, asset response parser)
- [ ] T009 Confirm T006 tests pass: `python3 -m pytest tests/story-engine/unit/test_search.py -v`
- [ ] T010 [P] Write failing integration test in `tests/story-engine/integration/test_immich_api.py`: `test_immich_reachable`, `test_search_person_by_name_returns_results`, `test_smart_search_returns_assets` (requires live Immich)
- [ ] T011 [P] Confirm T010 integration tests pass against live Immich: `IMMICH_URL=http://immich-immich-server-1.orb.local python3 -m pytest tests/story-engine/integration/test_immich_api.py -v`

---

## Phase 3: US1 — Conversational Story Request

**Story goal**: User describes a story in natural language → Claude searches Immich → proposes ordered scenario with captions and narrative.

**Independent test**: `python3 setup/story-engine/scripts/search-photos.py --query "birthday" --person "Edgar" --after 2025-03-01 --before 2025-03-31` returns JSON array of assets. `python3 setup/story-engine/scripts/manage-scenario.py create --title "Test" --request "test"` creates `scenario.json` in `$STORIES_DIR`.

- [ ] T012 [US1] Write failing unit tests in `tests/story-engine/unit/test_scenario.py`: `test_create_scenario_writes_json`, `test_create_scenario_initial_state_is_draft`, `test_create_scenario_generates_id_from_date_and_title`, `test_show_scenario_reads_json`, `test_list_scenarios_returns_all`, `test_scenario_id_format`
- [ ] T013 [US1] Confirm T012 tests fail: `python3 -m pytest tests/story-engine/unit/test_scenario.py -x`
- [ ] T014 [US1] Implement `manage-scenario.py` commands: `create` (writes scenario.json with draft state), `show` (prints JSON), `list` (table of id/title/state/items/created_at)
- [ ] T015 [US1] Confirm T012 tests pass: `python3 -m pytest tests/story-engine/unit/test_scenario.py::test_create* tests/story-engine/unit/test_scenario.py::test_show* tests/story-engine/unit/test_scenario.py::test_list* -v`
- [ ] T016 [US1] Write failing unit test: `test_search_exit_code_2_on_no_results` — `search-photos.py` returns exit 2 and empty array when Immich returns zero hits
- [ ] T017 [US1] Confirm T016 fails, then implement the no-results exit code in `search-photos.py`
- [ ] T018 [US1] Create `.claude/skills/story-engine/SKILL.md` with US1 workflow: how Claude should interpret a story request, call `search-photos.py`, select top N assets, generate captions and narrative, call `manage-scenario.py create` and `add-item`, present scenario to user

---

## Phase 4: US2 — Scenario Review and Refinement

**Story goal**: User reviews scenario conversationally — add/remove items, reorder, change narrative tone — and gets updated scenario.

**Independent test**: All `manage-scenario.py` mutation commands (add-item, remove-item, reorder, set-narrative) pass unit tests without network access.

- [ ] T019 [US2] Write failing unit tests in `tests/story-engine/unit/test_scenario.py`: `test_add_item_appends_to_end`, `test_add_item_at_position_inserts`, `test_add_item_enforces_60_item_limit`, `test_remove_item_renumbers_positions`, `test_reorder_validates_all_positions_present`, `test_reorder_rejects_duplicates`, `test_set_narrative_updates_field`
- [ ] T020 [US2] Confirm T019 tests fail: `python3 -m pytest tests/story-engine/unit/test_scenario.py::test_add* tests/story-engine/unit/test_scenario.py::test_remove* tests/story-engine/unit/test_scenario.py::test_reorder* -x`
- [ ] T021 [US2] Implement `manage-scenario.py` commands: `add-item` (with position insert and 60-item guard), `remove-item` (renumber positions), `reorder` (validate and apply new order), `set-narrative`
- [ ] T022 [US2] Confirm T019 tests pass: `python3 -m pytest tests/story-engine/unit/test_scenario.py -v`
- [ ] T023 [US2] Update `.claude/skills/story-engine/SKILL.md` with US2 refinement workflow: how Claude should interpret refinement requests ("remove airport photos", "make it funnier", "add pool photos", "max 10"), map to script commands, and re-present updated scenario

---

## Phase 5: US3 — Music Selection

**Story goal**: Claude suggests mood-matched music from bundled library; user accepts, picks alternative, provides own file, or skips.

**Independent test**: `manage-scenario.py set-music` commands pass for all three types (bundled/user/none) and validate file existence.

- [ ] T024 [US3] Add 12 royalty-free MP3 tracks (4 per mood) to `setup/story-engine/music/`: `upbeat/track{1..4}.mp3`, `calm/track{1..4}.mp3`, `sentimental/track{1..4}.mp3` — source from Pixabay Music (CC0); satisfies FR-005 requirement of 10–20 bundled tracks
- [ ] T025 [US3] Write failing unit tests: `test_set_music_bundled_sets_path`, `test_set_music_user_validates_file_exists`, `test_set_music_user_rejects_missing_file`, `test_set_music_none_sets_type_none`, `test_list_bundled_tracks_by_mood`
- [ ] T026 [US3] Confirm T025 tests fail: `python3 -m pytest tests/story-engine/unit/test_scenario.py::test_set_music* -x`
- [ ] T027 [US3] Implement `manage-scenario.py set-music` command (bundled/user/none types, file existence validation) and `list-music` command (table of bundled tracks by mood)
- [ ] T028 [US3] Confirm T025 tests pass: `python3 -m pytest tests/story-engine/unit/test_scenario.py::test_set_music* -v`
- [ ] T029 [US3] Update `.claude/skills/story-engine/SKILL.md` with US3 music workflow: mood detection from narrative, present 2 suggestions with descriptions, handle user-supplied file, handle skip

---

## Phase 6: US4 — Video Generation

**Story goal**: User says "generate" → Claude downloads originals, converts HEIC, assembles MP4 via FFmpeg, reports output path.

**Independent test**: `assemble-video.py --dry-run SCENARIO_ID` prints correct FFmpeg command without executing or downloading anything.

- [ ] T030 [US4] Write failing unit tests in `tests/story-engine/unit/test_assembly.py`: `test_xfade_offset_calculation_2_items`, `test_xfade_offset_calculation_5_items`, `test_total_duration_calculation`, `test_scale_pad_filter_string`, `test_audio_filter_with_fade_out`, `test_filter_complex_for_images_only`, `test_filter_complex_for_mixed_inputs`
- [ ] T031 [US4] Confirm T030 tests fail: `python3 -m pytest tests/story-engine/unit/test_assembly.py -x`
- [ ] T032 [US4] Write failing unit tests: `test_heic_detected_from_mime_type`, `test_sips_command_for_heic`, `test_assemble_rejects_non_approved_state`, `test_assemble_dry_run_prints_command_no_exec`, `test_temp_dir_path_format`
- [ ] T033 [US4] Confirm T032 tests fail: `python3 -m pytest tests/story-engine/unit/test_assembly.py::test_heic* tests/story-engine/unit/test_assembly.py::test_assemble* tests/story-engine/unit/test_assembly.py::test_temp* -x`
- [ ] T034 [US4] Implement `assemble-video.py` core logic: `build_filter_complex()` (xfade timing math, scale+pad, audio trim+fade), `detect_heic()`, `sips_convert()`, `build_ffmpeg_cmd()`
- [ ] T035 [US4] Confirm T030 and T032 tests pass: `python3 -m pytest tests/story-engine/unit/test_assembly.py -v`
- [ ] T036 [US4] Implement `assemble-video.py` pipeline: precondition checks (state=approved, files exist, FFmpeg available), asset download loop (`GET /api/assets/{id}/original`), HEIC conversion, FFmpeg execution with `--progress` output, ffmpeg.log write, state→generated, temp dir cleanup
- [ ] T037 [US4] Implement `manage-scenario.py set-state` command with forward-only transition guard
- [ ] T038 [US4] Write failing unit test: `test_set_state_forward_only_transition` — set-state to `draft` from `reviewed` returns exit 3
- [ ] T039 [US4] Confirm T038 passes: `python3 -m pytest tests/story-engine/unit/test_scenario.py::test_set_state* -v`
- [ ] T040 [US4] Update `.claude/skills/story-engine/SKILL.md` with US4 generation workflow: advance state to approved, call `assemble-video.py`, report progress, handle retry (up to 3 per FR-012), report output path

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: End-to-end test, documentation, INSTALL.md update.

- [ ] T041 Write big (e2e) test in `tests/story-engine/e2e/test_full_story_flow.py`: `test_full_story_flow` — search → create scenario → add 3 items → set music → approve → assemble → assert output is valid MP4 via `ffprobe -v error -select_streams v:0 -show_entries stream=codec_name` returns `h264` (requires live Immich + FFmpeg on Mac Mini)
- [ ] T042 [P] Create `setup/story-engine/README.md`: overview, prerequisites, installation, usage, configuration reference
- [ ] T043 [P] Update `INSTALL.md` Phase 4 with Story Engine setup steps (FFmpeg install, stories dir, SKILL.md location)
- [ ] T044 [P] Write benchmark test in `tests/story-engine/integration/test_performance.py`: `test_scenario_generation_under_30s` — time full search + scenario create against live Immich 15K-item library; assert elapsed < 30s (SC-001)
- [ ] T045 [P] Write benchmark test in `tests/story-engine/integration/test_performance.py`: `test_video_assembly_under_5min` — time `assemble-video.py` for a 30-item approved scenario; assert elapsed < 300s (SC-003)
- [ ] T046 [P] Write unit test in `tests/story-engine/unit/test_assembly.py`: `test_no_external_requests` — mock `requests.get` and assert `assemble-video.py` only calls URLs matching `IMMICH_URL`; no calls to any external host (FR-009)

---

## Dependencies

```
Phase 1 (Setup)
  └── Phase 2 (Foundational: Immich client)
        ├── Phase 3 (US1: Story Request)   ← search-photos.py + manage-scenario.py create/show/list
        │     └── Phase 4 (US2: Refinement) ← manage-scenario.py mutation commands
        │           └── Phase 5 (US3: Music) ← manage-scenario.py set-music
        │                 └── Phase 6 (US4: Video) ← assemble-video.py
        │                       └── Phase 7 (Polish)
        └── Phase 6 (US4: search required for asset download)
```

US1 → US2 → US3 → US4 must be implemented in order (each story depends on the previous scenario state).

---

## Parallel Execution Opportunities

Within Phase 2 (after T009 passes):
- T010 (integration tests) and T012 (US1 scenario unit tests) can run in parallel

Within Phase 6:
- T030/T031 (FFmpeg math tests) and T032/T033 (HEIC/precondition tests) can run in parallel before T034

Within Phase 7:
- T042 (README), T043 (INSTALL.md), T044 (SC-001 benchmark), T045 (SC-003 benchmark), T046 (FR-009 privacy test) are all fully independent [P]

---

## Implementation Strategy

**MVP**: Phase 1 + Phase 2 + Phase 3 (US1 only)
- Delivers: "describe story → Claude searches Immich → proposes scenario" with working `search-photos.py` and `manage-scenario.py create/show/list`
- Tests: T006–T017 all passing
- Validates SC-001 (30s scenario generation) and SC-004 (90% correct event identification)

**V1 Complete**: All phases (US1–US4)
- Delivers full workflow: request → refine → music → generate
- All unit and integration tests passing
- SC-001 through SC-006 validated
