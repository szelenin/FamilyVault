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
5. After all phases complete: run the Phase 3 final verification

**Assumed access**: SSH to `macmini.local` as `szelenin`, sudo available interactively.

---

## Architecture overview (read this before starting)

FamilyVault is a **three-source merge** with Immich as the canonical content store:

- **Bytes** flow into Immich from Google Takeout (via `immich-go`) and going forward from the Immich mobile app. iCloud osxphotos export feeds the filesystem only — iCloud bytes are not imported into Immich's library by default (they may be selectively imported later for Live Photos and iCloud-only photos).
- **Metadata** is merged from Google JSON sidecars (during import) and iCloud `Photos.sqlite` (in a later phase, not part of this install). Per-field merge policy: GPS prefers Google, favorites/albums/captions are iCloud-only, tags are union.
- **Identity matching** across the three sources uses a strategy-D cascade (SHA-256 → filename + capture date + size + dimensions → pHash). Phase 2 of this install scaffolds it; the merge tool itself is built later.

The architecture document is at `docs/architecture/2026-04-26-three-source-merge.md`. The Phase 1 (Google import) design and plan are at `docs/architecture/2026-04-26-phase-1-google-import{.md, -plan.md}`. Read those if you need to dive deeper than this install guide.

---

## Prerequisites

Before starting, verify these. If any fail, ask the user to resolve before proceeding.

| Check | Command | Expected |
|-------|---------|----------|
| Mac Mini reachable | `ssh macmini.local "echo ok"` | `ok` |
| RAID mounted | `ssh macmini.local "ls /Volumes/HomeRAID"` | directory listing |
| iCloud signed in | `ssh macmini.local "defaults read MobileMeAccounts 2>/dev/null \| grep -c AccountID"` | `1` or more |
| Mac Mini total RAM | `ssh macmini.local "sysctl -n hw.memsize \| awk '{printf \"%.0f\\n\", \$1/1024/1024/1024}'"` | record the value (e.g., `24`) — used in Phase 1.1 |
| 3TB+ free on RAID | `ssh macmini.local "df -g /Volumes/HomeRAID \| awk 'NR==2{print \$4}'"` | `>= 3000` (need ~2.4 TB Google + headroom for iCloud + Immich library growth) |
| 200GB+ free on internal SSD | `ssh macmini.local "df -g /Users/szelenin \| awk 'NR==2{print \$4}'"` | `>= 200` (postgres + thumbs + model cache after import) |

---

## Phase 0: Hardware & Folder Structure

**Skip if**: All four required directories listed below already exist.

**Exit condition**: All folders exist on the correct device (RAID vs internal SSD).

### Step 0.1 — Create folder structure

The split-storage layout puts only the original photo/video bytes on the RAID; everything else (Immich's database, ML models, thumbnails, transcoded videos) lives on the Mac Mini's internal SSD for performance and resilience.

**On the RAID** (large, redundant, slower):

| Path | Contains | Size estimate |
|---|---|---|
| `/Volumes/HomeRAID/icloud-export/` | osxphotos export of iCloud library — filesystem only, NOT mounted into Immich | grows with iCloud library |
| `/Volumes/HomeRAID/google-takeout/` | Google Takeout zips — cold archive after import | ~2.4 TB for full Takeout |
| `/Volumes/HomeRAID/immich-library/` | Immich's managed photo/video bytes (originals only) — mounted into the container at `/usr/src/app/upload/upload` | grows with imports |

**On the Mac Mini internal SSD** (small, fast, no redundancy):

| Path | Container target | Contains |
|---|---|---|
| `/Users/szelenin/immich-data/upload/` | `/usr/src/app/upload` | Immich's parent upload dir; thumbs/, encoded-video/, profile/, backups/ — everything EXCEPT `/upload/upload` (which is overridden to RAID above) |
| `/Users/szelenin/immich-data/postgres/` | `/var/lib/postgresql/data` | Immich PostgreSQL DB |
| `/Users/szelenin/immich-data/model-cache/` | `/cache` | Immich ML model weights (~2 GB) |

**Why mount RAID at `/upload/upload` and not `/upload/library`?** Immich v2.6.3 with the storage template **disabled** (this install's config) writes uploaded asset bytes to `/usr/src/app/upload/upload/<userId>/<XX>/<YY>/<assetUUID>.<ext>`. The `library/` subdirectory is only used when the storage template is enabled. We mount RAID at `/upload/upload` so original bytes go to RAID directly, and the rest of `/upload` (thumbs, transcodes, etc.) stays on internal SSD. (See `docs/architecture/phase-1-run/execution-log.md` post-mortem for the full story — the original install put RAID at the wrong subpath, filled the internal SSD in 3.5 hours, and triggered a SIGKILL of the OrbStack VM.)

**[AGENT]**

```bash
ssh macmini.local "mkdir -p /Volumes/HomeRAID/{icloud-export,google-takeout,immich-library} && \
                   mkdir -p /Users/szelenin/immich-data/{upload,postgres,model-cache} && \
                   chmod 700 /Users/szelenin/immich-data/postgres"
```

**Verify**:

```bash
ssh macmini.local "ls -ld /Volumes/HomeRAID/{icloud-export,google-takeout,immich-library} \
                          /Users/szelenin/immich-data/{upload,postgres,model-cache}"
```

**Expected**: 6 directories listed; postgres has mode `drwx------` (700), others `drwxr-xr-x` (755).

A helper script that creates these directories (and refuses if RAID isn't mounted) lives at `scripts/phase0-mkdirs.sh` for re-runs.

### Step 0.2 — Set up iCloud Shared Photo Library (if family sharing)

**[USER]** Ask: *"Do you want to merge your spouse/partner's iCloud library with yours? This lets osxphotos export both libraries in one pass."*

If yes → *"On your iPhone: Settings → [Your Name] → iCloud → Photos → Shared Library → Invite Participant. Have your partner accept. Choose 'Move All My Photos & Videos' when prompted. Tell me when your partner has accepted."*

Wait for confirmation before proceeding.

---

## Phase 1: Immich Install

**Skip if**: `curl -sf http://macmini.local:2283/api/server/ping` returns `{"res":"pong"}` AND `/Users/szelenin/immich-data/api-key.txt` exists.

**Exit condition**: Immich UI accessible at `http://macmini.local:2283`, admin user exists, API key saved at `/Users/szelenin/immich-data/api-key.txt`, server statistics returns `photos: 0, videos: 0`, transcoding policy = `disabled`, mount layout shows RAID at `/upload/upload`.

### Step 1.1 — Calculate VM resource budget

OrbStack runs Immich inside a Linux VM with a memory ceiling. Setting the limit too high relative to total Mac Mini RAM can cause macOS to SIGKILL the VM under host pressure (this is what happened in the first run; see post-mortem).

**[AGENT]** Sample current usage:

```bash
ssh macmini.local "
TOTAL_GB=\$(sysctl -n hw.memsize | awk '{print int(\$1/1024/1024/1024)}')
echo \"total: \${TOTAL_GB} GB\"
echo \"reserve for macOS + Chrome/etc: ~6 GB\"
echo \"headroom buffer: ~3 GB\"
echo \"safe OrbStack ceiling: \$((TOTAL_GB - 9)) GB\""
```

**Inside the VM at peak load** (during heavy Phase 2 import):

| Component | Idle | Peak |
|---|---|---|
| `immich-server` (Node.js, processes uploads) | 500 MB | 1.5–2 GB |
| `immich-microservices` (background jobs, paused during import) | 500 MB | 500 MB |
| `immich-machine-learning` (idle = no models loaded) | 200 MB | 200 MB |
| `postgres` | 1 GB | 3–4 GB |
| `redis` | 100 MB | 100 MB |
| Linux kernel + page cache | 1 GB | 3 GB |
| **Total** | ~3 GB | ~9–10 GB |

So Immich peak is ~10 GB. Add ~2 GB headroom inside the VM → set OrbStack memory ceiling to **min(safe-host-ceiling, 14 GB)**. On a 24 GB Mac Mini that's 14 GB; on a 16 GB Mac Mini that's only 7 GB and you'd want to scale down concurrency in Phase 2.7.

### Step 1.2 — Install OrbStack

**[AGENT]** Check if installed:

```bash
ssh macmini.local "/usr/local/bin/docker --version 2>/dev/null && echo installed || echo missing"
```

If `installed` → skip to Step 1.3.

**[AGENT]** Download and install:

```bash
ssh macmini.local "curl -fsSL --max-time 300 'https://orbstack.dev/download/stable/latest/arm64' -o /tmp/OrbStack.dmg
hdiutil attach /tmp/OrbStack.dmg -nobrowse -quiet 2>/dev/null
ls /Volumes/ | grep -i orb"
```

Note the volume name (e.g., `Install OrbStack v2.0.5`), then:

```bash
ssh macmini.local "cp -R '/Volumes/Install OrbStack v2.0.5/OrbStack.app' /Applications/ && hdiutil detach '/Volumes/Install OrbStack v2.0.5' -quiet
open /Applications/OrbStack.app"
```

**[USER]**: *"OrbStack is opening on your screen. Please: 1) Select 'Docker' when asked what to use, 2) Click through the setup, 3) Approve any system extension prompts in System Settings, 4) **Open Settings → System → set Memory limit to the value calculated in Step 1.1** (e.g., 14 GiB on a 24 GB Mac Mini), CPU limit can stay at None. Click Apply and Restart. 5) Tell me when you see the OrbStack window showing 'No Containers'."*

**Verify**:

```bash
ssh macmini.local "/usr/local/bin/docker --version && /usr/local/bin/docker compose version && \
                   /usr/local/bin/docker run --rm alpine nproc"
```

**Expected**: Docker version, Compose version, CPU count.

### Step 1.3 — Generate .env with random credentials

**[AGENT]**

```bash
ssh macmini.local "
ENV_FILE=/Users/szelenin/projects/takeout/takeout/setup/immich/.env
if [ -f \"\$ENV_FILE\" ]; then echo exists; exit 0; fi
DB_PASS=\$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-32)
JWT=\$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)
cat > \"\$ENV_FILE\" << EOF
UPLOAD_LOCATION=/usr/src/app/upload
DB_USERNAME=immich
DB_PASSWORD=\$DB_PASS
DB_DATABASE_NAME=immich
JWT_SECRET=\$JWT
EOF
chmod 600 \"\$ENV_FILE\"
echo created"
```

**Expected**: `created` or `exists`.

**Note**: `.env` is in `.gitignore`. If you wipe and re-init postgres later, the credentials in `.env` become the new postgres init credentials — keep this file safe.

### Step 1.4 — Start Immich containers (split-storage layout)

The compose file at `setup/immich/docker-compose.yml` is configured for the split-storage layout described in Phase 0:

- `immich-server` and `immich-microservices`: parent upload mount → internal SSD; the `upload/` subdir override → RAID (this is where original asset bytes go with storage template disabled — see Phase 0 explanation)
- `immich-machine-learning`: model cache → internal SSD
- `postgres`: data dir → internal SSD
- The compose exposes `2283:2283` directly so `localhost:2283` works without a TCP proxy.

**[AGENT]**

```bash
ssh macmini.local "cd /Users/szelenin/projects/takeout/takeout/setup/immich && /usr/local/bin/docker compose up -d 2>&1 | tail -10"
```

**Wait for healthy**:

```bash
ssh macmini.local "until /usr/local/bin/docker ps --format '{{.Names}} {{.Status}}' | grep immich-server | grep -q healthy; do sleep 5; done; echo healthy"
```

**Verify mount layout** (this is the critical check — must match exactly, otherwise asset bytes won't go to RAID):

```bash
ssh macmini.local "/usr/local/bin/docker inspect immich-immich-server-1 --format '{{range .Mounts}}{{.Source}} → {{.Destination}}{{println}}{{end}}'"
```

**Expected** (the `upload/upload` line is the one that prevents the disk-fill disaster):

```
/Users/szelenin/immich-data/upload → /usr/src/app/upload
/Volumes/HomeRAID/immich-library → /usr/src/app/upload/upload
/Volumes/HomeRAID/icloud-export → /usr/src/app/icloud-export
```

**Verify localhost reachable**:

```bash
ssh macmini.local "curl -sf http://localhost:2283/api/server/version"
```

**Expected**: JSON like `{"major":2,"minor":6,"patch":3}`.

### Step 1.5 — Bootstrap admin user via API

**[USER]** Ask: *"What email and full name do you want for the Immich admin account?"* Default to the user's existing email if they don't specify. Record both.

**[AGENT]** Create the admin user, login, and create an API key. The password is auto-generated; save it to a mode-600 file the user can retrieve later.

```bash
ssh macmini.local "
URL=http://localhost:2283
EMAIL='<email-from-user>'
NAME='<name-from-user>'
PWD_FILE=/Users/szelenin/immich-data/admin-password.txt
KEY_FILE=/Users/szelenin/immich-data/api-key.txt

if [ -f \"\$KEY_FILE\" ]; then echo 'api key already exists'; exit 0; fi

PWD=\$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)
echo \"\$PWD\" > \"\$PWD_FILE\" && chmod 600 \"\$PWD_FILE\"

curl -sf -X POST \"\$URL/api/auth/admin-sign-up\" -H 'Content-Type: application/json' \
  -d \"{\\\"email\\\":\\\"\$EMAIL\\\",\\\"password\\\":\\\"\$PWD\\\",\\\"name\\\":\\\"\$NAME\\\"}\" > /dev/null

TOKEN=\$(curl -sf -X POST \"\$URL/api/auth/login\" -H 'Content-Type: application/json' \
  -d \"{\\\"email\\\":\\\"\$EMAIL\\\",\\\"password\\\":\\\"\$PWD\\\"}\" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"accessToken\"])')

SECRET=\$(curl -sf -X POST \"\$URL/api/api-keys\" -H \"Authorization: Bearer \$TOKEN\" \
  -H 'Content-Type: application/json' -d '{\"name\":\"familyvault-setup\",\"permissions\":[\"all\"]}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"secret\"])')

echo -n \"\$SECRET\" > \"\$KEY_FILE\" && chmod 600 \"\$KEY_FILE\"
echo 'admin user + api key created'"
```

**Note about the `permissions` field**: as of Immich v2.6.3, `POST /api/api-keys` requires a non-empty `permissions` array. Passing just `{"name":"..."}` returns HTTP 400. Use `["all"]` for full admin access.

**Verify**:

```bash
ssh macmini.local "curl -sf -H \"x-api-key: \$(cat /Users/szelenin/immich-data/api-key.txt)\" http://localhost:2283/api/server/statistics | python3 -m json.tool"
```

**Expected**: `photos: 0, videos: 0`. Tell the user: *"Your admin password is in `/Users/szelenin/immich-data/admin-password.txt` (mode 600). The API key is in `api-key.txt` next to it."*

### Step 1.6 — Disable video transcoding

The plan keeps Immich's encoded-video output on the internal SSD. To prevent that folder ballooning to 2–4 TB on a 250k-asset library, disable transcoding at the system-config level.

**[AGENT]**

```bash
ssh macmini.local "
URL=http://localhost:2283
KEY=\$(cat /Users/szelenin/immich-data/api-key.txt)
CONF=\$(curl -sf -H \"x-api-key: \$KEY\" \"\$URL/api/system-config\")
NEW=\$(echo \"\$CONF\" | python3 -c 'import sys,json; c=json.load(sys.stdin); c[\"ffmpeg\"][\"transcode\"]=\"disabled\"; print(json.dumps(c))')
curl -sf -X PUT \"\$URL/api/system-config\" -H \"x-api-key: \$KEY\" \
  -H 'Content-Type: application/json' -d \"\$NEW\" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"ffmpeg\"][\"transcode\"])'"
```

**Expected**: `disabled`. Re-running this is idempotent.

### Step 1.7 — Boot agent (auto-start Immich on Mac Mini boot)

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

**Expected**: line like `<PID>  -  com.familyvault.immich`.

**Verify after 30s**:

```bash
ssh macmini.local "curl -sf http://localhost:2283/api/server/ping"
```

**Expected**: `{"res":"pong"}`.

**[USER]** Ask: *"Please open `http://macmini.local:2283` in your browser. You should see the Immich login screen. Log in with the email/password from Step 1.5 (password is in `admin-password.txt` on the Mac Mini). Confirm you see an empty library."*

---

## Phase 2: Import from Google and iCloud

**Skip if**: Phase 1.5 audit report exists at `docs/architecture/phase-1-run/phase-1-audit-report.json` AND `launchctl list | grep com.familyvault.sync` returns a match (iCloud daily sync set up).

**Exit condition**: Google Takeout fully imported into Immich (asset count within ±1% of manifest), and iCloud daily sync running. Audit report committed.

This phase imports your historical archive from Google Takeout into Immich, and sets up daily iCloud sync to filesystem (which feeds future metadata-merge work in architecture Phase 3 — not part of this install).

### Step 2.1 — Order Google Takeout (USER, then 2–5 day wait)

Google Takeout takes 2–5 days to prepare. Order it now so it can build while you set up iCloud sync in parallel.

**[USER]**: *"Go to https://takeout.google.com → click 'Deselect all' → scroll down and select **only 'Google Photos'** → click 'Next step' at the bottom → choose:*
- *Delivery method: 'Add to Drive'*
- *File type: '.zip'*
- *File size: '50 GB' (Google splits the export into multiple zips of this size)*

*Click 'Create export'. Google will email you when it's ready (2–5 days). Don't proceed past Step 2.4 until you have the email and the zips appear in your Google Drive under a 'Takeout' folder."*

You may proceed with Step 2.2 (iCloud setup) immediately. Steps 2.3+ wait for Google's email.

### Step 2.2 — Set up iCloud daily sync (filesystem only)

This sets up `osxphotos` to export your iCloud library to `/Volumes/HomeRAID/icloud-export/` daily. **The exported files are not imported into Immich's library** in this install — they are filesystem-only output that will feed metadata-merge work in a future architecture phase. iCloud's bytes are kept separate from Immich's bytes for now.

**[AGENT]** Install osxphotos and exiftool:

```bash
ssh macmini.local "HOMEBREW_NO_AUTO_UPDATE=1 /opt/homebrew/bin/brew install exiftool 2>&1 | tail -3"
ssh macmini.local "pip3 install osxphotos 2>&1 | tail -3"
```

**Verify**:

```bash
ssh macmini.local "/opt/homebrew/bin/osxphotos --version && /opt/homebrew/bin/exiftool -ver"
```

**Expected**: osxphotos and exiftool versions printed.

**[USER]** Ask whether the Photos library lives on the Mac Mini's internal disk or the RAID. If internal:

*"We need to move your Photos Library to the RAID to avoid filling the internal drive during sync. Please: 1) Quit Photos.app, 2) In Finder, drag your Photos Library from `~/Pictures/` to `/Volumes/HomeRAID/`, 3) Hold Option and open Photos.app, select the RAID library, 4) Tell me when Photos.app shows your library normally."*

**[USER]**: *"In Photos.app: Settings → iCloud → select 'Download Originals to this Mac'. Tell me when it's set."*

**[AGENT]** Wait for download to complete (can take days):

```bash
ssh macmini.local "/opt/homebrew/bin/osxphotos info 2>&1 | grep 'Missing'"
```

**Expected when complete**: `total: 0, photos: 0, videos: 0`.

**[AGENT]** Run the canonical sync script for the first full export:

```bash
ssh macmini.local "cd ~/projects/takeout/takeout && tmux new -d -s icloud-export \
  './scripts/sync.sh /Volumes/HomeRAID/icloud-export \"/Volumes/HomeRAID/Photos Library.photoslibrary\"'"
```

The flag set is locked at the spec-014 minimum: `--update --update-errors`, `--fix-orientation`, `--exiftool-option '-m'`, `--person-keyword`, `--album-keyword`. The expensive flags `--favorite-rating` and `--sidecar` are intentionally excluded — see `specs/014-sync-metadata-flags/` for rationale. For favorites, run `scripts/apply-favorites.py` separately when needed.

**[AGENT]** Schedule daily launchd sync at 2 AM:

```bash
ssh macmini.local "mkdir -p /Volumes/HomeRAID/scripts && \
  cp ~/projects/takeout/takeout/scripts/sync.sh /Volumes/HomeRAID/scripts/sync.sh && \
  chmod +x /Volumes/HomeRAID/scripts/sync.sh"

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

### Step 2.3 — Download Google Takeout (when ready)

**Wait until** the user confirms the email from Google has arrived and Takeout zips are visible in Google Drive under a `Takeout` folder.

**[AGENT]** Configure rclone if not already done:

```bash
ssh macmini.local "/opt/homebrew/bin/rclone listremotes | grep gdrive || echo 'needs setup'"
```

If `needs setup`, **[USER]**: *"Please run this on the Mac Mini and follow the browser prompts: `/opt/homebrew/bin/rclone config` → New remote → name `gdrive` → type `drive` → leave client_id blank → follow auth. Tell me when done."*

**[AGENT]** Download:

```bash
ssh macmini.local "nohup /opt/homebrew/bin/rclone copy gdrive:Takeout /Volumes/HomeRAID/google-takeout/ \
  --transfers 4 --checkers 8 --drive-chunk-size 128M \
  --retries 10 --low-level-retries 20 --bwlimit 50M \
  --log-file /Volumes/HomeRAID/google-takeout/rclone.log --log-level INFO > /dev/null 2>&1 &
echo \$!"
```

**Verify when done**:

```bash
ssh macmini.local "tail -3 /Volumes/HomeRAID/google-takeout/rclone.log"
ssh macmini.local "ls /Volumes/HomeRAID/google-takeout/*.zip | wc -l"
```

**Expected**: log shows no errors; the zip count matches what Google said it would create. The Takeout splits into one tiny `*-001.zip` (~2 MB, contains only `archive_browser.html` — the manifest) and many `*-3-NNN.zip` photo-data zips at 50 GB each. Record both counts.

### Step 2.4 — Extract Takeout manifest

The manifest is the validation oracle for the audit. It's parsed from `archive_browser.html` (the file inside the small `*-001.zip`).

**[AGENT]** Find the small zip and parse:

```bash
ssh macmini.local "
SMALL_ZIP=\$(ls -S /Volumes/HomeRAID/google-takeout/*.zip | tail -1)
echo \"manifest zip: \$SMALL_ZIP\"
unzip -o \"\$SMALL_ZIP\" -d /tmp/ 2>&1 | tail -3"

# parse to JSON manifest in the repo
ssh macmini.local "cd ~/projects/takeout/takeout && python3 -c \"
import re, json
html = open('/tmp/Takeout/archive_browser.html').read()
files = re.findall(r'class=\\\"extracted-file-name\\\"[^>]*>([^<]+)</', html)
folders = re.findall(r'class=\\\"extracted-folder-name\\\"[^>]*>([^<]+)</', html)
ext_counts = {}
for f in files:
    ext = f.rsplit('.',1)[-1].lower() if '.' in f else 'no-ext'
    ext_counts[ext] = ext_counts.get(ext,0)+1
year_folders = sorted([fo for fo in folders if fo.startswith('Photos from ')])
album_folders = sorted([fo for fo in folders if not fo.startswith('Photos from ')])
out = {
    'total_files_in_html': len(files),
    'total_folders': len(folders),
    'extension_counts': dict(sorted(ext_counts.items(), key=lambda x: -x[1])),
    'year_folder_count': len(year_folders),
    'year_folder_range': [year_folders[0] if year_folders else None, year_folders[-1] if year_folders else None],
    'user_album_count': len(album_folders),
    'user_albums': album_folders,
}
print(json.dumps(out, indent=2, ensure_ascii=False))
\" > docs/architecture/google-takeout-manifest.json"
```

**Verify**:

```bash
ssh macmini.local "jq '{total_files_in_html, user_album_count, year_folder_range}' \
                       ~/projects/takeout/takeout/docs/architecture/google-takeout-manifest.json"
```

**Expected**: JSON showing total file count, album count, and year range. Commit the manifest to the repo.

### Step 2.5 — Install immich-go and run pre-flight

**[AGENT]**

```bash
ssh macmini.local "/opt/homebrew/bin/brew install immich-go 2>&1 | tail -5 && immich-go --version"
```

**Expected**: `immich-go version 0.31.x`.

**[AGENT]** Run pre-flight (must be run from worktree root — the manifest path inside the script is relative):

```bash
ssh macmini.local "cd ~/projects/takeout/takeout && ./scripts/phase1-preflight.sh"
```

**Expected**: 7 checks all `OK`, ending with `ALL CHECKS PASSED.` If anything fails, fix the underlying issue before proceeding (e.g., insufficient disk, Immich not responding, immich-go missing).

### Step 2.6 — Run the import (24–48 hours unattended)

The import processes all photo-data zips in a single immich-go invocation; per-zip checkpointing isn't viable because Google scatters sidecars and Live Photo pairs across zip boundaries.

**[USER]**: *"The Google import will run for 24–48 hours. Please: 1) make sure your Mac Mini won't sleep (System Settings → Battery/Energy Saver → never sleep when plugged in), 2) close other heavy apps to free RAM, 3) leave OrbStack running. I'll start the import now and come back to verify when it finishes."*

**[AGENT]** Start the import + monitor in detached background processes:

```bash
ssh macmini.local "
nohup ~/projects/takeout/takeout/scripts/phase1-monitor.sh /Users/szelenin/immich-data/import-progress.log \
  > /Users/szelenin/immich-data/monitor-stdout.log 2>&1 &
echo \$! > /Users/szelenin/immich-data/monitor.pid

nohup ~/projects/takeout/takeout/scripts/phase1-import.sh \
  > /Users/szelenin/immich-data/import-stdout.log 2>&1 &
echo \$! > /Users/szelenin/immich-data/import.pid"
```

**Verify started cleanly** (check after ~5 minutes):

```bash
ssh macmini.local "
(kill -0 \$(cat /Users/szelenin/immich-data/import.pid) && echo 'import alive') || echo 'import DEAD'
tail -5 /Users/szelenin/immich-data/immich-go.log
tail -3 /Users/szelenin/immich-data/import-progress.log"
```

**Expected**: import process alive; immich-go log shows `discovered` lines; monitor CSV has at least 5 rows (one per minute).

The discovery phase typically takes 30–90 minutes before the first asset uploads. After that, expect ~500–1500 assets/min throughput.

**Watch host memory pressure during the run** (separate session — this is what would have caught the first run's SIGKILL):

```bash
ssh macmini.local "memory_pressure 2>&1 | head -3 && /usr/local/bin/docker stats --no-stream"
```

If `memory_pressure` reports beyond `Normal`, or any container's `MEM USAGE` exceeds ~80% of its allotment, stop the import (`kill $(cat /Users/szelenin/immich-data/import.pid)`), reduce `--concurrent-tasks` in `scripts/phase1-import.sh` to 2, and re-run. Server-side hash dedup will skip already-uploaded photos.

**Watch disk fill rate during the run** (catches mount path bugs early):

```bash
ssh macmini.local "while true; do df -h / /Volumes/HomeRAID | head -3 | grep -E '/(System|Volumes)'; sleep 300; done"
```

Internal SSD (`/System/Volumes/Data`) free space should stay roughly **flat** during the import — if it's dropping by GB/min, the mount layout is wrong (asset bytes are landing on internal instead of RAID). Stop and re-verify Step 1.4's `docker inspect` output.

### Step 2.7 — Resume Immich background jobs (post-import)

When `import.pid` no longer exists (the import finished), Immich has the original bytes but background jobs (metadata extraction, thumbnail gen, smart search, face detection) are still paused per the `--pause-immich-jobs` flag. Resume them so Immich becomes browsable.

**[AGENT]**

```bash
ssh macmini.local "
URL=http://localhost:2283
KEY=\$(cat /Users/szelenin/immich-data/api-key.txt)
for q in metadataExtraction thumbnailGeneration smartSearch faceDetection faceRecognition library sidecar duplicateDetection; do
  echo \"resume \$q\"
  curl -sf -X PUT \"\$URL/api/jobs/\$q\" -H \"x-api-key: \$KEY\" \
       -H 'Content-Type: application/json' -d '{\"command\":\"resume\"}' | head -c 200
  echo
done"
```

**Wait for metadata-extraction to drain**:

```bash
ssh macmini.local "until [ \"\$(curl -sf -H 'x-api-key: '\$(cat /Users/szelenin/immich-data/api-key.txt) \
                              http://localhost:2283/api/jobs | jq '.metadataExtraction.jobCounts.waiting')\" = 0 ]; do
  curl -sf -H 'x-api-key: '\$(cat /Users/szelenin/immich-data/api-key.txt) \
       http://localhost:2283/api/jobs | jq '{meta: .metadataExtraction.jobCounts, thumb: .thumbnailGeneration.jobCounts}'
  sleep 300
done
echo 'metadata extraction drained'"
```

Background jobs continue (thumbnail generation, ML, faces) for many more hours. The audit can run as soon as metadata extraction reaches 0; the others are nice-to-have for the audit's accuracy but not strictly required.

### Step 2.8 — Run Phase 1.5 audit

The audit compares Immich's actual state to the Takeout manifest and reports DNG sibling buckets (the deferred Option-B decision).

**[AGENT]**

```bash
ssh macmini.local "cd ~/projects/takeout/takeout && python3 -m scripts.phase1_audit \
  --manifest docs/architecture/google-takeout-manifest.json \
  --server http://localhost:2283 \
  --api-key-file /Users/szelenin/immich-data/api-key.txt \
  --report /Users/szelenin/immich-data/phase-1-audit-report.json"
```

**Expected**: console summary listing each check `[PASS]` or `[FAIL]`; final summary `N/M passed`. Exit 0 if all pass, 1 otherwise.

**Commit the report**:

```bash
ssh macmini.local "cp /Users/szelenin/immich-data/phase-1-audit-report.json \
                      ~/projects/takeout/takeout/docs/architecture/phase-1-run/phase-1-audit-report.json"
# then commit from your local checkout
```

**On any FAIL**: read the message in the report. Common causes:
- Total count low → some uploads errored; re-run `phase1-import.sh` (server-side dedup skips successes).
- Album names missing → immich-go's album sync didn't catch one; manually create via UI or accept partial.
- DNG-only count > expected → some HEIC siblings didn't import; investigate before deciding bucket policy.

---

## Phase 3: Final Verification

Run after Phase 2 completes.

**[AGENT]** Run all checks:

```bash
ssh macmini.local "
URL=http://localhost:2283
KEY=\$(cat /Users/szelenin/immich-data/api-key.txt)

echo '=== Immich health ===' && curl -sf \"\$URL/api/server/ping\"

echo '=== asset counts vs manifest ===' \
&& EXPECTED=\$(jq -r '.total_files_in_html - (.extension_counts.json // 0) - (.extension_counts[\"no-ext\"] // 0)' \
              ~/projects/takeout/takeout/docs/architecture/google-takeout-manifest.json) \
&& ACTUAL=\$(curl -sf -H \"x-api-key: \$KEY\" \"\$URL/api/server/statistics\" | jq '.photos + .videos') \
&& echo \"expected=\$EXPECTED actual=\$ACTUAL\"

echo '=== albums ===' \
&& curl -sf -H \"x-api-key: \$KEY\" \"\$URL/api/albums\" | jq 'length'

echo '=== iCloud sync agent ===' && launchctl list | grep com.familyvault.sync

echo '=== Immich boot agent ===' && launchctl list | grep com.familyvault.immich

echo '=== orientation: no Rotate-180 in iCloud export ===' \
&& exiftool -fast2 -r -Orientation -if '\$Orientation eq \"Rotate 180\"' /Volumes/HomeRAID/icloud-export 2>/dev/null \
   | grep -c 'File Name' || echo 0

echo '=== storage layout (originals on RAID, everything else on internal SSD) ===' \
&& /usr/local/bin/docker inspect immich-immich-server-1 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'"
```

**Expected**:

- Ping returns `{"res":"pong"}`
- `actual` is within ±1% of `expected`
- Album count equals manifest's `user_album_count`
- Both launchctl lines present
- Rotate-180 count: 0
- Mounts show `/Volumes/HomeRAID/immich-library → /usr/src/app/upload/upload` (this is the critical line — proves bytes go to RAID)

**[USER]** Manual acceptance tests:
1. *"Open `http://macmini.local:2283`. Confirm the Immich timeline shows your photos with year navigation working from 2004 to current year."*
2. *"Restart your Mac Mini. Within 2 minutes, Immich should be reachable again at the same URL — no manual steps."*
3. *"Try searching 'birthday' or 'beach' in Immich and confirm relevant photos appear (this requires CLIP smart-search to have run)."*
4. *"Confirm the iCloud daily sync runs: tomorrow morning, check `tail /Volumes/HomeRAID/sync.log` — there should be a successful run from 2 AM."*

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Internal SSD fills rapidly during import | Mount layout wrong — bytes going to internal instead of RAID | Verify Step 1.4's `docker inspect` shows `/Volumes/HomeRAID/immich-library → /usr/src/app/upload/upload` (not `/upload/library`). If wrong, follow the post-mortem in `docs/architecture/phase-1-run/execution-log.md` for clean recovery |
| OrbStack VM killed (SIGKILL) mid-import | Mac Mini host RAM exhausted | Lower `--concurrent-tasks` in `phase1-import.sh`; close other apps; verify VM memory limit ≤ host total - 9 GB |
| immich-go discovery phase re-runs every retry | Expected — no checkpoint resume | Avoid mid-run crashes (stable power, tmux session); each retry costs ~30–90 min before uploads resume |
| Photo count below expected after audit | Some files errored during upload | Re-run `phase1-import.sh`; server-side hash dedup skips successes; only failed photos retry |
| Live Photos imported as separate HEIC + MOV | immich-go pairing bug ([#1298](https://github.com/simulot/immich-go/issues/1298)) | Phase 1.5 audit reports unpaired count; mitigation deferred to architecture Open Item #6 |
| iCloud daily sync's `sync.log` shows osxphotos errors | iCloud signed out, RAID unmounted, or Photos.app holding the library | Check user's iCloud session; confirm RAID mounted; ensure Photos.app is closed during the 2 AM window |
| `POST /api/api-keys` returns HTTP 400 "permissions must contain at least 1 elements" | Immich v2.6.3 requires non-empty permissions array | Add `"permissions":["all"]` to the JSON body (already in Step 1.5 example) |
| `phase1-preflight.sh` says "Manifest present: MISSING" | Running from wrong cwd; manifest path is relative | Run from worktree root: `cd ~/projects/takeout/takeout && ./scripts/phase1-preflight.sh` |

---

## What this install does NOT cover

These belong to later phases of the architecture (`docs/architecture/2026-04-26-three-source-merge.md`):

- **Phase 1.5 (mobile pilot)**: testing the Immich mobile app as a replacement for iCloud Photos sync
- **Phase 2 (identity tooling)**: Strategy-D cascade matcher built and tested
- **Phase 3 (metadata merge)**: pulling iCloud favorites/albums/captions into Immich, merging Google JSON tags
- **Phase 4 (cutover decision)**: choosing whether to keep, downgrade, or drop iCloud Photos subscription

Story Engine setup (FFmpeg, scenarios, etc.) lives in `setup/story-engine/README.md` and is independent of this install.
