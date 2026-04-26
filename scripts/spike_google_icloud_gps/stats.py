"""Phase A baseline statistics + decision gate."""
from __future__ import annotations
from typing import Iterable, Mapping


def _has_real_gps(lat, lon) -> bool:
    """A pair counts as real GPS if both are non-None and not (0,0)."""
    return (lat is not None) and (lon is not None) and not (lat == 0.0 and lon == 0.0)


def compute_baseline(sidecars: Iterable[Mapping]) -> dict:
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


def should_proceed_to_matching(baseline: Mapping) -> bool:
    """Decision gate. Proceed only if Google has net GPS contribution beyond original EXIF."""
    return baseline["geodata_differs_from_exif"] > 0
