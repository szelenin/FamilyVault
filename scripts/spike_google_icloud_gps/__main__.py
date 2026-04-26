"""CLI entry for the Google-vs-iCloud GPS spike. Orchestrates phases A, B+C, D."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from .parser import walk_sidecars
from .stats import compute_baseline, should_proceed_to_matching
from .matcher import IcloudIndex, evaluate_photo
from .reporter import write_results_csv, write_summary_report
from .sampler import stratified_sample

DEFAULT_EXTRACTED = Path("/Volumes/HomeRAID/google-extracted/account1")
DEFAULT_ICLOUD_LIBRARY = Path("/Volumes/HomeRAID/Photos Library.photoslibrary")
DEFAULT_EXPORT_DIR = Path("/Volumes/HomeRAID/icloud-export")
DEFAULT_OUT_DIR = Path("docs/spike")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--extracted", type=Path, default=DEFAULT_EXTRACTED)
    p.add_argument("--library", type=Path, default=DEFAULT_ICLOUD_LIBRARY)
    p.add_argument("--export", type=Path, default=DEFAULT_EXPORT_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--phase", choices=["A", "BC", "D", "all"], default="all")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    # Filter to PHOTO sidecars only — Google Takeout has non-photo metadata
    # files (album-titles, user-generated-memory-titles, etc.) whose `title`
    # field is a list or empty. Real photo sidecars have a string title that
    # ends in a media extension.
    all_sidecars = list(walk_sidecars(args.extracted))
    media_exts = (".heic", ".jpg", ".jpeg", ".png", ".mov", ".mp4", ".dng", ".tiff", ".tif", ".gif")
    sidecars = [
        s for s in all_sidecars
        if isinstance(s["title"], str) and s["title"].lower().endswith(media_exts)
    ]
    skipped = len(all_sidecars) - len(sidecars)
    print(f"Phase A: parsed {len(all_sidecars)} sidecars from {args.extracted}; "
          f"{len(sidecars)} are photo/video sidecars ({skipped} non-photo skipped)")
    baseline = compute_baseline(sidecars)
    print(f"  total={baseline['total']}  with_geodata={baseline['with_geodata']}  "
          f"geodata_differs_from_exif={baseline['geodata_differs_from_exif']}")
    if args.phase == "A":
        return 0
    if not should_proceed_to_matching(baseline):
        print("Phase A decision gate: hypothesis weak (geoData ≈ geoDataExif). "
              "Stopping. No matching performed.")
        write_summary_report(
            args.out / "2026-04-26-google-vs-icloud-gps-report.md",
            baseline=baseline,
            rows=[],
        )
        return 0

    photos_db = args.library / "database" / "Photos.sqlite"
    export_db = args.export / ".osxphotos_export.db"
    print(f"Phase B+C: building iCloud index from {photos_db.name}")
    idx = IcloudIndex(photos_db=photos_db, export_db=export_db)

    rows: list = []
    for i, sc in enumerate(sidecars, 1):
        if i % 200 == 0:
            print(f"  evaluating {i}/{len(sidecars)}...")
        # Google Takeout sidecars are named "<photo>.supplemental-metadata.json"
        # Strip the suffix to derive the photo path.
        google_path = None
        if sc["sidecar_path"]:
            sidecar_str = str(sc["sidecar_path"])
            if sidecar_str.endswith(".supplemental-metadata.json"):
                google_path = Path(sidecar_str[:-len(".supplemental-metadata.json")])
            else:
                google_path = sc["sidecar_path"].with_suffix("")
            # Confirm the path actually exists on disk; otherwise leave as None
            if not google_path.exists():
                google_path = None
        candidates = idx.find_by_filename(sc["title"])
        rows.extend(evaluate_photo(sidecar=sc, google_path=google_path, icloud_candidates=candidates))

    results_path = args.out / "2026-04-26-google-vs-icloud-gps-results.csv"
    report_path = args.out / "2026-04-26-google-vs-icloud-gps-report.md"
    write_results_csv(results_path, rows)
    write_summary_report(report_path, baseline=baseline, rows=rows)
    print(f"Phase B+C: wrote {len(rows)} rows to {results_path.name}")

    if args.phase == "BC":
        return 0

    review_path = args.out / "2026-04-26-google-vs-icloud-gps-review.csv"
    sampled = stratified_sample(rows)
    write_results_csv(review_path, sampled)
    print(f"Phase D: wrote {len(sampled)} sampled rows to {review_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
