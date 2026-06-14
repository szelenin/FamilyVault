# Tasks: IMP-018 VLM Captioning & Extraction

**Input**: Design documents from `/specs/016-vlm-captioning/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: MANDATORY (TDD) — per the FamilyVault Constitution (Principle I & II, NON-NEGOTIABLE), every unit has a failing test written and confirmed failing before implementation. Mocking policy: real temp-dir SQLite (never mocked); mocks only for external model/Immich/subprocess calls.

**Organization**: by user story (US1→US4), priority order. Each story is an independently testable increment.

**Interpreter**: all `pytest`/python commands run under `/opt/homebrew/bin/python3.13`.

## Path Conventions

- Source: `setup/understanding/`
- Tests: `tests/understanding/{unit,integration,e2e}/` (conftest adds `setup/understanding` to `sys.path`, per `tests/story-engine/conftest.py`)

---

## Phase 1: Setup

- [ ] T001 [P] Create module skeleton: `setup/understanding/__init__.py`, `setup/understanding/index/__init__.py`, `setup/understanding/fetch/__init__.py`, `setup/understanding/caption/__init__.py`
- [ ] T002 [P] Write `setup/understanding/config.sh` (INDEX_DB native default `~/.familyvault/index/familyvault.db`, INDEX_BACKUP_DIR on RAID, IMMICH_URL/IMMICH_API_KEY_FILE, STAGING_DIR, STAGING_BUDGET=10G, MEMORY_POLICY=auto, OLLAMA_URL, model names qwen3-vl:8b/bge-m3/MLX, frame caps)
- [ ] T003 [P] Create `tests/understanding/{unit,integration,e2e}/` with `conftest.py` adding `setup/understanding` to `sys.path`; register `integration` + `e2e` pytest markers (opt-in) in repo pytest config
- [ ] T004 Write `setup/understanding/setup.sh` (idempotent): `ollama pull qwen3-vl:8b` + `ollama pull bge-m3`; `pip install --break-system-packages` (python3.13) `mlx-vlm scenedetect`; ensure `ffmpeg`; cache MLX model; document `python3.13` + Ollama-runner gotchas (ref `setup/local-agent/SETUP-NOTES.md`)

---

## Phase 2: Foundational (blocking — shared by all stories)

**The index core, captioner interface, and embedder are written here because every story writes to/through them.**

- [ ] T005 Write failing unit tests for status model in `tests/understanding/unit/test_status.py` (enum values; valid transitions pending→done/no_preview/error; error/no_preview→pending via retry)
- [ ] T006 Implement `setup/understanding/index/status.py` to pass T005
- [ ] T007 Write failing unit tests for the index in `tests/understanding/unit/test_db.py` (real temp-dir SQLite, WAL; `open_db` migrate; `upsert_asset`/`upsert_segments`; `plan` incremental selection by pending + changed `source_hash` + `schema_ver<current`; `set_status`; `counts`; FTS5 sync via triggers; vector store + brute-force cosine `search`; `backup` copies file)
- [ ] T008 Implement `setup/understanding/index/db.py` (schema: `assets`, `video_segments`, `assets_fts`, `runs`; WAL; functions per `contracts/captioner.md` Index API) to pass T007
- [ ] T009 [P] Write failing unit tests for the captioner contract in `tests/understanding/unit/test_base.py` (CaptionResult shape; `REQUIRED_MODELS` map for photo/video)
- [ ] T010 [P] Implement `setup/understanding/caption/base.py` (CaptionResult, captioner protocol, `REQUIRED_MODELS`) to pass T009
- [ ] T011 [P] Write failing unit tests for the embedder in `tests/understanding/unit/test_embed.py` (`embed`/`embed_query` return a serialized vector; injectable Ollama client mocked)
- [ ] T012 [P] Implement `setup/understanding/caption/embed.py` (multilingual `bge-m3` via Ollama embeddings; injectable client) to pass T011

**Checkpoint**: index + interfaces + embedder exist and are unit-green. No story logic yet.

---

## Phase 3: User Story 1 — Searchable understanding of photos (P1) 🎯 MVP

**Goal**: Caption + OCR + embed every photo into the index; meaning-based and exact-text search (incl. cross-language) return the right photo.
**Independent test**: Run on a small photo set → every photo `done` (or recorded status); `search "playing piano"` and a cross-language query return the expected photo; re-run processes 0.

### Tests (write first, confirm failing)

- [ ] T013 [P] [US1] Failing unit tests for the photo fetcher in `tests/understanding/unit/test_fetch_immich_photo.py` (list assets; download preview to staging; **missing preview → `no_preview`**; capture `source_hash` + cached Immich fields) with mocked Immich
- [ ] T014 [P] [US1] Failing unit tests for the photo captioner in `tests/understanding/unit/test_photo_ollama.py` (preview → CaptionResult; English caption; OCR; model errors → typed exception, never crash) with a mock model
- [ ] T015 [P] [US1] Failing unit tests for the photo run orchestration in `tests/understanding/unit/test_cli_run_photo.py` (chunking to staging budget; incremental skip of `done`; per-asset error isolation; DB backup at end) with mocks
- [ ] T016 [US1] Failing e2e test in `tests/understanding/e2e/test_photo_e2e.py` (tiny photo fixture → `run --type photo` → rows `done` with caption + embedding; FTS query **and** vector query each return the expected asset)

### Implementation

- [ ] T017 [US1] Implement `setup/understanding/fetch/immich.py` photo path (list assets, download preview, missing-preview detection, `source_hash`, cached fields) to pass T013
- [ ] T018 [US1] Implement `setup/understanding/caption/photo_ollama.py` (Ollama `qwen3-vl:8b`; structured English caption+OCR prompt; OCR dedupe; embed via `embed.py`) to pass T014
- [ ] T019 [US1] Implement `setup/understanding/index_cli.py` `run --type photo` (chunked fetch→caption→embed→write→cleanup; incremental; per-asset error isolation; DB backup) + `status` command, to pass T015
- [ ] T020 [US1] Implement `index_cli.py` `search "<query>"` (smoke hybrid FTS ∪ vector; multilingual query embed) to pass T016

**Checkpoint**: US1 = shippable MVP (photo concept/text/cross-language search the archive never had).

---

## Phase 4: User Story 2 — Video understanding incl. the moment (P2)

**Goal**: Video-level caption + timestamped segments + OCR; searchable; "when" locatable.
**Independent test**: Run on a single-shot and a multi-scene clip → each has a video-level caption + ≥1 segment; multi-scene reflects >1 scene; on-screen text captured + searchable.

### Tests (write first, confirm failing)

- [ ] T021 [P] [US2] Failing unit tests for frame sampling in `tests/understanding/unit/test_sampling.py` (hybrid: scene-detect → 1–2/scene + first/mid/last + min3/max~16–24; uniform fallback when ≤1 scene; OCR-tier frame selection) on synthetic scene lists
- [ ] T022 [P] [US2] Failing unit tests for the video captioner in `tests/understanding/unit/test_video_mlx.py` (frames → CaptionResult with `segments` + timestamps; map-reduce path when over frame budget; OCR dedupe) with a mock MLX backend
- [ ] T023 [P] [US2] Failing unit tests for video frame extraction in `tests/understanding/unit/test_fetch_immich_video.py` (ffmpeg invocation to staging; mocked ffmpeg)
- [ ] T024 [US2] Failing e2e test in `tests/understanding/e2e/test_video_e2e.py` (single-shot + multi-scene fixtures → `run --type video` → video-level caption + ≥1 segment; multi-scene >1 scene; OCR captured)

### Implementation

- [ ] T025 [P] [US2] Implement `setup/understanding/fetch/sampling.py` (PySceneDetect ContentDetector/AdaptiveDetector + caps + uniform fallback + OCR-tier high-res frames) to pass T021
- [ ] T026 [US2] Extend `setup/understanding/fetch/immich.py` with video frame extraction via ffmpeg to staging, to pass T023
- [ ] T027 [US2] Implement `setup/understanding/caption/video_mlx.py` (MLX-VLM multi-frame single call; map-reduce fallback; populate `segments`) to pass T022
- [ ] T028 [US2] Wire `index_cli.py` `run --type video` (sampling + video_mlx + `video_segments` + embed); extend `setup.sh` with video deps, to pass T024

**Checkpoint**: US2 independently testable (video activity/text/moment search).

---

## Phase 5: User Story 3 — Safe, unattended, resource-governed batch (P2)

**Goal**: Automatic memory governance + bounded staging + resumability so big runs are safe and unattended. (Incremental/resumable/chunked land in US1; this adds the governor and policy.)
**Independent test**: Interrupt + re-run skips done; simulate low RAM → governor frees memory least-disruptively, completes without OOM, restores Immich; staging never exceeds budget.

### Tests (write first, confirm failing)

- [ ] T029 [P] [US3] Failing unit tests for the memory governor in `tests/understanding/unit/test_resources.py` (escalation on mocked memory readings + `/api/ps`: unload non-required models → stop Immich → stop OrbStack; restore **only what was stopped**; `--memory auto|force|never` behavior) with mocked subprocess/command runners
- [ ] T030 [P] [US3] Failing unit tests for per-phase model lifecycle in `tests/understanding/unit/test_model_lifecycle.py` (`REQUIRED_MODELS` → unload models not in the phase's set; only one path's models resident)
- [ ] T031 [US3] Failing integration test (opt-in marker) in `tests/understanding/integration/test_governor_live.py` (under simulated low free-RAM the run frees memory and restores the photo server)

### Implementation

- [ ] T032 [US3] Implement `setup/understanding/resources.py` (measure RAM via `psutil`; escalate; record + restore; injectable command runners) to pass T029
- [ ] T033 [US3] Integrate governor into `index_cli.py run` (Govern step before caption; `--memory auto|force|never`; per-phase model load/unload) to pass T030
- [ ] T034 [US3] Enforce staging budget + `--clean-staging` + resume-on-failure in `index_cli.py` (verify chunk cleanup steady-state ≈ one chunk; resumable after crash)

**Checkpoint**: US3 independently testable (safe unattended large runs).

---

## Phase 6: User Story 4 — Environment readiness & missing-preview remediation (P3)

**Goal**: Fail-fast readiness scoped per type; missing previews reported with remediation; retryable.
**Independent test**: `doctor` with a missing component stops in ~seconds with the exact fix (and a photo run doesn't require MLX); `report` lists missing-preview assets + remediation; `retry` re-queues them.

### Tests (write first, confirm failing)

- [ ] T035 [P] [US4] Failing unit tests for the preflight in `tests/understanding/unit/test_doctor.py` (pass/fail + exact-fix messages on a mocked env; **scoped per `--type`** — photo run does not require MLX/ffmpeg/scenedetect)
- [ ] T036 [P] [US4] Failing unit tests for `report` + `retry` in `tests/understanding/unit/test_report_retry.py` (`report` lists `no_preview` IDs + Immich regeneration call; `retry --status no_preview|error` sets those back to `pending`)

### Implementation

- [ ] T037 [US4] Implement `setup/understanding/preflight.py` `doctor` (scoped presence-on-disk checks; fail-fast remediation messages) to pass T035
- [ ] T038 [US4] Wire `doctor` to auto-run at the start of `run`; implement `index_cli.py` `report` + `retry` commands, to pass T036
- [ ] T039 [US4] Finalize `setup.sh` (full deps + documentation); add optional `--auto-regenerate` flag to trigger Immich preview regeneration and re-fetch

**Checkpoint**: US4 independently testable (readiness + remediation).

---

## Phase 7: Polish & Cross-Cutting

- [ ] T040 [P] Write `setup/understanding/README.md` (usage from `quickstart.md`: setup → doctor → phased run → search → tests)
- [ ] T041 [P] Add edge-case unit tests across modules in `tests/understanding/unit/` (idempotent re-run = 0 processed; changed asset re-processed; `--memory never` insufficient-RAM clean stop; video with no scenes; over-budget clip map-reduce) and confirm the unit suite runs < 60s
- [ ] T042 Run the `quickstart.md` acceptance smoke end-to-end on the Mac Mini (photos + a couple clips) and record results in the PR/quickstart
- [ ] T043 [P] Update `docs/PRD.md` IMP-018 status (→ done when SC met) and confirm the design-doc link; note IMP-019/020/021/022 remain the follow-ups

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → blocks everything.
- **Foundational (Phase 2)** → blocks all user stories (index, interfaces, embedder). T005→T006, T007→T008, T009→T010, T011→T012.
- **US1 (Phase 3)** → depends on Foundational. **MVP.** Tests T013–T016 before impl T017–T020.
- **US2 (Phase 4)** → depends on Foundational (and reuses US1's fetch/cli). Tests T021–T024 before impl T025–T028.
- **US3 (Phase 5)** → depends on a working `run` (US1). Tests T029–T031 before impl T032–T034.
- **US4 (Phase 6)** → depends on `run` + fetch (US1) for the missing-preview status it reports. Tests T035–T036 before impl T037–T039.
- **Polish (Phase 7)** → after the stories it touches.

**Story independence**: US2/US3/US4 each build on the US1 spine but are separately testable and shippable. US1 alone is a viable MVP.

## Parallel Execution Examples

- **Setup**: T001, T002, T003 in parallel (different files).
- **Foundational**: the test/impl pairs T009/T010 (base) and T011/T012 (embed) can run parallel to the db pair T007/T008 (different files).
- **US1 tests**: T013, T014, T015 in parallel (different test files) before their implementations.
- **US2 tests**: T021, T022, T023 in parallel.
- **Within impl**: tasks marked [P] touch different files and have no incomplete dependency.

## Implementation Strategy

1. **MVP = Phase 1 + 2 + US1.** Ship photo captioning/OCR/embedding + hybrid search first; it delivers standalone value and proves the whole spine.
2. **Then US2 (video)** — the high-value, higher-complexity layer.
3. **Then US3 (resource governance)** — makes large unattended runs safe on 24 GB.
4. **Then US4 (readiness/remediation)** — operator polish; the missing-preview *status* already exists from US1, US4 adds the formal `doctor`/`report`/`retry`.
5. Commit after each passing test group (per constitution Development Workflow).

**MVP scope**: T001–T020 (Setup + Foundational + US1).
