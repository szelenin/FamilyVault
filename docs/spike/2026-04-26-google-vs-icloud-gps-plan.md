# Google vs iCloud GPS Spike — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python matcher that, given one extracted Google Takeout archive and the existing iCloud library, evaluates 8 signals per photo (name, date, size, dim, is_original, hash_db, sha256, phash) plus a composite confidence, writes a per-photo CSV plus a human-readable report, and produces a stratified sample for manual review.

**Architecture:** A small Python sub-package under `scripts/spike_google_icloud_gps/` with one module per concern (parser, stats, signals, matcher, reporter, sampler). Each module is tested independently with synthetic fixtures (pytest); the integration is verified by running the matcher against a real extracted archive once everything is unit-green.

**Tech Stack:** Python 3.13 (already on Mac Mini), `Pillow` + `imagehash` (perceptual hashing), `pytest` (already used by the project per constitution), `sqlite3` stdlib, `exiftool` subprocess, plain Python CSV writer.

---

## File Structure

```
scripts/spike_google_icloud_gps/
├── __init__.py            # package marker
├── __main__.py            # CLI entry: orchestrates Phase A → B+C → D
├── parser.py              # JSON sidecar parsing → in-memory dict
├── stats.py               # Phase A baseline counters + decision gate
├── signals.py             # The 8 signal computations + composite confidence
├── matcher.py             # Per-photo evaluation orchestrator
├── reporter.py            # CSV writer + markdown report generator
└── sampler.py             # Stratified sampling for manual review

tests/spike_google_icloud_gps/
├── __init__.py
├── conftest.py            # pytest fixtures (synthetic Google + iCloud rows)
├── test_parser.py
├── test_stats.py
├── test_signals.py
├── test_matcher.py
├── test_reporter.py
└── test_sampler.py
```

Reasoning for split:
- **parser, stats** are Phase A only. Pure functions over JSON dicts. Trivial to unit-test.
- **signals** has 8 distinct functions, each with its own decision rule. One file groups them; one test class per signal.
- **matcher** is the only place that does I/O against the real Photos.sqlite + export DB + filesystem. Wraps signals.
- **reporter** is the only place that knows about the CSV column order and report markdown. Wraps writers.
- **sampler** is independent — it reads the CSV, picks rows by stratum, writes a smaller CSV.

Each module under 150 LOC. The test files mirror the source layout 1:1.

Output artifacts go to `docs/spike/`:
- `2026-04-26-google-vs-icloud-gps-results.csv` — every (Google, iCloud-candidate) pair
- `2026-04-26-google-vs-icloud-gps-report.md` — human report
- `2026-04-26-google-vs-icloud-gps-review.csv` — 100 sampled rows for user review (after Phase D)

---

## Phase 0: Setup

### Task 0.1: Install Python dependencies

**Files:**
- No new files. Verify Python 3.13 is available; install Pillow + imagehash.

- [ ] **Step 1: Verify Python 3.13 + pytest**

```bash
python3 --version
python3 -m pytest --version
```

Expected: `Python 3.13.x` and `pytest 8.x` (already on Mac Mini per CLAUDE.md).

- [ ] **Step 2: Install Pillow and imagehash**

```bash
pip3 install Pillow imagehash
```

Expected: `Successfully installed pillow-... imagehash-...`

- [ ] **Step 3: Verify imports work**

```bash
python3 -c "from PIL import Image; import imagehash; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit (no code changes; just confirming env)**

No commit; this is environment setup only.

### Task 0.2: Create the package skeleton

**Files:**
- Create: `scripts/spike_google_icloud_gps/__init__.py`
- Create: `scripts/spike_google_icloud_gps/__main__.py`
- Create: `tests/spike_google_icloud_gps/__init__.py`
- Create: `tests/spike_google_icloud_gps/conftest.py`

- [ ] **Step 1: Create empty package markers**

```bash
mkdir -p scripts/spike_google_icloud_gps tests/spike_google_icloud_gps
touch scripts/spike_google_icloud_gps/__init__.py tests/spike_google_icloud_gps/__init__.py
```

- [ ] **Step 2: Write `__main__.py` skeleton**

Path: `scripts/spike_google_icloud_gps/__main__.py`

```python
"""CLI entry for the Google-vs-iCloud GPS spike. Orchestrates phases A, B+C, D."""
import argparse
import sys
from pathlib import Path

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
    print(f"spike: extracted={args.extracted} library={args.library}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Write `conftest.py` with shared fixtures**

Path: `tests/spike_google_icloud_gps/conftest.py`

```python
"""Shared pytest fixtures: synthetic Google sidecars and iCloud rows."""
from __future__ import annotations
import pytest


@pytest.fixture
def google_photo_with_gps() -> dict:
    return {
        "title": "IMG_2910.HEIC",
        "photoTakenTime": {"timestamp": "1694973809"},
        "geoData": {"latitude": 25.7264, "longitude": -80.2414, "altitude": 0.0},
        "geoDataExif": {"latitude": 25.7264, "longitude": -80.2414, "altitude": 0.0},
    }


@pytest.fixture
def google_photo_no_gps() -> dict:
    return {
        "title": "IMG_0001.JPG",
        "photoTakenTime": {"timestamp": "1500000000"},
        "geoData": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
        "geoDataExif": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
    }


@pytest.fixture
def google_photo_added_gps() -> dict:
    """Google added GPS via Location History; original EXIF had none."""
    return {
        "title": "IMG_5000.HEIC",
        "photoTakenTime": {"timestamp": "1700000000"},
        "geoData": {"latitude": 40.7128, "longitude": -74.0060, "altitude": 10.0},
        "geoDataExif": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
    }


@pytest.fixture
def icloud_row_match() -> dict:
    """An iCloud row that should match google_photo_with_gps."""
    return {
        "uuid": "ABC-123",
        "filename": "IMG_2910.HEIC",
        "date_created_unix": 1694973809.5,
        "size_bytes": 2_500_000,
        "width": 4032,
        "height": 3024,
        "stable_hash": "sha-fixture-1",
        "latitude": 25.7264,
        "longitude": -80.2414,
        "filepath": "_/IMG_2910.HEIC",
    }


@pytest.fixture
def icloud_row_no_gps() -> dict:
    """An iCloud row whose GPS is absent (sentinel -180.0)."""
    return {
        "uuid": "DEF-456",
        "filename": "IMG_5000.HEIC",
        "date_created_unix": 1700000001.0,
        "size_bytes": 3_100_000,
        "width": 4032,
        "height": 3024,
        "stable_hash": "sha-fixture-2",
        "latitude": -180.0,
        "longitude": -180.0,
        "filepath": "_/IMG_5000.HEIC",
    }
```

- [ ] **Step 4: Verify pytest discovers nothing yet**

```bash
python3 -m pytest tests/spike_google_icloud_gps/ -v
```

Expected: `no tests ran in 0.0s` (no test files yet, but the package + conftest are valid).

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps tests/spike_google_icloud_gps
git commit -m "spike(gps): scaffold package + pytest fixtures"
```

---

## Phase 1: JSON sidecar parser

### Task 1.1: Parse one JSON sidecar

**Files:**
- Create: `scripts/spike_google_icloud_gps/parser.py`
- Create: `tests/spike_google_icloud_gps/test_parser.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/spike_google_icloud_gps/test_parser.py`

```python
"""Tests for parser.parse_sidecar."""
from __future__ import annotations
import json
from pathlib import Path

from scripts.spike_google_icloud_gps.parser import parse_sidecar


def test_parse_sidecar_with_gps(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "IMG_2910.HEIC.json"
    sidecar_path.write_text(json.dumps({
        "title": "IMG_2910.HEIC",
        "photoTakenTime": {"timestamp": "1694973809"},
        "geoData": {"latitude": 25.7264, "longitude": -80.2414, "altitude": 0.0},
        "geoDataExif": {"latitude": 25.7264, "longitude": -80.2414, "altitude": 0.0},
    }))
    result = parse_sidecar(sidecar_path)
    assert result["title"] == "IMG_2910.HEIC"
    assert result["taken_time_unix"] == 1694973809
    assert result["geo_lat"] == 25.7264
    assert result["geo_lon"] == -80.2414
    assert result["exif_lat"] == 25.7264
    assert result["exif_lon"] == -80.2414
    assert result["sidecar_path"] == sidecar_path


def test_parse_sidecar_with_no_gps(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "IMG_0001.JPG.json"
    sidecar_path.write_text(json.dumps({
        "title": "IMG_0001.JPG",
        "photoTakenTime": {"timestamp": "1500000000"},
        "geoData": {"latitude": 0.0, "longitude": 0.0},
        "geoDataExif": {"latitude": 0.0, "longitude": 0.0},
    }))
    result = parse_sidecar(sidecar_path)
    assert result["geo_lat"] == 0.0
    assert result["geo_lon"] == 0.0


def test_parse_sidecar_missing_geodata(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "screenshot.png.json"
    sidecar_path.write_text(json.dumps({
        "title": "screenshot.png",
        "photoTakenTime": {"timestamp": "1500000000"},
    }))
    result = parse_sidecar(sidecar_path)
    assert result["geo_lat"] is None
    assert result["geo_lon"] is None
    assert result["exif_lat"] is None
    assert result["exif_lon"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_parser.py -v
```

Expected: 3 failures with `ModuleNotFoundError: No module named 'scripts.spike_google_icloud_gps.parser'` (or `ImportError`).

- [ ] **Step 3: Write minimal implementation**

Path: `scripts/spike_google_icloud_gps/parser.py`

```python
"""Google Takeout JSON sidecar parser. Pure functions only — no I/O beyond reading the file."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def parse_sidecar(sidecar_path: Path) -> dict[str, Any]:
    """Read one Google Takeout `.json` sidecar and normalize the fields we care about.

    Returns a dict with the sidecar's title, taken_time_unix, geo lat/lon (Google's view),
    exif lat/lon (Google's view of original EXIF), and the sidecar_path itself.
    Missing geoData fields become None (NOT 0.0 — caller decides).
    """
    with sidecar_path.open() as f:
        raw = json.load(f)

    geo = raw.get("geoData") or {}
    exif = raw.get("geoDataExif") or {}

    return {
        "title": raw.get("title", ""),
        "taken_time_unix": int(raw.get("photoTakenTime", {}).get("timestamp", "0")),
        "geo_lat": geo.get("latitude") if "latitude" in geo else None,
        "geo_lon": geo.get("longitude") if "longitude" in geo else None,
        "exif_lat": exif.get("latitude") if "latitude" in exif else None,
        "exif_lon": exif.get("longitude") if "longitude" in exif else None,
        "sidecar_path": sidecar_path,
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_parser.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/parser.py tests/spike_google_icloud_gps/test_parser.py
git commit -m "spike(gps): JSON sidecar parser"
```

### Task 1.2: Walk a directory and yield all sidecars

**Files:**
- Modify: `scripts/spike_google_icloud_gps/parser.py` (add `walk_sidecars`)
- Modify: `tests/spike_google_icloud_gps/test_parser.py` (add test)

- [ ] **Step 1: Write the failing test**

Append to `tests/spike_google_icloud_gps/test_parser.py`:

```python
def test_walk_sidecars_finds_all_json(tmp_path: Path) -> None:
    """Generator yields one parsed dict per *.json sidecar in the tree."""
    from scripts.spike_google_icloud_gps.parser import walk_sidecars

    (tmp_path / "albums").mkdir()
    (tmp_path / "Photos from 2023").mkdir()

    (tmp_path / "Photos from 2023" / "IMG_1.JPG.json").write_text(json.dumps({
        "title": "IMG_1.JPG", "photoTakenTime": {"timestamp": "1"},
    }))
    (tmp_path / "Photos from 2023" / "IMG_2.JPG.json").write_text(json.dumps({
        "title": "IMG_2.JPG", "photoTakenTime": {"timestamp": "2"},
    }))
    (tmp_path / "albums" / "IMG_3.JPG.json").write_text(json.dumps({
        "title": "IMG_3.JPG", "photoTakenTime": {"timestamp": "3"},
    }))
    # A non-sidecar file should be ignored:
    (tmp_path / "Photos from 2023" / "IMG_1.JPG").write_bytes(b"\x00")

    titles = sorted(s["title"] for s in walk_sidecars(tmp_path))
    assert titles == ["IMG_1.JPG", "IMG_2.JPG", "IMG_3.JPG"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_parser.py::test_walk_sidecars_finds_all_json -v
```

Expected: FAIL with `ImportError: cannot import name 'walk_sidecars'`.

- [ ] **Step 3: Add `walk_sidecars` to parser.py**

Append to `scripts/spike_google_icloud_gps/parser.py`:

```python
from typing import Iterator


def walk_sidecars(root: Path) -> Iterator[dict[str, Any]]:
    """Recursively yield parsed sidecars for every `*.json` under root."""
    for sidecar_path in root.rglob("*.json"):
        yield parse_sidecar(sidecar_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_parser.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/parser.py tests/spike_google_icloud_gps/test_parser.py
git commit -m "spike(gps): walk_sidecars generator"
```

---

## Phase 2: Phase A baseline stats + decision gate

### Task 2.1: Compute baseline stats from a list of parsed sidecars

**Files:**
- Create: `scripts/spike_google_icloud_gps/stats.py`
- Create: `tests/spike_google_icloud_gps/test_stats.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/spike_google_icloud_gps/test_stats.py`

```python
"""Tests for stats.compute_baseline + stats.should_proceed_to_matching."""
from __future__ import annotations
from scripts.spike_google_icloud_gps.stats import (
    compute_baseline,
    should_proceed_to_matching,
)


def _make(geo, exif):
    return {
        "title": "x.JPG",
        "taken_time_unix": 0,
        "geo_lat": geo[0], "geo_lon": geo[1],
        "exif_lat": exif[0], "exif_lon": exif[1],
        "sidecar_path": None,
    }


def test_compute_baseline_counts_geodata_and_exif():
    sidecars = [
        _make((10, 20), (10, 20)),    # geoData == exif
        _make((30, 40), (0, 0)),      # geoData added by Google (different from exif=0,0)
        _make((50, 60), (None, None)),  # geoData; exif unknown
        _make((None, None), (None, None)),  # no GPS at all
    ]
    b = compute_baseline(sidecars)
    assert b["total"] == 4
    assert b["with_geodata"] == 3
    assert b["geodata_differs_from_exif"] == 2


def test_should_proceed_to_matching_when_google_added_gps():
    """If Google has any net GPS contribution beyond exif, proceed."""
    baseline = {"total": 100, "with_geodata": 80, "geodata_differs_from_exif": 30}
    assert should_proceed_to_matching(baseline) is True


def test_should_stop_when_geodata_equals_exif_everywhere():
    """If geoData ≈ geoDataExif for everything, hypothesis is rejected."""
    baseline = {"total": 100, "with_geodata": 80, "geodata_differs_from_exif": 0}
    assert should_proceed_to_matching(baseline) is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_stats.py -v
```

Expected: 3 failures (ImportError).

- [ ] **Step 3: Write minimal implementation**

Path: `scripts/spike_google_icloud_gps/stats.py`

```python
"""Phase A baseline statistics + decision gate."""
from __future__ import annotations
from typing import Iterable, Mapping


def _has_real_gps(lat, lon) -> bool:
    """A pair counts as real GPS if both are non-None and not (0,0)."""
    return (lat is not None) and (lon is not None) and not (lat == 0.0 and lon == 0.0)


def compute_baseline(sidecars: Iterable[Mapping]) -> dict[str, int]:
    """Count: total photos, # with non-zero geoData, # where geoData differs from geoDataExif."""
    total = 0
    with_geodata = 0
    geodata_differs = 0
    for s in sidecars:
        total += 1
        g_real = _has_real_gps(s["geo_lat"], s["geo_lon"])
        e_real = _has_real_gps(s["exif_lat"], s["exif_lon"])
        if g_real:
            with_geodata += 1
        if g_real and (not e_real or s["geo_lat"] != s["exif_lat"] or s["geo_lon"] != s["exif_lon"]):
            geodata_differs += 1
    return {
        "total": total,
        "with_geodata": with_geodata,
        "geodata_differs_from_exif": geodata_differs,
    }


def should_proceed_to_matching(baseline: Mapping[str, int]) -> bool:
    """Decision gate. Proceed only if Google has net GPS contribution beyond original EXIF."""
    return baseline["geodata_differs_from_exif"] > 0
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_stats.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/stats.py tests/spike_google_icloud_gps/test_stats.py
git commit -m "spike(gps): Phase A baseline stats + decision gate"
```

---

## Phase 3: The 8 signals

This phase has 8 tasks (3.1 through 3.8) — one per signal. Each is the same shape: write failing test, implement, pass, commit.

### Task 3.1: Signal s1 — name_match

**Files:**
- Create: `scripts/spike_google_icloud_gps/signals.py`
- Create: `tests/spike_google_icloud_gps/test_signals.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/spike_google_icloud_gps/test_signals.py`

```python
"""Tests for signal computations."""
from __future__ import annotations
import pytest

from scripts.spike_google_icloud_gps.signals import name_match


def test_name_match_exact():
    assert name_match("IMG_2910.HEIC", "IMG_2910.HEIC") is True


def test_name_match_case_insensitive():
    assert name_match("img_2910.heic", "IMG_2910.HEIC") is True


def test_name_match_different():
    assert name_match("IMG_1234.HEIC", "IMG_5678.HEIC") is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py::test_name_match_exact -v
```

Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

Path: `scripts/spike_google_icloud_gps/signals.py`

```python
"""The 8 matching signals + composite confidence. Pure functions; no I/O.

Each signal compares one Google sidecar against one iCloud row and returns
either a bool, a number, or None. None means "could not compute" (e.g., a
required input was missing).
"""
from __future__ import annotations


def name_match(google_title: str, icloud_filename: str) -> bool:
    """Lowercased filename equality."""
    return google_title.lower() == icloud_filename.lower()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/signals.py tests/spike_google_icloud_gps/test_signals.py
git commit -m "spike(gps): signal s1 name_match"
```

### Task 3.2: Signal s2 — date_diff_seconds

- [ ] **Step 1: Write the failing test**

Append to `tests/spike_google_icloud_gps/test_signals.py`:

```python
from scripts.spike_google_icloud_gps.signals import date_diff_seconds


def test_date_diff_seconds_zero():
    assert date_diff_seconds(1694973809, 1694973809.0) == 0.0


def test_date_diff_seconds_subsecond():
    diff = date_diff_seconds(1694973809, 1694973809.7)
    assert abs(diff - 0.7) < 1e-9


def test_date_diff_seconds_minutes():
    assert date_diff_seconds(1694973809, 1694973959.0) == 150.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -k date_diff -v
```

Expected: 3 failures (ImportError).

- [ ] **Step 3: Add to signals.py**

Append:

```python
def date_diff_seconds(google_unix: int, icloud_unix: float) -> float:
    """Absolute difference between Google's photoTakenTime and iCloud's ZDATECREATED."""
    return abs(float(google_unix) - icloud_unix)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/signals.py tests/spike_google_icloud_gps/test_signals.py
git commit -m "spike(gps): signal s2 date_diff_seconds"
```

### Task 3.3: Signal s3 — size_match

- [ ] **Step 1: Write the failing test**

Append:

```python
from scripts.spike_google_icloud_gps.signals import size_match


def test_size_match_exact():
    assert size_match(2_500_000, 2_500_000) is True


def test_size_match_within_one_percent():
    assert size_match(2_500_000, 2_510_000) is True   # 0.4% diff


def test_size_match_two_percent_off():
    assert size_match(2_500_000, 2_550_000) is False  # 2% diff
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -k size_match -v
```

Expected: 3 failures.

- [ ] **Step 3: Add to signals.py**

```python
def size_match(google_bytes: int, icloud_bytes: int) -> bool:
    """True if file sizes match within 1%."""
    if icloud_bytes == 0:
        return False
    return abs(google_bytes - icloud_bytes) / icloud_bytes <= 0.01
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -v
```

Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/signals.py tests/spike_google_icloud_gps/test_signals.py
git commit -m "spike(gps): signal s3 size_match"
```

### Task 3.4: Signal s4 — dim_match

- [ ] **Step 1: Write the failing test**

Append:

```python
from scripts.spike_google_icloud_gps.signals import dim_match


def test_dim_match_exact():
    assert dim_match((4032, 3024), (4032, 3024)) is True


def test_dim_match_swapped_returns_false():
    """Different orientation = different dimensions, do not equate."""
    assert dim_match((4032, 3024), (3024, 4032)) is False


def test_dim_match_unknown():
    assert dim_match(None, (4032, 3024)) is None
    assert dim_match((4032, 3024), None) is None
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -k dim_match -v
```

- [ ] **Step 3: Add to signals.py**

```python
def dim_match(google_wh: tuple[int, int] | None, icloud_wh: tuple[int, int] | None) -> bool | None:
    """Width × height equality. None when either side is unknown."""
    if google_wh is None or icloud_wh is None:
        return None
    return google_wh == icloud_wh
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -v
```

Expected: 12 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/signals.py tests/spike_google_icloud_gps/test_signals.py
git commit -m "spike(gps): signal s4 dim_match"
```

### Task 3.5: Signal s5 — is_original (derived)

- [ ] **Step 1: Write the failing test**

Append:

```python
from scripts.spike_google_icloud_gps.signals import is_original


def test_is_original_true_when_size_and_dim_match():
    assert is_original(size_match=True, dim_match=True) == "True"


def test_is_original_false_when_size_mismatch():
    assert is_original(size_match=False, dim_match=False) == "False"


def test_is_original_unknown_when_inputs_unknown():
    assert is_original(size_match=False, dim_match=None) == "Unknown"
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -k is_original -v
```

- [ ] **Step 3: Add to signals.py**

```python
def is_original(size_match: bool, dim_match: bool | None) -> str:
    """Classify Google's copy as 'True' (original), 'False' (compressed), or 'Unknown'.

    True when both size and dimensions match the iCloud original.
    False when sizes mismatch (compressed copy is smaller).
    Unknown when dimensions can't be read.
    """
    if dim_match is None:
        return "Unknown"
    if size_match and dim_match:
        return "True"
    return "False"
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -v
```

Expected: 15 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/signals.py tests/spike_google_icloud_gps/test_signals.py
git commit -m "spike(gps): signal s5 is_original"
```

### Task 3.6: Signal s6 — hash_db_match

The osxphotos `ZORIGINALSTABLEHASH` is a hex string in the iCloud sqlite. For the Google file, we compute the same hash via the same algorithm (SHA-1 of file bytes, per osxphotos source). For non-original files this WILL fail; signal returns False. Caller passes `is_original` as a hint to skip work when known compressed.

- [ ] **Step 1: Write the failing test**

Append:

```python
from scripts.spike_google_icloud_gps.signals import hash_db_match


def test_hash_db_match_skipped_when_compressed():
    """When is_original = 'False', skip the hash; return None (recorded as N/A)."""
    assert hash_db_match(google_path=None, icloud_stable_hash="abc", is_original="False") is None


def test_hash_db_match_returns_true_on_equal_hash(tmp_path):
    """When file content matches the recorded hash, signal is True."""
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello world")
    # Compute SHA-1 of "hello world" in Python:
    import hashlib
    expected = hashlib.sha1(b"hello world").hexdigest()
    assert hash_db_match(google_path=f, icloud_stable_hash=expected, is_original="True") is True


def test_hash_db_match_returns_false_on_different_hash(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello world")
    assert hash_db_match(google_path=f, icloud_stable_hash="deadbeef", is_original="True") is False
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -k hash_db -v
```

- [ ] **Step 3: Add to signals.py**

```python
import hashlib
from pathlib import Path


def hash_db_match(google_path: Path | None, icloud_stable_hash: str, is_original: str) -> bool | None:
    """SHA-1 of Google's bytes vs iCloud's ZORIGINALSTABLEHASH.

    Returns None when is_original='False' (skip — recorded as N/A in output).
    Returns True/False otherwise.
    """
    if is_original == "False":
        return None
    if google_path is None or not google_path.exists():
        return False
    h = hashlib.sha1()
    with google_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest() == icloud_stable_hash
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -v
```

Expected: 18 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/signals.py tests/spike_google_icloud_gps/test_signals.py
git commit -m "spike(gps): signal s6 hash_db_match"
```

### Task 3.7: Signal s7 — sha256_match

- [ ] **Step 1: Write the failing test**

Append:

```python
from scripts.spike_google_icloud_gps.signals import sha256_match


def test_sha256_match_skipped_when_compressed():
    assert sha256_match(google_path=None, icloud_path=None, is_original="False") is None


def test_sha256_match_true_for_identical_bytes(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"identical")
    b.write_bytes(b"identical")
    assert sha256_match(a, b, is_original="True") is True


def test_sha256_match_false_for_different_bytes(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"foo")
    b.write_bytes(b"bar")
    assert sha256_match(a, b, is_original="True") is False
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -k sha256 -v
```

- [ ] **Step 3: Add to signals.py**

```python
def sha256_match(google_path: Path | None, icloud_path: Path | None, is_original: str) -> bool | None:
    """SHA-256 of both files compared.

    Returns None when is_original='False' (skip — recorded as N/A).
    """
    if is_original == "False":
        return None
    if google_path is None or icloud_path is None:
        return False
    if not google_path.exists() or not icloud_path.exists():
        return False
    g = hashlib.sha256()
    with google_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            g.update(chunk)
    i = hashlib.sha256()
    with icloud_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            i.update(chunk)
    return g.hexdigest() == i.hexdigest()
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -v
```

Expected: 21 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/signals.py tests/spike_google_icloud_gps/test_signals.py
git commit -m "spike(gps): signal s7 sha256_match"
```

### Task 3.8: Signal s8 — phash_distance

Perceptual hash via `imagehash` library. Hamming distance between two pHashes. Distance ≤ 8 typically means "same image, possibly re-encoded."

- [ ] **Step 1: Write the failing test**

Append:

```python
from scripts.spike_google_icloud_gps.signals import phash_distance


def test_phash_distance_zero_for_same_file(tmp_path):
    """Two copies of the same image should have distance 0."""
    from PIL import Image
    img_path = tmp_path / "img.jpg"
    Image.new("RGB", (64, 64), color=(128, 50, 200)).save(img_path)
    other_path = tmp_path / "img2.jpg"
    Image.new("RGB", (64, 64), color=(128, 50, 200)).save(other_path)
    assert phash_distance(img_path, other_path) == 0


def test_phash_distance_returns_int(tmp_path):
    from PIL import Image
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    Image.new("RGB", (64, 64), color=(0, 0, 0)).save(a)
    Image.new("RGB", (64, 64), color=(255, 255, 255)).save(b)
    d = phash_distance(a, b)
    assert isinstance(d, int)
    assert d > 0


def test_phash_distance_returns_none_for_missing_file(tmp_path):
    assert phash_distance(tmp_path / "nope.jpg", tmp_path / "nope2.jpg") is None
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -k phash -v
```

- [ ] **Step 3: Add to signals.py**

```python
def phash_distance(google_path: Path | None, icloud_path: Path | None) -> int | None:
    """Perceptual-hash Hamming distance between two images. None on missing files."""
    if google_path is None or icloud_path is None:
        return None
    if not google_path.exists() or not icloud_path.exists():
        return None
    from PIL import Image
    import imagehash
    g = imagehash.phash(Image.open(google_path))
    i = imagehash.phash(Image.open(icloud_path))
    return g - i  # imagehash supports `-` as Hamming distance
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -v
```

Expected: 24 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/signals.py tests/spike_google_icloud_gps/test_signals.py
git commit -m "spike(gps): signal s8 phash_distance"
```

---

## Phase 4: Composite confidence

### Task 4.1: composite_confidence weighted score

**Files:**
- Modify: `scripts/spike_google_icloud_gps/signals.py` (append `composite_confidence`)
- Modify: `tests/spike_google_icloud_gps/test_signals.py` (append tests)

- [ ] **Step 1: Write the failing test**

Append to test file:

```python
from scripts.spike_google_icloud_gps.signals import composite_confidence


def test_composite_perfect_match():
    """All signals fire positively → confidence near 1.0."""
    score = composite_confidence(
        s1_name=True, s2_date_sec=0.0, s3_size=True, s4_dim=True,
        s6_hash_db=True, s7_sha256=True, s8_phash=0,
    )
    assert score >= 0.9


def test_composite_no_match():
    """All signals false / N/A → confidence 0."""
    score = composite_confidence(
        s1_name=False, s2_date_sec=99999.0, s3_size=False, s4_dim=False,
        s6_hash_db=None, s7_sha256=None, s8_phash=None,
    )
    assert score == 0.0


def test_composite_compressed_original():
    """Name + date match; size + dim mismatch (compressed); pHash close."""
    score = composite_confidence(
        s1_name=True, s2_date_sec=0.5, s3_size=False, s4_dim=False,
        s6_hash_db=None, s7_sha256=None, s8_phash=2,
    )
    # name (0.10) + date (~0.15) + phash close (~0.20) = 0.45ish
    assert 0.40 <= score <= 0.55


def test_composite_clamps_to_one():
    score = composite_confidence(
        s1_name=True, s2_date_sec=0.0, s3_size=True, s4_dim=True,
        s6_hash_db=True, s7_sha256=True, s8_phash=0,
    )
    assert score <= 1.0
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -k composite -v
```

- [ ] **Step 3: Add to signals.py**

```python
def composite_confidence(
    s1_name: bool,
    s2_date_sec: float,
    s3_size: bool,
    s4_dim: bool | None,
    s6_hash_db: bool | None,
    s7_sha256: bool | None,
    s8_phash: int | None,
) -> float:
    """Weighted sum across all signals; clamped to [0, 1].

    Weights chosen to give byte-equality (s6/s7) the most weight, then phash, then
    name+date+size+dim. This formula is provisional and refined after manual review.
    """
    score = 0.0
    if s1_name:
        score += 0.10
    if s2_date_sec is not None:
        # Saturates to full credit at exact match; 0 credit at 2s away
        score += 0.15 * max(0.0, 1.0 - min(1.0, s2_date_sec / 2.0))
    if s3_size:
        score += 0.10
    if s4_dim is True:
        score += 0.10
    if s6_hash_db is True:
        score += 0.30
    if s7_sha256 is True:
        score += 0.30
    if s8_phash is not None:
        # Distance ≤ 8 is "same image perceptually"; saturates to full credit
        score += 0.20 * max(0.0, 1.0 - min(1.0, s8_phash / 8.0))
    return max(0.0, min(1.0, score))
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_signals.py -v
```

Expected: 28 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/signals.py tests/spike_google_icloud_gps/test_signals.py
git commit -m "spike(gps): composite confidence formula"
```

---

## Phase 5: Per-photo evaluation orchestrator

### Task 5.1: Build the iCloud index for fast filename lookup

**Files:**
- Create: `scripts/spike_google_icloud_gps/matcher.py`
- Create: `tests/spike_google_icloud_gps/test_matcher.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/spike_google_icloud_gps/test_matcher.py`

```python
"""Tests for matcher.IcloudIndex and evaluate_photo."""
from __future__ import annotations
import sqlite3
from pathlib import Path

from scripts.spike_google_icloud_gps.matcher import IcloudIndex


def _make_export_db(tmp_path: Path) -> Path:
    """Create a minimal .osxphotos_export.db with a fake export_data table."""
    db_path = tmp_path / ".osxphotos_export.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE export_data (uuid TEXT, filepath TEXT)")
    conn.execute("INSERT INTO export_data VALUES ('UUID-A', '_/IMG_2910.HEIC')")
    conn.execute("INSERT INTO export_data VALUES ('UUID-B', '_/IMG_5000.HEIC')")
    conn.commit()
    conn.close()
    return db_path


def _make_photos_db(tmp_path: Path) -> Path:
    """Create a minimal Photos.sqlite with the columns matcher reads."""
    db_dir = tmp_path / "Photos Library.photoslibrary" / "database"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "Photos.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE ZASSET (
        Z_PK INTEGER PRIMARY KEY, ZUUID TEXT, ZTRASHEDSTATE INT,
        ZDATECREATED REAL, ZLATITUDE REAL, ZLONGITUDE REAL, ZADDITIONALATTRIBUTES INT
    )""")
    conn.execute("""CREATE TABLE ZADDITIONALASSETATTRIBUTES (
        Z_PK INTEGER PRIMARY KEY, ZORIGINALFILENAME TEXT,
        ZORIGINALFILESIZE INT, ZORIGINALWIDTH INT, ZORIGINALHEIGHT INT,
        ZORIGINALSTABLEHASH TEXT
    )""")
    conn.execute("INSERT INTO ZADDITIONALASSETATTRIBUTES VALUES (1, 'IMG_2910.HEIC', 2500000, 4032, 3024, 'sha-A')")
    conn.execute("INSERT INTO ZADDITIONALASSETATTRIBUTES VALUES (2, 'IMG_5000.HEIC', 3100000, 4032, 3024, 'sha-B')")
    conn.execute("INSERT INTO ZASSET VALUES (10, 'UUID-A', 0, 717096209.5, 25.7264, -80.2414, 1)")
    conn.execute("INSERT INTO ZASSET VALUES (11, 'UUID-B', 0, 722000001.0, -180.0, -180.0, 2)")
    conn.commit()
    conn.close()
    return db_path


def test_icloud_index_lookup_by_filename(tmp_path):
    photos_db = _make_photos_db(tmp_path)
    export_db = _make_export_db(tmp_path)
    idx = IcloudIndex(photos_db=photos_db, export_db=export_db)
    matches = idx.find_by_filename("IMG_2910.HEIC")
    assert len(matches) == 1
    m = matches[0]
    assert m["uuid"] == "UUID-A"
    assert m["filename"] == "IMG_2910.HEIC"
    assert m["size_bytes"] == 2500000
    assert m["stable_hash"] == "sha-A"
    assert m["latitude"] == 25.7264


def test_icloud_index_lookup_no_match(tmp_path):
    photos_db = _make_photos_db(tmp_path)
    export_db = _make_export_db(tmp_path)
    idx = IcloudIndex(photos_db=photos_db, export_db=export_db)
    assert idx.find_by_filename("NONEXISTENT.HEIC") == []
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_matcher.py -v
```

Expected: 2 ImportError failures.

- [ ] **Step 3: Implement IcloudIndex**

Path: `scripts/spike_google_icloud_gps/matcher.py`

```python
"""Per-photo evaluation orchestrator.

IcloudIndex: in-memory map filename → list of iCloud rows. Built once at startup.
evaluate_photo: given a Google sidecar dict and IcloudIndex, run all signals
and return one or more rows (one per candidate iCloud match, or one row with
no candidate).
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from urllib.parse import quote


def _uri(p: Path) -> str:
    return f"file:{quote(str(p))}?mode=ro"


class IcloudIndex:
    """Loads the iCloud library + export tracking DB once and provides filename lookup."""

    def __init__(self, photos_db: Path, export_db: Path) -> None:
        self.photos_db = photos_db
        self.export_db = export_db
        self._by_filename: dict[str, list[dict]] = {}
        self._load()

    def _load(self) -> None:
        # Build uuid → filepath map from export DB
        with sqlite3.connect(str(self.export_db)) as conn:
            uuid_to_path = dict(conn.execute(
                "SELECT uuid, filepath FROM export_data WHERE filepath IS NOT NULL"
            ).fetchall())

        # Read all asset rows from Photos.sqlite (read-only)
        with sqlite3.connect(_uri(self.photos_db), uri=True) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT a.ZUUID AS uuid, aa.ZORIGINALFILENAME AS filename,
                       a.ZDATECREATED AS date_created_apple,
                       a.ZLATITUDE AS latitude, a.ZLONGITUDE AS longitude,
                       aa.ZORIGINALFILESIZE AS size_bytes,
                       aa.ZORIGINALWIDTH AS width, aa.ZORIGINALHEIGHT AS height,
                       aa.ZORIGINALSTABLEHASH AS stable_hash
                FROM ZASSET a
                JOIN ZADDITIONALASSETATTRIBUTES aa ON aa.Z_PK = a.ZADDITIONALATTRIBUTES
                WHERE a.ZTRASHEDSTATE = 0
            """).fetchall()

        for r in rows:
            row = dict(r)
            # Apple's epoch starts 2001-01-01; convert to Unix
            row["date_created_unix"] = (row["date_created_apple"] or 0) + 978307200
            row["filepath"] = uuid_to_path.get(row["uuid"])
            key = (row["filename"] or "").lower()
            self._by_filename.setdefault(key, []).append(row)

    def find_by_filename(self, filename: str) -> list[dict]:
        return list(self._by_filename.get(filename.lower(), []))
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_matcher.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/matcher.py tests/spike_google_icloud_gps/test_matcher.py
git commit -m "spike(gps): IcloudIndex with filename lookup"
```

### Task 5.2: evaluate_photo — run all signals and return rows

- [ ] **Step 1: Write the failing test**

Append to `tests/spike_google_icloud_gps/test_matcher.py`:

```python
from scripts.spike_google_icloud_gps.matcher import evaluate_photo


def test_evaluate_photo_perfect_match(tmp_path, google_photo_with_gps, icloud_row_match):
    """A Google photo with exact-match iCloud row should produce one high-confidence row."""
    rows = evaluate_photo(
        sidecar=google_photo_with_gps,
        google_path=None,           # no real file in this test → hash signals return False/None
        icloud_candidates=[icloud_row_match],
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["google_title"] == "IMG_2910.HEIC"
    assert r["icloud_uuid"] == "ABC-123"
    assert r["s1_name_match"] is True
    assert r["s2_date_diff_seconds"] < 1.0
    assert r["s3_size_match"] in (True, None)  # cannot read file size for None path
    # gps_gap = Google has GPS AND iCloud has GPS != -180 → False
    assert r["gps_gap"] is False


def test_evaluate_photo_unmatched(tmp_path, google_photo_with_gps):
    """A Google photo with no iCloud candidate produces one row with confidence 0."""
    rows = evaluate_photo(
        sidecar=google_photo_with_gps,
        google_path=None,
        icloud_candidates=[],
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["icloud_uuid"] is None
    assert r["composite_confidence"] == 0.0


def test_evaluate_photo_gps_gap(tmp_path, google_photo_added_gps, icloud_row_no_gps):
    """Google has GPS, iCloud has -180 sentinel → gps_gap True."""
    rows = evaluate_photo(
        sidecar=google_photo_added_gps,
        google_path=None,
        icloud_candidates=[icloud_row_no_gps],
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["gps_gap"] is True
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_matcher.py -k evaluate_photo -v
```

- [ ] **Step 3: Implement evaluate_photo**

Append to `scripts/spike_google_icloud_gps/matcher.py`:

```python
from typing import Any
from .signals import (
    name_match, date_diff_seconds, size_match, dim_match, is_original,
    hash_db_match, sha256_match, phash_distance, composite_confidence,
)


def _has_real_gps(lat, lon) -> bool:
    return (lat is not None) and (lon is not None) and lat != -180.0 and not (lat == 0.0 and lon == 0.0)


def evaluate_photo(
    sidecar: dict,
    google_path: Path | None,
    icloud_candidates: list[dict],
) -> list[dict[str, Any]]:
    """Run all signals for one Google photo against each candidate iCloud row.

    Returns one output row per candidate. If no candidates, returns a single row with
    icloud_uuid=None and composite_confidence=0 — flagging it as a Google-only photo.
    """
    g_has_gps = _has_real_gps(sidecar["geo_lat"], sidecar["geo_lon"])

    if not icloud_candidates:
        return [{
            "google_title": sidecar["title"],
            "google_path": str(google_path) if google_path else None,
            "icloud_uuid": None,
            "icloud_filepath": None,
            "s1_name_match": None,
            "s2_date_diff_seconds": None,
            "s3_size_match": None,
            "s4_dim_match": None,
            "s5_is_original": None,
            "s6_hash_db_match": None,
            "s7_sha256_match": None,
            "s8_phash_distance": None,
            "google_geo_lat": sidecar["geo_lat"],
            "google_geo_lon": sidecar["geo_lon"],
            "icloud_lat": None,
            "icloud_lon": None,
            "gps_gap": g_has_gps,  # Google has GPS, no iCloud match at all
            "composite_confidence": 0.0,
        }]

    out: list[dict] = []
    for cand in icloud_candidates:
        # Google file size + dimensions, only if we have the path
        google_size = google_path.stat().st_size if (google_path and google_path.exists()) else None
        google_wh = None  # populated by exiftool/PIL caller in production; tests pass None

        s1 = name_match(sidecar["title"], cand["filename"])
        s2 = date_diff_seconds(sidecar["taken_time_unix"], cand["date_created_unix"])
        s3 = size_match(google_size, cand["size_bytes"]) if google_size else False
        s4 = dim_match(google_wh, (cand.get("width"), cand.get("height")) if cand.get("width") else None)
        s5 = is_original(s3, s4)
        s6 = hash_db_match(google_path, cand.get("stable_hash") or "", s5)
        s7 = sha256_match(google_path, Path(cand["filepath"]) if cand.get("filepath") else None, s5)
        s8 = phash_distance(google_path, Path(cand["filepath"]) if cand.get("filepath") else None)

        conf = composite_confidence(
            s1_name=s1, s2_date_sec=s2, s3_size=bool(s3), s4_dim=s4,
            s6_hash_db=s6, s7_sha256=s7, s8_phash=s8,
        )

        i_has_gps = _has_real_gps(cand["latitude"], cand["longitude"])

        out.append({
            "google_title": sidecar["title"],
            "google_path": str(google_path) if google_path else None,
            "icloud_uuid": cand["uuid"],
            "icloud_filepath": cand.get("filepath"),
            "s1_name_match": s1,
            "s2_date_diff_seconds": s2,
            "s3_size_match": s3 if google_size else None,
            "s4_dim_match": s4,
            "s5_is_original": s5,
            "s6_hash_db_match": s6,
            "s7_sha256_match": s7,
            "s8_phash_distance": s8,
            "google_geo_lat": sidecar["geo_lat"],
            "google_geo_lon": sidecar["geo_lon"],
            "icloud_lat": cand["latitude"],
            "icloud_lon": cand["longitude"],
            "gps_gap": g_has_gps and not i_has_gps,
            "composite_confidence": conf,
        })
    return out
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_matcher.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/matcher.py tests/spike_google_icloud_gps/test_matcher.py
git commit -m "spike(gps): evaluate_photo orchestrator"
```

---

## Phase 6: CSV writer + report generator

### Task 6.1: Write rows to CSV

**Files:**
- Create: `scripts/spike_google_icloud_gps/reporter.py`
- Create: `tests/spike_google_icloud_gps/test_reporter.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/spike_google_icloud_gps/test_reporter.py`

```python
"""Tests for reporter.write_results_csv + reporter.write_summary_report."""
from __future__ import annotations
import csv
from pathlib import Path

from scripts.spike_google_icloud_gps.reporter import (
    write_results_csv,
    write_summary_report,
    RESULT_COLUMNS,
)


def test_write_results_csv(tmp_path):
    out_path = tmp_path / "results.csv"
    rows = [
        {"google_title": "IMG_1.HEIC", "icloud_uuid": "ABC", "composite_confidence": 0.95,
         **{k: None for k in RESULT_COLUMNS if k not in ("google_title","icloud_uuid","composite_confidence")}},
        {"google_title": "IMG_2.HEIC", "icloud_uuid": None,  "composite_confidence": 0.0,
         **{k: None for k in RESULT_COLUMNS if k not in ("google_title","icloud_uuid","composite_confidence")}},
    ]
    write_results_csv(out_path, rows)
    with out_path.open() as f:
        reader = csv.DictReader(f)
        out_rows = list(reader)
    assert len(out_rows) == 2
    assert out_rows[0]["google_title"] == "IMG_1.HEIC"
    assert out_rows[0]["composite_confidence"] == "0.95"


def test_write_summary_report(tmp_path):
    out_path = tmp_path / "report.md"
    baseline = {"total": 1500, "with_geodata": 800, "geodata_differs_from_exif": 200}
    rows = [
        {"composite_confidence": 0.95, "gps_gap": True, "icloud_uuid": "A", **{k: None for k in RESULT_COLUMNS if k not in ("composite_confidence","gps_gap","icloud_uuid")}},
        {"composite_confidence": 0.85, "gps_gap": False, "icloud_uuid": "B", **{k: None for k in RESULT_COLUMNS if k not in ("composite_confidence","gps_gap","icloud_uuid")}},
        {"composite_confidence": 0.10, "gps_gap": False, "icloud_uuid": None, **{k: None for k in RESULT_COLUMNS if k not in ("composite_confidence","gps_gap","icloud_uuid")}},
    ]
    write_summary_report(out_path, baseline, rows)
    text = out_path.read_text()
    assert "Total photos" in text
    assert "1500" in text
    assert "GPS gap" in text or "gps_gap" in text
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_reporter.py -v
```

- [ ] **Step 3: Implement reporter.py**

Path: `scripts/spike_google_icloud_gps/reporter.py`

```python
"""CSV results writer + markdown summary report generator."""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterable, Mapping


RESULT_COLUMNS: list[str] = [
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
    baseline: Mapping[str, int],
    rows: list[Mapping],
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
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_reporter.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/reporter.py tests/spike_google_icloud_gps/test_reporter.py
git commit -m "spike(gps): CSV writer + report generator"
```

---

## Phase 7: Stratified sampler for manual review

### Task 7.1: Sample N rows per bucket

**Files:**
- Create: `scripts/spike_google_icloud_gps/sampler.py`
- Create: `tests/spike_google_icloud_gps/test_sampler.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/spike_google_icloud_gps/test_sampler.py`

```python
"""Tests for sampler.stratified_sample."""
from __future__ import annotations
import random

from scripts.spike_google_icloud_gps.sampler import stratified_sample


def _row(conf: float) -> dict:
    return {"composite_confidence": conf, "icloud_uuid": "x" if conf > 0 else None}


def test_stratified_sample_selects_buckets():
    random.seed(0)
    rows = (
        [_row(0.95) for _ in range(100)]   # high
        + [_row(0.65) for _ in range(50)]   # medium
        + [_row(0.20) for _ in range(40)]   # low
        + [_row(0.0) for _ in range(60)]    # unmatched
    )
    sampled = stratified_sample(rows, high_n=30, med_n=30, low_n=30, unmatched_n=30)
    bucket_counts = {"high": 0, "medium": 0, "low": 0, "unmatched": 0}
    for r in sampled:
        c = r["composite_confidence"]
        if c >= 0.85:
            bucket_counts["high"] += 1
        elif c >= 0.50:
            bucket_counts["medium"] += 1
        elif c > 0:
            bucket_counts["low"] += 1
        else:
            bucket_counts["unmatched"] += 1
    assert bucket_counts == {"high": 30, "medium": 30, "low": 30, "unmatched": 30}


def test_stratified_sample_respects_small_buckets():
    """If a bucket has fewer than N rows, use all available."""
    rows = [_row(0.95)] * 5 + [_row(0.0)] * 5
    sampled = stratified_sample(rows, high_n=30, med_n=30, low_n=30, unmatched_n=30)
    assert len(sampled) == 10
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_sampler.py -v
```

- [ ] **Step 3: Implement sampler.py**

Path: `scripts/spike_google_icloud_gps/sampler.py`

```python
"""Stratified sampling for manual review."""
from __future__ import annotations
import random
from typing import Iterable, Mapping


def stratified_sample(
    rows: Iterable[Mapping],
    high_n: int = 30, med_n: int = 30, low_n: int = 30, unmatched_n: int = 30,
) -> list[Mapping]:
    """Pick up to N rows from each confidence bucket."""
    buckets: dict[str, list[Mapping]] = {"high": [], "medium": [], "low": [], "unmatched": []}
    for r in rows:
        c = r.get("composite_confidence") or 0
        if c >= 0.85:
            buckets["high"].append(r)
        elif c >= 0.50:
            buckets["medium"].append(r)
        elif c > 0:
            buckets["low"].append(r)
        else:
            buckets["unmatched"].append(r)
    out: list[Mapping] = []
    for name, n in (("high", high_n), ("medium", med_n), ("low", low_n), ("unmatched", unmatched_n)):
        b = buckets[name]
        out.extend(random.sample(b, min(n, len(b))))
    return out
```

- [ ] **Step 4: Run test, verify pass**

```bash
python3 -m pytest tests/spike_google_icloud_gps/test_sampler.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/spike_google_icloud_gps/sampler.py tests/spike_google_icloud_gps/test_sampler.py
git commit -m "spike(gps): stratified sampler"
```

---

## Phase 8: CLI orchestration

### Task 8.1: Wire up `__main__.py` to drive Phase A

**Files:**
- Modify: `scripts/spike_google_icloud_gps/__main__.py`

- [ ] **Step 1: Update `__main__.py` to drive Phase A**

Replace contents of `scripts/spike_google_icloud_gps/__main__.py`:

```python
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
import csv

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
    sidecars = list(walk_sidecars(args.extracted))
    print(f"Phase A: parsed {len(sidecars)} sidecars from {args.extracted}")
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

    rows: list[dict] = []
    for i, sc in enumerate(sidecars, 1):
        if i % 200 == 0:
            print(f"  evaluating {i}/{len(sidecars)}...")
        google_path = sc["sidecar_path"].with_suffix("") if sc["sidecar_path"] else None
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
```

- [ ] **Step 2: Verify imports and dry-run**

```bash
python3 -m scripts.spike_google_icloud_gps --help
```

Expected: argparse help text.

- [ ] **Step 3: Run the full unit test suite — all phases together**

```bash
python3 -m pytest tests/spike_google_icloud_gps/ -v
```

Expected: 32 PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/spike_google_icloud_gps/__main__.py
git commit -m "spike(gps): CLI orchestration for phases A, BC, D"
```

---

## Phase 9: Run it on real data

### Task 9.1: Extract zip 1

**Files:**
- No code changes. This is operational.

- [ ] **Step 1: Confirm there's free disk space**

```bash
df -h /Volumes/HomeRAID
```

Expected: Avail ≥ 70 GB (one zip is ~50 GB; extracted may be similar size).

- [ ] **Step 2: Create extraction directory**

```bash
mkdir -p /Volumes/HomeRAID/google-extracted/account1
```

- [ ] **Step 3: Extract the zip — runs ~30 min on this RAID**

```bash
cd /Volumes/HomeRAID/google-extracted/account1
unzip /Volumes/HomeRAID/google-takeout/takeout-20260403T195541Z-001.zip
```

Expected: completion message "X file(s) successfully unzipped".

- [ ] **Step 4: Verify**

```bash
find /Volumes/HomeRAID/google-extracted/account1 -name '*.json' | wc -l
find /Volumes/HomeRAID/google-extracted/account1 -type f \! -name '*.json' | wc -l
```

Expected: nonzero counts; JSON count roughly equals media count (one sidecar per media file).

### Task 9.2: Run Phase A only

- [ ] **Step 1: Run only Phase A on the extracted archive**

```bash
python3 -m scripts.spike_google_icloud_gps --phase A
```

Expected: prints baseline stats. If `geodata_differs_from_exif` is **0**, the hypothesis is rejected; report `docs/spike/2026-04-26-google-vs-icloud-gps-report.md` is written; STOP.

- [ ] **Step 2: Inspect the report**

```bash
cat docs/spike/2026-04-26-google-vs-icloud-gps-report.md
```

If hypothesis rejected, the spike is complete. Skip the rest of Phase 9 and go to Phase 10 (final commit + summary).

If `geodata_differs_from_exif > 0`, proceed to Task 9.3.

### Task 9.3: Run Phase BC

- [ ] **Step 1: Run B+C (full evaluation)**

```bash
python3 -m scripts.spike_google_icloud_gps --phase BC
```

Expected: writes `results.csv` and updates `report.md`. Logs progress every 200 photos. Should take 1-2 hours on this RAID.

- [ ] **Step 2: Spot-check the CSV**

```bash
head -5 docs/spike/2026-04-26-google-vs-icloud-gps-results.csv
echo ""
wc -l docs/spike/2026-04-26-google-vs-icloud-gps-results.csv
```

Expected: column header + N rows (where N >= sidecar count).

### Task 9.4: Run Phase D — stratified sample

- [ ] **Step 1: Generate the manual-review sample**

```bash
python3 -m scripts.spike_google_icloud_gps --phase D
```

Expected: writes `2026-04-26-google-vs-icloud-gps-review.csv` with up to 120 sampled rows.

- [ ] **Step 2: Hand off to user for manual review**

The review CSV has the same columns as results.csv. The user opens it in a spreadsheet, adds a `verdict` column with values: `correct` / `wrong` / `should-be-unmatched` / `unsure`, optionally a one-line note.

---

## Phase 10: Decision and final commit

### Task 10.1: Update spec design doc with results

**Files:**
- Modify: `docs/spike/2026-04-26-google-vs-icloud-gps-design.md`

- [ ] **Step 1: Add a "Results" section at the end of the design doc**

Manually edit `docs/spike/2026-04-26-google-vs-icloud-gps-design.md` and append a `## Results` section summarizing the baseline numbers, Phase B+C row counts, and the GPS gap headline number. Pull text from the auto-generated report.

- [ ] **Step 2: Commit**

```bash
git add docs/spike/2026-04-26-google-vs-icloud-gps-design.md docs/spike/2026-04-26-google-vs-icloud-gps-results.csv docs/spike/2026-04-26-google-vs-icloud-gps-report.md docs/spike/2026-04-26-google-vs-icloud-gps-review.csv
git commit -m "spike(gps): real-data results + report"
```

### Task 10.2: Decide and write a recommendation

- [ ] **Step 1: Based on the headline number from the report, write a 3-line recommendation**

If `gps_gap > 500` and high-confidence: **OPEN BACK-FILL SPEC** — propose a follow-up spec to extract all 50 archives and patch GPS.

If `gps_gap == 0` or near-zero: **CLOSE THE SPIKE** — hypothesis rejected.

If `gps_gap` is small (<500): **DOCUMENT AND MOVE ON** — the gap exists but isn't worth the back-fill cost.

Write the recommendation as a final paragraph in the design doc's "Results" section and commit.

- [ ] **Step 2: Final commit**

```bash
git commit -am "spike(gps): final decision recorded"
```

---

## Self-review

### Spec coverage

| Spec section | Implementation | Task |
|--------------|---------------|------|
| Phase A pre-flight (extract, parse, stats, decision gate) | parser, stats modules; Task 9.1, 9.2 | 1.1, 1.2, 2.1, 8.1, 9.1, 9.2 |
| Phase B+C per-photo evaluation (8 signals + composite) | signals, matcher modules | 3.1-3.8, 4.1, 5.1, 5.2 |
| Output table (CSV) | reporter.write_results_csv | 6.1 |
| Stratified manual-review sample | sampler module | 7.1 |
| Spike report (markdown) | reporter.write_summary_report | 6.1 |
| Decision criteria (close / small / open back-fill) | Task 10.2 | 10.2 |
| Originality classifier as a per-photo signal | signals.is_original (s5) | 3.5 |
| Skips for sha256/hash_db on compressed copies recorded as N/A | hash_db_match and sha256_match return None when is_original='False' | 3.6, 3.7 |
| Edge case: multi-candidate per Google photo (multi-row output) | evaluate_photo returns list[dict] | 5.2 |
| Edge case: Google-only photos (no iCloud match) | evaluate_photo returns row with icloud_uuid=None | 5.2 |
| Edge case: filename case sensitivity | name_match lowercases | 3.1 |

### Placeholder scan

- No "TBD" / "TODO" / "implement later" found.
- Every step has either a code block or an exact command.
- Every test is the actual test code, not "test the function."

### Type consistency

- `is_original` is `str` ("True"/"False"/"Unknown") — same in all signal calls and composite_confidence.
- `composite_confidence` returns `float` in [0, 1] — used as ordering key in sampler.
- `RESULT_COLUMNS` is the canonical column list — both writer and tests use it.
- Method names: `find_by_filename`, `evaluate_photo`, `compute_baseline`, `should_proceed_to_matching`, `write_results_csv`, `write_summary_report`, `stratified_sample` — used consistently across the plan.

---

## Execution Handoff

Plan complete and saved to `docs/spike/2026-04-26-google-vs-icloud-gps-plan.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Each task is 2-5 minutes; the whole code-write phase (Tasks 0.1 through 8.1) takes ~1-2 hours of agent time. The real-data run (Task 9) is operational and slow on the RAID (~2-3 hours).

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

Which approach?
