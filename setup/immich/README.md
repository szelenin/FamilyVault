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
| `scripts/boot-immich.sh` | Boot sequence: RAID check → Docker wait → compose up → TCP proxy |
| `scripts/check-raid-mount.sh` | RAID mount check with 60s timeout |
| `scripts/tcp-proxy.py` | TCP proxy: forwards 0.0.0.0:2283 → Immich container via OrbStack DNS |
| `scripts/provision-api-key.sh` | Admin account + API key creation |
| `scripts/register-library.sh` | External library registration |
| `scripts/configure-ml.sh` | ML/face recognition verification |
| `launchd/com.familyvault.immich.plist` | Boot-time launchd agent (KeepAlive=true) |

## Boot Sequence

At login, launchd runs `boot-immich.sh` which does:

1. Wait for `/Volumes/HomeRAID` to mount (60s timeout)
2. Wait for OrbStack's Docker daemon at `~/.orbstack/run/docker.sock` (120s timeout)
3. `docker compose up -d`
4. Sleep 10s for containers to get OrbStack IPs
5. `exec python3 tcp-proxy.py` — proxy runs in the foreground as the launchd process

The proxy resolves `immich-immich-server-1.orb.local` via DNS at startup, so it works even if OrbStack assigns a different IP after a reboot.

## Troubleshooting

**Immich not accessible after reboot**

Check the boot log first:
```bash
cat /tmp/familyvault-immich.log
cat /tmp/familyvault-immich-error.log
```

| Symptom | Cause | Fix |
|---------|-------|-----|
| Log ends at "Waiting for Docker daemon" after 120s | OrbStack VM took too long to initialize | `launchctl kickstart -k gui/$(id -u)/com.familyvault.immich` — boot script now runs `open -a OrbStack` before waiting |
| `docker compose up` error in error log | Docker socket exists but OrbStack VM not ready | Wait 30s and re-run `launchctl kickstart -k gui/$(id -u)/com.familyvault.immich` |
| Proxy log shows wrong IP (empty replies) | OrbStack assigned new IP, old proxy running | `launchctl kickstart -k gui/$(id -u)/com.familyvault.immich` — proxy re-resolves IP on each start |
| `launchctl list` shows error code `-` | Job not running | Check error log; re-run kickstart |

**Restarting manually**:
```bash
launchctl kickstart -k gui/$(id -u)/com.familyvault.immich
# Wait 30s, then:
curl http://localhost:2283/api/server/ping
```
