"""Tests for the manifest loader."""
from __future__ import annotations
from pathlib import Path

from scripts.phase1_audit.manifest import Manifest, load_manifest


def test_load_manifest_returns_typed_object(manifest_path: Path) -> None:
    m = load_manifest(manifest_path)
    assert isinstance(m, Manifest)
    assert m.user_album_count == 3
    assert m.user_albums == ("Trip A", "Trip B", "Trip C")


def test_manifest_expected_media_count_excludes_json_and_no_ext(manifest_path: Path) -> None:
    m = load_manifest(manifest_path)
    # 100 - 40 (json) = 60 (no 'no-ext' bucket in fixture, so just subtract json)
    assert m.expected_media_count() == 60


def test_manifest_extension_counts_accessor(manifest_path: Path) -> None:
    m = load_manifest(manifest_path)
    assert m.count_for_extension("heic") == 30
    assert m.count_for_extension("missing") == 0
