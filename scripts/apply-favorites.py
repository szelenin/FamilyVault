#!/usr/bin/env python3
"""
apply-favorites.py

Direct exiftool batch — writes XMP:Rating=5 to every photo flagged as favorite
in your iCloud Photos library, bypassing osxphotos's --favorite-rating flag.

Why this exists: osxphotos --favorite-rating writes Rating=5 for favorites AND
Rating=0 for non-favorites. The non-favorite branch forces a re-export of every
photo in the library (~80k files), which is unworkable on slow storage. This
script writes Rating=5 only to favorites — the ~1,800-2,000 photos that
matter — and leaves the rest untouched. Immich treats "Rating absent" the same
as Rating=0.

Usage:
    python3 scripts/apply-favorites.py
    python3 scripts/apply-favorites.py --dry-run
    python3 scripts/apply-favorites.py --library /path/to/Photos.photoslibrary --export /path/to/icloud-export
"""

import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

DEFAULT_LIBRARY = "/Volumes/HomeRAID/Photos Library.photoslibrary"
DEFAULT_EXPORT = "/Volumes/HomeRAID/icloud-export"
EXIFTOOL = "/opt/homebrew/bin/exiftool"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.strip().split("\n", 1)[0])
    p.add_argument("--library", default=DEFAULT_LIBRARY)
    p.add_argument("--export", default=DEFAULT_EXPORT)
    p.add_argument("--dry-run", action="store_true", help="Print what would change; do not write.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    photos_db = Path(args.library) / "database" / "Photos.sqlite"
    export_db = Path(args.export) / ".osxphotos_export.db"

    if not photos_db.exists():
        print(f"ERROR: Photos.sqlite not found: {photos_db}", file=sys.stderr)
        return 2
    if not export_db.exists():
        print(f"ERROR: osxphotos export DB not found: {export_db}", file=sys.stderr)
        return 2
    if not Path(EXIFTOOL).exists():
        print(f"ERROR: exiftool not found at {EXIFTOOL}", file=sys.stderr)
        return 2

    # 1. Get UUIDs of every favorited shared-library photo
    photos_uri = f"file:{quote(str(photos_db))}?mode=ro"
    with sqlite3.connect(photos_uri, uri=True) as conn:
        rows = conn.execute(
            "SELECT ZUUID FROM ZASSET "
            "WHERE ZTRASHEDSTATE=0 "
            "  AND ZLIBRARYSCOPESHARESTATE!=0 "
            "  AND ZFAVORITE=1"
        ).fetchall()
    favorite_uuids = [r[0] for r in rows]
    print(f"Library favorites in shared scope: {len(favorite_uuids)}")

    # 2. Resolve each UUID to its export file path
    files: list[Path] = []
    missing_uuids = []
    with sqlite3.connect(str(export_db)) as conn:
        for uuid in favorite_uuids:
            row = conn.execute(
                "SELECT filepath FROM export_data WHERE uuid=? LIMIT 1", (uuid,)
            ).fetchone()
            if not row:
                missing_uuids.append(uuid)
                continue
            full = Path(args.export) / row[0]
            if full.exists():
                files.append(full)
            else:
                missing_uuids.append(uuid)
    print(f"Resolved to existing exported files: {len(files)}")
    if missing_uuids:
        print(f"  ({len(missing_uuids)} favorites not in export — likely raw DNG or hidden)")

    if args.dry_run:
        print("\n=== DRY RUN — no files modified ===")
        for f in files[:10]:
            print(f"  Would write XMP:Rating=5 to: {f}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more")
        return 0

    # 3. Batch exiftool — pass all files in one invocation; exiftool is much
    # faster when it doesn't fork-per-file.
    print(f"\nWriting XMP:Rating=5 to {len(files)} files via exiftool...")
    if not files:
        return 0

    # exiftool's "-@ -" mode reads file paths from stdin (fastest for large lists).
    cmd = [
        EXIFTOOL,
        "-overwrite_original",
        "-XMP:Rating=5",
        "-q",  # quiet
        "-progress",
        "-@",
        "-",
    ]
    proc = subprocess.run(
        cmd,
        input="\n".join(str(f) for f in files),
        text=True,
        capture_output=True,
    )
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print("--- exiftool stderr ---", file=sys.stderr)
        print(proc.stderr, file=sys.stderr)

    if proc.returncode != 0:
        print(f"ERROR: exiftool exited {proc.returncode}", file=sys.stderr)
        return 1

    print(f"Done: wrote XMP:Rating=5 to {len(files)} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
