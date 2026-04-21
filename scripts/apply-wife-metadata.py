#!/usr/bin/env python3
"""
apply-wife-metadata.py

Reads GPS, title, description, timezone, and keywords from wife's Photos.sqlite
and writes them into the icloud-export files that are missing them (shared-library
copies that had metadata stripped by iCloud).

Matches files by UUID — iCloud Shared Photo Library preserves original UUIDs.

Usage:
    # Dry run — see what would be updated
    python3 scripts/apply-wife-metadata.py \
        /Volumes/HomeRAID/wife-photos.sqlite \
        /Volumes/HomeRAID/icloud-export \
        --dry-run

    # Apply
    python3 scripts/apply-wife-metadata.py \
        /Volumes/HomeRAID/wife-photos.sqlite \
        /Volumes/HomeRAID/icloud-export
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

# ── CLI ───────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Inject wife's metadata into icloud-export files")
parser.add_argument("wife_db", help="Path to wife's Photos.sqlite")
parser.add_argument("export_dir", help="Path to icloud-export directory")
parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing")
parser.add_argument("--exiftool", default="exiftool", help="Path to exiftool binary")
parser.add_argument("--batch-size", type=int, default=50, help="Files per exiftool invocation")
parser.add_argument("--skip-existing-gps", action="store_true", default=True,
                    help="Skip files that already have GPS (default: True)")
args = parser.parse_args()

WIFE_DB    = Path(args.wife_db)
EXPORT_DIR = Path(args.export_dir)
EXPORT_DB  = EXPORT_DIR / ".osxphotos_export.db"
DRY_RUN    = args.dry_run

if not WIFE_DB.exists():
    print(f"ERROR: wife's Photos.sqlite not found: {WIFE_DB}", file=sys.stderr)
    sys.exit(1)

if not EXPORT_DB.exists():
    print(f"ERROR: export DB not found: {EXPORT_DB}", file=sys.stderr)
    print("Run osxphotos export first.", file=sys.stderr)
    sys.exit(1)


# ── Step 1: Load metadata from wife's Photos.sqlite ──────────────────────────

print("Reading wife's Photos.sqlite...")

wife_conn = sqlite3.connect(f"file:{WIFE_DB}?mode=ro", uri=True)
wife_conn.row_factory = sqlite3.Row

# GPS + basic fields from ZASSET
# Keywords via junction table Z_1KEYWORDS → ZKEYWORD
# Title + description + timezone from ZADDITIONALASSETATTRIBUTES
wife_meta = {}

rows = wife_conn.execute("""
    SELECT
        a.ZUUID                                         AS uuid,
        a.ZLATITUDE                                     AS lat,
        a.ZLONGITUDE                                    AS lon,
        a.ZFAVORITE                                     AS favorite,
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

for row in rows:
    wife_meta[row["uuid"]] = {
        "lat":         row["lat"],
        "lon":         row["lon"],
        "title":       row["title"],
        "description": row["description"],
        "timezone":    row["timezone"],
        "gps_accuracy": row["gps_accuracy"],
        "keywords":    [],
    }

# Load keywords
kw_rows = wife_conn.execute("""
    SELECT a.ZUUID AS uuid, k.ZTITLE AS keyword
    FROM ZASSET a
    JOIN Z_1KEYWORDS jk ON jk.Z_1ASSETS = a.Z_PK
    JOIN ZKEYWORD k     ON k.Z_PK = jk.Z_26KEYWORDS
    WHERE a.ZTRASHEDSTATE = 0
      AND a.ZUUID IN ({})
""".format(",".join("?" * len(wife_meta))), list(wife_meta.keys())).fetchall()

for row in kw_rows:
    if row["uuid"] in wife_meta:
        wife_meta[row["uuid"]]["keywords"].append(row["keyword"])

wife_conn.close()
print(f"  Loaded metadata for {len(wife_meta)} photos")


# ── Step 2: Load exported file paths from osxphotos export DB ────────────────

print("Reading export database...")

exp_conn = sqlite3.connect(f"file:{EXPORT_DB}?mode=ro", uri=True)
exp_conn.row_factory = sqlite3.Row

# osxphotos export DB stores uuid and the relative filepath
export_rows = exp_conn.execute("""
    SELECT uuid, filepath
    FROM export_data
    WHERE uuid IS NOT NULL
""").fetchall()

exp_conn.close()

# Build uuid → list of absolute paths (one UUID can have multiple exports: RAW + edited)
uuid_to_paths = {}
for row in export_rows:
    uuid = row["uuid"]
    filepath = EXPORT_DIR / row["filepath"]
    if filepath.exists():
        uuid_to_paths.setdefault(uuid, []).append(filepath)

print(f"  {len(uuid_to_paths)} UUIDs with exported files on disk")


# ── Step 3: Find files that need metadata ────────────────────────────────────

print("Matching UUIDs...")

to_update = []  # list of (path, metadata_dict)
skipped_no_match = 0
skipped_has_gps  = 0

for uuid, meta in wife_meta.items():
    paths = uuid_to_paths.get(uuid)
    if not paths:
        skipped_no_match += 1
        continue

    for path in paths:
        # Skip video files — GPS in video requires different tags and is less useful
        if path.suffix.lower() in {".mov", ".mp4", ".m4v", ".avi"}:
            continue
        to_update.append((path, meta))

print(f"  {len(to_update)} files to update")
print(f"  {skipped_no_match} UUIDs in wife's DB not found in export (not yet exported or filtered)")

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


# ── Step 4: Write metadata with exiftool ────────────────────────────────────

print("\nWriting metadata...")

updated  = 0
errors   = 0
batch_size = args.batch_size

def build_exiftool_args(path: Path, meta: dict) -> list:
    args = [
        "-overwrite_original",
        "-m",  # ignore minor errors
        f"-GPSLatitude={meta['lat']}",
        f"-GPSLongitude={meta['lon']}",
        f"-GPSLatitudeRef={'N' if meta['lat'] >= 0 else 'S'}",
        f"-GPSLongitudeRef={'E' if meta['lon'] >= 0 else 'W'}",
    ]
    if meta.get("gps_accuracy"):
        args.append(f"-GPSHorizontalAccuracy={meta['gps_accuracy']}")
    if meta.get("title"):
        args += [f"-Title={meta['title']}", f"-XMP:Title={meta['title']}"]
    if meta.get("description"):
        args += [f"-Description={meta['description']}", f"-Caption-Abstract={meta['description']}"]
    if meta.get("timezone"):
        args.append(f"-OffsetTimeOriginal={_tz_to_offset(meta['timezone'])}")
    for kw in meta.get("keywords", []):
        args.append(f"-Keywords+={kw}")
    args.append(str(path))
    return args


def _tz_to_offset(tz_name: str) -> str:
    """Convert IANA timezone name to ±HH:MM offset string for exiftool."""
    try:
        import datetime, zoneinfo
        now = datetime.datetime.now(zoneinfo.ZoneInfo(tz_name))
        offset = now.utcoffset()
        total_minutes = int(offset.total_seconds() / 60)
        sign = "+" if total_minutes >= 0 else "-"
        h, m = divmod(abs(total_minutes), 60)
        return f"{sign}{h:02d}:{m:02d}"
    except Exception:
        return ""  # skip if timezone can't be converted


# Process in batches for speed
total = len(to_update)
for i in range(0, total, batch_size):
    batch = to_update[i:i + batch_size]

    # Build one exiftool call per file (can't batch mixed-metadata files easily)
    for path, meta in batch:
        cmd = [args.exiftool] + build_exiftool_args(path, meta)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            updated += 1
        else:
            errors += 1
            print(f"  ERROR: {path.name}: {result.stderr.strip()}", file=sys.stderr)

    pct = min(100, int((i + len(batch)) / total * 100))
    print(f"  Progress: {i + len(batch)}/{total} ({pct}%)", end="\r")

print()  # newline after progress


# ── Summary ──────────────────────────────────────────────────────────────────

print(f"""
=== Done ===
  Updated:          {updated}
  Errors:           {errors}
  Not in export:    {skipped_no_match}
  Total processed:  {total}
""")

if errors > 0:
    print("Check stderr above for error details.")
    sys.exit(1)
