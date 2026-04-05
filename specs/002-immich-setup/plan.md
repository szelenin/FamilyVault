# Implementation Plan: Immich Setup

**Branch**: `002-immich-setup` | **Date**: 2026-04-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-immich-setup/spec.md`

## Summary

Deploy Immich v2.6.3 via Docker Compose on the Mac Mini, persisting all data to
`/Volumes/HomeRAID/immich`, with `/Volumes/HomeRAID/icloud-export` mounted as an
external library (read-only). A launchd plist + wrapper script handles boot-time
ordering (RAID mount check before Docker start). A post-startup script provisions
an admin account and API key, storing the key at `/Volumes/HomeRAID/immich/api-key.txt`
for downstream consumers (AI Story Engine, ImmichMCP).

## Technical Context

**Language/Version**: Bash (macOS-native, no runtime dependency)
**Primary Dependencies**: Docker Compose (via OrbStack), Immich v2.6.3, bats-core (testing)
**Storage**: PostgreSQL (managed by Immich Docker Compose), Redis, files on `/Volumes/HomeRAID/immich`
**Testing**: bats-core (bash unit + integration tests)
**Target Platform**: macOS (Apple Silicon, Mac Mini), headless home server
**Project Type**: Infrastructure setup (scripts + config files)
**Performance Goals**: Immich web UI accessible within 2 min of boot (SC-001); API health check < 500ms (SC-005)
**Constraints**: No Docker Desktop (OrbStack or Homebrew Docker); RAID must be mounted before Docker starts; external library is read-only
**Scale/Scope**: ~15,000 photos, single-user, local network only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### Principle I — Test-First (NON-NEGOTIABLE)

**Status: PASS**

Every setup script function has a corresponding bats test written before the
function body. Tests cover: RAID mount detection, Docker Compose health check,
API key provisioning, external library registration, and launchd plist install.

### Principle II — Three-Layer Testing Pyramid

**Status: PASS**

- **Small (bats unit)**: Test each script function in isolation using temp dirs
  and mock commands (e.g., fake `docker` binary). Cover RAID check logic,
  timeout logic, API key file write, error messages.
- **Medium (bats integration)**: Test against a real running Docker Compose stack
  in CI or on the Mac Mini. Validate: containers start, API responds, external
  library path is accessible inside container.
- **Big (manual/e2e)**: Open `http://macmini.local:2283` in browser, verify UI
  loads and photos appear after library scan. Documented in quickstart.md as
  manual acceptance steps (automated browser test not required for v1).

### Principle III — AI-Interaction First

**Status: PASS**

FR-008 and FR-010 ensure the REST API is exposed and an API key is provisioned
at a known path. No GUI required to operate Immich after initial admin setup.
The provisioning script itself is AI-callable (takes no interactive input).

### Principle IV — Simplicity and YAGNI

**Status: PASS**

No custom middleware or abstractions. Three deliverables: `docker-compose.yml`,
`setup.sh` (one-time setup), `launchd/immich.plist` (boot agent). No database
layer, no ORM, no framework — plain Docker Compose config + bash scripts.

### Principle V — Privacy and Local-First

**Status: PASS**

All containers run on local network only. External library is read-only bind
mount — Immich cannot delete originals. No external services called. Machine
learning runs locally via `immich-machine-learning` container.

## Project Structure

### Documentation (this feature)

```text
specs/002-immich-setup/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.md           # Immich API key contract for downstream consumers
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
setup/immich/
├── docker-compose.yml       # Immich stack definition (pinned v2.6.3)
├── .env.example             # Environment variable template (no secrets)
├── setup.sh                 # One-time setup: install, start, provision admin + API key
├── launchd/
│   └── com.familyvault.immich.plist  # launchd agent for boot-time start
└── scripts/
    ├── check-raid-mount.sh  # Wait for /Volumes/HomeRAID with timeout
    ├── provision-api-key.sh # Create admin account + API key via REST API
    └── register-library.sh  # Register icloud-export as external library

tests/immich/
├── unit/
│   ├── check-raid-mount.bats
│   ├── provision-api-key.bats
│   └── register-library.bats
└── integration/
    └── immich-stack.bats    # Full stack: start → health check → API key → library
```

**Structure Decision**: Infrastructure-only project — no src/ tree. All deliverables
are config files, bash scripts, and bats tests. Follows existing project pattern
of `/scripts` for operational scripts.

## Complexity Tracking

No constitution violations. All principles satisfied with standard bash + Docker Compose.
