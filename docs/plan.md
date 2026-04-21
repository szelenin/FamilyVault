# FamilyVault — Full Migration Plan

## Context

~2TB of photos/videos exist on both iCloud and Google Photos. The goal is to download
everything to a Mac Mini home server with 12TB RAID1 storage, preserve all metadata,
and run Immich as a self-hosted photo app. Ongoing sync is required.

Both accounts are merged into an **iCloud Shared Photo Library**. Wife is the primary
photo producer (~80% of photos are hers).

---

## Key Decision: iCloud as Primary Source

**iCloud wins over Google for the primary download.**

| Factor | iCloud | Google Photos |
|--------|--------|---------------|
| Original quality | Always exact originals | Only if "Original Quality" was set |
| HEIC preservation | Yes | Depends on upload method |
| Live Photos | Native paired HEIC+MOV | Split into separate files |
| Metadata (EXIF) | Embedded in files | Stripped into sidecar JSON (broken) |
| Edited photos | Original + edit preserved | Usually only edited version |
| Export tooling | osxphotos (excellent) | Takeout + post-processing (painful) |
| Ongoing sync | Yes (osxphotos --update) | No (API dead since March 2025) |

**Strategy: Full iCloud export as primary → wife's metadata injection → Google Takeout only for delta.**

---

## Critical Issue: Shared Library Strips Metadata

When photos cross from wife's library into the Shared Photo Library, iCloud strips:

| Field | Status |
|-------|--------|
| **GPS coordinates** | **Stripped** — affects ~80% of library |
| People/face tags | Stripped — Immich re-detects anyway |
| Memories | Stripped |

**Fix**: export wife's `Photos.sqlite` (metadata DB, no originals needed) and use
`apply-wife-metadata.py` to inject exact GPS, titles, descriptions, keywords, and
timezone into the exported files before Immich indexes them.

---

## Folder Structure

```
/Volumes/HomeRAID/
├── icloud-export/          ← primary photo library (osxphotos export)
├── wife-photos.sqlite      ← wife's metadata DB (copy from her account)
├── google-takeout/         ← raw Takeout archives (already downloaded, 2.4TB)
├── google-processed/       ← after gpth metadata fix
├── google-delta/           ← Google-unique files only (after dedup)
└── immich/                 ← Immich data (postgres, thumbs, upload)
```

---

## Phase 0: Hardware Setup ✅

1. 12TB RAID1 attached and formatted as APFS, mounted at `/Volumes/HomeRAID`
2. iCloud Shared Photo Library set up — both accounts merged
3. Photos Library on RAID: `/Volumes/HomeRAID/Photos Library.photoslibrary`
4. Tools installed: `osxphotos`, `exiftool`, `rclone`
5. Immich installed and running (Docker via OrbStack)

---

## Phase 1: iCloud Full Export

**Status**: in progress (~1,650 / 80,246 exported before pause)

### Run Export

```bash
# Runs in tmux — survives SSH disconnect
ssh macmini
export PATH=/opt/homebrew/bin:$PATH
tmux new -s icloud-export
cd ~/projects/takeout/takeout
./scripts/export-icloud.sh \
  /Volumes/HomeRAID/icloud-export \
  "/Volumes/HomeRAID/Photos Library.photoslibrary"
```

The `--update` flag resumes from where it left off. Previously exported files are skipped.

**Monitor progress:**
```bash
tail -f /Volumes/HomeRAID/icloud-export/export.log
```

**Expected duration**: 3–5 hours unattended.

**Before starting**: stop Immich completely to free CPU:
```bash
~/.orbstack/bin/docker stop $(~/.orbstack/bin/docker ps -q)
```

### What export-icloud.sh does

- `--exiftool`: reads GPS, dates, keywords from Photos.sqlite → writes into files
- `--fix-orientation`: corrects EXIF rotation flags
- `--sidecar xmp --sidecar json`: creates XMP and JSON sidecars per file
- `--update --update-errors`: incremental — only exports new/changed/failed files
- `--touch-file`: sets file mtime to capture date (correct for backup tools)

**Note**: `--exiftool` only writes GPS for photos owned by your account. Wife's shared
copies get GPS stripped by iCloud before osxphotos ever sees them. That's what Phase 2 fixes.

---

## Phase 2: Wife's Metadata Extraction and Injection

**Status**: pending — do this while export runs or after

### Why

~80% of photos are from your wife's Shared Library. iCloud strips GPS (and other fields)
from these when they appear in your library. `apply-wife-metadata.py` reads her original
`Photos.sqlite` (which has full GPS for all her photos) and writes it directly into the
exported files by UUID match.

### Step 1 — Get wife's Photos.sqlite (15 min)

On Mac Mini, create a second macOS user for wife's Apple ID:
1. System Settings → Users & Groups → Add User
2. Log in as her
3. **Before opening Photos.app**: System Settings → Apple ID → iCloud → Photos →
   confirm **"Optimize Mac Storage"** is selected (prevents downloading 2TB of originals)
4. Open Photos.app → wait until photo count stabilizes (5–15 min — only metadata syncs)
5. Copy her database to the RAID:
   ```bash
   cp ~/Pictures/Photos\ Library.photoslibrary/database/Photos.sqlite \
      /Volumes/HomeRAID/wife-photos.sqlite
   ```
6. Log out of her account

### Step 2 — Run metadata injection

```bash
# Dry run first — shows what would be updated
python3 scripts/apply-wife-metadata.py \
  /Volumes/HomeRAID/wife-photos.sqlite \
  /Volumes/HomeRAID/icloud-export \
  --dry-run

# Apply
python3 scripts/apply-wife-metadata.py \
  /Volumes/HomeRAID/wife-photos.sqlite \
  /Volumes/HomeRAID/icloud-export
```

**What it injects** (by UUID match):

| Field | Source | EXIF tag written |
|-------|--------|-----------------|
| GPS coordinates | `ZASSET.ZLATITUDE/ZLONGITUDE` | `GPSLatitude/Longitude` |
| Title | `ZADDITIONALASSETATTRIBUTES.ZTITLE` | `Title` |
| Description | `ZADDITIONALASSETATTRIBUTES.ZASSETDESCRIPTION` | `Description` |
| Timezone | `ZADDITIONALASSETATTRIBUTES.ZTIMEZONENAME` | `OffsetTime` |
| Keywords | `ZKEYWORD` join | `Keywords` |

**Expected**: ~80% of files updated with GPS. Files already having GPS are skipped.

### Step 3 — Verify GPS coverage

```bash
# Sample 100 exported files — check GPS coverage
total=0; with_gps=0
while IFS= read -r f; do
  [ $total -ge 100 ] && break
  total=$((total + 1))
  exiftool -fast2 -GPSLatitude "$f" 2>/dev/null | grep -q "GPS" && with_gps=$((with_gps + 1))
done < <(find /Volumes/HomeRAID/icloud-export -name "*.HEIC" -o -name "*.jpg")
echo "GPS coverage: $with_gps / $total"
# PASS: ≥95% (your photos + wife's photos both covered)
```

---

## Phase 3: Immich Setup

**Status**: pending — do after Phase 2 injection is complete

### Start Immich (fresh install — DB was wiped)

```bash
cd /path/to/immich
~/.orbstack/bin/docker compose up -d
```

Open `http://macmini:2283` → complete first-run setup (create admin user, save API key
to `/Volumes/HomeRAID/immich/api-key.txt`).

### Add external library

```bash
IMMICH_KEY=$(cat /Volumes/HomeRAID/immich/api-key.txt)

curl -X POST http://localhost:2283/api/libraries \
  -H "x-api-key: $IMMICH_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "iCloud Export",
    "importPaths": ["/usr/src/app/icloud-export"],
    "exclusionPatterns": ["**/*.DNG","**/*.dng","**/*.RAW","**/*.raw"]
  }' | jq '{id, name}'
```

### Trigger scan

```bash
LIBRARY_ID="<id from above>"
curl -X POST "http://localhost:2283/api/libraries/$LIBRARY_ID/scan" \
  -H "x-api-key: $IMMICH_KEY"
```

Immich will index all files. ML jobs (face detection, CLIP search) run automatically.
For 80k+ photos this takes several hours — leave it running overnight.

---

## Phase 4: Google Takeout (Secondary — Delta Only)

**Status**: 2.4TB of archives already downloaded to `/Volumes/HomeRAID/google-takeout/`

Full instructions: `docs/playbooks/google-takeout-import.md`

Summary:
1. Extract archives → `google-processed/`
2. Fix metadata with `gpth` (JSON sidecars → EXIF)
3. Dedup against `icloud-export/` with `czkawka` → `google-delta/`
4. Add `google-delta/` as second Immich external library
5. Run Immich duplicate detection for HEIC/JPEG format pairs

---

## Phase 5: Ongoing Sync

```bash
# Add to crontab (runs daily at 2 AM):
0 2 * * * /Users/szelenin/projects/takeout/takeout/scripts/sync.sh \
  >> /Volumes/HomeRAID/sync.log 2>&1
```

New photos → iCloud → Photos.app → picked up on next sync run.
Lag: a few hours from shooting to appearing on RAID.

**Note**: wife's metadata injection does NOT need to re-run for new photos — new photos
taken after the Shared Library was set up come through with GPS intact. The stripping
only affected historical photos from before the Shared Library merge.

---

## Phase 6: Verification

```bash
# T1: GPS coverage on wife's photos
find /Volumes/HomeRAID/icloud-export -name "* (1).HEIC" | head -50 | while read f; do
  exiftool -fast2 -GPSLatitude "$f" | grep -q GPS && echo "OK: $f" || echo "NO GPS: $f"
done

# T2: File count matches Photos.app
export PATH=/opt/homebrew/bin:$PATH
osxphotos info --library "/Volumes/HomeRAID/Photos Library.photoslibrary" | grep -i "photos"

# T3: No upside-down files
exiftool -fast2 -r -Orientation -if '$Orientation eq "Rotate 180"' \
  /Volumes/HomeRAID/icloud-export 2>/dev/null | grep "File Name"
# PASS: 0 results

# T4: Immich asset count
IMMICH_KEY=$(cat /Volumes/HomeRAID/immich/api-key.txt)
curl -s -H "x-api-key: $IMMICH_KEY" \
  http://localhost:2283/api/server/statistics | jq '{photos, videos}'
# PASS: ~80k photos
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/export-icloud.sh` | Full iCloud export with all fixes |
| `scripts/sync.sh` | Daily incremental sync |
| `scripts/apply-wife-metadata.py` | Inject GPS + metadata from wife's Photos.sqlite |
| `docs/playbooks/google-takeout-import.md` | Google Takeout dedup and import |

---

## Current Status

| Phase | Status |
|-------|--------|
| Phase 0: Hardware | ✅ Complete |
| Phase 1: iCloud export | 🔄 In progress (1,650 / 80,246 — paused) |
| Phase 2: Wife's metadata | ⏳ Pending — need her Photos.sqlite |
| Phase 3: Immich setup | ⏳ Pending — after Phase 2 |
| Phase 4: Google Takeout | ⏳ Pending — archives on disk, not processed |
| Phase 5: Ongoing sync | ⏳ Pending |
| Phase 6: Verification | ⏳ Pending |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Export interrupted again | `--update` resumes exactly where it stopped |
| Wife's UUID doesn't match shared copy UUID | Verify with sample query before running injection |
| GPS coverage still low after injection | Check dry-run output; fallback to infer-gps.py for remaining gaps |
| Google Takeout HEIC/JPEG duplicates | Immich built-in duplicate detection cleans up after import |
| RAID failure during migration | Do not delete cloud copies until Phase 6 verification passes |
| Mac wakes from sleep mid-transfer | System Settings → Battery → Prevent sleep while on power |
