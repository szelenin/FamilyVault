"""Tests for matcher.IcloudIndex and evaluate_photo."""
from __future__ import annotations
import sqlite3
from pathlib import Path

from scripts.spike_google_icloud_gps.matcher import IcloudIndex, evaluate_photo


def _make_export_db(tmp_path: Path) -> Path:
    db_path = tmp_path / ".osxphotos_export.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE export_data (uuid TEXT, filepath TEXT)")
    conn.execute("INSERT INTO export_data VALUES ('UUID-A', '_/IMG_2910.HEIC')")
    conn.execute("INSERT INTO export_data VALUES ('UUID-B', '_/IMG_5000.HEIC')")
    conn.commit()
    conn.close()
    return db_path


def _make_photos_db(tmp_path: Path) -> Path:
    db_dir = tmp_path / "Photos Library.photoslibrary" / "database"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "Photos.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE ZASSET (
        Z_PK INTEGER PRIMARY KEY, ZUUID TEXT, ZTRASHEDSTATE INT,
        ZDATECREATED REAL, ZLATITUDE REAL, ZLONGITUDE REAL, ZADDITIONALATTRIBUTES INT
    )""")
    conn.execute("""CREATE TABLE ZADDITIONALASSETATTRIBUTES (
        Z_PK INTEGER PRIMARY KEY, ZORIGINALFILENAME TEXT,
        ZORIGINALFILESIZE INT, ZORIGINALWIDTH INT, ZORIGINALHEIGHT INT,
        ZORIGINALSTABLEHASH TEXT
    )""")
    conn.execute("INSERT INTO ZADDITIONALASSETATTRIBUTES VALUES (1, 'IMG_2910.HEIC', 2500000, 4032, 3024, 'sha-A')")
    conn.execute("INSERT INTO ZADDITIONALASSETATTRIBUTES VALUES (2, 'IMG_5000.HEIC', 3100000, 4032, 3024, 'sha-B')")
    conn.execute("INSERT INTO ZASSET VALUES (10, 'UUID-A', 0, 717096209.5, 25.7264, -80.2414, 1)")
    conn.execute("INSERT INTO ZASSET VALUES (11, 'UUID-B', 0, 722000001.0, -180.0, -180.0, 2)")
    conn.commit()
    conn.close()
    return db_path


def test_icloud_index_lookup_by_filename(tmp_path):
    photos_db = _make_photos_db(tmp_path)
    export_db = _make_export_db(tmp_path)
    idx = IcloudIndex(photos_db=photos_db, export_db=export_db)
    matches = idx.find_by_filename("IMG_2910.HEIC")
    assert len(matches) == 1
    m = matches[0]
    assert m["uuid"] == "UUID-A"
    assert m["filename"] == "IMG_2910.HEIC"
    assert m["size_bytes"] == 2500000
    assert m["stable_hash"] == "sha-A"
    assert m["latitude"] == 25.7264


def test_icloud_index_lookup_no_match(tmp_path):
    photos_db = _make_photos_db(tmp_path)
    export_db = _make_export_db(tmp_path)
    idx = IcloudIndex(photos_db=photos_db, export_db=export_db)
    assert idx.find_by_filename("NONEXISTENT.HEIC") == []


def test_evaluate_photo_perfect_match(google_photo_with_gps, icloud_row_match):
    rows = evaluate_photo(
        sidecar={
            "title": google_photo_with_gps["title"],
            "taken_time_unix": int(google_photo_with_gps["photoTakenTime"]["timestamp"]),
            "geo_lat": google_photo_with_gps["geoData"]["latitude"],
            "geo_lon": google_photo_with_gps["geoData"]["longitude"],
            "exif_lat": google_photo_with_gps["geoDataExif"]["latitude"],
            "exif_lon": google_photo_with_gps["geoDataExif"]["longitude"],
            "sidecar_path": None,
        },
        google_path=None,
        icloud_candidates=[icloud_row_match],
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["google_title"] == "IMG_2910.HEIC"
    assert r["icloud_uuid"] == "ABC-123"
    assert r["s1_name_match"] is True
    assert r["s2_date_diff_seconds"] < 1.0
    assert r["gps_gap"] is False


def test_evaluate_photo_unmatched(google_photo_with_gps):
    rows = evaluate_photo(
        sidecar={
            "title": google_photo_with_gps["title"],
            "taken_time_unix": int(google_photo_with_gps["photoTakenTime"]["timestamp"]),
            "geo_lat": google_photo_with_gps["geoData"]["latitude"],
            "geo_lon": google_photo_with_gps["geoData"]["longitude"],
            "exif_lat": google_photo_with_gps["geoDataExif"]["latitude"],
            "exif_lon": google_photo_with_gps["geoDataExif"]["longitude"],
            "sidecar_path": None,
        },
        google_path=None,
        icloud_candidates=[],
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["icloud_uuid"] is None
    assert r["composite_confidence"] == 0.0
    assert r["gps_gap"] is True  # google has GPS, no iCloud match


def test_evaluate_photo_gps_gap(google_photo_added_gps, icloud_row_no_gps):
    rows = evaluate_photo(
        sidecar={
            "title": google_photo_added_gps["title"],
            "taken_time_unix": int(google_photo_added_gps["photoTakenTime"]["timestamp"]),
            "geo_lat": google_photo_added_gps["geoData"]["latitude"],
            "geo_lon": google_photo_added_gps["geoData"]["longitude"],
            "exif_lat": google_photo_added_gps["geoDataExif"]["latitude"],
            "exif_lon": google_photo_added_gps["geoDataExif"]["longitude"],
            "sidecar_path": None,
        },
        google_path=None,
        icloud_candidates=[icloud_row_no_gps],
    )
    assert len(rows) == 1
    assert rows[0]["gps_gap"] is True
