#!/usr/bin/env python3
"""
infer-gps.py — GPS temporal nearest-neighbor inference for shared library copies.

Shared iCloud library photos with a "(1)" suffix often lack GPS because iCloud
strips location from the copied file. This script finds those files, locates the
nearest-in-time photo WITH GPS from the same export tree, and writes that GPS
to the GPS-less file via exiftool (only if within MAX_SECONDS_GAP).

Usage:
    python3 scripts/infer-gps.py /Volumes/HomeRAID/icloud-export [--dry-run] [--max-gap 3600]

Requirements:
    brew install exiftool   (uses exiftool CLI via subprocess — no pip packages needed)
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


MAX_SECONDS_GAP_DEFAULT = 3600  # 1 hour — don't infer GPS across too large a time gap
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".heic", ".png", ".mov", ".mp4", ".dng", ".raw", ".tiff"}


def parse_args():
    p = argparse.ArgumentParser(description="Infer GPS for shared-library copies that lack location.")
    p.add_argument("export_dir", help="Root of the osxphotos export tree")
    p.add_argument("--dry-run", action="store_true", help="Print what would be done without writing")
    p.add_argument("--max-gap", type=int, default=MAX_SECONDS_GAP_DEFAULT,
                   help=f"Max seconds between source and target photo (default: {MAX_SECONDS_GAP_DEFAULT})")
    p.add_argument("--batch-size", type=int, default=500,
                   help="Number of files to feed to exiftool per invocation (default: 500)")
    return p.parse_args()


def collect_files(export_dir: Path) -> list[Path]:
    """Walk the export tree and collect all supported media files."""
    files = []
    for root, _, filenames in os.walk(export_dir):
        for fname in filenames:
            if Path(fname).suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(Path(root) / fname)
    return files


def read_exif_batch(files: list[Path]) -> list[dict]:
    """Read DateTimeOriginal + GPS from a batch of files via exiftool JSON output."""
    if not files:
        return []
    cmd = [
        "exiftool", "-json", "-fast2",
        "-DateTimeOriginal", "-GPSLatitude#", "-GPSLongitude#", "-GPSAltitude#",
        "-m",  # ignore minor errors
    ] + [str(f) for f in files]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):  # 1 = minor warnings, still OK
        print(f"Warning: exiftool returned {result.returncode}", file=sys.stderr)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def parse_datetime(dt_str: str | None) -> int | None:
    """Parse exiftool DateTimeOriginal string to Unix timestamp."""
    if not dt_str:
        return None
    import re
    from datetime import datetime, timezone
    # Format: "2023:07:15 14:32:05" or "2023:07:15 14:32:05+02:00"
    m = re.match(r"(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})", dt_str)
    if not m:
        return None
    try:
        dt = datetime(*[int(x) for x in m.groups()], tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        return None


def is_shared_copy(path: Path) -> bool:
    """Heuristic: shared library copies often have ' (1)' before the extension."""
    stem = path.stem
    return stem.endswith(" (1)") or stem.endswith("_(1)")


def write_gps(target: Path, lat: float, lon: float, alt: float | None, dry_run: bool) -> bool:
    """Write GPS coordinates to a file via exiftool."""
    args = [
        "exiftool",
        "-overwrite_original",
        "-m",
        f"-GPSLatitude={abs(lat)}",
        f"-GPSLatitudeRef={'N' if lat >= 0 else 'S'}",
        f"-GPSLongitude={abs(lon)}",
        f"-GPSLongitudeRef={'E' if lon >= 0 else 'W'}",
    ]
    if alt is not None:
        args += [f"-GPSAltitude={abs(alt)}", f"-GPSAltitudeRef={'0' if alt >= 0 else '1'}"]
    args.append(str(target))

    if dry_run:
        print(f"  [DRY-RUN] Would write GPS ({lat:.5f}, {lon:.5f}) to {target}")
        return True

    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        print(f"  Error writing GPS to {target}: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def main():
    args = parse_args()
    export_dir = Path(args.export_dir)

    if not export_dir.is_dir():
        print(f"Error: directory not found: {export_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {export_dir} ...")
    all_files = collect_files(export_dir)
    print(f"Found {len(all_files):,} media files")

    # Read EXIF in batches
    print("Reading EXIF metadata (this may take a few minutes) ...")
    exif_data: dict[Path, dict] = {}
    batch_size = args.batch_size
    for i in range(0, len(all_files), batch_size):
        batch = all_files[i:i + batch_size]
        records = read_exif_batch(batch)
        for rec in records:
            src_path = Path(rec.get("SourceFile", ""))
            exif_data[src_path] = rec
        done = min(i + batch_size, len(all_files))
        print(f"  {done:,}/{len(all_files):,} files read...", end="\r")
    print()

    # Build index: timestamp → (lat, lon, alt) for files WITH GPS
    print("Building GPS index ...")
    gps_index: list[tuple[int, float, float, float | None]] = []  # (ts, lat, lon, alt)
    for path, rec in exif_data.items():
        lat = rec.get("GPSLatitude")
        lon = rec.get("GPSLongitude")
        ts = parse_datetime(rec.get("DateTimeOriginal"))
        if lat is not None and lon is not None and ts is not None:
            alt = rec.get("GPSAltitude")
            gps_index.append((ts, float(lat), float(lon), float(alt) if alt is not None else None))

    gps_index.sort(key=lambda x: x[0])
    print(f"GPS index: {len(gps_index):,} photos with location")

    if not gps_index:
        print("No photos with GPS found — nothing to infer from.")
        sys.exit(0)

    # Find shared copies without GPS
    candidates = []
    for path, rec in exif_data.items():
        if not is_shared_copy(path):
            continue
        lat = rec.get("GPSLatitude")
        lon = rec.get("GPSLongitude")
        if lat is not None and lon is not None:
            continue  # already has GPS
        ts = parse_datetime(rec.get("DateTimeOriginal"))
        if ts is None:
            continue  # no timestamp — can't infer
        candidates.append((path, ts))

    print(f"Candidates without GPS: {len(candidates):,}")
    if not candidates:
        print("All shared copies already have GPS. Nothing to do.")
        sys.exit(0)

    # Binary search helper
    import bisect
    timestamps = [g[0] for g in gps_index]

    updated = 0
    skipped_gap = 0
    skipped_error = 0

    for path, ts in candidates:
        # Find nearest GPS entry by timestamp
        idx = bisect.bisect_left(timestamps, ts)
        best = None
        best_diff = float("inf")

        for candidate_idx in [idx - 1, idx]:
            if 0 <= candidate_idx < len(gps_index):
                diff = abs(gps_index[candidate_idx][0] - ts)
                if diff < best_diff:
                    best_diff = diff
                    best = gps_index[candidate_idx]

        if best is None or best_diff > args.max_gap:
            skipped_gap += 1
            continue

        _, lat, lon, alt = best
        ok = write_gps(path, lat, lon, alt, args.dry_run)
        if ok:
            updated += 1
            if not args.dry_run:
                print(f"  GPS inferred ({lat:.4f}, {lon:.4f}, gap={best_diff}s) → {path.name}")
        else:
            skipped_error += 1

    print()
    print("=== Summary ===")
    print(f"Updated:        {updated:,}")
    print(f"Skipped (gap):  {skipped_gap:,}  (nearest GPS > {args.max_gap}s away)")
    print(f"Skipped (err):  {skipped_error:,}")
    if args.dry_run:
        print("(dry-run mode — no files were modified)")


if __name__ == "__main__":
    main()
