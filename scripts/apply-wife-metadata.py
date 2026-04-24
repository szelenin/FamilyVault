#!/usr/bin/env python3
"""
apply-wife-metadata.py

Reads GPS, title, description, timezone, and keywords from wife's Photos.sqlite
and writes them into the icloud-export files that are missing them (shared-library
copies that had metadata stripped by iCloud).

Matching strategy: wife's DB uses UUID-based internal filenames (Optimize Storage),
so UUID matching is impossible. Instead we match by capture date (ZDATECREATED):

  wife's DB (date → GPS)
      → shared library DB (date → UUID)
      → export DB (UUID → filepath)

Usage:
    python3 scripts/apply-wife-metadata.py \
        "/Volumes/HomeRAID/alice/Photos Library.photoslibrary/database/Photos.sqlite" \
        /Volumes/HomeRAID/icloud-export \
        --shared-db "/Volumes/HomeRAID/Photos Library.photoslibrary/database/Photos.sqlite" \
        --dry-run

    # Apply
    python3 scripts/apply-wife-metadata.py \
        "/Volumes/HomeRAID/alice/Photos Library.photoslibrary/database/Photos.sqlite" \
        /Volumes/HomeRAID/icloud-export \
        --shared-db "/Volumes/HomeRAID/Photos Library.photoslibrary/database/Photos.sqlite"
"""

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

# ── CLI ───────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Inject wife's metadata into icloud-export files")
parser.add_argument("wife_db", help="Path to wife's Photos.sqlite")
parser.add_argument("export_dir", help="Path to icloud-export directory")
parser.add_argument("--shared-db", help="Path to shared/your Photos.sqlite (UUID bridge)",
                    default="/Volumes/HomeRAID/Photos Library.photoslibrary/database/Photos.sqlite")
parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing")
parser.add_argument("--exiftool", default="/opt/homebrew/bin/exiftool", help="Path to exiftool binary")
parser.add_argument("--date-tolerance", type=float, default=0.5,
                    help="Max seconds difference for date match (default: 0.5)")
args = parser.parse_args()

WIFE_DB    = Path(args.wife_db)
EXPORT_DIR = Path(args.export_dir)
SHARED_DB  = Path(args.shared_db)
EXPORT_DB  = EXPORT_DIR / ".osxphotos_export.db"
DRY_RUN    = args.dry_run
TOL        = args.date_tolerance

for label, path in [("wife_db", WIFE_DB), ("shared_db", SHARED_DB), ("export_db", EXPORT_DB)]:
    if not path.exists():
        print(f"ERROR: {label} not found: {path}", file=sys.stderr)
        sys.exit(1)


# ── Step 1: Load GPS metadata from wife's Photos.sqlite ──────────────────────

print("Reading wife's Photos.sqlite...")

wife_conn = sqlite3.connect(f"file:{str(WIFE_DB).replace(' ', '%20')}?mode=ro", uri=True)
wife_conn.row_factory = sqlite3.Row

rows = wife_conn.execute("""
    SELECT
        a.ZDATECREATED                                  AS date,
        a.ZLATITUDE                                     AS lat,
        a.ZLONGITUDE                                    AS lon,
        aa.ZTITLE                                       AS title,
        aa.ZASSETDESCRIPTION                            AS description,
        aa.ZTIMEZONENAME                                AS timezone,
        aa.ZGPSHORIZONTALACCURACY                       AS gps_accuracy
    FROM ZASSET a
    LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON aa.Z_PK = a.ZADDITIONALATTRIBUTES
    WHERE a.ZTRASHEDSTATE = 0
      AND a.ZLATITUDE IS NOT NULL
      AND a.ZLATITUDE != -180.0
""").fetchall()

print(f"  {len(rows)} photos with GPS in wife's library")

# Index by date (rounded to nearest 0.5s to handle float precision)
# date → list of meta dicts (multiple shots at same timestamp = burst)
wife_by_date = {}
for row in rows:
    d = round(row["date"] / TOL) * TOL
    meta = {
        "lat":          row["lat"],
        "lon":          row["lon"],
        "title":        row["title"],
        "description":  row["description"],
        "timezone":     row["timezone"],
        "gps_accuracy": row["gps_accuracy"],
        "keywords":     [],
    }
    wife_by_date.setdefault(d, []).append(meta)

# Load keywords
try:
    kw_rows = wife_conn.execute("""
        SELECT a.ZDATECREATED AS date, k.ZTITLE AS keyword
        FROM ZASSET a
        JOIN ZADDITIONALASSETATTRIBUTES aa ON aa.Z_PK = a.ZADDITIONALATTRIBUTES
        JOIN Z_1KEYWORDS jk ON jk.Z_1ASSETATTRIBUTES = aa.Z_PK
        JOIN ZKEYWORD k     ON k.Z_PK = jk.Z_52KEYWORDS
        WHERE a.ZTRASHEDSTATE = 0
          AND a.ZLATITUDE IS NOT NULL AND a.ZLATITUDE != -180.0
    """).fetchall()
except Exception:
    kw_rows = wife_conn.execute("""
        SELECT a.ZDATECREATED AS date, k.ZTITLE AS keyword
        FROM ZASSET a
        JOIN Z_1KEYWORDS jk ON jk.Z_1ASSETS = a.Z_PK
        JOIN ZKEYWORD k     ON k.Z_PK = jk.Z_26KEYWORDS
        WHERE a.ZTRASHEDSTATE = 0
          AND a.ZLATITUDE IS NOT NULL AND a.ZLATITUDE != -180.0
    """).fetchall()

for row in kw_rows:
    d = round(row["date"] / TOL) * TOL
    for meta in wife_by_date.get(d, []):
        if row["keyword"] not in meta["keywords"]:
            meta["keywords"].append(row["keyword"])

wife_conn.close()
print(f"  Indexed {len(wife_by_date)} distinct capture times with GPS")


# ── Step 2: Bridge date → UUID via shared library Photos.sqlite ───────────────

print("Reading shared library DB (date → UUID bridge)...")

shared_conn = sqlite3.connect(f"file:{str(SHARED_DB).replace(' ', '%20')}?mode=ro", uri=True)
shared_conn.row_factory = sqlite3.Row

shared_rows = shared_conn.execute("""
    SELECT ZUUID AS uuid, ZDATECREATED AS date, ZLATITUDE AS lat
    FROM ZASSET
    WHERE ZTRASHEDSTATE = 0
      AND (ZLATITUDE IS NULL OR ZLATITUDE = -180.0)
""").fetchall()
shared_conn.close()

print(f"  {len(shared_rows)} shared-library assets without GPS (candidates)")

# For each shared asset without GPS, look up wife's GPS by date
date_to_uuid_meta = {}   # uuid → meta
ambiguous = 0
no_match  = 0

for row in shared_rows:
    d = round(row["date"] / TOL) * TOL
    candidates = wife_by_date.get(d, [])
    if len(candidates) == 0:
        no_match += 1
    elif len(candidates) == 1:
        date_to_uuid_meta[row["uuid"]] = candidates[0]
    else:
        # Ambiguous — multiple wife photos at same timestamp (burst). Skip for safety.
        ambiguous += 1

print(f"  Matched: {len(date_to_uuid_meta)}  |  Ambiguous (skipped): {ambiguous}  |  No match: {no_match}")


# ── Step 3: Load exported file paths from osxphotos export DB ────────────────

print("Reading export database...")

exp_conn = sqlite3.connect(str(EXPORT_DB))
exp_conn.row_factory = sqlite3.Row

export_rows = exp_conn.execute("""
    SELECT uuid, filepath
    FROM export_data
    WHERE uuid IS NOT NULL
""").fetchall()

exp_conn.close()

uuid_to_paths = {}
for row in export_rows:
    uuid = row["uuid"]
    if uuid not in date_to_uuid_meta:
        continue
    filepath = EXPORT_DIR / row["filepath"]
    if filepath.exists():
        uuid_to_paths.setdefault(uuid, []).append(filepath)

print(f"  {len(uuid_to_paths)} matched UUIDs have exported files on disk")


# ── Step 4: Build update list ─────────────────────────────────────────────────

to_update = []  # list of (path, meta)

SKIP_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".json", ".xmp"}

for uuid, meta in date_to_uuid_meta.items():
    paths = uuid_to_paths.get(uuid, [])
    for path in paths:
        if path.suffix.lower() in SKIP_EXTENSIONS:
            continue  # skip video and sidecars — write GPS to media files only
        to_update.append((path, meta))

print(f"  {len(to_update)} photo files to update with GPS")

if DRY_RUN:
    print("\n=== DRY RUN — no files will be modified ===\n")
    for path, meta in to_update[:20]:
        print(f"  Would update: {path.name}")
        print(f"    GPS: {meta['lat']:.6f}, {meta['lon']:.6f}")
        if meta["title"]:       print(f"    Title: {meta['title']}")
        if meta["description"]: print(f"    Description: {meta['description']}")
        if meta["timezone"]:    print(f"    Timezone: {meta['timezone']}")
        if meta["keywords"]:    print(f"    Keywords: {', '.join(meta['keywords'])}")
    if len(to_update) > 20:
        print(f"  ... and {len(to_update) - 20} more")
    print(f"\nWould update {len(to_update)} files. Re-run without --dry-run to apply.")
    sys.exit(0)


# ── Step 5: Write metadata with exiftool ─────────────────────────────────────

print("\nWriting metadata...")

updated = 0
errors  = 0
total   = len(to_update)


def _tz_to_offset(tz_name: str) -> str:
    try:
        import datetime, zoneinfo
        now = datetime.datetime.now(zoneinfo.ZoneInfo(tz_name))
        offset = now.utcoffset()
        total_minutes = int(offset.total_seconds() / 60)
        sign = "+" if total_minutes >= 0 else "-"
        h, m = divmod(abs(total_minutes), 60)
        return f"{sign}{h:02d}:{m:02d}"
    except Exception:
        return ""


def build_exiftool_args(path: Path, meta: dict) -> list:
    cmd = [
        "-overwrite_original", "-m",
        f"-GPSLatitude={meta['lat']}",
        f"-GPSLongitude={meta['lon']}",
        f"-GPSLatitudeRef={'N' if meta['lat'] >= 0 else 'S'}",
        f"-GPSLongitudeRef={'E' if meta['lon'] >= 0 else 'W'}",
    ]
    if meta.get("title"):
        cmd += [f"-Title={meta['title']}", f"-XMP:Title={meta['title']}"]
    if meta.get("description"):
        cmd += [f"-Description={meta['description']}", f"-Caption-Abstract={meta['description']}"]
    if meta.get("timezone"):
        offset = _tz_to_offset(meta["timezone"])
        if offset:
            cmd.append(f"-OffsetTimeOriginal={offset}")
    for kw in meta.get("keywords", []):
        cmd.append(f"-Keywords+={kw}")
    cmd.append(str(path))
    return cmd


for i, (path, meta) in enumerate(to_update):
    cmd = [args.exiftool] + build_exiftool_args(path, meta)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        updated += 1
    else:
        errors += 1
        print(f"  ERROR: {path.name}: {result.stderr.strip()}", file=sys.stderr)

    if (i + 1) % 100 == 0 or (i + 1) == total:
        pct = int((i + 1) / total * 100)
        print(f"  Progress: {i+1}/{total} ({pct}%)", end="\r")

print()

print(f"""
=== Done ===
  Updated:          {updated}
  Errors:           {errors}
  Total processed:  {total}
""")

if errors > 0:
    print("Check stderr above for error details.")
    sys.exit(1)
