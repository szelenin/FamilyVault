# Quickstart: Immich Setup

**Feature**: 002-immich-setup | **Date**: 2026-04-04

## Prerequisites

- Mac Mini (Apple Silicon) with macOS
- `/Volumes/HomeRAID` mounted (12TB RAID1)
- OrbStack installed (`brew install orbstack`) — or Homebrew Docker as fallback
- `bats-core` installed for running tests: `brew install bats-core bats-support bats-assert`

## One-Time Setup

```bash
# From the repo root on the Mac Mini:
cd setup/immich

# Run tests first (TDD: tests before implementation)
bats ../../tests/immich/unit/

# Run setup (starts Docker stack, provisions admin + API key, registers library)
./setup.sh
```

**Setup takes ~3 minutes.** It will:
1. Check `/Volumes/HomeRAID` is mounted
2. Start the Docker Compose stack (Immich v2.6.3)
3. Wait for Immich to be healthy at `http://localhost:2283`
4. Create the admin account (first run only)
5. Provision API key → `/Volumes/HomeRAID/immich/api-key.txt`
6. Register `/Volumes/HomeRAID/icloud-export` as an external library
7. Install the launchd agent for boot-time auto-start

## Verify Setup

```bash
# Health check
curl http://macmini.local:2283/api/server/ping
# Expected: {"res":"pong"}

# API key works
curl -H "x-api-key: $(cat /Volumes/HomeRAID/immich/api-key.txt)" \
     http://macmini.local:2283/api/libraries
# Expected: JSON array with at least one library entry

# Integration tests
bats tests/immich/integration/immich-stack.bats
```

## Manual Acceptance (Big Tests)

These are the user-facing acceptance steps from the spec. Perform after setup:

1. Open `http://macmini.local:2283` in a browser → Immich login screen appears
2. Log in with admin credentials → Timeline view shows
3. Navigate to Libraries → external library listed with icloud-export path
4. After initial scan completes: photo count matches `ls /Volumes/HomeRAID/icloud-export | wc -l` (within 1%)
5. Search "beach" or "birthday" → semantically relevant results appear
6. **Reboot test**: Restart Mac Mini → Immich accessible within 2 minutes, no manual steps

## Boot Agent

The launchd agent is installed by `setup.sh` at:
```
~/Library/LaunchAgents/com.familyvault.immich.plist
```

To manage manually:
```bash
launchctl load ~/Library/LaunchAgents/com.familyvault.immich.plist   # enable
launchctl unload ~/Library/LaunchAgents/com.familyvault.immich.plist # disable
launchctl start com.familyvault.immich                                # start now
```

## Directory Reference

| Path | Purpose |
|------|---------|
| `setup/immich/docker-compose.yml` | Immich stack definition |
| `setup/immich/setup.sh` | One-time setup script |
| `setup/immich/launchd/com.familyvault.immich.plist` | Boot agent |
| `setup/immich/scripts/check-raid-mount.sh` | RAID mount checker (60s timeout) |
| `setup/immich/scripts/provision-api-key.sh` | Admin + API key provisioning |
| `setup/immich/scripts/register-library.sh` | External library registration |
| `/Volumes/HomeRAID/immich/` | All Immich data (DB, thumbnails, cache) |
| `/Volumes/HomeRAID/immich/api-key.txt` | API key for downstream services |
| `/Volumes/HomeRAID/icloud-export/` | Photo library (read-only to Immich) |

## Troubleshooting

**Immich not accessible after boot**: Check RAID is mounted (`ls /Volumes/HomeRAID`),
then check Docker: `docker compose -f setup/immich/docker-compose.yml ps`

**API key file missing**: Re-run `setup/immich/scripts/provision-api-key.sh`

**Library scan not finding photos**: Verify the bind mount: 
`docker exec immich_server ls /usr/src/app/icloud-export | head`
