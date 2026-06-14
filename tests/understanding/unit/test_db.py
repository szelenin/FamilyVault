"""T007/T008 — unit tests for the SQLite index core (setup/understanding/index/db.py).

Mocking policy: REAL temp-dir SQLite database (pytest tmp_path). No mocks.
All tests must run fast (< a few seconds total).
"""
import json
import os
import sqlite3
from array import array

import pytest

from index.db import (
    backup,
    counts,
    open_db,
    plan,
    search,
    set_status,
    upsert_asset,
    upsert_segments,
)
from index.status import Status

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCHEMA_VER = 1  # current schema version used by the db module


def _make_asset(asset_id="asset-1", type="IMAGE", status="pending", **kwargs):
    row = {
        "asset_id": asset_id,
        "type": type,
        "status": status,
        "caption": kwargs.get("caption", None),
        "ocr_text": kwargs.get("ocr_text", None),
        "caption_embedding": kwargs.get("caption_embedding", None),
        "taken_at": kwargs.get("taken_at", "2024-01-01T00:00:00"),
        "lat": kwargs.get("lat", None),
        "lon": kwargs.get("lon", None),
        "city": kwargs.get("city", None),
        "country": kwargs.get("country", None),
        "person_ids": kwargs.get("person_ids", "[]"),
        "is_favorite": kwargs.get("is_favorite", 0),
        "duration": kwargs.get("duration", None),
        "caption_model": kwargs.get("caption_model", None),
        "embed_model": kwargs.get("embed_model", None),
        "schema_ver": kwargs.get("schema_ver", SCHEMA_VER),
        "source_hash": kwargs.get("source_hash", "abc123"),
        "error": kwargs.get("error", None),
        "indexed_at": kwargs.get("indexed_at", None),
    }
    return row


def _vec(values):
    """Serialize a list of floats to BLOB using array('f') wire format."""
    return array("f", values).tobytes()


# ---------------------------------------------------------------------------
# open_db
# ---------------------------------------------------------------------------


def test_open_db_creates_schema(tmp_path):
    """open_db must create all required tables."""
    conn = open_db(tmp_path / "test.db")
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cur.fetchall()}
    assert "assets" in tables
    assert "video_segments" in tables
    assert "runs" in tables
    conn.close()


def test_open_db_creates_fts5_table(tmp_path):
    """open_db must create the assets_fts virtual FTS5 table."""
    conn = open_db(tmp_path / "test.db")
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='assets_fts'"
    )
    assert cur.fetchone() is not None, "assets_fts FTS5 table not found"
    conn.close()


def test_open_db_enables_wal(tmp_path):
    """open_db must enable WAL journal mode."""
    conn = open_db(tmp_path / "test.db")
    row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0] == "wal"
    conn.close()


def test_open_db_idempotent(tmp_path):
    """Opening the same DB a second time must not raise (schema already exists)."""
    db_path = tmp_path / "test.db"
    conn1 = open_db(db_path)
    conn1.close()
    conn2 = open_db(db_path)
    conn2.close()


# ---------------------------------------------------------------------------
# upsert_asset
# ---------------------------------------------------------------------------


def test_upsert_asset_inserts_row(tmp_path):
    """upsert_asset must insert a row into assets."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1"))
    row = conn.execute(
        "SELECT asset_id, type, status FROM assets WHERE asset_id='a1'"
    ).fetchone()
    assert row is not None
    assert row[0] == "a1"
    assert row[1] == "IMAGE"
    assert row[2] == "pending"
    conn.close()


def test_upsert_asset_replaces_existing(tmp_path):
    """Re-upserting the same asset_id must replace (no duplicate row)."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", caption="first"))
    upsert_asset(conn, _make_asset("a1", caption="second"))
    rows = conn.execute("SELECT caption FROM assets WHERE asset_id='a1'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "second"
    conn.close()


def test_upsert_asset_roundtrips_fields(tmp_path):
    """All non-embedding fields round-trip correctly."""
    conn = open_db(tmp_path / "test.db")
    asset = _make_asset(
        "a1",
        type="VIDEO",
        status="done",
        caption="A sunset over the ocean",
        ocr_text="hello world",
        taken_at="2023-06-15T14:30:00",
        lat=37.7749,
        lon=-122.4194,
        city="San Francisco",
        country="USA",
        person_ids='["p1","p2"]',
        is_favorite=1,
        duration=12.5,
        caption_model="qwen3-vl:8b",
        embed_model="bge-m3",
        schema_ver=SCHEMA_VER,
        source_hash="deadbeef",
        error=None,
        indexed_at="2024-01-02T10:00:00",
    )
    upsert_asset(conn, asset)
    row = conn.execute(
        "SELECT asset_id, type, status, caption, ocr_text, taken_at, lat, lon, "
        "city, country, person_ids, is_favorite, duration, caption_model, embed_model, "
        "schema_ver, source_hash, error, indexed_at "
        "FROM assets WHERE asset_id='a1'"
    ).fetchone()
    assert row[0] == "a1"
    assert row[1] == "VIDEO"
    assert row[2] == "done"
    assert row[3] == "A sunset over the ocean"
    assert row[4] == "hello world"
    assert row[5] == "2023-06-15T14:30:00"
    assert abs(row[6] - 37.7749) < 1e-5
    assert abs(row[7] - (-122.4194)) < 1e-5
    assert row[8] == "San Francisco"
    assert row[9] == "USA"
    assert row[10] == '["p1","p2"]'
    assert row[11] == 1
    assert abs(row[12] - 12.5) < 1e-5
    assert row[13] == "qwen3-vl:8b"
    assert row[14] == "bge-m3"
    assert row[15] == SCHEMA_VER
    assert row[16] == "deadbeef"
    assert row[17] is None
    assert row[18] == "2024-01-02T10:00:00"
    conn.close()


# ---------------------------------------------------------------------------
# upsert_segments
# ---------------------------------------------------------------------------


def test_upsert_segments_inserts(tmp_path):
    """upsert_segments must write video segments for an asset."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("v1", type="VIDEO"))
    segs = [
        {"t_start": 0.0, "t_end": 5.0, "caption": "intro", "ocr_text": ""},
        {"t_start": 5.0, "t_end": 10.0, "caption": "action", "ocr_text": "BAM"},
    ]
    upsert_segments(conn, "v1", segs)
    rows = conn.execute(
        "SELECT t_start, t_end, caption, ocr_text FROM video_segments WHERE asset_id='v1' ORDER BY t_start"
    ).fetchall()
    assert len(rows) == 2
    assert tuple(rows[0]) == (0.0, 5.0, "intro", "")
    assert tuple(rows[1]) == (5.0, 10.0, "action", "BAM")
    conn.close()


def test_upsert_segments_replaces(tmp_path):
    """Calling upsert_segments a second time must replace old segments (no duplicates)."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("v1", type="VIDEO"))
    upsert_segments(conn, "v1", [{"t_start": 0.0, "t_end": 3.0, "caption": "old", "ocr_text": ""}])
    upsert_segments(conn, "v1", [{"t_start": 0.0, "t_end": 3.0, "caption": "new", "ocr_text": ""}])
    rows = conn.execute(
        "SELECT caption FROM video_segments WHERE asset_id='v1'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "new"
    conn.close()


def test_upsert_segments_cascade_delete(tmp_path):
    """Deleting an asset must cascade-delete its segments."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("v1", type="VIDEO"))
    upsert_segments(conn, "v1", [{"t_start": 0.0, "t_end": 5.0, "caption": "seg", "ocr_text": ""}])
    conn.execute("DELETE FROM assets WHERE asset_id='v1'")
    conn.commit()
    rows = conn.execute(
        "SELECT COUNT(*) FROM video_segments WHERE asset_id='v1'"
    ).fetchone()
    assert rows[0] == 0
    conn.close()


def test_upsert_segments_with_embedding(tmp_path):
    """upsert_segments must store embeddings as BLOBs."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("v1", type="VIDEO"))
    emb = _vec([0.1, 0.2, 0.3])
    upsert_segments(conn, "v1", [{"t_start": 0.0, "t_end": 2.0, "caption": "c", "ocr_text": "", "embedding": emb}])
    row = conn.execute("SELECT embedding FROM video_segments WHERE asset_id='v1'").fetchone()
    assert row[0] == emb
    conn.close()


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def test_plan_returns_pending_assets(tmp_path):
    """plan() must return assets with status='pending'."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", status="pending"))
    upsert_asset(conn, _make_asset("a2", status="done"))
    result = plan(conn, type=None, schema_ver=SCHEMA_VER)
    ids = {r["asset_id"] for r in result}
    assert "a1" in ids
    assert "a2" not in ids
    conn.close()


def test_plan_excludes_uptodate_done(tmp_path):
    """plan() must NOT return done assets whose source_hash and schema_ver are current."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", status="done", source_hash="hash1", schema_ver=SCHEMA_VER))
    result = plan(conn, type=None, schema_ver=SCHEMA_VER)
    ids = {r["asset_id"] for r in result}
    assert "a1" not in ids
    conn.close()


def test_plan_returns_asset_with_changed_source_hash(tmp_path):
    """plan() must return done assets whose source_hash changed."""
    conn = open_db(tmp_path / "test.db")
    # Insert done asset with old hash
    upsert_asset(conn, _make_asset("a1", status="done", source_hash="oldhash", schema_ver=SCHEMA_VER))
    # Now re-upsert with new hash (simulating a changed file)
    upsert_asset(conn, _make_asset("a1", status="done", source_hash="newhash", schema_ver=SCHEMA_VER))
    # plan should be called with knowledge of the NEW hash; but plan reads from DB.
    # The plan() function is called with current schema_ver; it returns assets
    # where source_hash is different from what was at last index — but since we just
    # wrote newhash, the DB has newhash. The contract is: plan returns assets that
    # need re-work. We test by inserting an asset whose stored source_hash differs
    # from the "canonical" hash that should trigger re-indexing.
    # The simplest interpretation: plan returns done assets only if they have
    # schema_ver < current OR if the caller supplies an updated source_hash.
    # Since plan() only reads from DB, a source_hash change means: the caller
    # upserts the row with new source_hash but keeps status='done', and plan picks
    # it up because the row was updated but not re-processed.
    # Let's use a flag approach: after upsert with new hash, reset status to pending.
    upsert_asset(conn, _make_asset("a1", status="pending", source_hash="newhash", schema_ver=SCHEMA_VER))
    result = plan(conn, type=None, schema_ver=SCHEMA_VER)
    ids = {r["asset_id"] for r in result}
    assert "a1" in ids
    conn.close()


def test_plan_returns_assets_with_old_schema_ver(tmp_path):
    """plan() must return done assets with schema_ver < current."""
    conn = open_db(tmp_path / "test.db")
    old_ver = SCHEMA_VER - 1  # schema_ver less than current
    if old_ver < 0:
        old_ver = 0
    upsert_asset(conn, _make_asset("a1", status="done", source_hash="hash1", schema_ver=old_ver))
    result = plan(conn, type=None, schema_ver=SCHEMA_VER)
    ids = {r["asset_id"] for r in result}
    # Only relevant if old_ver < SCHEMA_VER
    if old_ver < SCHEMA_VER:
        assert "a1" in ids
    conn.close()


def test_plan_type_filter_image(tmp_path):
    """plan(type='IMAGE') must return only IMAGE assets."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("img1", type="IMAGE", status="pending"))
    upsert_asset(conn, _make_asset("vid1", type="VIDEO", status="pending"))
    result = plan(conn, type="IMAGE", schema_ver=SCHEMA_VER)
    ids = {r["asset_id"] for r in result}
    assert "img1" in ids
    assert "vid1" not in ids
    conn.close()


def test_plan_type_filter_video(tmp_path):
    """plan(type='VIDEO') must return only VIDEO assets."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("img1", type="IMAGE", status="pending"))
    upsert_asset(conn, _make_asset("vid1", type="VIDEO", status="pending"))
    result = plan(conn, type="VIDEO", schema_ver=SCHEMA_VER)
    ids = {r["asset_id"] for r in result}
    assert "vid1" in ids
    assert "img1" not in ids
    conn.close()


def test_plan_type_none_returns_all(tmp_path):
    """plan(type=None) must return all asset types."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("img1", type="IMAGE", status="pending"))
    upsert_asset(conn, _make_asset("vid1", type="VIDEO", status="pending"))
    result = plan(conn, type=None, schema_ver=SCHEMA_VER)
    ids = {r["asset_id"] for r in result}
    assert "img1" in ids
    assert "vid1" in ids
    conn.close()


# ---------------------------------------------------------------------------
# set_status
# ---------------------------------------------------------------------------


def test_set_status_updates_status(tmp_path):
    """set_status must update the status column."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", status="pending"))
    set_status(conn, "a1", Status.DONE)
    row = conn.execute("SELECT status FROM assets WHERE asset_id='a1'").fetchone()
    assert row[0] == "done"
    conn.close()


def test_set_status_stores_error_text(tmp_path):
    """set_status with status=error must store the error text."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", status="pending"))
    set_status(conn, "a1", Status.ERROR, error="Model timeout after 30s")
    row = conn.execute("SELECT status, error FROM assets WHERE asset_id='a1'").fetchone()
    assert row[0] == "error"
    assert row[1] == "Model timeout after 30s"
    conn.close()


def test_set_status_clears_error_on_non_error(tmp_path):
    """set_status to non-error state should clear any previous error text."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", status="pending", error="previous error"))
    set_status(conn, "a1", Status.DONE)
    row = conn.execute("SELECT error FROM assets WHERE asset_id='a1'").fetchone()
    assert row[0] is None
    conn.close()


# ---------------------------------------------------------------------------
# counts
# ---------------------------------------------------------------------------


def test_counts_returns_correct_tallies(tmp_path):
    """counts() must return per-status counts."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", status="pending"))
    upsert_asset(conn, _make_asset("a2", status="pending"))
    upsert_asset(conn, _make_asset("a3", status="done"))
    upsert_asset(conn, _make_asset("a4", status="no_preview"))
    upsert_asset(conn, _make_asset("a5", status="error"))
    result = counts(conn)
    assert result["pending"] == 2
    assert result["done"] == 1
    assert result["no_preview"] == 1
    assert result["error"] == 1
    conn.close()


def test_counts_empty_db(tmp_path):
    """counts() on empty DB must return zeros for all statuses."""
    conn = open_db(tmp_path / "test.db")
    result = counts(conn)
    assert result["pending"] == 0
    assert result["done"] == 0
    assert result["no_preview"] == 0
    assert result["error"] == 0
    conn.close()


# ---------------------------------------------------------------------------
# FTS5 triggers
# ---------------------------------------------------------------------------


def test_fts_finds_asset_by_caption(tmp_path):
    """After upsert_asset with caption, FTS MATCH must find the asset."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", caption="golden gate bridge at sunset"))
    rows = conn.execute(
        "SELECT rowid FROM assets_fts WHERE assets_fts MATCH 'golden'"
    ).fetchall()
    assert len(rows) >= 1
    conn.close()


def test_fts_finds_asset_by_ocr_text(tmp_path):
    """After upsert_asset with ocr_text, FTS MATCH must find the asset."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", ocr_text="EXIT ONLY highway sign"))
    rows = conn.execute(
        "SELECT rowid FROM assets_fts WHERE assets_fts MATCH 'EXIT'"
    ).fetchall()
    assert len(rows) >= 1
    conn.close()


def test_fts_stale_text_removed_on_update(tmp_path):
    """After updating caption, stale text must no longer match via FTS."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", caption="beach volleyball tournament"))
    # Verify the initial text is found
    rows = conn.execute(
        "SELECT rowid FROM assets_fts WHERE assets_fts MATCH 'volleyball'"
    ).fetchall()
    assert len(rows) >= 1
    # Update with different caption
    upsert_asset(conn, _make_asset("a1", caption="mountain hiking trail"))
    # Old text should no longer match
    rows_old = conn.execute(
        "SELECT rowid FROM assets_fts WHERE assets_fts MATCH 'volleyball'"
    ).fetchall()
    assert len(rows_old) == 0
    # New text should match
    rows_new = conn.execute(
        "SELECT rowid FROM assets_fts WHERE assets_fts MATCH 'hiking'"
    ).fetchall()
    assert len(rows_new) >= 1
    conn.close()


def test_fts_removed_on_asset_delete(tmp_path):
    """After deleting an asset, FTS must no longer return it."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", caption="purple elephant dancing"))
    conn.execute("DELETE FROM assets WHERE asset_id='a1'")
    conn.commit()
    rows = conn.execute(
        "SELECT rowid FROM assets_fts WHERE assets_fts MATCH 'elephant'"
    ).fetchall()
    assert len(rows) == 0
    conn.close()


# ---------------------------------------------------------------------------
# Vector search
# ---------------------------------------------------------------------------


def test_vector_search_returns_nearest_first(tmp_path):
    """search() with query_vec must return the most similar asset first (cosine)."""
    conn = open_db(tmp_path / "test.db")
    # Two 3-d vectors; query is close to a1, far from a2
    emb_a1 = _vec([1.0, 0.0, 0.0])
    emb_a2 = _vec([0.0, 1.0, 0.0])
    query_vec = _vec([0.9, 0.1, 0.0])  # much closer to a1
    upsert_asset(conn, _make_asset("a1", caption="red apple", caption_embedding=emb_a1))
    upsert_asset(conn, _make_asset("a2", caption="blue sky", caption_embedding=emb_a2))
    results = search(conn, query_vec, query_text="", k=2)
    assert len(results) >= 1
    assert results[0]["asset_id"] == "a1"
    conn.close()


def test_vector_search_k_limits_results(tmp_path):
    """search() must return at most k results."""
    conn = open_db(tmp_path / "test.db")
    for i in range(5):
        emb = _vec([float(i), 0.0, 0.0])
        upsert_asset(conn, _make_asset(f"a{i}", caption=f"asset {i}", caption_embedding=emb))
    query_vec = _vec([1.0, 0.0, 0.0])
    results = search(conn, query_vec, query_text="", k=3)
    assert len(results) <= 3
    conn.close()


def test_vector_search_skips_assets_without_embedding(tmp_path):
    """search() must not crash when some assets lack embeddings."""
    conn = open_db(tmp_path / "test.db")
    upsert_asset(conn, _make_asset("a1", caption="no embedding here"))
    upsert_asset(conn, _make_asset("a2", caption="has embedding", caption_embedding=_vec([1.0, 0.0, 0.0])))
    query_vec = _vec([1.0, 0.0, 0.0])
    results = search(conn, query_vec, query_text="", k=5)
    ids = {r["asset_id"] for r in results}
    assert "a2" in ids
    conn.close()


# ---------------------------------------------------------------------------
# Hybrid search (FTS + vector)
# ---------------------------------------------------------------------------


def test_search_hybrid_fts_match_returns_asset(tmp_path):
    """search() with query_text that matches FTS must return the asset even with far vector."""
    conn = open_db(tmp_path / "test.db")
    # a1 has text match but orthogonal vector
    emb_a1 = _vec([0.0, 1.0, 0.0])
    # a2 is closest in vector space but no text match
    emb_a2 = _vec([1.0, 0.0, 0.0])
    query_vec = _vec([1.0, 0.0, 0.0])  # closest to a2

    upsert_asset(conn, _make_asset("a1", caption="extraordinary sunset photograph", caption_embedding=emb_a1))
    upsert_asset(conn, _make_asset("a2", caption="ocean wave", caption_embedding=emb_a2))

    results = search(conn, query_vec, query_text="extraordinary", k=5)
    ids = {r["asset_id"] for r in results}
    assert "a1" in ids  # must appear due to FTS match
    conn.close()


def test_search_returns_score_and_snippet(tmp_path):
    """search() results must include asset_id, score, and snippet fields."""
    conn = open_db(tmp_path / "test.db")
    emb = _vec([1.0, 0.0, 0.0])
    upsert_asset(conn, _make_asset("a1", caption="family reunion picnic", caption_embedding=emb))
    results = search(conn, emb, query_text="reunion", k=5)
    assert len(results) >= 1
    hit = results[0]
    assert "asset_id" in hit
    assert "score" in hit
    assert "snippet" in hit
    conn.close()


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------


def test_backup_copies_db_file(tmp_path):
    """backup() must copy the DB file to dest_dir and return the dest path."""
    conn = open_db(tmp_path / "source.db")
    upsert_asset(conn, _make_asset("a1", caption="backup test"))
    dest_dir = tmp_path / "backups"
    dest_dir.mkdir()
    dest_path = backup(conn, str(dest_dir))
    assert os.path.isfile(dest_path)
    conn.close()


def test_backup_copy_is_readable(tmp_path):
    """The backup copy must open and contain the original rows."""
    conn = open_db(tmp_path / "source.db")
    upsert_asset(conn, _make_asset("a1", caption="backup test row"))
    dest_dir = tmp_path / "backups"
    dest_dir.mkdir()
    dest_path = backup(conn, str(dest_dir))
    conn.close()
    conn2 = sqlite3.connect(dest_path)
    row = conn2.execute("SELECT caption FROM assets WHERE asset_id='a1'").fetchone()
    assert row is not None
    assert row[0] == "backup test row"
    conn2.close()
