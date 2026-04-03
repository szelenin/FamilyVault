# FamilyVault — Full Migration Plan

## Context

~2TB of photos/videos exist on both iCloud and Google Photos with near-100% overlap. The goal is to download everything to a Mac Mini home server with 12TB RAID1 storage, preserve all metadata, and run Immich as a self-hosted photo app. Ongoing sync is required.

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

**Strategy: Full iCloud export as primary → Google Takeout only for delta (unique files not in iCloud).**

---

## Phase 0: Hardware Setup

1. Attach external RAID to Mac Mini, format as APFS
2. Mount at `/Volumes/HomeRAID` (or your chosen name)
3. Create folder structure:
   ```
   /Volumes/HomeRAID/
   ├── icloud-export/
   ├── google-takeout/
   ├── google-processed/
   ├── google-delta/
   └── immich/
   ```
4. If you have a spouse/partner with a separate iCloud account:
   - Set up **iCloud Shared Photo Library**: Settings → Photos → Shared Library → Invite Participant
   - Both participants choose "Move All My Photos & Videos"
   - This merges both libraries — osxphotos will export everything in one pass

---

## Phase 1: iCloud Full Export

### Move Photos Library to RAID
If your Mac's internal drive lacks space for the full library:
```bash
# Quit Photos.app first, then:
mv ~/Pictures/Photos\ Library.photoslibrary /Volumes/HomeRAID/

# Reopen Photos.app holding the Option key → select the library on HomeRAID
# Then: Photos → Settings → General → "Use as System Photo Library"
```

### Enable Download Originals
Photos.app → Settings → iCloud → **"Download Originals to this Mac"**

Wait for full download (several days for large libraries). Monitor the status bar at the bottom of Photos.app.

### Install Tools
```bash
brew install exiftool rclone czkawka
pip install osxphotos
# Install gpth (GooglePhotosTakeoutHelper):
curl -L https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper/releases/download/v3.4.3/gpth-macos \
  -o /usr/local/bin/gpth && chmod +x /usr/local/bin/gpth
```

### Run Full Export
```bash
./scripts/export-icloud.sh /Volumes/HomeRAID/icloud-export
```

Or manually:
```bash
osxphotos export /Volumes/HomeRAID/icloud-export \
  --directory "{folder_album}" \
  --exiftool \
  --sidecar xmp --sidecar json \
  --person-keyword --album-keyword \
  --update --ramdb \
  --export-edited --export-live --export-raw --export-bursts \
  --touch-file --verbose
```

### Verify
- Spot-check ~20 random files for EXIF dates, GPS coordinates, faces
- Verify album folder structure matches Photos.app albums
- Check Live Photos are properly paired (HEIC + MOV)
- Compare file count: `osxphotos info` vs files on disk

---

## Phase 2: Google Takeout (Secondary — Delta Only)

### Request Takeout
1. Go to [takeout.google.com](https://takeout.google.com)
2. Deselect all → select **Google Photos only**
3. File size: **50 GB**, delivery: **Add to Google Drive**
4. Submit and wait 2-5 days for Google to prepare the export

### Download via rclone
```bash
# Configure rclone (first time only):
rclone config  # follow prompts, select Google Drive, full access scope

./scripts/download-takeout.sh gdrive /Volumes/HomeRAID/google-takeout
```

### Process and Find Delta
```bash
./scripts/process-takeout.sh \
  /Volumes/HomeRAID/google-takeout \
  /Volumes/HomeRAID/google-processed \
  /Volumes/HomeRAID/icloud-export \
  /Volumes/HomeRAID/google-delta
```

Merge Google-only files into the main library, verify metadata, then delete the Takeout archives to free space.

---

## Phase 3: Ongoing Sync

### Daily Cron Job
```bash
# Edit crontab:
crontab -e

# Add this line (runs daily at 2 AM):
0 2 * * * /path/to/FamilyVault/scripts/sync.sh >> /Volumes/HomeRAID/sync.log 2>&1
```

New photos taken on any device in the Shared Library will sync to iCloud → appear in Photos.app → get picked up by the next sync run. Typical lag: a few hours.

---

## Phase 4: Immich

```bash
# Install Docker Desktop for Mac, then:
mkdir -p /Volumes/HomeRAID/immich && cd /Volumes/HomeRAID/immich
curl -L https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml -o docker-compose.yml
curl -L https://github.com/immich-app/immich/releases/latest/download/example.env -o .env
# Edit .env to set UPLOAD_LOCATION=/Volumes/HomeRAID/icloud-export
docker compose up -d
```

Immich provides face recognition, location maps, memories, search, and sharing. It also has built-in ML-based duplicate detection as a safety net.

---

## Phase 5: Verification and Cleanup

1. Compare file counts on disk vs iCloud library (`osxphotos info`)
2. Spot-check metadata: random files across different years
3. Test Live Photos play correctly in Immich
4. Delete Takeout archives from Google Drive (reclaim cloud quota)
5. Consider canceling or downgrading Google One / iCloud+ subscriptions

---

## Storage Budget

| Item | Size |
|------|------|
| iCloud export (steady state) | ~2 TB |
| Google Takeout archives (temporary) | ~2 TB |
| Google processed (temporary) | ~2 TB |
| Immich thumbnails/cache | ~200 GB |
| **Peak usage** | **~6 TB** |
| **Final steady state** | **~2.5 TB** |
| **RAID1 usable capacity** | **~6 TB** |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Photos.app download stalls | Monitor daily; restart if stuck; can take 1-2 weeks |
| Google Takeout export fails | Retry; verify archive count matches expected |
| Metadata loss in Takeout | Use exiftool to verify; accept iCloud as canonical source |
| RAID failure during migration | Do not delete cloud copies until fully verified |
| Mac wakes from sleep mid-transfer | Set Mac Mini to never sleep during migration |
