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
