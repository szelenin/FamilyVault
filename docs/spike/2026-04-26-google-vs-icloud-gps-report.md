# Spike Report: Google Takeout vs iCloud GPS Coverage

## Phase A — Baseline (from Google JSON sidecars)

- Total photos in archive: 973
- Photos with geoData (Google's lat/lon): 742
- Photos where geoData differs from geoDataExif: 7
  (= Google's net contribution beyond original EXIF)

## Phase B+C — Per-photo evaluation

- Total rows produced: 2367
- Matched to iCloud (any confidence): 1890
- High confidence (>=0.85): 0
- Medium confidence (0.50-0.85): 0
- Low confidence (>0, <0.50): 1890
- Unmatched (Google-only candidates): 477

## The headline number

- **GPS gap rows: 1686** photos where Google has GPS and iCloud lacks it.

(Each row is one Google-photo / iCloud-candidate pair; a single Google photo
can produce multiple rows if it has multiple candidates.)

## Next step

- Generate stratified sample for manual review:
  `python3 -m scripts.spike_google_icloud_gps --phase D`

- Open `2026-04-26-google-vs-icloud-gps-results.csv` in a spreadsheet
  and sort by `composite_confidence` to inspect.
