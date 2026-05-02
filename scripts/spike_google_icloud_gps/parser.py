"""Google Takeout JSON sidecar parser. Pure functions only — no I/O beyond reading the file."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Iterator


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


def walk_sidecars(root: Path) -> Iterator[dict[str, Any]]:
    """Recursively yield parsed sidecars for every `*.json` under root."""
    for sidecar_path in root.rglob("*.json"):
        yield parse_sidecar(sidecar_path)
