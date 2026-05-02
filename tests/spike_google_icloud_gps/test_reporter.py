"""Tests for reporter.write_results_csv + reporter.write_summary_report."""
from __future__ import annotations
import csv
from pathlib import Path

from scripts.spike_google_icloud_gps.reporter import (
    write_results_csv,
    write_summary_report,
    RESULT_COLUMNS,
)


def _row(**kwargs) -> dict:
    base = {k: None for k in RESULT_COLUMNS}
    base.update(kwargs)
    return base


def test_write_results_csv(tmp_path):
    out_path = tmp_path / "results.csv"
    rows = [
        _row(google_title="IMG_1.HEIC", icloud_uuid="ABC", composite_confidence=0.95),
        _row(google_title="IMG_2.HEIC", icloud_uuid=None, composite_confidence=0.0),
    ]
    write_results_csv(out_path, rows)
    with out_path.open() as f:
        out_rows = list(csv.DictReader(f))
    assert len(out_rows) == 2
    assert out_rows[0]["google_title"] == "IMG_1.HEIC"
    assert out_rows[0]["composite_confidence"] == "0.95"


def test_write_summary_report(tmp_path):
    out_path = tmp_path / "report.md"
    baseline = {"total": 1500, "with_geodata": 800, "geodata_differs_from_exif": 200}
    rows = [
        _row(composite_confidence=0.95, gps_gap=True, icloud_uuid="A"),
        _row(composite_confidence=0.85, gps_gap=False, icloud_uuid="B"),
        _row(composite_confidence=0.10, gps_gap=False, icloud_uuid=None),
    ]
    write_summary_report(out_path, baseline, rows)
    text = out_path.read_text()
    assert "Total photos" in text
    assert "1500" in text
    assert "GPS gap" in text or "gps_gap" in text
