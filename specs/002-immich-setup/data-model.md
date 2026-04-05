# Data Model: Immich Setup

**Feature**: 002-immich-setup | **Date**: 2026-04-04

This feature is infrastructure/configuration — the data model describes
configuration entities and their relationships, not application domain objects.

## Entities

### ImmichStack

The running Docker Compose deployment.

| Field | Value | Notes |
|-------|-------|-------|
| version | `v2.6.3` | Pinned at setup time |
| services | immich-server, immich-microservices, immich-machine-learning, redis, postgres | All required |
| restart_policy | `unless-stopped` | All services |
| data_root | `/Volumes/HomeRAID/immich` | On RAID, not internal drive |
| network | `bridge` (Docker default) | Local only |

### ExternalLibrary

Represents the iCloud export folder registered inside Immich.

| Field | Value | Notes |
|-------|-------|-------|
| type | `EXTERNAL` | Immich library type |
| host_path | `/Volumes/HomeRAID/icloud-export` | Source of truth |
| container_path | `/usr/src/app/icloud-export` | Bind-mounted read-only |
| scan_schedule | daily (midnight) | Immich built-in scheduler |
| ownership | read-only | Immich cannot modify/delete files |

### ImmichApiKey

The provisioned API key stored for downstream consumers.

| Field | Value | Notes |
|-------|-------|-------|
| name | `familyvault-setup` | Human-readable label in Immich UI |
| file_path | `/Volumes/HomeRAID/immich/api-key.txt` | Known location for consumers |
| permissions | admin | Required for library management |
| file_mode | `600` | Owner read-only; no group/world access |

### LaunchdAgent

The macOS boot-time agent that starts the Immich stack.

| Field | Value | Notes |
|-------|-------|-------|
| plist_path | `~/Library/LaunchAgents/com.familyvault.immich.plist` | User-level agent |
| run_at_load | `true` | Starts on login/boot |
| wrapper_script | `setup/immich/scripts/check-raid-mount.sh` | Checks RAID before Docker |
| raid_timeout | 60 seconds | Abort if RAID not mounted within this window |

## Volume Layout

```text
/Volumes/HomeRAID/immich/          # FR-003: all Immich data on RAID
├── postgres/                       # PostgreSQL data directory
├── upload/                         # Immich upload storage (thumbnails, processed)
├── model-cache/                    # ML model cache
└── api-key.txt                     # FR-010: provisioned API key (mode 600)

/Volumes/HomeRAID/icloud-export/   # FR-004: external library (read-only, not owned by Immich)
```

## State Transitions

### Setup Script State

```
UNINITIALIZED
    → [check-raid-mount.sh passes] → RAID_CONFIRMED
    → [docker compose up -d] → STACK_STARTING
    → [health check passes on :2283] → STACK_HEALTHY
    → [provision-api-key.sh] → ADMIN_PROVISIONED
    → [register-library.sh] → LIBRARY_REGISTERED
    → SETUP_COMPLETE
```

### Container Restart States (managed by Docker)

```
RUNNING → [crash] → RESTARTING (unless-stopped policy) → RUNNING
RUNNING → [manual stop] → STOPPED (unless-stopped policy, no restart)
STOPPED → [Docker daemon restart / launchd boot] → RUNNING
```
