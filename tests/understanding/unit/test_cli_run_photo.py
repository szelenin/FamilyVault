"""T015/T019/T020 — unit tests for the CLI run-photo orchestrator.

Mocking policy:
  - REAL temp-dir SQLite (open_db on tmp_path)
  - REAL temp staging dir
  - FAKE session (MagicMock), FAKE captioner, FAKE embed_fn
  - Only external boundaries are mocked (Immich API, VLM, embedder)

These tests cover:
  - happy path: 2 fake photos → both status=done, captions stored
  - incremental skip: pre-seeded done asset not re-captioned
  - changed asset: old source_hash → re-processed
  - per-asset error isolation: one error, other still done
  - missing preview: download_preview returns None → status=no_preview
  - chunking/staging cleanup: chunk_size=1 → staging clean at end
  - backup: backup_dir set → DB copy created
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

from index.db import open_db, counts, upsert_asset
from index.status import Status
from caption.base import CaptionResult
from caption.photo_ollama import CaptionError
from index_cli import run_photos


# ---------------------------------------------------------------------------
# Helpers / shared fakes
# ---------------------------------------------------------------------------

SCHEMA_VER = 1


def _fake_immich_asset(asset_id: str, source_hash: str, **kwargs) -> dict:
    """Build a minimal raw Immich asset dict."""
    return {
        "id": asset_id,
        "type": "IMAGE",
        "localDateTime": "2024-06-01T10:00:00",
        "fileCreatedAt": "2024-06-01T10:00:00",
        "exifInfo": {
            "latitude": None,
            "longitude": None,
            "city": None,
            "country": None,
        },
        "people": [],
        "isFavorite": False,
        "duration": None,
        "checksum": source_hash,
        **kwargs,
    }


def _make_fake_session(assets: list[dict]):
    """Return a mock session whose list_photo_assets will yield *assets*.

    The session's .post() returns a paginated Immich-style response.
    The session's .get() returns a fake 200 preview response with dummy bytes.
    """
    session = MagicMock()

    # list_photo_assets calls session.post(...) once (single page)
    mock_list_resp = MagicMock()
    mock_list_resp.json.return_value = {
        "assets": {"items": assets, "nextPage": None}
    }
    session.post.return_value = mock_list_resp

    # download_preview calls session.get(...)
    mock_preview_resp = MagicMock()
    mock_preview_resp.status_code = 200
    mock_preview_resp.content = b"FAKEIMAGEDATA"
    session.get.return_value = mock_preview_resp

    return session


def _make_captioner(caption: str = "A nice photo.", model: str = "fake-model") -> MagicMock:
    """Return a fake captioner that always returns a CaptionResult."""
    captioner = MagicMock()
    captioner.caption.return_value = CaptionResult(
        caption=caption, ocr_text="", model=model
    )
    return captioner


def _fake_embed_fn(text: str) -> bytes:
    """Deterministic fake embed: returns 4 bytes based on text length."""
    from array import array
    val = float(len(text) % 16)
    return array("f", [val, 0.0, 0.0, 1.0]).tobytes()


# ---------------------------------------------------------------------------
# T015a — happy path: 2 assets, both done
# ---------------------------------------------------------------------------


def test_happy_path_two_assets_done(tmp_path):
    """Two new assets → both rows status=done, captions + embeddings stored."""
    conn = open_db(tmp_path / "index.db")
    staging = tmp_path / "staging"
    staging.mkdir()

    assets = [
        _fake_immich_asset("img-1", "hash-1"),
        _fake_immich_asset("img-2", "hash-2"),
    ]
    session = _make_fake_session(assets)
    captioner = _make_captioner("A family photo.")

    result = run_photos(
        conn,
        session=session,
        captioner=captioner,
        embed_fn=_fake_embed_fn,
        staging_dir=staging,
        schema_ver=SCHEMA_VER,
    )

    # Both assets processed
    assert result["done"] == 2
    assert result["pending"] == 0
    assert result["error"] == 0

    # Caption + embedding stored
    for aid in ("img-1", "img-2"):
        row = conn.execute(
            "SELECT status, caption, caption_embedding FROM assets WHERE asset_id=?",
            (aid,),
        ).fetchone()
        assert row is not None, f"{aid} not found"
        assert row["status"] == "done"
        assert row["caption"] == "A family photo."
        assert row["caption_embedding"] is not None

    conn.close()


# ---------------------------------------------------------------------------
# T015b — incremental skip: pre-seeded done asset not re-captioned
# ---------------------------------------------------------------------------


def test_incremental_skip_done_asset_unchanged_hash(tmp_path):
    """Pre-seeded done asset with matching source_hash → captioner NOT called."""
    conn = open_db(tmp_path / "index.db")
    staging = tmp_path / "staging"
    staging.mkdir()

    # Pre-seed img-1 as done with current hash + schema_ver
    upsert_asset(conn, {
        "asset_id": "img-1",
        "type": "IMAGE",
        "status": "done",
        "caption": "Already captioned.",
        "ocr_text": "",
        "caption_embedding": _fake_embed_fn("Already captioned."),
        "taken_at": "2024-01-01T00:00:00",
        "lat": None, "lon": None, "city": None, "country": None,
        "person_ids": "[]", "is_favorite": 0, "duration": None,
        "caption_model": "fake-model", "embed_model": "bge-m3",
        "schema_ver": SCHEMA_VER, "source_hash": "hash-stable",
        "error": None, "indexed_at": "2024-01-01T12:00:00",
    })

    # New asset img-2
    assets = [
        _fake_immich_asset("img-1", "hash-stable"),   # same hash → skip
        _fake_immich_asset("img-2", "hash-new"),       # new → process
    ]
    session = _make_fake_session(assets)
    captioner = _make_captioner("New caption.")

    run_photos(
        conn,
        session=session,
        captioner=captioner,
        embed_fn=_fake_embed_fn,
        staging_dir=staging,
        schema_ver=SCHEMA_VER,
    )

    # Captioner called exactly once (for img-2 only)
    assert captioner.caption.call_count == 1

    # img-1 still has old caption (not clobbered)
    row = conn.execute(
        "SELECT caption FROM assets WHERE asset_id='img-1'"
    ).fetchone()
    assert row["caption"] == "Already captioned."

    conn.close()


# ---------------------------------------------------------------------------
# T015c — changed asset: old source_hash → re-processed
# ---------------------------------------------------------------------------


def test_changed_asset_reprocessed(tmp_path):
    """Pre-seeded done asset with OLD source_hash → captioner called, row updated."""
    conn = open_db(tmp_path / "index.db")
    staging = tmp_path / "staging"
    staging.mkdir()

    # Pre-seed img-1 as done with OLD hash
    upsert_asset(conn, {
        "asset_id": "img-1",
        "type": "IMAGE",
        "status": "done",
        "caption": "Old caption.",
        "ocr_text": "",
        "caption_embedding": _fake_embed_fn("Old caption."),
        "taken_at": "2024-01-01T00:00:00",
        "lat": None, "lon": None, "city": None, "country": None,
        "person_ids": "[]", "is_favorite": 0, "duration": None,
        "caption_model": "fake-model", "embed_model": "bge-m3",
        "schema_ver": SCHEMA_VER, "source_hash": "hash-old",
        "error": None, "indexed_at": "2024-01-01T12:00:00",
    })

    # Immich returns img-1 with NEW hash
    assets = [_fake_immich_asset("img-1", "hash-NEW")]
    session = _make_fake_session(assets)
    captioner = _make_captioner("Updated caption.")

    run_photos(
        conn,
        session=session,
        captioner=captioner,
        embed_fn=_fake_embed_fn,
        staging_dir=staging,
        schema_ver=SCHEMA_VER,
    )

    # Captioner called for the changed asset
    assert captioner.caption.call_count == 1

    # Row updated
    row = conn.execute(
        "SELECT status, caption, source_hash FROM assets WHERE asset_id='img-1'"
    ).fetchone()
    assert row["status"] == "done"
    assert row["caption"] == "Updated caption."
    assert row["source_hash"] == "hash-NEW"

    conn.close()


# ---------------------------------------------------------------------------
# T015d — per-asset error isolation
# ---------------------------------------------------------------------------


def test_per_asset_error_isolation(tmp_path):
    """CaptionError on one asset → that asset=error; other asset=done; run completes."""
    conn = open_db(tmp_path / "index.db")
    staging = tmp_path / "staging"
    staging.mkdir()

    assets = [
        _fake_immich_asset("img-ok", "hash-ok"),
        _fake_immich_asset("img-bad", "hash-bad"),
    ]
    session = _make_fake_session(assets)

    # Captioner raises CaptionError for img-bad
    def _side_effect(paths, *, is_video, ocr_frames=None):
        if "img-bad" in paths[0]:
            raise CaptionError("model crashed")
        return CaptionResult(caption="Good photo.", ocr_text="", model="fake")

    captioner = MagicMock()
    captioner.caption.side_effect = _side_effect

    result = run_photos(
        conn,
        session=session,
        captioner=captioner,
        embed_fn=_fake_embed_fn,
        staging_dir=staging,
        schema_ver=SCHEMA_VER,
    )

    # run returns counts (does not raise)
    assert result["done"] == 1
    assert result["error"] == 1

    # img-ok is done
    row_ok = conn.execute(
        "SELECT status FROM assets WHERE asset_id='img-ok'"
    ).fetchone()
    assert row_ok["status"] == "done"

    # img-bad is error with message
    row_bad = conn.execute(
        "SELECT status, error FROM assets WHERE asset_id='img-bad'"
    ).fetchone()
    assert row_bad["status"] == "error"
    assert "model crashed" in row_bad["error"]

    conn.close()


# ---------------------------------------------------------------------------
# T015e — missing preview
# ---------------------------------------------------------------------------


def test_missing_preview_sets_no_preview(tmp_path):
    """download_preview returns None → status=no_preview; not counted as done/error."""
    conn = open_db(tmp_path / "index.db")
    staging = tmp_path / "staging"
    staging.mkdir()

    assets = [
        _fake_immich_asset("img-nopreview", "hash-np"),
        _fake_immich_asset("img-ok", "hash-ok"),
    ]

    # Session: img-nopreview gets a non-200 (no preview), img-ok gets 200
    session = MagicMock()
    # list call
    mock_list_resp = MagicMock()
    mock_list_resp.json.return_value = {
        "assets": {"items": assets, "nextPage": None}
    }
    session.post.return_value = mock_list_resp

    def _get_side_effect(url, **kwargs):
        resp = MagicMock()
        if "img-nopreview" in url:
            resp.status_code = 404
            resp.content = b""
        else:
            resp.status_code = 200
            resp.content = b"FAKEDATA"
        return resp

    session.get.side_effect = _get_side_effect

    captioner = _make_captioner("Some caption.")

    result = run_photos(
        conn,
        session=session,
        captioner=captioner,
        embed_fn=_fake_embed_fn,
        staging_dir=staging,
        schema_ver=SCHEMA_VER,
    )

    assert result["no_preview"] == 1
    assert result["done"] == 1
    assert result["error"] == 0

    row = conn.execute(
        "SELECT status FROM assets WHERE asset_id='img-nopreview'"
    ).fetchone()
    assert row["status"] == "no_preview"

    conn.close()


# ---------------------------------------------------------------------------
# T015f — chunking / staging cleanup
# ---------------------------------------------------------------------------


def test_chunking_staging_cleanup(tmp_path):
    """chunk_size=1, 3 assets → staging dir empty at end (files not accumulated)."""
    conn = open_db(tmp_path / "index.db")
    staging = tmp_path / "staging"
    staging.mkdir()

    assets = [
        _fake_immich_asset("img-1", "h1"),
        _fake_immich_asset("img-2", "h2"),
        _fake_immich_asset("img-3", "h3"),
    ]
    session = _make_fake_session(assets)
    captioner = _make_captioner("Photo.")

    run_photos(
        conn,
        session=session,
        captioner=captioner,
        embed_fn=_fake_embed_fn,
        staging_dir=staging,
        schema_ver=SCHEMA_VER,
        chunk_size=1,
    )

    # Staging dir is empty after run
    remaining = list(staging.iterdir())
    assert remaining == [], f"Staging not empty: {remaining}"

    # All three done
    assert counts(conn)["done"] == 3

    conn.close()


# ---------------------------------------------------------------------------
# T015g — backup
# ---------------------------------------------------------------------------


def test_backup_creates_db_copy(tmp_path):
    """With backup_dir set, a DB copy exists in backup_dir at end of run."""
    conn = open_db(tmp_path / "index.db")
    staging = tmp_path / "staging"
    staging.mkdir()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    assets = [_fake_immich_asset("img-1", "hash-1")]
    session = _make_fake_session(assets)
    captioner = _make_captioner("Photo.")

    run_photos(
        conn,
        session=session,
        captioner=captioner,
        embed_fn=_fake_embed_fn,
        staging_dir=staging,
        schema_ver=SCHEMA_VER,
        backup_dir=backup_dir,
    )

    backup_files = list(backup_dir.iterdir())
    assert len(backup_files) == 1, f"Expected 1 backup file, got: {backup_files}"
    assert backup_files[0].suffix == ".db"

    conn.close()


# ---------------------------------------------------------------------------
# T019 — limit parameter
# ---------------------------------------------------------------------------


def test_limit_parameter_respected(tmp_path):
    """limit=1 with 2 pending assets → only 1 processed."""
    conn = open_db(tmp_path / "index.db")
    staging = tmp_path / "staging"
    staging.mkdir()

    assets = [
        _fake_immich_asset("img-1", "h1"),
        _fake_immich_asset("img-2", "h2"),
    ]
    session = _make_fake_session(assets)
    captioner = _make_captioner("Photo.")

    run_photos(
        conn,
        session=session,
        captioner=captioner,
        embed_fn=_fake_embed_fn,
        staging_dir=staging,
        schema_ver=SCHEMA_VER,
        limit=1,
    )

    # Only 1 captioner call
    assert captioner.caption.call_count == 1
    c = counts(conn)
    # 1 done, 1 pending (not processed due to limit)
    assert c["done"] == 1
    assert c["pending"] == 1

    conn.close()
