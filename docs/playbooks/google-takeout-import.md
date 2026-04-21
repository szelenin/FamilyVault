# Google Takeout Import — Dedup Against iCloud

## Context

2.4TB of Google Takeout archives are already downloaded to `/Volumes/HomeRAID/google-takeout/`
(50 zip files, both accounts). iCloud export is the primary library. This playbook covers:

1. Extract archives
2. Fix metadata (JSON sidecars → EXIF) with `gpth`
3. Find Google-unique files (delta) with `czkawka`
4. Copy delta to `google-delta/`
5. Add `google-delta/` as a second Immich external library

**Run this AFTER iCloud export is complete and Immich is scanning iCloud.**

---

## Prerequisites

```bash
# Install gpth (Google Photos Takeout Helper)
# macOS — download binary from https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper/releases
# Pick the macOS arm64 binary, place it in ~/bin or /usr/local/bin
gpth --version

# Install czkawka
brew install czkawka
# or download GUI from https://github.com/qarmin/czkawka/releases
czkawka_cli --version

# Verify disk space — need ~2.5TB free for extracted + processed + delta
df -h /Volumes/HomeRAID
```

---

## Phase 1: Extract Archives

The archives use a naming scheme with multiple batches (the `-3-` prefix is the second account).

```bash
# Extract both accounts into separate subdirs to keep them organized
mkdir -p /Volumes/HomeRAID/google-extracted/account1
mkdir -p /Volumes/HomeRAID/google-extracted/account2

# Account 1 — the single zip (takeout-...-001.zip with no -3- infix)
cd /Volumes/HomeRAID/google-extracted/account1
unzip "/Volumes/HomeRAID/google-takeout/takeout-20260403T195541Z-001.zip"

# Account 2 — the multi-part set (takeout-...-3-001.zip through -3-050.zip)
cd /Volumes/HomeRAID/google-extracted/account2
for z in /Volumes/HomeRAID/google-takeout/takeout-20260403T195541Z-3-*.zip; do
  echo "Extracting $z..."
  unzip -n "$z"   # -n: never overwrite existing files (safe for multi-part)
done

# Verify extraction
echo "Account 1 files:"
find /Volumes/HomeRAID/google-extracted/account1 -type f | wc -l
echo "Account 2 files:"
find /Volumes/HomeRAID/google-extracted/account2 -type f | wc -l
```

**Expected**: The `Takeout/Google Photos/` subfolder inside each archive contains year-folders
with media files and `.json` sidecar files for each photo.

---

## Phase 2: Fix Metadata with gpth

Google Takeout stores metadata (date, GPS, title) in JSON sidecars, not in the file's EXIF.
`gpth` reads those JSON sidecars and writes the metadata back into the files, then outputs
a clean folder of renamed files without the JSON clutter.

```bash
mkdir -p /Volumes/HomeRAID/google-processed/account1
mkdir -p /Volumes/HomeRAID/google-processed/account2

# Process account 1
gpth \
  --input  "/Volumes/HomeRAID/google-extracted/account1/Takeout/Google Photos" \
  --output /Volumes/HomeRAID/google-processed/account1 \
  --divide-to-dates \
  2>&1 | tee /Volumes/HomeRAID/google-processed/gpth-account1.log

# Process account 2
gpth \
  --input  "/Volumes/HomeRAID/google-extracted/account2/Takeout/Google Photos" \
  --output /Volumes/HomeRAID/google-processed/account2 \
  --divide-to-dates \
  2>&1 | tee /Volumes/HomeRAID/google-processed/gpth-account2.log

# Check for errors
grep -i "error\|warning\|skip" /Volumes/HomeRAID/google-processed/gpth-account1.log | head -30
grep -i "error\|warning\|skip" /Volumes/HomeRAID/google-processed/gpth-account2.log | head -30
```

**What gpth does:**
- Reads `.json` sidecar → writes date, GPS, title back into EXIF
- Renames files to avoid collisions
- `--divide-to-dates` organizes output into `YYYY/MM/` folders
- Files without a JSON sidecar are still copied (with whatever EXIF they have)

**What to watch for in the log:**
- `No JSON found` — file had no sidecar; GPS/date may be missing or already in EXIF
- `Duplicate` — gpth skipped a file it already processed; normal for shared photos
- `Error` — file corrupt or unreadable; note the filename

---

## Phase 3: Dedup Against iCloud Export

`czkawka` compares files by **content hash** (not filename). A HEIC from iCloud and the
equivalent JPEG from Google with the same image content → detected as duplicate.

```bash
# Step 1 — build the duplicate list (dry run, no deletions)
# Reference dir = iCloud export (keep everything here)
# Other dir = Google processed (mark duplicates here for removal)
czkawka_cli duplicates \
  --directories /Volumes/HomeRAID/icloud-export \
  --reference-directories /Volumes/HomeRAID/google-processed \
  --hash-type Xxh3 \
  --minimal-file-size 102400 \
  --not-recursive \
  --file-to-save /Volumes/HomeRAID/google-processed/duplicates.txt \
  2>&1 | tee /Volumes/HomeRAID/google-processed/czkawka.log

# Check what was found
wc -l /Volumes/HomeRAID/google-processed/duplicates.txt
head -50 /Volumes/HomeRAID/google-processed/duplicates.txt
```

**Flags explained:**
- `--reference-directories` — iCloud is the reference; duplicates found here are NOT flagged
- `--directories` — Google processed; duplicates found here ARE flagged for removal
- `--hash-type Xxh3` — fast 128-bit hash (not perceptual — exact byte match only)
- `--minimal-file-size 102400` — skip files under 100KB (thumbnails, screenshots)

**Important caveat — format differences:**
HEIC (iCloud) and JPEG (Google) of the same photo will NOT match by byte hash even if they
show the same image — different formats, different bytes. This means some duplicates won't be
caught by czkawka. Two options:

**Option A — Accept some duplicates in Google delta** (recommended)
Google JPEG duplicates of iCloud HEICs are lower quality anyway. Accept them into the delta;
Immich will show them separately. Use Immich's built-in "Find Duplicates" (admin panel) after
import to review visually and mark/remove the lower-quality copies.

**Option B — Date+size dedup before czkawka**
Run a pre-filter: find Google files whose capture date AND file size are within 5% of an iCloud
file. This catches HEIC↔JPEG pairs. Requires a custom script (see Appendix).

Start with Option A — it's simpler and Immich's dedup UI handles the remainder well.

---

## Phase 4: Copy Delta to google-delta/

```bash
mkdir -p /Volumes/HomeRAID/google-delta

# czkawka outputs a text file listing duplicate paths (one per line, grouped by hash).
# Extract ONLY the Google-processed paths that are flagged as duplicates:
grep "/google-processed/" /Volumes/HomeRAID/google-processed/duplicates.txt \
  | sort > /Volumes/HomeRAID/google-processed/duplicates-google-paths.txt

echo "Duplicate count (will be excluded from delta):"
wc -l /Volumes/HomeRAID/google-processed/duplicates-google-paths.txt

# Copy everything from google-processed that is NOT in the duplicates list.
# rsync with --exclude-from expects paths relative to source; use a wrapper script instead.

# Build the exclude list as absolute paths for rsync --exclude-from:
# (rsync exclude-from needs paths relative to the source dir — compute them)
SOURCE=/Volumes/HomeRAID/google-processed
while IFS= read -r dup; do
  # Make path relative to source
  echo "${dup#$SOURCE/}"
done < /Volumes/HomeRAID/google-processed/duplicates-google-paths.txt \
  > /Volumes/HomeRAID/google-processed/rsync-excludes.txt

# Dry run first
rsync -av --dry-run \
  --exclude-from=/Volumes/HomeRAID/google-processed/rsync-excludes.txt \
  /Volumes/HomeRAID/google-processed/ \
  /Volumes/HomeRAID/google-delta/ \
  2>&1 | tail -20

# Apply (remove --dry-run when satisfied)
rsync -av \
  --exclude-from=/Volumes/HomeRAID/google-processed/rsync-excludes.txt \
  /Volumes/HomeRAID/google-processed/ \
  /Volumes/HomeRAID/google-delta/ \
  2>&1 | tee /Volumes/HomeRAID/google-delta/rsync.log

echo "Delta file count:"
find /Volumes/HomeRAID/google-delta -type f | wc -l

echo "Delta size:"
du -sh /Volumes/HomeRAID/google-delta
```

---

## Phase 5: Add google-delta as Immich External Library

```bash
IMMICH_KEY=$(cat /Volumes/HomeRAID/immich/api-key.txt)

# Create a new external library for the Google delta
curl -X POST http://localhost:2283/api/libraries \
  -H "x-api-key: $IMMICH_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Google Photos Delta",
    "importPaths": ["/Volumes/HomeRAID/google-delta"],
    "exclusionPatterns": []
  }' | jq '{id, name, importPaths}'

# Note the library ID returned above, then trigger a scan:
GOOGLE_LIBRARY_ID="<id from above>"
curl -X POST "http://localhost:2283/api/libraries/$GOOGLE_LIBRARY_ID/scan" \
  -H "x-api-key: $IMMICH_KEY"
echo "Google delta scan triggered."
```

---

## Phase 6: Visual Dedup in Immich (HEIC/JPEG pairs)

After the Google library scan completes, run Immich's built-in duplicate finder to catch
format-different duplicates (HEIC from iCloud vs JPEG from Google):

1. Immich web UI → Administration → Jobs → **Duplicate Detection** → Run
2. After job completes: Administration → Duplicates
3. For each duplicate pair: keep the iCloud HEIC (higher quality), mark Google JPEG as trash
4. Empty trash when done

This handles the Option A caveat from Phase 3.

---

## Verification

```bash
IMMICH_KEY=$(cat /Volumes/HomeRAID/immich/api-key.txt)

# Asset counts per library
curl -s -H "x-api-key: $IMMICH_KEY" http://localhost:2283/api/libraries | \
  jq '.[] | {name, assetCount}'

# Total
curl -s -H "x-api-key: $IMMICH_KEY" \
  http://localhost:2283/api/server/statistics | jq '{photos, videos}'

# Sample 5 delta files — confirm GPS present (gpth should have written it)
find /Volumes/HomeRAID/google-delta -name "*.jpg" -o -name "*.mp4" | head -5 | while read f; do
  echo "--- $(basename "$f")"
  exiftool -fast2 -GPSLatitude -DateTimeOriginal "$f" 2>/dev/null | grep -E "GPS|Date" || echo "  no GPS/date"
done
```

---

## Expected Outcome

| Metric | Expected |
|--------|----------|
| Google-unique files in delta | 5–15% of total Google library |
| Files with GPS after gpth | ~80% (Google is good at GPS) |
| Duplicates found by Immich dedup | A few hundred HEIC/JPEG pairs |
| Additional assets in Immich after Google import | +1,000–10,000 (Google-only photos) |

---

## Appendix: Date+Size Pre-filter Script (Option B)

If the czkawka pass leaves too many HEIC/JPEG duplicates visible in Immich, run this
before Phase 4 to additionally exclude Google files that match iCloud files by date+filesize:

```bash
# Build iCloud file index: "YYYYMMDD_HHMMSS|size" → filepath
# (Run on Mac Mini — takes ~20 min for full library)
python3 - <<'EOF'
import os, subprocess, json
from collections import defaultdict

ICLOUD = "/Volumes/HomeRAID/icloud-export"
GOOGLE = "/Volumes/HomeRAID/google-processed"
OUT    = "/Volumes/HomeRAID/google-processed/date-size-duplicates.txt"

def get_datetime_size(path):
    """Return (datetime_str, size) for a file using exiftool."""
    r = subprocess.run(
        ["exiftool", "-fast2", "-DateTimeOriginal", "-FileSize#", "-j", path],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        return None, None
    data = json.loads(r.stdout)[0]
    dt = data.get("DateTimeOriginal", "")
    sz = data.get("FileSize", 0)
    return dt, sz

print("Building iCloud index...")
icloud_index = defaultdict(list)
for root, _, files in os.walk(ICLOUD):
    for f in files:
        if f.lower().endswith(('.heic', '.jpg', '.jpeg', '.mp4', '.mov')):
            dt, sz = get_datetime_size(os.path.join(root, f))
            if dt:
                icloud_index[dt].append(sz)

print(f"iCloud index: {len(icloud_index)} unique datetimes")

print("Scanning Google processed for date+size matches...")
found = 0
with open(OUT, "w") as out:
    for root, _, files in os.walk(GOOGLE):
        for f in files:
            path = os.path.join(root, f)
            dt, sz = get_datetime_size(path)
            if dt and dt in icloud_index:
                # Check if any iCloud file is within 10% in size
                for ics in icloud_index[dt]:
                    if abs(ics - sz) / max(ics, sz, 1) < 0.10:
                        out.write(path + "\n")
                        found += 1
                        break

print(f"Date+size duplicates found: {found} → {OUT}")
EOF
```

Then append `date-size-duplicates.txt` to `rsync-excludes.txt` before running Phase 4 rsync.
