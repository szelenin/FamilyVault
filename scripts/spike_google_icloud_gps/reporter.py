"""CSV results writer + markdown summary report generator."""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterable, Mapping


RESULT_COLUMNS: list = [
    "google_title", "google_path",
    "icloud_uuid", "icloud_filepath",
    "s1_name_match", "s2_date_diff_seconds",
    "s3_size_match", "s4_dim_match", "s5_is_original",
    "s6_hash_db_match", "s7_sha256_match", "s8_phash_distance",
    "google_geo_lat", "google_geo_lon",
    "icloud_lat", "icloud_lon",
    "gps_gap", "composite_confidence",
]


def write_results_csv(out_path: Path, rows: Iterable[Mapping]) -> None:
    """Write per-photo evaluation rows to a CSV with stable column order."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in RESULT_COLUMNS})


def write_summary_report(
    out_path: Path,
    baseline: Mapping,
    rows: list,
) -> None:
    """Build the human-readable spike report from baseline stats + evaluation rows."""
    total = len(rows)
    matched = sum(1 for r in rows if r.get("icloud_uuid") is not None)
    high = sum(1 for r in rows if (r.get("composite_confidence") or 0) >= 0.85)
    medium = sum(1 for r in rows if 0.50 <= (r.get("composite_confidence") or 0) < 0.85)
    low = sum(1 for r in rows if 0 < (r.get("composite_confidence") or 0) < 0.50)
    unmatched = sum(1 for r in rows if (r.get("composite_confidence") or 0) == 0)
    gps_gap_count = sum(1 for r in rows if r.get("gps_gap"))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"""# Spike Report: Google Takeout vs iCloud GPS Coverage

## Phase A — Baseline (from Google JSON sidecars)

- Total photos in archive: {baseline['total']}
- Photos with geoData (Google's lat/lon): {baseline['with_geodata']}
- Photos where geoData differs from geoDataExif: {baseline['geodata_differs_from_exif']}
  (= Google's net contribution beyond original EXIF)

## Phase B+C — Per-photo evaluation

- Total rows produced: {total}
- Matched to iCloud (any confidence): {matched}
- High confidence (>=0.85): {high}
- Medium confidence (0.50-0.85): {medium}
- Low confidence (>0, <0.50): {low}
- Unmatched (Google-only candidates): {unmatched}

## The headline number

- **GPS gap rows: {gps_gap_count}** photos where Google has GPS and iCloud lacks it.

(Each row is one Google-photo / iCloud-candidate pair; a single Google photo
can produce multiple rows if it has multiple candidates.)

## Next step

- Generate stratified sample for manual review:
  `python3 -m scripts.spike_google_icloud_gps --phase D`

- Open `2026-04-26-google-vs-icloud-gps-results.csv` in a spreadsheet
  and sort by `composite_confidence` to inspect.
""")
