# Tasks: Immich Setup

**Input**: Design documents from `/specs/002-immich-setup/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is MANDATORY per FamilyVault Constitution Principle I. All test tasks must be
written and confirmed failing before their corresponding implementation tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project structure and test tooling — enables all subsequent phases

- [ ] T001 Create directory structure: `setup/immich/scripts/`, `setup/immich/launchd/`, `tests/immich/unit/`, `tests/immich/integration/`
- [ ] T002 [P] Verify bats-core + bats-support + bats-assert installed on Mac Mini: `brew install bats-core bats-support bats-assert` — document in `setup/immich/README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Docker Compose stack definition — MUST be complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Write failing bats test asserting docker-compose.yml defines exactly 5 services (immich-server, immich-microservices, immich-machine-learning, redis, postgres) and all volume source paths contain `/Volumes/HomeRAID/immich` in `tests/immich/unit/docker-compose-structure.bats` — confirm test FAILS before T004
- [ ] T004 Create `setup/immich/docker-compose.yml` with all 5 Immich v2.6.3 services pinned (`ghcr.io/immich-app/immich-server:v2.6.3` etc.), restart policy `unless-stopped` on all services, data volumes mapped to `/Volumes/HomeRAID/immich/`, `MACHINE_LEARNING_URL=http://immich-machine-learning:3003` on immich-server and immich-microservices — run T003 tests to confirm PASS
- [ ] T005 Write failing bats test asserting `.env.example` contains required keys (UPLOAD_LOCATION, DB_PASSWORD, JWT_SECRET) in `tests/immich/unit/env-config.bats` — confirm test FAILS before T006
- [ ] T006 Create `setup/immich/.env.example` with all keys required by docker-compose.yml (DB password, upload path, JWT secret — no real secrets) — run T005 tests to confirm PASS

**Checkpoint**: `bats tests/immich/unit/docker-compose-structure.bats tests/immich/unit/env-config.bats` passes — Docker stack definition is valid

---

## Phase 3: User Story 1 — Immich Running and Accessible (Priority: P1) 🎯 MVP

**Goal**: Immich starts automatically at boot, recovers from crashes, and is accessible at `http://macmini.local:2283`

**Independent Test**: `curl http://macmini.local:2283/api/server/ping` returns `{"res":"pong"}` within 500ms; restart Mac Mini and verify Immich is up within 2 minutes

### Tests for User Story 1

> **Write these tests FIRST — confirm they FAIL before implementation**

- [ ] T007 [US1] Write failing bats unit tests for `check-raid-mount.sh` covering: returns 0 when mount exists, returns 1 after 60s timeout when mount missing, logs clear error on timeout — save to `tests/immich/unit/check-raid-mount.bats`; confirm FAIL
- [ ] T008 [P] [US1] Write failing bats unit tests for `provision-api-key.sh` covering: writes API key to file, sets file permissions to 600, skips key creation if file already exists (idempotent) — save to `tests/immich/unit/provision-api-key.bats`; confirm FAIL
- [ ] T009 [P] [US1] Write failing bats unit test asserting launchd plist contains `RunAtLoad true` and references wrapper script path — save to `tests/immich/unit/launchd-plist.bats`; confirm FAIL
- [ ] T010 [P] [US1] Write failing bats integration test: start stack → wait for health at `:2283/api/server/ping` → assert HTTP 200 and response time under 500ms (`curl --max-time 0.5`) — save to `tests/immich/integration/immich-stack.bats`; confirm FAIL
- [ ] T011 [P] [US1] Write failing bats integration test: `docker stop immich_server` → sleep 35s → assert container is running again — append to `tests/immich/integration/immich-stack.bats`; confirm FAIL

### Implementation for User Story 1

- [ ] T012 [US1] Implement `setup/immich/scripts/check-raid-mount.sh`: poll `/Volumes/HomeRAID` every 5 seconds, exit 0 if mounted, exit 1 with logged error if not mounted after 60 seconds — run T007 tests to confirm PASS
- [ ] T013 [US1] Implement `setup/immich/scripts/provision-api-key.sh`: POST to `/api/auth/admin-sign-up` (idempotent), POST to `/api/auth/login`, POST to `/api/api-keys` to create key named `familyvault-setup`, write secret to `/Volumes/HomeRAID/immich/api-key.txt` with `chmod 600` — run T008 tests to confirm PASS
- [ ] T014 [US1] Create `setup/immich/launchd/com.familyvault.immich.plist`: `RunAtLoad true`, calls `check-raid-mount.sh` then `docker compose -f setup/immich/docker-compose.yml up -d` — run T009 tests to confirm PASS
- [ ] T015 [US1] Create `setup/immich/setup.sh` orchestrator: pre-flight checks (`docker` binary present, port 2283 free via `lsof -i :2283`), runs check-raid-mount → `docker compose up -d` → waits for health → runs provision-api-key.sh → installs launchd plist via `launchctl load` — run T010+T011 integration tests to confirm PASS

**Checkpoint**: All unit and integration tests pass; `http://macmini.local:2283` loads in browser; container auto-restarts after manual stop

---

## Phase 4: User Story 2 — External Library Indexed (Priority: P2)

**Goal**: `/Volumes/HomeRAID/icloud-export` is registered as an Immich external library, scanned daily, photos browsable by date/location/person

**Independent Test**: After running register-library.sh, navigate to Immich → Libraries → confirm external library listed with daily scan schedule; verify no files were copied from icloud-export

### Tests for User Story 2

> **Write these tests FIRST — confirm they FAIL before implementation**

- [ ] T016 [US2] Write failing bats unit test asserting docker-compose.yml bind-mounts `/Volumes/HomeRAID/icloud-export` as `:ro` into immich-server and immich-microservices — save to `tests/immich/unit/external-library-mount.bats`; confirm FAIL
- [ ] T017 [P] [US2] Write failing bats unit tests for `register-library.sh` covering: reads API key from `/Volumes/HomeRAID/immich/api-key.txt`, POSTs library with `type: EXTERNAL` and correct `importPaths`, configures daily `cronExpression`, triggers initial scan, skips registration if library already exists (idempotent) — save to `tests/immich/unit/register-library.bats`; confirm FAIL
- [ ] T018 [P] [US2] Write failing bats integration test: GET `/api/libraries` returns entry with `importPaths` containing `/usr/src/app/icloud-export` and a non-empty `cronExpression` — save to `tests/immich/integration/library-registered.bats`; confirm FAIL
- [ ] T019 [P] [US2] Write failing bats unit test asserting `register-library.sh` exits 0 when icloud-export mount path is empty directory (edge case: download still in progress) — append to `tests/immich/unit/register-library.bats`; confirm FAIL

### Implementation for User Story 2

- [ ] T020 [US2] Add read-only bind mount to `setup/immich/docker-compose.yml`: `/Volumes/HomeRAID/icloud-export:/usr/src/app/icloud-export:ro` on both `immich-server` and `immich-microservices` services — run T016 tests to confirm PASS
- [ ] T021 [US2] Implement `setup/immich/scripts/register-library.sh`: read API key from file, POST to `/api/libraries` with `type: EXTERNAL`, `importPaths: ["/usr/src/app/icloud-export"]`, and `cronExpression: "0 0 * * *"` (midnight daily), POST to `/api/libraries/{id}/scan`, idempotent (check existing libraries first) — run T017+T019 tests to confirm PASS
- [ ] T022 [US2] Add `register-library.sh` call to `setup/immich/setup.sh` orchestrator (after provision-api-key) — run T018 integration test to confirm PASS

**Checkpoint**: `bats tests/immich/unit/external-library-mount.bats tests/immich/unit/register-library.bats` pass; `bats tests/immich/integration/library-registered.bats` passes; library visible in Immich UI with daily schedule

---

## Phase 5: User Story 3 — Face Recognition and Search Enabled (Priority: P3)

**Goal**: Face clustering and CLIP semantic search are active and processing the library

**Independent Test**: Search "beach" in Immich and verify visually relevant results appear; confirm face clusters exist in the People section

### Tests for User Story 3

> **Write these tests FIRST — confirm they FAIL before implementation**

- [ ] T023 [US3] Write failing bats unit test asserting docker-compose.yml `immich-machine-learning` service has correct image tag and model cache volume at `/Volumes/HomeRAID/immich/model-cache` — save to `tests/immich/unit/ml-service-config.bats`; confirm FAIL
- [ ] T024 [P] [US3] Write failing bats integration test asserting GET `/api/server/config` returns `machineLearning.enabled`, `machineLearning.clip.enabled`, and `machineLearning.facialRecognition.enabled` all `true` — save to `tests/immich/integration/ml-enabled.bats`; confirm FAIL

### Implementation for User Story 3

- [ ] T025 [US3] Verify `setup/immich/docker-compose.yml` `immich-machine-learning` service has model cache volume at `/Volumes/HomeRAID/immich/model-cache` — this should already pass from T004; if not, add volume entry and re-run T023 to confirm PASS
- [ ] T026 [US3] Add `setup/immich/scripts/configure-ml.sh`: verify via GET `/api/server/config` that ML, CLIP, and face recognition are all enabled; log warning if any are disabled — call from `setup.sh` after library registration — run T024 integration test to confirm PASS

**Checkpoint**: `bats tests/immich/unit/ml-service-config.bats` passes; `bats tests/immich/integration/ml-enabled.bats` passes; People section shows face clusters after library scan

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Idempotency, documentation, and manual acceptance validation

- [ ] T027 [P] Verify `setup/immich/setup.sh` is fully idempotent: running it twice on the same Mac Mini produces no errors (admin already exists, API key file already present, library already registered, launchd plist already loaded)
- [ ] T028 Run the manual acceptance checklist from `specs/002-immich-setup/quickstart.md`: browser test at `http://macmini.local:2283`, reboot test (Mac Mini restart → Immich up within 2 min), photo count matches file count in icloud-export (within 1%)
- [ ] T029 [P] Commit all `setup/immich/` and `tests/immich/` files; update existing `specs/002-immich-setup/checklists/requirements.md` marking all items complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 — 🎯 MVP gate
- **Phase 4 (US2)**: Depends on Phase 3 (needs running Immich + API key)
- **Phase 5 (US3)**: Can start in parallel with Phase 4 (ML config verified against docker-compose.yml from Phase 2)
- **Phase 6 (Polish)**: Depends on all story phases

### Within Each Phase

1. Write test → confirm FAIL → implement → confirm PASS
2. All `[P]`-marked tasks within a phase can run in parallel (different files)
3. Integration tests run after unit tests pass

---

## Notes

- All bash scripts MUST use `set -euo pipefail` for safety
- `provision-api-key.sh` and `register-library.sh` must be idempotent (safe to re-run)
- Never commit real secrets — `.env` is gitignored; only `.env.example` is committed
- API key file permissions: `chmod 600 /Volumes/HomeRAID/immich/api-key.txt`
- bats tests for network calls should use a mock `curl` function in test setup to avoid real HTTP calls in unit tests
