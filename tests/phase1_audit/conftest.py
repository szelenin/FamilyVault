"""Shared pytest fixtures for the phase1_audit test package."""
from __future__ import annotations
import json
from pathlib import Path
import pytest


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    """Write a small valid manifest fixture and return its path."""
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({
        "source_zip": "test.zip",
        "total_files_in_html": 100,
        "total_folders": 5,
        "extension_counts": {
            "json": 40, "heic": 30, "jpg": 20, "mp4": 10
        },
        "year_folder_count": 2,
        "year_folder_range": ["Photos from 2020", "Photos from 2021"],
        "user_album_count": 3,
        "user_albums": ["Trip A", "Trip B", "Trip C"],
    }))
    return p
