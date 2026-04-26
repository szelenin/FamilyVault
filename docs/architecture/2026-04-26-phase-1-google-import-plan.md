# Phase 1 Implementation Plan: Google Takeout → Immich

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the user's complete Google Takeout (50 zips, 2.4 TB, ~243k items) into a freshly-reset Immich instance with new storage layout (RAID = originals only; Mac Mini internal = everything else), then audit the result against the Takeout manifest.

**Architecture:** Phase 0 resets Immich and migrates storage. Phase 1 runs `immich-go upload from-google-photos` once, against all 50 zips, with a parallel monitor. Phase 1.5 runs a Python audit package that compares Immich's actual state against `google-takeout-manifest.json` (the validation oracle).

**Tech Stack:** Bash 3.2+ (operational scripts), Python 3.13 + pytest (audit package), Docker Compose (Immich), `immich-go` CLI (Takeout uploader), `requests` (Python HTTP), `jq` (JSON munging in Bash).

**Design reference:** [`docs/architecture/2026-04-26-phase-1-google-import.md`](2026-04-26-phase-1-google-import.md)

---

## File structure

### Files to create

**Operational (Bash):**
- `scripts/phase0-snapshot.sh` — best-effort pre-wipe state snapshot
- `scripts/phase0-wipe.sh` — wipe old RAID Immich paths (with confirmation)
- `scripts/phase0-mkdirs.sh` — create new RAID + internal directories
- `scripts/phase1-preflight.sh` — pre-import disk/health/manifest checks
- `scripts/phase1-import.sh` — wrapper for the single-pass immich-go command
- `scripts/phase1-monitor.sh` — polls Immich every 60s during import

**Audit package (Python):**
- `scripts/phase1_audit/__init__.py` — empty
- `scripts/phase1_audit/manifest.py` — load and parse `google-takeout-manifest.json`
- `scripts/phase1_audit/immich_client.py` — thin REST wrapper around Immich API
- `scripts/phase1_audit/checks.py` — individual check functions
- `scripts/phase1_audit/__main__.py` — CLI: runs all checks, emits report

**Tests (Python):**
- `tests/phase1_audit/__init__.py` — empty
- `tests/phase1_audit/conftest.py` — shared pytest fixtures
- `tests/phase1_audit/test_manifest.py` — manifest loader tests
- `tests/phase1_audit/test_immich_client.py` — HTTP client tests with mocks
- `tests/phase1_audit/test_checks.py` — check-function tests with mock client

### Files to modify

- `setup/immich/docker-compose.yml` — split bind-mounts (originals on RAID, everything else on internal)

### Files to read but not modify

- `docs/architecture/google-takeout-manifest.json` — validation oracle (already committed)
- `docs/architecture/2026-04-26-phase-1-google-import.md` — design reference (already committed)

---

# Phase 0 — Immich reset and storage migration

## Task 1: Update docker-compose.yml for split storage

**Files:**
- Modify: `setup/immich/docker-compose.yml`

- [ ] **Step 1: Read current docker-compose.yml to confirm starting state**

Run: `cat setup/immich/docker-compose.yml`

Expected: shows three RAID-mounted paths (`/Volumes/HomeRAID/immich/{upload,model-cache,postgres}`) and one read-only iCloud mount (`/Volumes/HomeRAID/icloud-export`).

- [ ] **Step 2: Apply the new bind-mount layout**

Edit `setup/immich/docker-compose.yml`. Replace the `volumes:` blocks for `immich-server`, `immich-microservices`, `immich-machine-learning`, and `postgres` services with these:

```yaml
  immich-server:
    # ... unchanged sections ...
    volumes:
      - /Users/szelenin/immich-data/upload:${UPLOAD_LOCATION}
      - /Volumes/HomeRAID/immich-library:${UPLOAD_LOCATION}/library
      - /Volumes/HomeRAID/icloud-export:/usr/src/app/icloud-export:ro

  immich-microservices:
    # ... unchanged sections ...
    volumes:
      - /Users/szelenin/immich-data/upload:${UPLOAD_LOCATION}
      - /Volumes/HomeRAID/immich-library:${UPLOAD_LOCATION}/library
      - /Volumes/HomeRAID/icloud-export:/usr/src/app/icloud-export:ro

  immich-machine-learning:
    # ... unchanged sections ...
    volumes:
      - /Users/szelenin/immich-data/model-cache:/cache

  postgres:
    # ... unchanged sections ...
    volumes:
      - /Users/szelenin/immich-data/postgres:/var/lib/postgresql/data
```

The nested mount (`/upload` parent + `/upload/library` override) is the critical pattern — Docker handles the override correctly; the second mount masks the corresponding subdirectory inside the first.

The iCloud read-only mount stays as-is for now (we will detach the External Library via the Immich UI in Task 8, not by removing the docker mount).

- [ ] **Step 3: Validate compose syntax**

Run: `docker compose -f setup/immich/docker-compose.yml config > /dev/null && echo "OK"`

Expected: prints `OK`. (Do NOT run `up` yet — the new directories don't exist.)

- [ ] **Step 4: Commit**

```bash
git add setup/immich/docker-compose.yml
git commit -m "chore(015): split Immich storage — originals on RAID, everything else on internal SSD"
```

---

## Task 2: Pre-wipe state snapshot script

**Files:**
- Create: `scripts/phase0-snapshot.sh`

- [ ] **Step 1: Write the snapshot script**

Create `scripts/phase0-snapshot.sh`:

```bash
#!/usr/bin/env bash
# Best-effort snapshot of pre-wipe Immich state.
# For the record only — not used for restore. Tolerant of Immich being down.
set -euo pipefail

OUT="${1:-/tmp/immich-pre-wipe-state.json}"
API="http://localhost:2283"
KEY_FILE="/Volumes/HomeRAID/immich/api-key.txt"

echo "Writing snapshot to $OUT"

# Capture disk usage of old Immich paths (always works regardless of container state)
disk_usage=$(du -sh /Volumes/HomeRAID/immich/* 2>&1 | jq -Rs .)

# Capture container state
docker_ps=$(docker ps --format '{{.Names}}\t{{.Status}}' 2>&1 | grep -i immich | jq -Rs .)

# Capture API state if Immich responds
api_stats="null"
api_libraries="null"
if [[ -f "$KEY_FILE" ]]; then
  KEY=$(cat "$KEY_FILE")
  if curl -sfm 5 -H "x-api-key: $KEY" "$API/api/server/statistics" > /tmp/_stats.json 2>/dev/null; then
    api_stats=$(cat /tmp/_stats.json)
  fi
  if curl -sfm 5 -H "x-api-key: $KEY" "$API/api/libraries" > /tmp/_libs.json 2>/dev/null; then
    api_libraries=$(cat /tmp/_libs.json)
  fi
  rm -f /tmp/_stats.json /tmp/_libs.json
fi

cat <<EOF > "$OUT"
{
  "snapshot_taken": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "disk_usage": $disk_usage,
  "docker_immich_containers": $docker_ps,
  "api_server_statistics": $api_stats,
  "api_libraries": $api_libraries
}
EOF

echo "Snapshot written."
cat "$OUT" | jq . || cat "$OUT"
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/phase0-snapshot.sh`

- [ ] **Step 3: Run the snapshot**

Run: `scripts/phase0-snapshot.sh /tmp/immich-pre-wipe-state.json`

Expected: writes a JSON file with disk usage info; API fields will likely be `null` since Immich is stopped (that's fine).

Verify: `jq . /tmp/immich-pre-wipe-state.json` exits 0 (valid JSON).

- [ ] **Step 4: Commit**

```bash
git add scripts/phase0-snapshot.sh
git commit -m "feat(015): pre-wipe Immich state snapshot script"
```

---

## Task 3: Wipe script for old RAID Immich paths

**Files:**
- Create: `scripts/phase0-wipe.sh`

- [ ] **Step 1: Write the wipe script (no execution yet)**

Create `scripts/phase0-wipe.sh`:

```bash
#!/usr/bin/env bash
# Wipe the old RAID Immich tree.
# Destructive — prompts for explicit confirmation before deleting anything.
set -euo pipefail

PATHS=(
  "/Volumes/HomeRAID/immich/upload"
  "/Volumes/HomeRAID/immich/model-cache"
  "/Volumes/HomeRAID/immich/postgres"
  "/Volumes/HomeRAID/immich/api-key.txt"
  "/Volumes/HomeRAID/immich/library-id.txt"
)

echo "About to PERMANENTLY DELETE the following paths:"
for p in "${PATHS[@]}"; do
  if [[ -e "$p" ]]; then
    sz=$(du -sh "$p" 2>/dev/null | cut -f1)
    echo "  - $p ($sz)"
  else
    echo "  - $p (not present, skip)"
  fi
done

# Refuse to run if Immich containers are still up — postgres files would be locked
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qi immich; then
  echo "ERROR: Immich containers are running. Stop them first with 'docker compose -f setup/immich/docker-compose.yml down'." >&2
  exit 2
fi

read -r -p "Type 'WIPE' to confirm deletion: " confirm
if [[ "$confirm" != "WIPE" ]]; then
  echo "Aborted." >&2
  exit 1
fi

for p in "${PATHS[@]}"; do
  if [[ -e "$p" ]]; then
    echo "Removing $p ..."
    rm -rf "$p"
  fi
done

# Remove the now-empty parent if it has nothing left
if [[ -d /Volumes/HomeRAID/immich ]] && [[ -z "$(ls -A /Volumes/HomeRAID/immich 2>/dev/null)" ]]; then
  rmdir /Volumes/HomeRAID/immich
  echo "Removed empty /Volumes/HomeRAID/immich"
fi

echo "Done."
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/phase0-wipe.sh`

- [ ] **Step 3: Verify the script's safety logic without deleting anything**

Run: `echo "n" | scripts/phase0-wipe.sh 2>&1 | head -20`

Expected: prints the list of paths to delete, asks for confirmation, then aborts with exit code 1 because we typed "n" instead of "WIPE".

- [ ] **Step 4: Commit**

```bash
git add scripts/phase0-wipe.sh
git commit -m "feat(015): destructive wipe script for old RAID Immich paths"
```

---

## Task 4: Mkdirs script for new storage layout

**Files:**
- Create: `scripts/phase0-mkdirs.sh`

- [ ] **Step 1: Write the mkdirs script**

Create `scripts/phase0-mkdirs.sh`:

```bash
#!/usr/bin/env bash
# Create the new directories for the split-storage Immich layout.
set -euo pipefail

DIRS=(
  "/Users/szelenin/immich-data/upload"
  "/Users/szelenin/immich-data/postgres"
  "/Users/szelenin/immich-data/model-cache"
  "/Volumes/HomeRAID/immich-library"
)

for d in "${DIRS[@]}"; do
  if [[ -d "$d" ]]; then
    echo "Already exists: $d"
  else
    mkdir -p "$d"
    echo "Created: $d"
  fi
done

# Postgres expects a specific directory permission scheme
chmod 700 /Users/szelenin/immich-data/postgres

echo "All directories ready."
ls -ld "${DIRS[@]}"
```

- [ ] **Step 2: Make executable and run**

```bash
chmod +x scripts/phase0-mkdirs.sh
scripts/phase0-mkdirs.sh
```

Expected: each directory listed as either "Created" or "Already exists". Final `ls -ld` shows all four directories with mode `drwx------` for postgres and `drwxr-xr-x` for the others.

- [ ] **Step 3: Commit**

```bash
git add scripts/phase0-mkdirs.sh
git commit -m "feat(015): create new directories for split-storage Immich layout"
```

---

## Task 5: Run Phase 0 reset (operational, no commit)

This task chains the previous scripts into the actual reset. Nothing is committed in this task — it's pure operations.

- [ ] **Step 1: Confirm Immich containers are stopped**

Run: `docker ps --format '{{.Names}}' | grep -i immich || echo "no immich containers running"`

Expected: prints `no immich containers running`. If any containers ARE running, stop them with `docker compose -f setup/immich/docker-compose.yml down` first.

- [ ] **Step 2: Take pre-wipe snapshot**

Run: `scripts/phase0-snapshot.sh /tmp/immich-pre-wipe-state.json`

Expected: snapshot file written. Inspect with `jq . /tmp/immich-pre-wipe-state.json` to confirm.

- [ ] **Step 3: Wipe old RAID Immich paths (interactive — requires typing WIPE)**

Run: `scripts/phase0-wipe.sh`

When prompted "Type 'WIPE' to confirm deletion:", review the list of paths printed above. If the list looks correct, type `WIPE` and press Enter. Otherwise type anything else to abort.

Expected: each path removed with a "Removing ..." message.

Verify: `ls -la /Volumes/HomeRAID/ | grep -i immich` should show only `immich-library` (created in next step) or nothing.

- [ ] **Step 4: Create new directories**

Run: `scripts/phase0-mkdirs.sh`

Expected: directories created on Mac Mini internal and on RAID.

Verify: `ls -ld /Users/szelenin/immich-data/* /Volumes/HomeRAID/immich-library` shows all four directories.

- [ ] **Step 5: Bump OrbStack CPU allocation (manual UI step)**

Open OrbStack on Mac Mini. Go to Settings → System → Resources. Set CPU allocation to at least 8 cores (was likely 4 before). Click "Apply". OrbStack will restart its VM.

Verify: `docker run --rm alpine nproc` should print `8` or higher.

- [ ] **Step 6: Start Immich on the clean slate**

Run: `docker compose -f setup/immich/docker-compose.yml up -d`

Expected: pulls images if needed, starts all five services (immich-server, immich-microservices, immich-machine-learning, redis, postgres).

Verify: `docker compose -f setup/immich/docker-compose.yml ps` shows all services as "running" or "healthy".

- [ ] **Step 7: Initial Immich web UI setup (manual)**

Open `http://macmini:2283` in a browser. Steps:

1. Click "Get Started" → create admin account (your email + password).
2. After login: Account menu → API Keys → "New API Key" → copy the value.
3. Save the API key: `echo "<paste-key-here>" > /Users/szelenin/immich-data/api-key.txt && chmod 600 /Users/szelenin/immich-data/api-key.txt`
4. Admin → System Settings → Job Settings → Video Conversion → set "Transcode Policy" to **Disabled**. Click "Save".

- [ ] **Step 8: Verify clean state**

Run:

```bash
KEY=$(cat /Users/szelenin/immich-data/api-key.txt)
curl -sH "x-api-key: $KEY" http://localhost:2283/api/server/statistics | jq
```

Expected output (asset counts must be zero):

```json
{
  "photos": 0,
  "videos": 0,
  "usage": ...,
  "usageByUser": [...]
}
```

If `photos > 0` or `videos > 0`, something didn't get wiped — investigate before proceeding.

---

# Phase 1 — Google Takeout import

## Task 6: Pre-flight script

**Files:**
- Create: `scripts/phase1-preflight.sh`

- [ ] **Step 1: Write the pre-flight script**

Create `scripts/phase1-preflight.sh`:

```bash
#!/usr/bin/env bash
# Pre-flight checks before kicking off the Phase 1 import.
# Exits 0 only if every check passes.
set -euo pipefail

API="http://localhost:2283"
KEY_FILE="/Users/szelenin/immich-data/api-key.txt"
TAKEOUT_DIR="/Volumes/HomeRAID/google-takeout"
MANIFEST="docs/architecture/google-takeout-manifest.json"

fail=0
log() { printf "%-40s %s\n" "$1" "$2"; }

# 1. RAID free space ≥ 3 TB
raid_avail_gb=$(df -g /Volumes/HomeRAID | awk 'NR==2{print $4}')
if (( raid_avail_gb >= 3000 )); then
  log "RAID free space:" "${raid_avail_gb} GB OK"
else
  log "RAID free space:" "${raid_avail_gb} GB FAIL (need ≥3000)"; fail=1
fi

# 2. Internal SSD free space ≥ 200 GB
int_avail_gb=$(df -g /Users/szelenin | awk 'NR==2{print $4}')
if (( int_avail_gb >= 200 )); then
  log "Internal SSD free space:" "${int_avail_gb} GB OK"
else
  log "Internal SSD free space:" "${int_avail_gb} GB FAIL (need ≥200)"; fail=1
fi

# 3. Immich responds with photos=0 videos=0
if [[ ! -f "$KEY_FILE" ]]; then
  log "Immich API key:" "MISSING ($KEY_FILE)"; fail=1
else
  KEY=$(cat "$KEY_FILE")
  resp=$(curl -sfm 5 -H "x-api-key: $KEY" "$API/api/server/statistics" || echo "")
  if [[ -z "$resp" ]]; then
    log "Immich API health:" "FAIL (no response)"; fail=1
  else
    p=$(echo "$resp" | jq -r .photos)
    v=$(echo "$resp" | jq -r .videos)
    if [[ "$p" == "0" && "$v" == "0" ]]; then
      log "Immich starting state:" "photos=0 videos=0 OK"
    else
      log "Immich starting state:" "photos=$p videos=$v FAIL (must be 0/0)"; fail=1
    fi
  fi
fi

# 4. immich-go installed
if command -v immich-go >/dev/null; then
  log "immich-go:" "$(immich-go --version 2>&1 | head -1) OK"
else
  log "immich-go:" "NOT INSTALLED FAIL"; fail=1
fi

# 5. Exactly 50 takeout zips on disk (the -3-NNN pattern)
zip_count=$(find "$TAKEOUT_DIR" -name 'takeout-*-3-*.zip' -type f | wc -l | tr -d ' ')
if [[ "$zip_count" == "50" ]]; then
  log "Takeout zips on disk:" "50 OK"
else
  log "Takeout zips on disk:" "$zip_count FAIL (expected 50)"; fail=1
fi

# 6. Manifest present
if [[ -f "$MANIFEST" ]]; then
  total=$(jq -r .total_files_in_html "$MANIFEST")
  log "Manifest present:" "$total entries OK"
else
  log "Manifest present:" "MISSING ($MANIFEST) FAIL"; fail=1
fi

# 7. Video transcoding disabled (best-effort — try to read system config)
if [[ -n "${KEY:-}" ]]; then
  conf=$(curl -sfm 5 -H "x-api-key: $KEY" "$API/api/system-config" 2>/dev/null || echo "{}")
  policy=$(echo "$conf" | jq -r '.ffmpeg.transcode // "unknown"')
  if [[ "$policy" == "disabled" ]]; then
    log "Video transcoding policy:" "disabled OK"
  else
    log "Video transcoding policy:" "$policy WARN (recommended: disabled)"
  fi
fi

if (( fail == 0 )); then
  echo "ALL CHECKS PASSED."
else
  echo "PRE-FLIGHT FAILED — fix issues above before starting import." >&2
  exit 1
fi
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/phase1-preflight.sh`

- [ ] **Step 3: Run pre-flight (will likely show some FAILs at this point — that is expected, since immich-go is not yet installed)**

Run: `scripts/phase1-preflight.sh || true`

Expected: prints the list of checks. Reading down the list lets you see what's still missing. The "immich-go: NOT INSTALLED" line is expected on first run.

- [ ] **Step 4: Commit**

```bash
git add scripts/phase1-preflight.sh
git commit -m "feat(015): Phase 1 pre-flight check script"
```

---

## Task 7: Install immich-go

This is operational; no script to commit.

- [ ] **Step 1: Install immich-go via Homebrew**

Run: `brew install immich-go`

If the brew formula isn't available, fall back to GitHub release:

```bash
cd /tmp
curl -L -o immich-go.tar.gz \
  "https://github.com/simulot/immich-go/releases/latest/download/immich-go_Darwin_arm64.tar.gz"
tar xzf immich-go.tar.gz
sudo mv immich-go /usr/local/bin/
immich-go --version
```

- [ ] **Step 2: Verify installation**

Run: `immich-go --version`

Expected: prints a version string (e.g., `immich-go version 0.31.0`). Take note of the version — record it in the import command below if you want to lock it.

- [ ] **Step 3: Re-run pre-flight**

Run: `scripts/phase1-preflight.sh`

Expected: now passes the immich-go check. Other checks should also pass at this point.

---

## Task 8: Detach iCloud External Library (manual UI step, no commit)

The iCloud external library still appears in Immich because the read-only mount in docker-compose.yml was not removed. Detach it via UI so we start Phase 1 with zero pre-existing assets to count.

- [ ] **Step 1: Detach via Immich admin UI**

Open `http://macmini:2283` → log in as admin → Administration → External Libraries.

Find the iCloud External Library (most likely named `icloud-export` or similar). Click the "..." menu → "Delete". Confirm.

- [ ] **Step 2: Verify state is still 0/0**

Run:

```bash
KEY=$(cat /Users/szelenin/immich-data/api-key.txt)
curl -sH "x-api-key: $KEY" http://localhost:2283/api/server/statistics | jq '{photos, videos}'
```

Expected: `{"photos": 0, "videos": 0}`. If non-zero, the External Library deletion is still queueing — wait 30 seconds and re-check.

---

## Task 9: Import runner script

**Files:**
- Create: `scripts/phase1-import.sh`

- [ ] **Step 1: Write the import script**

Create `scripts/phase1-import.sh`:

```bash
#!/usr/bin/env bash
# Single-pass Google Takeout import via immich-go. Run inside tmux/screen.
set -euo pipefail

API="http://localhost:2283"
KEY_FILE="/Users/szelenin/immich-data/api-key.txt"
TAKEOUT_GLOB="/Volumes/HomeRAID/google-takeout/takeout-20260403T195541Z-3-*.zip"
LOG_FILE="/Users/szelenin/immich-data/immich-go.log"
SESSION_TAG="phase-1-google-$(date +%Y%m%d)"

if [[ ! -f "$KEY_FILE" ]]; then
  echo "API key not found at $KEY_FILE" >&2
  exit 1
fi

KEY=$(cat "$KEY_FILE")
zip_count=$(ls $TAKEOUT_GLOB 2>/dev/null | wc -l | tr -d ' ')
if [[ "$zip_count" != "50" ]]; then
  echo "Expected 50 zips matching $TAKEOUT_GLOB, found $zip_count" >&2
  exit 1
fi

echo "Starting immich-go import:"
echo "  zips:        $zip_count"
echo "  session-tag: $SESSION_TAG"
echo "  log-file:    $LOG_FILE"
echo "Hit Ctrl-C in the next 5 seconds to abort."
sleep 5

immich-go upload from-google-photos \
  --server="$API" \
  --api-key="$KEY" \
  --concurrent-tasks=4 \
  --client-timeout=60m \
  --pause-immich-jobs=true \
  --on-errors=continue \
  --session-tag="$SESSION_TAG" \
  --log-file="$LOG_FILE" \
  $TAKEOUT_GLOB

echo "immich-go finished. Resume Immich jobs with:"
echo "  curl -X PUT -H 'x-api-key: $KEY' '$API/api/jobs/{queue}/resume' (per queue)"
echo "Or via admin UI: Administration → Jobs → 'Resume All'"
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/phase1-import.sh`

- [ ] **Step 3: Verify the script syntax (do not run yet)**

Run: `bash -n scripts/phase1-import.sh && echo "syntax OK"`

Expected: `syntax OK`.

- [ ] **Step 4: Commit**

```bash
git add scripts/phase1-import.sh
git commit -m "feat(015): single-pass Google Takeout import wrapper"
```

---

## Task 10: Monitoring script

**Files:**
- Create: `scripts/phase1-monitor.sh`

- [ ] **Step 1: Write the monitor script**

Create `scripts/phase1-monitor.sh`:

```bash
#!/usr/bin/env bash
# Polls Immich every 60s during the Phase 1 import, logs to a file.
# Run in a separate tmux window/pane from the import.
set -euo pipefail

API="http://localhost:2283"
KEY_FILE="/Users/szelenin/immich-data/api-key.txt"
LOG="${1:-/Users/szelenin/immich-data/import-progress.log}"

KEY=$(cat "$KEY_FILE")
prev_total=0
prev_ts=$(date +%s)

echo "Monitoring Immich at $API; logging to $LOG"
echo "timestamp,photos,videos,total,delta_per_min,meta_waiting,thumb_waiting,smart_waiting,face_waiting" > "$LOG"

while true; do
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  now=$(date +%s)

  stats=$(curl -sfm 5 -H "x-api-key: $KEY" "$API/api/server/statistics" 2>/dev/null || echo "{}")
  jobs=$(curl -sfm 5 -H "x-api-key: $KEY" "$API/api/jobs" 2>/dev/null || echo "{}")

  p=$(echo "$stats" | jq -r '.photos // 0')
  v=$(echo "$stats" | jq -r '.videos // 0')
  total=$(( p + v ))

  meta=$(echo "$jobs" | jq -r '.metadataExtraction.jobCounts.waiting // 0')
  thumb=$(echo "$jobs" | jq -r '.thumbnailGeneration.jobCounts.waiting // 0')
  smart=$(echo "$jobs" | jq -r '.smartSearch.jobCounts.waiting // 0')
  face=$(echo "$jobs" | jq -r '.faceDetection.jobCounts.waiting // 0')

  dt=$(( now - prev_ts ))
  if (( dt > 0 )); then
    delta_per_min=$(( (total - prev_total) * 60 / dt ))
  else
    delta_per_min=0
  fi

  echo "$ts,$p,$v,$total,$delta_per_min,$meta,$thumb,$smart,$face" >> "$LOG"
  printf "[%s] photos=%d videos=%d total=%d (%+d/min) | meta_q=%d thumb_q=%d smart_q=%d face_q=%d\n" \
    "$ts" "$p" "$v" "$total" "$delta_per_min" "$meta" "$thumb" "$smart" "$face"

  prev_total=$total
  prev_ts=$now
  sleep 60
done
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/phase1-monitor.sh`

- [ ] **Step 3: Verify syntax**

Run: `bash -n scripts/phase1-monitor.sh && echo "syntax OK"`

Expected: `syntax OK`.

- [ ] **Step 4: Test monitor against the empty Immich (run for 2 minutes)**

Run in a separate terminal: `timeout 130 scripts/phase1-monitor.sh /tmp/test-monitor.log; cat /tmp/test-monitor.log`

Expected: header line + 2-3 data rows showing `photos=0 videos=0 total=0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/phase1-monitor.sh
git commit -m "feat(015): Immich progress monitor for long imports"
```

---

## Task 11: Run the actual import (operational, requires user permission)

**This task takes 24-48 hours of wall time. Schedule for a weekend.**

- [ ] **Step 1: Run pre-flight one final time**

Run: `scripts/phase1-preflight.sh`

Expected: ALL CHECKS PASSED.

- [ ] **Step 2: Start a tmux session**

Run: `tmux new -s phase1`

Inside tmux, split the window: press `Ctrl-b "` to create a horizontal split.

- [ ] **Step 3: In one tmux pane, start the import**

Run: `scripts/phase1-import.sh`

Watch for the 5-second abort window, then the immich-go discovery phase will begin (this takes 30-90 minutes by itself before any uploads start).

- [ ] **Step 4: In the other tmux pane, start the monitor**

Run: `scripts/phase1-monitor.sh /Users/szelenin/immich-data/import-progress.log`

The monitor prints one line per minute. Detach from tmux with `Ctrl-b d` when you want to leave it running. Re-attach with `tmux attach -t phase1`.

- [ ] **Step 5: Wait for completion**

Periodically check: `tmux attach -t phase1` → look at the import pane.

Expected end state (when immich-go exits cleanly):
- Import pane shows "immich-go finished" message and exits to shell prompt.
- Monitor's last line shows `total ≈ 242,000` (within ±5% — broken files immich-go skipped will be a few hundred to a few thousand).

If immich-go crashes mid-run: simply re-run `scripts/phase1-import.sh`. Server-side hash dedup will skip already-uploaded files; immich-go's discovery phase will re-run from scratch (cost: ~1 hour repeated work).

- [ ] **Step 6: Commit the immich-go log and monitor log to the repo**

```bash
mkdir -p docs/architecture/phase-1-run/
cp /Users/szelenin/immich-data/immich-go.log docs/architecture/phase-1-run/immich-go.log
cp /Users/szelenin/immich-data/import-progress.log docs/architecture/phase-1-run/import-progress.log
git add docs/architecture/phase-1-run/
git commit -m "feat(015): commit Phase 1 import logs for the record"
```

(If the logs are too big to commit, gzip them and adjust `.gitignore`.)

---

## Task 12: Resume Immich background jobs (manual)

After the import, ML and thumbnail jobs were paused. Resume them so Immich processes everything we just uploaded.

- [ ] **Step 1: Resume jobs via UI**

Open `http://macmini:2283` → Administration → Jobs.

For each queue (metadataExtraction, thumbnailGeneration, smartSearch, faceDetection, faceRecognition, library, sidecar, duplicateDetection): click the "Resume" button.

The queue depth will be in the millions after a 243k-asset import (each asset spawns multiple jobs). Expect the full processing run to take **another 24-48 hours**.

- [ ] **Step 2: Verify queues are draining**

Run:

```bash
KEY=$(cat /Users/szelenin/immich-data/api-key.txt)
curl -sH "x-api-key: $KEY" http://localhost:2283/api/jobs | jq '{
  meta: .metadataExtraction.jobCounts,
  thumb: .thumbnailGeneration.jobCounts
}'
```

Expected: `active > 0` for any resumed queue. Check again after 30 minutes — `waiting` should be decreasing.

---

# Phase 1.5 — Post-import audit (Python package)

## Task 13: Audit package skeleton + manifest loader (TDD)

**Files:**
- Create: `scripts/phase1_audit/__init__.py` (empty)
- Create: `scripts/phase1_audit/manifest.py`
- Create: `tests/phase1_audit/__init__.py` (empty)
- Create: `tests/phase1_audit/conftest.py`
- Create: `tests/phase1_audit/test_manifest.py`

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p scripts/phase1_audit tests/phase1_audit
: > scripts/phase1_audit/__init__.py
: > tests/phase1_audit/__init__.py
```

- [ ] **Step 2: Write `tests/phase1_audit/conftest.py` with shared fixtures**

```python
"""Shared pytest fixtures for the phase1_audit test package."""
from __future__ import annotations
import json
from pathlib import Path
import pytest


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    """Write a small valid manifest fixture and return its path."""
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({
        "source_zip": "test.zip",
        "total_files_in_html": 100,
        "total_folders": 5,
        "extension_counts": {
            "json": 40, "heic": 30, "jpg": 20, "mp4": 10
        },
        "year_folder_count": 2,
        "year_folder_range": ["Photos from 2020", "Photos from 2021"],
        "user_album_count": 3,
        "user_albums": ["Trip A", "Trip B", "Trip C"],
    }))
    return p
```

- [ ] **Step 3: Write the failing test for the manifest loader**

Create `tests/phase1_audit/test_manifest.py`:

```python
"""Tests for the manifest loader."""
from __future__ import annotations
from pathlib import Path

from scripts.phase1_audit.manifest import Manifest, load_manifest


def test_load_manifest_returns_typed_object(manifest_path: Path) -> None:
    m = load_manifest(manifest_path)
    assert isinstance(m, Manifest)
    assert m.user_album_count == 3
    assert m.user_albums == ("Trip A", "Trip B", "Trip C")


def test_manifest_expected_media_count_excludes_json_and_no_ext(manifest_path: Path) -> None:
    m = load_manifest(manifest_path)
    # 100 - 40 (json) = 60 (no 'no-ext' bucket in fixture, so just subtract json)
    assert m.expected_media_count() == 60


def test_manifest_extension_counts_accessor(manifest_path: Path) -> None:
    m = load_manifest(manifest_path)
    assert m.count_for_extension("heic") == 30
    assert m.count_for_extension("missing") == 0
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd /Users/szelenin/projects/takeout/takeout/.worktrees/015-three-source-merge && python3 -m pytest tests/phase1_audit/test_manifest.py -v`

Expected: 3 failures with `ModuleNotFoundError: No module named 'scripts.phase1_audit.manifest'` (or similar).

- [ ] **Step 5: Implement the manifest loader**

Create `scripts/phase1_audit/manifest.py`:

```python
"""Load and expose typed access to google-takeout-manifest.json."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Manifest:
    """In-memory view of google-takeout-manifest.json."""
    source_zip: str
    total_files_in_html: int
    total_folders: int
    extension_counts: Mapping[str, int]
    year_folder_count: int
    year_folder_range: tuple[str, str]
    user_album_count: int
    user_albums: tuple[str, ...]

    def expected_media_count(self) -> int:
        """Total media items expected in Immich (excludes sidecars and no-ext entries)."""
        non_media = self.extension_counts.get("json", 0) + self.extension_counts.get("no-ext", 0)
        return self.total_files_in_html - non_media

    def count_for_extension(self, ext: str) -> int:
        """Count of files with the given lowercase extension. Returns 0 if absent."""
        return self.extension_counts.get(ext.lower(), 0)


def load_manifest(path: Path) -> Manifest:
    """Read the manifest JSON at path and return a Manifest object."""
    raw = json.loads(Path(path).read_text())
    yfr = raw.get("year_folder_range") or [None, None]
    return Manifest(
        source_zip=raw["source_zip"],
        total_files_in_html=raw["total_files_in_html"],
        total_folders=raw["total_folders"],
        extension_counts=dict(raw["extension_counts"]),
        year_folder_count=raw["year_folder_count"],
        year_folder_range=(yfr[0], yfr[1]),
        user_album_count=raw["user_album_count"],
        user_albums=tuple(raw["user_albums"]),
    )
```

- [ ] **Step 6: Run tests to verify pass**

Run: `python3 -m pytest tests/phase1_audit/test_manifest.py -v`

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add scripts/phase1_audit/__init__.py scripts/phase1_audit/manifest.py \
        tests/phase1_audit/__init__.py tests/phase1_audit/conftest.py tests/phase1_audit/test_manifest.py
git commit -m "feat(015): manifest loader for Phase 1.5 audit"
```

---

## Task 14: Immich REST client (TDD)

**Files:**
- Create: `scripts/phase1_audit/immich_client.py`
- Create: `tests/phase1_audit/test_immich_client.py`

- [ ] **Step 1: Write failing tests with mocked HTTP responses**

Create `tests/phase1_audit/test_immich_client.py`:

```python
"""Tests for the Immich REST client."""
from __future__ import annotations
from unittest.mock import MagicMock, patch

import pytest

from scripts.phase1_audit.immich_client import ImmichClient


def _mock_response(status=200, json_body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_body if json_body is not None else {}
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return r


def test_client_get_statistics_calls_correct_endpoint() -> None:
    with patch("requests.get", return_value=_mock_response(json_body={"photos": 100, "videos": 20})) as g:
        c = ImmichClient(server="http://x", api_key="k")
        out = c.get_statistics()
    assert out == {"photos": 100, "videos": 20}
    args, kwargs = g.call_args
    assert args[0] == "http://x/api/server/statistics"
    assert kwargs["headers"] == {"x-api-key": "k"}


def test_client_list_albums_returns_list() -> None:
    body = [{"id": "a", "albumName": "Trip A"}, {"id": "b", "albumName": "Trip B"}]
    with patch("requests.get", return_value=_mock_response(json_body=body)):
        c = ImmichClient(server="http://x", api_key="k")
        out = c.list_albums()
    assert out == body


def test_client_search_metadata_posts_payload() -> None:
    body = {"assets": {"items": [{"originalFileName": "a.heic"}], "total": 1}}
    with patch("requests.post", return_value=_mock_response(json_body=body)) as p:
        c = ImmichClient(server="http://x", api_key="k")
        items = c.search_metadata({"originalFileName": ".heic"})
    assert items == body["assets"]["items"]
    args, kwargs = p.call_args
    assert args[0] == "http://x/api/search/metadata"
    assert kwargs["json"] == {"originalFileName": ".heic"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/phase1_audit/test_immich_client.py -v`

Expected: 3 failures with `ModuleNotFoundError: No module named 'scripts.phase1_audit.immich_client'`.

- [ ] **Step 3: Implement the client**

Create `scripts/phase1_audit/immich_client.py`:

```python
"""Thin wrapper around the Immich REST API for the audit."""
from __future__ import annotations
from typing import Any, Mapping
import requests


class ImmichClient:
    """Minimal Immich REST client. Only methods the audit needs."""

    def __init__(self, server: str, api_key: str, timeout: float = 30.0) -> None:
        self._server = server.rstrip("/")
        self._headers = {"x-api-key": api_key}
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self._server}{path}"

    def get_statistics(self) -> Mapping[str, Any]:
        """GET /api/server/statistics — total photo/video counts and per-user breakdown."""
        r = requests.get(self._url("/api/server/statistics"), headers=self._headers, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def list_albums(self) -> list[Mapping[str, Any]]:
        """GET /api/albums — list of all albums."""
        r = requests.get(self._url("/api/albums"), headers=self._headers, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def search_metadata(self, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        """POST /api/search/metadata — returns the assets.items list directly."""
        r = requests.post(self._url("/api/search/metadata"), json=payload,
                          headers=self._headers, timeout=self._timeout)
        r.raise_for_status()
        return r.json()["assets"]["items"]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest tests/phase1_audit/test_immich_client.py -v`

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/phase1_audit/immich_client.py tests/phase1_audit/test_immich_client.py
git commit -m "feat(015): Immich REST client for Phase 1.5 audit"
```

---

## Task 15: Audit checks — total count + per-extension count (TDD)

**Files:**
- Create: `scripts/phase1_audit/checks.py`
- Create: `tests/phase1_audit/test_checks.py`

- [ ] **Step 1: Write failing tests for total/extension checks**

Create `tests/phase1_audit/test_checks.py`:

```python
"""Tests for individual audit checks."""
from __future__ import annotations
from unittest.mock import MagicMock

from scripts.phase1_audit.manifest import Manifest
from scripts.phase1_audit.checks import (
    check_total_count,
    check_extension_count,
    CheckResult,
)


def _manifest(**over) -> Manifest:
    base = dict(
        source_zip="t.zip", total_files_in_html=100, total_folders=0,
        extension_counts={"heic": 30, "json": 40, "mp4": 30},
        year_folder_count=0, year_folder_range=(None, None),
        user_album_count=0, user_albums=(),
    )
    base.update(over)
    return Manifest(**base)


def test_total_count_pass_within_tolerance() -> None:
    m = _manifest()  # expected = 100 - 40 = 60
    client = MagicMock()
    client.get_statistics.return_value = {"photos": 30, "videos": 30}  # exact 60
    r = check_total_count(client, m, tolerance=0.01)
    assert r.passed is True
    assert r.actual == 60
    assert r.expected == 60


def test_total_count_pass_at_edge_of_tolerance() -> None:
    m = _manifest()  # expected = 60; ±1% = 0.6 → integer floor 0
    client = MagicMock()
    # 60 + 1 = 61 — outside ±0.6 in absolute terms → check uses fractional
    client.get_statistics.return_value = {"photos": 30, "videos": 30}
    r = check_total_count(client, m, tolerance=0.01)
    assert r.passed is True


def test_total_count_fail_outside_tolerance() -> None:
    m = _manifest()  # expected = 60
    client = MagicMock()
    client.get_statistics.return_value = {"photos": 0, "videos": 0}
    r = check_total_count(client, m, tolerance=0.01)
    assert r.passed is False
    assert "0" in r.message


def test_extension_count_uses_search_metadata() -> None:
    m = _manifest()  # heic = 30
    client = MagicMock()
    client.search_metadata.return_value = [{"id": str(i)} for i in range(30)]
    r = check_extension_count(client, m, "heic", tolerance=0.01)
    assert r.passed is True
    client.search_metadata.assert_called_once()
    payload = client.search_metadata.call_args.args[0]
    assert ".heic" in payload.get("originalFileName", "").lower() \
        or "heic" in payload.get("originalFileName", "").lower()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest tests/phase1_audit/test_checks.py -v`

Expected: failures with `ModuleNotFoundError: No module named 'scripts.phase1_audit.checks'`.

- [ ] **Step 3: Implement the checks**

Create `scripts/phase1_audit/checks.py`:

```python
"""Individual audit checks. Each returns a CheckResult."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .immich_client import ImmichClient
from .manifest import Manifest


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    expected: Any
    actual: Any
    message: str = ""


def _within_tolerance(actual: int, expected: int, tolerance: float) -> bool:
    """Return True if actual is within (expected * tolerance) of expected, with a min slack of 1."""
    if expected == 0:
        return actual == 0
    slack = max(1, int(expected * tolerance))
    return abs(actual - expected) <= slack


def check_total_count(client: ImmichClient, manifest: Manifest, tolerance: float = 0.01) -> CheckResult:
    """Verify Immich's photos+videos count matches manifest's expected media count within tolerance."""
    stats = client.get_statistics()
    actual = int(stats.get("photos", 0)) + int(stats.get("videos", 0))
    expected = manifest.expected_media_count()
    passed = _within_tolerance(actual, expected, tolerance)
    return CheckResult(
        name="total_count",
        passed=passed,
        expected=expected,
        actual=actual,
        message=f"Immich={actual} expected={expected} (tolerance ±{tolerance:.0%})",
    )


def check_extension_count(client: ImmichClient, manifest: Manifest,
                          ext: str, tolerance: float = 0.01) -> CheckResult:
    """Verify Immich's count of assets ending in .<ext> matches manifest within tolerance."""
    expected = manifest.count_for_extension(ext)
    items = client.search_metadata({"originalFileName": f".{ext.lower()}"})
    actual = len(items)
    passed = _within_tolerance(actual, expected, tolerance)
    return CheckResult(
        name=f"extension_count_{ext.lower()}",
        passed=passed,
        expected=expected,
        actual=actual,
        message=f".{ext} Immich={actual} expected={expected}",
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest tests/phase1_audit/test_checks.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/phase1_audit/checks.py tests/phase1_audit/test_checks.py
git commit -m "feat(015): audit checks — total count + extension count"
```

---

## Task 16: Audit checks — albums (TDD)

**Files:**
- Modify: `scripts/phase1_audit/checks.py` (add functions)
- Modify: `tests/phase1_audit/test_checks.py` (add tests)

- [ ] **Step 1: Add failing tests for album checks**

Append to `tests/phase1_audit/test_checks.py`:

```python
from scripts.phase1_audit.checks import (
    check_album_count,
    check_album_names,
    check_year_folders_not_albums,
)


def test_album_count_exact_match() -> None:
    m = _manifest(user_album_count=3, user_albums=("A", "B", "C"))
    client = MagicMock()
    client.list_albums.return_value = [
        {"albumName": "A"}, {"albumName": "B"}, {"albumName": "C"}
    ]
    r = check_album_count(client, m)
    assert r.passed is True
    assert r.actual == 3


def test_album_count_mismatch_fails() -> None:
    m = _manifest(user_album_count=3, user_albums=("A", "B", "C"))
    client = MagicMock()
    client.list_albums.return_value = [{"albumName": "A"}]  # only 1
    r = check_album_count(client, m)
    assert r.passed is False


def test_album_names_all_present() -> None:
    m = _manifest(user_album_count=2, user_albums=("Trip A", "Trip B"))
    client = MagicMock()
    client.list_albums.return_value = [
        {"albumName": "Trip A"}, {"albumName": "Trip B"}, {"albumName": "Extra"}
    ]
    r = check_album_names(client, m)
    assert r.passed is True


def test_album_names_missing_one_fails() -> None:
    m = _manifest(user_album_count=2, user_albums=("Trip A", "Trip B"))
    client = MagicMock()
    client.list_albums.return_value = [{"albumName": "Trip A"}]  # missing Trip B
    r = check_album_names(client, m)
    assert r.passed is False
    assert "Trip B" in r.message


def test_year_folders_not_albums_passes_when_clean() -> None:
    m = _manifest()
    client = MagicMock()
    client.list_albums.return_value = [
        {"albumName": "Trip A"}, {"albumName": "Beach"}
    ]
    r = check_year_folders_not_albums(client, m)
    assert r.passed is True


def test_year_folders_not_albums_fails_when_present() -> None:
    m = _manifest()
    client = MagicMock()
    client.list_albums.return_value = [
        {"albumName": "Trip A"}, {"albumName": "Photos from 2019"}  # leaked
    ]
    r = check_year_folders_not_albums(client, m)
    assert r.passed is False
    assert "Photos from 2019" in r.message
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest tests/phase1_audit/test_checks.py -v -k "album or year_folders"`

Expected: 6 failures with `ImportError: cannot import name 'check_album_count'` or similar.

- [ ] **Step 3: Implement album checks**

Append to `scripts/phase1_audit/checks.py`:

```python
def check_album_count(client: ImmichClient, manifest: Manifest) -> CheckResult:
    """Immich's album count must equal the manifest's user_album_count exactly."""
    albums = client.list_albums()
    actual = len(albums)
    expected = manifest.user_album_count
    return CheckResult(
        name="album_count",
        passed=(actual == expected),
        expected=expected,
        actual=actual,
        message=f"Immich albums={actual} manifest expects={expected}",
    )


def check_album_names(client: ImmichClient, manifest: Manifest) -> CheckResult:
    """Every album in the manifest must exist in Immich (extras allowed)."""
    immich_names = {a.get("albumName", "") for a in client.list_albums()}
    missing = [name for name in manifest.user_albums if name not in immich_names]
    return CheckResult(
        name="album_names",
        passed=(len(missing) == 0),
        expected=list(manifest.user_albums),
        actual=sorted(immich_names),
        message=("all manifest albums present" if not missing
                 else f"missing albums: {missing[:5]}"),
    )


def check_year_folders_not_albums(client: ImmichClient, manifest: Manifest) -> CheckResult:
    """No 'Photos from YYYY' folder name should appear as an Immich album."""
    immich_names = [a.get("albumName", "") for a in client.list_albums()]
    leaked = [n for n in immich_names if n.startswith("Photos from ") and n[12:].isdigit()]
    return CheckResult(
        name="year_folders_not_albums",
        passed=(len(leaked) == 0),
        expected=[],
        actual=leaked,
        message=("no year folders leaked as albums" if not leaked
                 else f"year folders found as albums: {leaked}"),
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest tests/phase1_audit/test_checks.py -v`

Expected: 10 passed total (4 from Task 15 + 6 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/phase1_audit/checks.py tests/phase1_audit/test_checks.py
git commit -m "feat(015): audit checks — album count, names, no-year-folders"
```

---

## Task 17: Audit check — DNG sibling (TDD)

This is the centerpiece of Phase 1.5: the deferred Option-B decision.

**Files:**
- Modify: `scripts/phase1_audit/checks.py` (add function)
- Modify: `tests/phase1_audit/test_checks.py` (add tests)

- [ ] **Step 1: Add failing tests**

Append to `tests/phase1_audit/test_checks.py`:

```python
from scripts.phase1_audit.checks import check_dng_siblings


def test_dng_siblings_buckets_correctly() -> None:
    m = _manifest(extension_counts={"json": 0, "dng": 3, "heic": 1, "jpg": 1})
    client = MagicMock()
    # Three DNGs in Immich
    client.search_metadata.side_effect = [
        # first call: list of DNGs
        [
            {"originalFileName": "IMG_001.DNG"},
            {"originalFileName": "IMG_002.DNG"},
            {"originalFileName": "IMG_003.DNG"},
        ],
        # second call: search for IMG_001 (matches HEIC sibling in this fixture)
        [{"originalFileName": "IMG_001.HEIC"}],
        # third call: search for IMG_002 (matches JPG sibling)
        [{"originalFileName": "IMG_002.jpg"}],
        # fourth call: search for IMG_003 (no sibling — only the DNG itself)
        [{"originalFileName": "IMG_003.DNG"}],
    ]
    r = check_dng_siblings(client, m)
    assert r.passed is True  # the check passes if buckets are populated; the user decides what to do
    assert r.actual["with_sibling"] == 2
    assert r.actual["without_sibling"] == 1
    assert r.actual["dng_total"] == 3


def test_dng_siblings_passes_when_zero_dng() -> None:
    m = _manifest(extension_counts={"json": 0, "heic": 5})  # no DNG
    client = MagicMock()
    client.search_metadata.return_value = []
    r = check_dng_siblings(client, m)
    assert r.passed is True
    assert r.actual["dng_total"] == 0
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest tests/phase1_audit/test_checks.py -v -k "dng"`

Expected: 2 failures with `ImportError`.

- [ ] **Step 3: Implement the DNG sibling check**

Append to `scripts/phase1_audit/checks.py`:

```python
import os


def check_dng_siblings(client: ImmichClient, manifest: Manifest) -> CheckResult:
    """For each DNG in Immich, check if a HEIC/JPG sibling (same basename) exists.

    This check always 'passes' — its purpose is to populate buckets so the user can
    decide what to do with DNG-with-sibling vs DNG-only assets.
    """
    dngs = client.search_metadata({"originalFileName": ".dng"})
    dng_total = len(dngs)
    if dng_total == 0:
        return CheckResult(
            name="dng_siblings",
            passed=True,
            expected={"dng_total": manifest.count_for_extension("dng")},
            actual={"dng_total": 0, "with_sibling": 0, "without_sibling": 0,
                    "with_sibling_files": [], "without_sibling_files": []},
            message="no DNG assets in Immich; nothing to bucket",
        )

    sibling_exts = ("heic", "jpg", "jpeg", "png")
    with_sibling: list[str] = []
    without_sibling: list[str] = []
    for dng in dngs:
        full = dng.get("originalFileName", "")
        base = os.path.splitext(full)[0]
        found = False
        for ext in sibling_exts:
            results = client.search_metadata({"originalFileName": f"{base}.{ext}"})
            # Filter exact basename matches that are NOT the DNG itself
            for r in results:
                rname = r.get("originalFileName", "")
                if rname.lower() != full.lower() and rname.lower().startswith(base.lower() + "."):
                    found = True
                    break
            if found:
                break
        (with_sibling if found else without_sibling).append(full)

    return CheckResult(
        name="dng_siblings",
        passed=True,
        expected={"dng_total": manifest.count_for_extension("dng")},
        actual={
            "dng_total": dng_total,
            "with_sibling": len(with_sibling),
            "without_sibling": len(without_sibling),
            "with_sibling_files": with_sibling[:50],
            "without_sibling_files": without_sibling[:50],
        },
        message=f"DNG buckets — with_sibling={len(with_sibling)} without_sibling={len(without_sibling)}",
    )
```

Note: with 1,171 DNGs in the real archive and up to 4 sibling-extension queries each, that's up to 4,684 API calls. Each is fast (~50 ms) so total ~4 minutes. Acceptable for an audit run.

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest tests/phase1_audit/test_checks.py -v`

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/phase1_audit/checks.py tests/phase1_audit/test_checks.py
git commit -m "feat(015): DNG sibling audit check"
```

---

## Task 18: Audit CLI (`__main__.py`)

**Files:**
- Create: `scripts/phase1_audit/__main__.py`

- [ ] **Step 1: Write the CLI**

Create `scripts/phase1_audit/__main__.py`:

```python
"""CLI entry for the Phase 1.5 audit. Runs every check, emits JSON report.

Usage:
    python3 -m scripts.phase1_audit \
        --manifest docs/architecture/google-takeout-manifest.json \
        --server http://localhost:2283 \
        --api-key-file /Users/szelenin/immich-data/api-key.txt \
        --report /Users/szelenin/immich-data/phase-1-audit-report.json
"""
from __future__ import annotations
import argparse
import dataclasses
import json
import sys
from pathlib import Path

from .checks import (
    check_album_count,
    check_album_names,
    check_dng_siblings,
    check_extension_count,
    check_total_count,
    check_year_folders_not_albums,
)
from .immich_client import ImmichClient
from .manifest import load_manifest


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--server", default="http://localhost:2283")
    p.add_argument("--api-key-file", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    api_key = args.api_key_file.read_text().strip()
    client = ImmichClient(server=args.server, api_key=api_key)
    manifest = load_manifest(args.manifest)

    results = []
    results.append(check_total_count(client, manifest))
    for ext in ("heic", "jpg", "jpeg", "png", "mp4", "mov", "dng", "nef"):
        if manifest.count_for_extension(ext) > 0:
            results.append(check_extension_count(client, manifest, ext))
    results.append(check_album_count(client, manifest))
    results.append(check_album_names(client, manifest))
    results.append(check_year_folders_not_albums(client, manifest))
    results.append(check_dng_siblings(client, manifest))

    report = {
        "manifest_path": str(args.manifest),
        "server": args.server,
        "checks": [dataclasses.asdict(r) for r in results],
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
        },
    }
    args.report.write_text(json.dumps(report, indent=2, default=str))

    # Console summary
    for r in results:
        flag = "PASS" if r.passed else "FAIL"
        print(f"  [{flag}] {r.name}: {r.message}")
    print(f"\nSummary: {report['summary']['passed']}/{report['summary']['total']} passed")
    print(f"Full report: {args.report}")

    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the CLI shows help correctly**

Run: `python3 -m scripts.phase1_audit --help`

Expected: prints the usage block with `--manifest`, `--server`, `--api-key-file`, `--report` options.

- [ ] **Step 3: Run all audit tests one final time**

Run: `python3 -m pytest tests/phase1_audit/ -v`

Expected: all 12 tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/phase1_audit/__main__.py
git commit -m "feat(015): Phase 1.5 audit CLI"
```

---

## Task 19: Run the actual audit (operational)

**Prerequisite:** Phase 1 import (Task 11) has completed and Immich background jobs (Task 12) have caught up. The audit reads Immich state, so background processing should be largely done — wait until `metadataExtraction` queue is at zero before running.

- [ ] **Step 1: Verify Immich background jobs are mostly drained**

Run:

```bash
KEY=$(cat /Users/szelenin/immich-data/api-key.txt)
curl -sH "x-api-key: $KEY" http://localhost:2283/api/jobs | \
  jq '{meta: .metadataExtraction.jobCounts.waiting,
       thumb: .thumbnailGeneration.jobCounts.waiting}'
```

Expected: `meta` = 0 (or very small). `thumb` may still be running but doesn't affect audit.

- [ ] **Step 2: Run the audit**

Run:

```bash
python3 -m scripts.phase1_audit \
  --manifest docs/architecture/google-takeout-manifest.json \
  --server http://localhost:2283 \
  --api-key-file /Users/szelenin/immich-data/api-key.txt \
  --report /Users/szelenin/immich-data/phase-1-audit-report.json
```

Expected: prints PASS/FAIL per check; final summary line shows passed/total.

If any check fails: read its message, decide whether to (a) accept (gross-mismatch was expected for some reason) or (b) investigate.

- [ ] **Step 3: Commit the audit report**

```bash
mkdir -p docs/architecture/phase-1-run/
cp /Users/szelenin/immich-data/phase-1-audit-report.json docs/architecture/phase-1-run/
git add docs/architecture/phase-1-run/phase-1-audit-report.json
git commit -m "feat(015): commit Phase 1.5 audit report"
```

- [ ] **Step 4: Document DNG bucket sizes for the deferred decision**

Read the `dng_siblings` check result in the audit report:

```bash
jq '.checks[] | select(.name == "dng_siblings") | .actual' \
  docs/architecture/phase-1-run/phase-1-audit-report.json
```

Note the `with_sibling` and `without_sibling` counts. These numbers feed into the deferred Open Item #5 in the design doc (DNG bucket policy). Decision happens in a follow-up PR, not in this plan.

---

# Acceptance criteria

1. ✅ `setup/immich/docker-compose.yml` has the split bind-mount layout (Task 1).
2. ✅ Old RAID Immich tree gone; `/Volumes/HomeRAID/immich-library/` exists (Task 5).
3. ✅ `pre-flight.sh` reports ALL CHECKS PASSED before import (Task 11.1).
4. ✅ Immich `photos + videos ≈ 242,656 ± 1%` after import (audit total_count check passes).
5. ✅ All 138 user album names appear in Immich; no "Photos from YYYY" leaks (audit album checks pass).
6. ✅ Audit report committed at `docs/architecture/phase-1-run/phase-1-audit-report.json`.
7. ✅ All 12 audit unit tests pass (`pytest tests/phase1_audit/ -v`).
8. ✅ DNG bucket counts captured for follow-up decision.

---

# Self-review notes

**Spec coverage:**
- Phase 0 step 0.1 (containers stopped) → Task 5.1
- Phase 0 step 0.2 (snapshot) → Tasks 2 + 5.2
- Phase 0 step 0.3 (compose update) → Task 1
- Phase 0 step 0.4 (mkdirs) → Tasks 4 + 5.4
- Phase 0 step 0.5 (wipe) → Tasks 3 + 5.3
- Phase 0 step 0.6 (manifest) → already done before plan (committed in `87ca38d`)
- Phase 0 step 0.7 (OrbStack CPU) → Task 5.5
- Phase 0 step 0.8 (compose up) → Task 5.6
- Phase 0 step 0.9 (UI setup, transcode disabled) → Task 5.7
- Phase 1 step 1.1 (immich-go install) → Task 7
- Phase 1 step 1.2 (pre-flight) → Tasks 6 + 11.1
- Phase 1 step 1.3 (run import) → Tasks 9 + 11.3
- Phase 1 step 1.4 (monitor) → Tasks 10 + 11.4
- Phase 1.5 audit checks → Tasks 13–18; integration run → Task 19

**Placeholder scan:** none. Every task has explicit code, paths, and verification commands.

**Type consistency:** `Manifest`, `CheckResult`, `ImmichClient` defined in Task 13/14/15 with consistent attribute names. Re-used in 16, 17, 18 with the same signatures.

**Detached iCloud library:** Task 8 covers the architecture doc's "Phase 1.0 detach iCloud" via the Immich admin UI. The read-only filesystem mount stays in docker-compose.yml so future Phase 3 work can re-attach if needed.
