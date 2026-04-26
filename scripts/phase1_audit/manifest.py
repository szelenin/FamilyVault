"""Load and expose typed access to google-takeout-manifest.json."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Manifest:
    """In-memory view of google-takeout-manifest.json."""
    source_zip: str
    total_files_in_html: int
    total_folders: int
    extension_counts: Mapping[str, int]
    year_folder_count: int
    year_folder_range: tuple[str | None, str | None]
    user_album_count: int
    user_albums: tuple[str, ...]

    def expected_media_count(self) -> int:
        """Total media items expected in Immich (excludes sidecars and no-ext entries)."""
        non_media = self.extension_counts.get("json", 0) + self.extension_counts.get("no-ext", 0)
        return self.total_files_in_html - non_media

    def count_for_extension(self, ext: str) -> int:
        """Count of files with the given lowercase extension. Returns 0 if absent."""
        return self.extension_counts.get(ext.lower(), 0)


def load_manifest(path: Path) -> Manifest:
    """Read the manifest JSON at path and return a Manifest object."""
    raw = json.loads(Path(path).read_text())
    yfr = raw.get("year_folder_range") or [None, None]
    return Manifest(
        source_zip=raw["source_zip"],
        total_files_in_html=raw["total_files_in_html"],
        total_folders=raw["total_folders"],
        extension_counts=dict(raw["extension_counts"]),
        year_folder_count=raw["year_folder_count"],
        year_folder_range=(yfr[0], yfr[1]),
        user_album_count=raw["user_album_count"],
        user_albums=tuple(raw["user_albums"]),
    )
