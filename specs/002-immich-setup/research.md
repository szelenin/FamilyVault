# Research: Immich Setup

**Feature**: 002-immich-setup | **Date**: 2026-04-04

## Decision 1: Immich Version

**Decision**: Pin to Immich v2.6.3
**Rationale**: Current stable release (March 26, 2026). Pinning prevents
unexpected breaking changes from automatic updates. Upgrades are out of scope
per the spec assumptions.
**Alternatives considered**: `release` tag (floating) — rejected: violates
FR-009 repeatability requirement.

## Decision 2: Docker Runtime

**Decision**: OrbStack (preferred) or Homebrew Docker (fallback)
**Rationale**: Spec explicitly excludes Docker Desktop due to licensing and
overhead on a headless server. OrbStack is lightweight, has excellent Apple
Silicon performance, and supports `docker compose` natively. Homebrew Docker
is the fallback for headless servers without OrbStack.
**Alternatives considered**: Docker Desktop — rejected per spec assumption.
Colima — considered but OrbStack has better macOS integration and stability.

## Decision 3: Boot-Time RAID Ordering (FR-011)

**Decision**: launchd plist + wrapper bash script with mount check
**Rationale**: macOS standard mechanism for boot-time agents. The wrapper
script runs `check-raid-mount.sh` (polls `/Volumes/HomeRAID` with 60s timeout),
then runs `docker compose up -d`. launchd handles restart on failure.
**Alternatives considered**: Pure launchd with `AssociatedBundleIdentifiers`
for volume events — too complex, not reliable across macOS versions.

## Decision 4: Docker Compose restart policy

**Decision**: `restart: unless-stopped` on all Immich services
**Rationale**: Matches FR-002 exactly. Containers restart on crash and after
Docker daemon restarts (which happens after boot via launchd). `always` was
considered but `unless-stopped` allows clean manual shutdown during maintenance.
**Alternatives considered**: `on-failure` — doesn't restart after daemon
reboot; `always` — prevents intentional stop.

## Decision 5: API Key Provisioning (FR-010)

**Decision**: `provision-api-key.sh` — calls Immich REST API after stack is healthy
**Flow**:
1. POST `/api/auth/admin-sign-up` (first-run only; idempotent check via GET `/api/server/config`)
2. POST `/api/auth/login` to obtain access token
3. POST `/api/api-keys` to create named API key (`familyvault-setup`)
4. Write key secret to `/Volumes/HomeRAID/immich/api-key.txt` (mode 600)
**Rationale**: Immich has no built-in CLI key creation in Docker deployment.
REST API is the supported programmatic path. Script is idempotent: skips
admin creation if already done, skips key creation if file already exists.
**Alternatives considered**: Direct PostgreSQL INSERT — fragile, bypasses
Immich business logic; not repeatable across versions.

## Decision 6: External Library Registration (FR-004)

**Decision**: `register-library.sh` — calls Immich REST API post-provisioning
**Flow**:
1. Use API key from `/Volumes/HomeRAID/immich/api-key.txt`
2. POST `/api/libraries` with `type: EXTERNAL` and `importPaths: ["/usr/src/app/icloud-export"]`
3. POST `/api/libraries/{id}/scan` to trigger initial scan
**Rationale**: REST API is the repeatable, version-safe path. The container
path `/usr/src/app/icloud-export` maps to host `/Volumes/HomeRAID/icloud-export`
via the bind mount in docker-compose.yml.
**Alternatives considered**: Manual UI configuration — violates FR-009 (repeatability).

## Decision 7: Scheduled Library Scan (FR-005)

**Decision**: Immich built-in job scheduler (configured via REST API or UI)
**Rationale**: Immich has a native `library scan` scheduled job configurable
to run daily. No external cron needed. Default schedule: midnight daily.
**Alternatives considered**: External cron calling the scan API — adds
complexity with no benefit since Immich already supports this natively.

## Decision 8: Test Framework

**Decision**: bats-core for all bash script tests
**Rationale**: TAP-compliant, macOS-native (`brew install bats-core`), supports
setup/teardown, helper libraries (bats-support, bats-assert). Standard for
bash testing. Aligns with Constitution Principle I (test-first).
**Alternatives considered**: pytest with subprocess — adds Python dependency
with no benefit over bats for shell script testing.
