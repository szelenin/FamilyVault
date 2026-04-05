# Immich Setup

Deploys Immich v2.6.3 on the Mac Mini via Docker Compose with:
- All data stored on `/Volumes/HomeRAID/immich`
- `/Volumes/HomeRAID/icloud-export` as a read-only external library
- Boot-time RAID mount check via launchd
- Admin account and API key provisioned automatically

## Prerequisites

- OrbStack installed: `brew install orbstack`
- bats-core installed: `brew install bats-core bats-support bats-assert`
- `/Volumes/HomeRAID` mounted

## One-Time Setup

```bash
cp setup/immich/.env.example setup/immich/.env
# Edit .env — fill in DB_PASSWORD and JWT_SECRET with real values
./setup/immich/setup.sh
```

## Run Tests

```bash
# Unit tests (fast, no Docker required)
bats tests/immich/unit/

# Integration tests (requires running Docker)
bats tests/immich/integration/
```

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Immich stack (5 services, v2.6.3) |
| `.env.example` | Environment variable template |
| `setup.sh` | One-time setup orchestrator |
| `scripts/check-raid-mount.sh` | RAID mount check with 60s timeout |
| `scripts/provision-api-key.sh` | Admin account + API key creation |
| `scripts/register-library.sh` | External library registration |
| `scripts/configure-ml.sh` | ML/face recognition verification |
| `launchd/com.familyvault.immich.plist` | Boot-time launchd agent |
