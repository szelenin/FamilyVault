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
