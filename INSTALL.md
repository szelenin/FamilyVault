# FamilyVault — Installation Guide

> **For AI agents**: This guide is your executable script. Follow phases in order.
> Each step is labeled `[AGENT]` (you run it) or `[USER]` (tell the user and wait).
> Every step includes a verification command — confirm it passes before proceeding.
> All steps are idempotent: safe to re-run if interrupted.

## How to Use This Guide

1. Check prerequisites first — skip phases whose exit conditions are already met
2. For `[AGENT]` steps: run the command via SSH, check the verify output
3. For `[USER]` steps: give the user the exact instruction quoted, wait for their confirmation
4. If a verify fails: follow the "On failure" guidance before retrying
5. After all phases complete: run the Phase 5 final verification

**Assumed access**: SSH to `macmini.local` as `szelenin`, sudo available interactively.

---

## Prerequisites

Before starting, verify these. If any fail, ask the user to resolve before proceeding.

| Check | Command | Expected |
|-------|---------|----------|
| Mac Mini reachable | `ssh macmini.local "echo ok"` | `ok` |
| RAID mounted | `ssh macmini.local "ls /Volumes/HomeRAID"` | directory listing |
| iCloud signed in | `ssh macmini.local "defaults read MobileMeAccounts 2>/dev/null \| grep -c AccountID"` | `1` or more |
| 2TB+ free on RAID | `ssh macmini.local "df -h /Volumes/HomeRAID \| awk 'NR==2{print \$4}'"` | > 2Ti |

---

## Phase 0: Hardware & Folder Structure

**Skip if**: `/Volumes/HomeRAID/icloud-export` already exists.

**Exit condition**: All required folders exist on RAID.

### Step 0.1 — Create folder structure

**[AGENT]**
```bash
ssh macmini.local "mkdir -p /Volumes/HomeRAID/{icloud-export,google-takeout,google-processed,google-delta,immich}"
```
**Verify**:
```bash
ssh macmini.local "ls /Volumes/HomeRAID"
```
**Expected**: `google-delta  google-processed  google-takeout  icloud-export  immich`

### Step 0.2 — Set up iCloud Shared Photo Library (if family sharing)

**[USER]** Ask: *"Do you want to merge your spouse/partner's iCloud library with yours? This lets osxphotos export both libraries in one pass."*

If yes → *"On your iPhone: Settings → [Your Name] → iCloud → Photos → Shared Library → Invite Participant. Have your partner accept. Choose 'Move All My Photos & Videos' when prompted. Tell me when your partner has accepted."*

Wait for confirmation before proceeding.

---

## Phase 1: iCloud Export

**Skip if**: Exit condition already met.

**Exit condition**: `ssh macmini.local "/opt/homebrew/bin/osxphotos info 2>&1 | grep 'Missing.*total: 0'"` returns a match.

### Step 1.1 — Install export tools

**[AGENT]**
```bash
ssh macmini.local "HOMEBREW_NO_AUTO_UPDATE=1 /opt/homebrew/bin/brew install exiftool rclone 2>&1 | tail -3"
ssh macmini.local "pip3 install osxphotos 2>&1 | tail -3"
```
**Verify**:
```bash
ssh macmini.local "/opt/homebrew/bin/osxphotos version 2>/dev/null || python3 -m osxphotos version"
```
**Expected**: version string like `osxphotos, version 0.x.x`

### Step 1.2 — Move Photos Library to RAID (if not already there)

**[AGENT]** Check current location:
```bash
ssh macmini.local "defaults read com.apple.Photos libraryPath 2>/dev/null || echo 'default'"
```

If output contains `/Volumes/HomeRAID` → skip this step.

If not → **[USER]**: *"We need to move your Photos Library to the RAID to avoid filling the internal drive. Please: 1) Quit Photos.app, 2) In Finder, drag your Photos Library from Pictures/ to /Volumes/HomeRAID/, 3) Hold Option and open Photos.app, select the RAID library, 4) Tell me when Photos.app opens and shows your photos."*

### Step 1.3 — Enable Download Originals

**[USER]**: *"In Photos.app: Settings → iCloud → select 'Download Originals to this Mac'. Tell me when it's set."*

**[AGENT]** Monitor download progress:
```bash
ssh macmini.local "/opt/homebrew/bin/osxphotos info 2>&1 | grep 'Missing'"
```
**Expected when complete**: `total: 0, photos: 0, videos: 0`

Tell the user: *"iCloud is downloading your originals. This can take 1-3 days for a large library. We can continue setting up other components while it downloads. I'll check progress periodically."*

### Step 1.4 — Run osxphotos full export (via export-icloud.sh)

**Run only when Step 1.3 exit condition is met** (Missing total = 0).

The wrapper script `scripts/export-icloud.sh` runs osxphotos with the full IMP-011 flag
set (`--update-errors`, `--fix-orientation`, `--export-edited`, `--exiftool-option '-m'`,
report CSV). Re-running the same command is always safe — `--update` resumes incrementally.

**[AGENT]**
```bash
ssh macmini.local "cd ~/projects/takeout/takeout && tmux new -d -s icloud-export \
  './scripts/export-icloud.sh /Volumes/HomeRAID/icloud-export \
   \"/Volumes/HomeRAID/Photos Library.photoslibrary\"'"
```

**[USER]**: *"osxphotos is exporting your library to the RAID. This can take 3–5 hours on the first run. I'll notify you when it's done."*

**[AGENT]** Poll until complete:
```bash
ssh macmini.local "tail -5 \$(ls -t /Volumes/HomeRAID/icloud-export/osxphotos-export-*.log | head -1)"
```
**Expected when done**: log contains `Done: exporting`

**Verify**:
```bash
ssh macmini.local "find /Volumes/HomeRAID/icloud-export -name '*.jpg' -o -name '*.heic' -o -name '*.mp4' -o -name '*.HEIC' -o -name '*.JPG' -o -name '*.MP4' -o -name '*.MOV' | wc -l"
```
**Expected**: number matching Photos.app count (within 5%).

### Step 1.5 — Inject wife's metadata + infer GPS for stragglers (DEFENSIVE — usually no-op)

> **Note**: Spec 013 research (see `specs/013-wife-metadata-import/research.md`)
> proved that iCloud Shared Photo Library propagates ALL metadata between
> participants automatically, and `osxphotos --update --exiftool` from the daily
> launchd sync re-writes metadata-only changes into export files. This step is
> kept as a **defensive cold-start tool** for fresh re-exports or transient sync
> race conditions; in steady state it should report 0 files to update.

After the export completes, optionally run two scripts to catch any sync race
conditions. Most photos lack GPS because Location Services was off for the iPhone
Camera (not because iCloud stripped it), so coverage gains are typically negligible
(~24 files on the Apr 23 IMP-011 run, 0 expected in steady state).

**Skip if**: `ssh macmini.local "ls /Volumes/HomeRAID/alice/Photos\\ Library.photoslibrary/database/Photos.sqlite 2>/dev/null"` returns empty (wife's library not staged) — see plan.md Phase 2 Step 1.

**[AGENT]** Wife's metadata (date-bridge match):
```bash
ssh macmini.local "cd ~/projects/takeout/takeout && python3 scripts/apply-wife-metadata.py \
  '/Volumes/HomeRAID/alice/Photos Library.photoslibrary/database/Photos.sqlite' \
  /Volumes/HomeRAID/icloud-export \
  --shared-db '/Volumes/HomeRAID/Photos Library.photoslibrary/database/Photos.sqlite' \
  --dry-run"
```
**Expected**: `Matched: N | Ambiguous (skipped): … | … files to update`. If N looks reasonable, re-run without `--dry-run`.

**[AGENT]** GPS inference for `(N)` shared-copy duplicates:
```bash
ssh macmini.local "cd ~/projects/takeout/takeout && python3 scripts/infer-gps.py /Volumes/HomeRAID/icloud-export --dry-run"
```
**Expected**: list of files that would receive inferred GPS. If reasonable, re-run without `--dry-run`.

---

## Phase 2: Google Takeout

**Skip if**: `ls /Volumes/HomeRAID/google-takeout/*.zip 2>/dev/null | wc -l` > 0 AND rclone is complete (see verify below).

**Exit condition**: All Takeout zip files downloaded and verified.

### Step 2.1 — Request Google Takeout

**[USER]**: *"Go to takeout.google.com → deselect all → select only 'Google Photos' → click Next → choose 'Add to Google Drive', zip size 50GB → click 'Create export'. This takes 2-5 days to prepare. Tell me the file names that appear in your Google Drive when it's ready (they start with 'takeout-')."*

Wait for user to confirm Takeout files are available in Google Drive.

### Step 2.2 — Configure rclone Google Drive remote

**[AGENT]** Check if already configured:
```bash
ssh macmini.local "/opt/homebrew/bin/rclone listremotes | grep gdrive"
```

If `gdrive:` appears → skip to Step 2.3.

**[USER]**: *"We need to authorize rclone to access your Google Drive. Please run this command in a terminal on the Mac Mini and follow the browser prompts: `/opt/homebrew/bin/rclone config` — choose New remote, name it 'gdrive', type 'drive', leave client_id blank, follow browser auth. Tell me when done."*

### Step 2.3 — Download Takeout archives

**[AGENT]**
```bash
ssh macmini.local "nohup /opt/homebrew/bin/rclone copy gdrive:Takeout /Volumes/HomeRAID/google-takeout/ \
  --transfers 4 --checkers 8 --drive-chunk-size 128M \
  --retries 10 --low-level-retries 20 \
  --bwlimit 50M \
  --log-file /Volumes/HomeRAID/google-takeout/rclone.log \
  --log-level INFO > /dev/null 2>&1 &
echo \$!"
```

**[USER]**: *"Google Takeout is downloading in the background at 50MB/s (bandwidth-limited to leave room for iCloud). This will take many hours for a large library."*

**Verify when done**:
```bash
ssh macmini.local "tail -3 /Volumes/HomeRAID/google-takeout/rclone.log"
ssh macmini.local "ls /Volumes/HomeRAID/google-takeout/*.zip | wc -l"
```
**Expected**: log shows no errors; zip count matches number of Takeout archives.

---

## Phase 3: Ongoing Sync

**Skip if**: `ssh macmini.local "launchctl list | grep com.familyvault.sync"` returns a match.

**Exit condition**: launchd agent loaded; daily sync runs at 2 AM.

> macOS Sequoia blocks `crontab` modifications without Full Disk Access. Use a launchd agent instead.

### Step 3.1 — Stage sync.sh on the RAID

**[AGENT]**
```bash
ssh macmini.local "mkdir -p /Volumes/HomeRAID/scripts && \
  cp ~/projects/takeout/takeout/scripts/sync.sh /Volumes/HomeRAID/scripts/sync.sh && \
  chmod +x /Volumes/HomeRAID/scripts/sync.sh"
```
**Verify**:
```bash
ssh macmini.local "ls -la /Volumes/HomeRAID/scripts/sync.sh"
```
**Expected**: file exists, executable.

### Step 3.2 — Install launchd plist for daily sync

**[AGENT]**
```bash
ssh macmini.local 'cat > ~/Library/LaunchAgents/com.familyvault.sync.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>           <string>com.familyvault.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Volumes/HomeRAID/scripts/sync.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>2</integer><key>Minute</key><integer>0</integer></dict>
    <key>StandardOutPath</key> <string>/Volumes/HomeRAID/sync.log</string>
    <key>StandardErrorPath</key><string>/Volumes/HomeRAID/sync.log</string>
    <key>RunAtLoad</key>       <false/>
</dict>
</plist>
PLIST
launchctl unload ~/Library/LaunchAgents/com.familyvault.sync.plist 2>/dev/null || true
launchctl load   ~/Library/LaunchAgents/com.familyvault.sync.plist'
```

**Verify**:
```bash
ssh macmini.local "launchctl list | grep com.familyvault.sync"
```
**Expected**: line like `-  0  com.familyvault.sync` (loaded; no error code).

**On failure**: `tail /Volumes/HomeRAID/sync.log` for last run output.

---

## Phase 4: Immich

**Skip if**: `curl -sf http://macmini.local:2283/api/server/ping` returns `{"res":"pong"}`.

**Exit condition**: Immich web UI accessible at `http://macmini.local:2283`, external library registered, API key at `/Volumes/HomeRAID/immich/api-key.txt`.

### Step 4.1 — Install OrbStack (Docker runtime)

**[AGENT]** Check if installed:
```bash
ssh macmini.local "/usr/local/bin/docker --version 2>/dev/null && echo installed || echo missing"
```

If `installed` → skip to Step 4.2.

**[AGENT]** Download and install OrbStack:
```bash
ssh macmini.local "curl -fsSL --max-time 300 'https://orbstack.dev/download/stable/latest/arm64' -o /tmp/OrbStack.dmg"
ssh macmini.local "hdiutil attach /tmp/OrbStack.dmg -nobrowse -quiet 2>/dev/null; ls /Volumes/ | grep -i orb"
```

Note the volume name from output, then:
```bash
ssh macmini.local "cp -R '/Volumes/Install OrbStack v2.0.5/OrbStack.app' /Applications/ && hdiutil detach '/Volumes/Install OrbStack v2.0.5' -quiet"
ssh macmini.local "open /Applications/OrbStack.app"
```

**[USER]**: *"OrbStack is opening on your screen. Please: 1) Select 'Docker' when asked what to use, 2) Click through the setup, 3) Approve any system extension prompts in System Settings. Tell me when you see the OrbStack window showing 'No Containers'."*

**Verify**:
```bash
ssh macmini.local "/usr/local/bin/docker --version && /usr/local/bin/docker compose version"
```
**Expected**: Docker version 28.x, Compose version v2.x

### Step 4.2 — Create .env with credentials

**[AGENT]**
```bash
ssh macmini.local "
if [ ! -f /Users/szelenin/projects/takeout/takeout/setup/immich/.env ]; then
  DB_PASS=\$(openssl rand -base64 16 | tr -d '/+=')
  JWT=\$(openssl rand -base64 32 | tr -d '/+=')
  cat > /Users/szelenin/projects/takeout/takeout/setup/immich/.env << EOF
UPLOAD_LOCATION=/usr/src/app/upload
DB_USERNAME=immich
DB_PASSWORD=\$DB_PASS
DB_DATABASE_NAME=immich
JWT_SECRET=\$JWT
EOF
  echo created
else
  echo exists
fi"
```
**Expected**: `created` or `exists`

### Step 4.3 — Start Immich stack

**[AGENT]**
```bash
ssh macmini.local "cd /Users/szelenin/projects/takeout/takeout/setup/immich && /usr/local/bin/docker compose up -d 2>&1 | tail -5"
```

Wait for containers to be healthy:
```bash
ssh macmini.local "for i in \$(seq 1 24); do /usr/local/bin/docker ps --format '{{.Names}} {{.Status}}' | grep -c healthy && break || sleep 5; done"
```
**Expected**: `4` (four healthy containers)

### Step 4.4 — Start TCP proxy (LAN access)

OrbStack only binds ports to localhost, not the LAN. The TCP proxy forwards `0.0.0.0:2283` to the Immich container. It resolves the container's current OrbStack IP automatically via DNS (`immich-immich-server-1.orb.local`) — no hardcoded IPs.

**[AGENT]**
```bash
ssh macmini.local "
kill \$(pgrep -f 'python3.*tcp-proxy') 2>/dev/null || true
sleep 1
/usr/bin/python3 /Users/szelenin/projects/takeout/takeout/setup/immich/scripts/tcp-proxy.py > /tmp/immich-proxy.log 2>&1 &
disown
sleep 3
cat /tmp/immich-proxy.log"
```
**Expected**: `Immich proxy: 0.0.0.0:2283 -> 192.168.138.x:80 (resolved from immich-immich-server-1.orb.local)`

**Verify**:
```bash
ssh macmini.local "curl -sf http://127.0.0.1:2283/api/server/ping"
```
**Expected**: `{"res":"pong"}`

**On failure**: Check that the Immich server container is healthy: `ssh macmini.local "/usr/local/bin/docker ps | grep immich-server"`

### Step 4.5 — Provision admin account and API key

**[AGENT]**
```bash
ssh macmini.local "
IMMICH_URL=http://immich-immich-server-1.orb.local
API_KEY_FILE=/Volumes/HomeRAID/immich/api-key.txt
if [ -f \"\$API_KEY_FILE\" ]; then echo exists; exit 0; fi
curl -sf -X POST \"\$IMMICH_URL/api/auth/admin-sign-up\" \
  -H 'Content-Type: application/json' \
  -d '{\"name\":\"Admin\",\"email\":\"admin@familyvault.local\",\"password\":\"FamilyVault2026!\"}' > /dev/null
TOKEN=\$(curl -sf -X POST \"\$IMMICH_URL/api/auth/login\" \
  -H 'Content-Type: application/json' \
  -d '{\"email\":\"admin@familyvault.local\",\"password\":\"FamilyVault2026!\"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"accessToken\"])')
SECRET=\$(curl -sf -X POST \"\$IMMICH_URL/api/api-keys\" \
  -H \"Authorization: Bearer \$TOKEN\" \
  -H 'Content-Type: application/json' \
  -d '{\"name\":\"familyvault-setup\",\"permissions\":[\"all\"]}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"secret\"])')
mkdir -p /Volumes/HomeRAID/immich
echo -n \"\$SECRET\" > \"\$API_KEY_FILE\" && chmod 600 \"\$API_KEY_FILE\"
echo saved"
```
**Expected**: `exists` or `saved`

### Step 4.6 — Register icloud-export as external library (with DNG exclusion)

The export contains both ProRAW DNG and the processed HEIC/JPEG sibling. Indexing both
duplicates every ProRAW shot and surfaces the dark/raw DNG as the gallery preview. The
exclusion patterns must be set **before** the first scan so DNG never gets indexed.

**[AGENT]**
```bash
ssh macmini.local "
IMMICH_URL=http://immich-immich-server-1.orb.local
API_KEY=\$(cat /Volumes/HomeRAID/immich/api-key.txt)
EXISTING=\$(curl -sf -H \"x-api-key: \$API_KEY\" \"\$IMMICH_URL/api/libraries\" \
  | python3 -c 'import sys,json; libs=json.load(sys.stdin); print(next((l[\"id\"] for l in libs if any(\"icloud-export\" in p for p in l.get(\"importPaths\",[]))),\"\"))')
if [ -n \"\$EXISTING\" ]; then echo exists; exit 0; fi
OWNER=\$(curl -sf -H \"x-api-key: \$API_KEY\" \"\$IMMICH_URL/api/users/me\" | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"id\"])')
LIB_ID=\$(curl -sf -X POST \"\$IMMICH_URL/api/libraries\" \
  -H \"x-api-key: \$API_KEY\" -H 'Content-Type: application/json' \
  -d \"{\\\"name\\\":\\\"iCloud Export\\\",\\\"ownerId\\\":\\\"\$OWNER\\\",\\\"importPaths\\\":[\\\"/usr/src/app/icloud-export\\\"],\\\"exclusionPatterns\\\":[\\\"**/*.DNG\\\",\\\"**/*.dng\\\",\\\"**/*.RAW\\\",\\\"**/*.raw\\\",\\\"**/*.CR2\\\",\\\"**/*.cr2\\\",\\\"**/*.ARW\\\",\\\"**/*.arw\\\"]}\" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"id\"])')
curl -sf -X POST \"\$IMMICH_URL/api/libraries/\$LIB_ID/scan\" -H \"x-api-key: \$API_KEY\" > /dev/null
echo \"registered: \$LIB_ID\""
```
**Expected**: `exists` or `registered: <uuid>`

### Step 4.7 — Install launchd boot agent

The launchd agent runs `boot-immich.sh` at login, which: (1) waits for RAID mount, (2) waits for OrbStack's Docker daemon (up to 120s), (3) runs `docker compose up -d`, (4) waits 10s, then (5) execs the TCP proxy in the foreground. The agent has `KeepAlive=true`, so launchd restarts it if it crashes.

**[AGENT]**
```bash
ssh macmini.local "
PLIST=~/Library/LaunchAgents/com.familyvault.immich.plist
cp /Users/szelenin/projects/takeout/takeout/setup/immich/launchd/com.familyvault.immich.plist \"\$PLIST\"
launchctl unload \"\$PLIST\" 2>/dev/null || true
launchctl load \"\$PLIST\"
sleep 30
launchctl list | grep familyvault"
```
**Expected**: line like `9081  -  com.familyvault.immich` (PID present, no error code)

**Verify** (after 30s):
```bash
ssh macmini.local "curl -sf http://127.0.0.1:2283/api/server/ping"
```
**Expected**: `{"res":"pong"}`

**On failure**: Check boot log: `ssh macmini.local "cat /tmp/familyvault-immich.log; cat /tmp/familyvault-immich-error.log"`

**[USER]** Ask: *"Please open http://macmini.local:2283 in your browser. You should see the Immich login screen. Log in with email `admin@familyvault.local` and password `FamilyVault2026!`. Tell me what you see."*

---

## Phase 4.5: Story Engine Setup

Install the AI Story Engine so Claude can create video clips from your Immich library.

### Step 4.5.1: Install FFmpeg

**[AGENT]** Install FFmpeg on Mac Mini:
```bash
ssh macmini "/opt/homebrew/bin/brew install ffmpeg"
```

**Verify**:
```bash
ssh macmini "/opt/homebrew/bin/ffmpeg -version 2>&1 | head -1"
```
Expected: `ffmpeg version 8.x ...`

### Step 4.5.2: Install Python requests

**[AGENT]** Install requests library:
```bash
ssh macmini "pip3 install requests"
```

**Verify**:
```bash
ssh macmini "python3 -c 'import requests; print(requests.__version__)'"
```
Expected: version number printed.

### Step 4.5.3: Create stories directory

**[AGENT]** Create the stories output directory:
```bash
ssh macmini "mkdir -p /Volumes/HomeRAID/stories"
```

**Verify**:
```bash
ssh macmini "ls /Volumes/HomeRAID/stories && echo ok"
```
Expected: `ok`

### Step 4.5.4: Sync scripts to Mac Mini

**[AGENT]** Copy story engine scripts:
```bash
rsync -av setup/story-engine/scripts/ macmini:~/projects/takeout/takeout/setup/story-engine/scripts/
```

**Verify**:
```bash
ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/manage_scenario.py list"
```
Expected: `No scenarios found.`

### Step 4.5.5: Verify SKILL.md is in place

The Claude Code skill file at `.claude/skills/story-engine/SKILL.md` tells Claude how to handle story requests. It is already in the repository. To use story engine, start a conversation with Claude Code and say:

> "Create a story about [event]"

Claude will search Immich, propose a scenario, and guide you through music selection and video generation. See `setup/story-engine/README.md` for full usage.

---

## Phase 5: Final Verification

Run after all phases complete.

**[AGENT]** Run all checks:
```bash
# iCloud download complete
ssh macmini.local "/opt/homebrew/bin/osxphotos info 2>&1 | grep 'Missing.*total: 0'"

# osxphotos export populated icloud-export
ssh macmini.local "find /Volumes/HomeRAID/icloud-export -name '*.jpg' -o -name '*.heic' | wc -l"

# Daily sync launchd agent loaded
ssh macmini.local "launchctl list | grep com.familyvault.sync"

# Orientation: no Rotate-180 files (IMP-011 T5)
ssh macmini.local "exiftool -fast2 -r -Orientation -if '\$Orientation eq \"Rotate 180\"' /Volumes/HomeRAID/icloud-export 2>/dev/null | grep -c 'File Name'"
# Expected: 0

# DNG excluded from Immich (spot-check via search): known DNG filename returns 0 results
# Use the Immich web UI search box or:
ssh macmini.local "cat /Volumes/HomeRAID/immich/api-key.txt | xargs -I{} curl -sf -H 'x-api-key: {}' \
  'http://immich-immich-server-1.orb.local/api/search/metadata?originalFileName=IMG_5909.DNG' \
  | python3 -c 'import sys,json; print(len(json.load(sys.stdin).get(\"assets\",{}).get(\"items\",[])))'"
# Expected: 0

# Immich API healthy
curl -sf http://macmini.local:2283/api/server/ping

# API key file exists with correct permissions
ssh macmini.local "ls -la /Volumes/HomeRAID/immich/api-key.txt"

# External library registered
ssh macmini.local "cat /Volumes/HomeRAID/immich/api-key.txt | xargs -I{} curl -sf -H 'x-api-key: {}' http://immich-immich-server-1.orb.local/api/libraries | python3 -c 'import sys,json; libs=json.load(sys.stdin); print(len(libs), \"libraries\")'"
```

**[USER]** Manual acceptance tests:
1. *"Open http://macmini.local:2283 and confirm the Immich timeline shows your photos"*
2. *"Restart your Mac Mini and confirm Immich is accessible within 2 minutes — no manual steps"*
3. *"Try searching 'birthday' or 'beach' in Immich and confirm relevant photos appear"*
