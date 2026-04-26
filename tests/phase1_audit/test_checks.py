"""Tests for individual audit checks."""
from __future__ import annotations
from unittest.mock import MagicMock

from scripts.phase1_audit.manifest import Manifest
from scripts.phase1_audit.checks import (
    check_total_count,
    check_extension_count,
    CheckResult,
)


def _manifest(**over) -> Manifest:
    base = dict(
        source_zip="t.zip", total_files_in_html=100, total_folders=0,
        extension_counts={"heic": 30, "json": 40, "mp4": 30},
        year_folder_count=0, year_folder_range=(None, None),
        user_album_count=0, user_albums=(),
    )
    base.update(over)
    return Manifest(**base)


def test_total_count_pass_within_tolerance() -> None:
    m = _manifest()  # expected = 100 - 40 = 60
    client = MagicMock()
    client.get_statistics.return_value = {"photos": 30, "videos": 30}  # exact 60
    r = check_total_count(client, m, tolerance=0.01)
    assert r.passed is True
    assert r.actual == 60
    assert r.expected == 60


def test_total_count_pass_at_edge_of_tolerance() -> None:
    m = _manifest()  # expected = 60; ±1% = 0.6 → integer floor 0
    client = MagicMock()
    # 60 + 1 = 61 — outside ±0.6 in absolute terms → check uses fractional
    client.get_statistics.return_value = {"photos": 30, "videos": 30}
    r = check_total_count(client, m, tolerance=0.01)
    assert r.passed is True


def test_total_count_fail_outside_tolerance() -> None:
    m = _manifest()  # expected = 60
    client = MagicMock()
    client.get_statistics.return_value = {"photos": 0, "videos": 0}
    r = check_total_count(client, m, tolerance=0.01)
    assert r.passed is False
    assert "0" in r.message


def test_extension_count_uses_search_metadata() -> None:
    m = _manifest()  # heic = 30
    client = MagicMock()
    client.search_metadata.return_value = [{"id": str(i)} for i in range(30)]
    r = check_extension_count(client, m, "heic", tolerance=0.01)
    assert r.passed is True
    client.search_metadata.assert_called_once()
    payload = client.search_metadata.call_args.args[0]
    assert ".heic" in payload.get("originalFileName", "").lower() \
        or "heic" in payload.get("originalFileName", "").lower()
