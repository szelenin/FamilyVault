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
