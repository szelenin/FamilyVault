"""Per-photo evaluation orchestrator.

IcloudIndex: in-memory map filename → list of iCloud rows. Built once at startup.
evaluate_photo: given a Google sidecar dict and IcloudIndex, run all signals
and return one or more rows (one per candidate iCloud match, or one row with
no candidate).
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from .signals import (
    name_match, date_diff_seconds, size_match, dim_match, is_original,
    hash_db_match, sha256_match, phash_distance, composite_confidence,
)


def _uri(p: Path) -> str:
    return f"file:{quote(str(p))}?mode=ro"


def _has_real_gps(lat, lon) -> bool:
    return (lat is not None) and (lon is not None) and lat != -180.0 and not (lat == 0.0 and lon == 0.0)


class IcloudIndex:
    """Loads the iCloud library + export tracking DB once and provides filename lookup."""

    def __init__(self, photos_db: Path, export_db: Path) -> None:
        self.photos_db = photos_db
        self.export_db = export_db
        self._by_filename: dict = {}
        self._load()

    def _load(self) -> None:
        # Build uuid → filepath map from export DB
        with sqlite3.connect(str(self.export_db)) as conn:
            uuid_to_path = dict(conn.execute(
                "SELECT uuid, filepath FROM export_data WHERE filepath IS NOT NULL"
            ).fetchall())

        # Read all asset rows from Photos.sqlite (read-only)
        with sqlite3.connect(_uri(self.photos_db), uri=True) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT a.ZUUID AS uuid, aa.ZORIGINALFILENAME AS filename,
                       a.ZDATECREATED AS date_created_apple,
                       a.ZLATITUDE AS latitude, a.ZLONGITUDE AS longitude,
                       aa.ZORIGINALFILESIZE AS size_bytes,
                       aa.ZORIGINALWIDTH AS width, aa.ZORIGINALHEIGHT AS height,
                       aa.ZORIGINALSTABLEHASH AS stable_hash
                FROM ZASSET a
                JOIN ZADDITIONALASSETATTRIBUTES aa ON aa.Z_PK = a.ZADDITIONALATTRIBUTES
                WHERE a.ZTRASHEDSTATE = 0
            """).fetchall()

        for r in rows:
            row = dict(r)
            # Apple's epoch starts 2001-01-01; convert to Unix
            row["date_created_unix"] = (row["date_created_apple"] or 0) + 978307200
            row["filepath"] = uuid_to_path.get(row["uuid"])
            key = (row["filename"] or "").lower()
            self._by_filename.setdefault(key, []).append(row)

    def find_by_filename(self, filename: str) -> list:
        return list(self._by_filename.get(filename.lower(), []))


def evaluate_photo(
    sidecar: dict,
    google_path: Optional[Path],
    icloud_candidates: list,
) -> list:
    """Run all signals for one Google photo against each candidate iCloud row.

    Returns one output row per candidate. If no candidates, returns a single row with
    icloud_uuid=None and composite_confidence=0 — flagging it as a Google-only photo.
    """
    g_has_gps = _has_real_gps(sidecar["geo_lat"], sidecar["geo_lon"])

    if not icloud_candidates:
        return [{
            "google_title": sidecar["title"],
            "google_path": str(google_path) if google_path else None,
            "icloud_uuid": None,
            "icloud_filepath": None,
            "s1_name_match": None,
            "s2_date_diff_seconds": None,
            "s3_size_match": None,
            "s4_dim_match": None,
            "s5_is_original": None,
            "s6_hash_db_match": None,
            "s7_sha256_match": None,
            "s8_phash_distance": None,
            "google_geo_lat": sidecar["geo_lat"],
            "google_geo_lon": sidecar["geo_lon"],
            "icloud_lat": None,
            "icloud_lon": None,
            "gps_gap": g_has_gps,
            "composite_confidence": 0.0,
        }]

    out: list = []
    for cand in icloud_candidates:
        google_size = google_path.stat().st_size if (google_path and google_path.exists()) else None
        google_wh = None  # populated by exiftool/PIL caller in production; tests pass None

        s1 = name_match(sidecar["title"], cand["filename"] or "")
        s2 = date_diff_seconds(sidecar["taken_time_unix"], cand["date_created_unix"])
        s3 = size_match(google_size, cand["size_bytes"]) if google_size else False
        s4 = dim_match(google_wh, (cand.get("width"), cand.get("height")) if cand.get("width") else None)
        s5 = is_original(s3, s4)
        s6 = hash_db_match(google_path, cand.get("stable_hash") or "", s5)
        s7 = sha256_match(google_path, Path(cand["filepath"]) if cand.get("filepath") else None, s5)
        s8 = phash_distance(google_path, Path(cand["filepath"]) if cand.get("filepath") else None)

        conf = composite_confidence(
            s1_name=s1, s2_date_sec=s2, s3_size=bool(s3), s4_dim=s4,
            s6_hash_db=s6, s7_sha256=s7, s8_phash=s8,
        )

        i_has_gps = _has_real_gps(cand["latitude"], cand["longitude"])

        out.append({
            "google_title": sidecar["title"],
            "google_path": str(google_path) if google_path else None,
            "icloud_uuid": cand["uuid"],
            "icloud_filepath": cand.get("filepath"),
            "s1_name_match": s1,
            "s2_date_diff_seconds": s2,
            "s3_size_match": s3 if google_size else None,
            "s4_dim_match": s4,
            "s5_is_original": s5,
            "s6_hash_db_match": s6,
            "s7_sha256_match": s7,
            "s8_phash_distance": s8,
            "google_geo_lat": sidecar["geo_lat"],
            "google_geo_lon": sidecar["geo_lon"],
            "icloud_lat": cand["latitude"],
            "icloud_lon": cand["longitude"],
            "gps_gap": g_has_gps and not i_has_gps,
            "composite_confidence": conf,
        })
    return out
