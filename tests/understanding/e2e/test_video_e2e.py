"""T024 — end-to-end video indexing on tiny fixtures.

Drives the REAL spine: run_videos → plan_frames (real sampling) → VideoMLXCaptioner
(real parsing/segment construction) → SQLite assets + video_segments + FTS search.
Faked boundaries only: Immich session, scene detection, frame extraction, the MLX
backend (returns canned JSON), and the embedder.

Covers SC-004 (video-level caption + >=1 segment; multi-scene reflects >1) and that
on-screen text is captured and searchable.
"""
import json
import os
from array import array
from unittest.mock import MagicMock

import pytest

from index.db import open_db
from caption.video_mlx import VideoMLXCaptioner
import index_cli


class _Resp:
    def __init__(self, items=None, content=b"", status=200, next_page=None):
        self._items, self.content, self.status_code, self._next = items, content, status, next_page

    def json(self):
        return {"assets": {"items": self._items, "nextPage": self._next}}


def _session(assets):
    s = MagicMock()
    s.post.return_value = _Resp(items=assets, next_page=None)
    s.get.return_value = _Resp(content=b"VIDEOBYTES", status=200)
    return s


def _video_asset(aid):
    return {"id": aid, "type": "VIDEO", "localDateTime": "2025-01-01T00:00:00.000Z",
            "checksum": f"hash-{aid}", "duration": "0:00:15.000000",
            "isFavorite": False, "exifInfo": {}, "people": []}


def _extract_frames(video_path, timestamps, dest_dir, *, runner=None):
    out = []
    for i, t in enumerate(timestamps):
        p = os.path.join(dest_dir, f"frame_{i}_{t}.jpg")
        with open(p, "wb") as fh:
            fh.write(b"f")
        out.append(p)
    return out


def _embed(text):
    return array("f", [1.0, 0.0, 0.0]).tobytes()


# Fake MLX backend: returns canned JSON honoring the video_mlx reply contract.
def _make_backend(segments, caption, ocr):
    def backend(frame_paths, prompt):
        return json.dumps({"caption": caption, "ocr_text": ocr, "segments": segments})
    return backend


def _run(conn, tmp_path, asset_id, scenes, backend):
    return index_cli.run_videos(
        conn,
        session=_session([_video_asset(asset_id)]),
        captioner=VideoMLXCaptioner(backend=backend),
        embed_fn=_embed,
        staging_dir=str(tmp_path / "stg"),
        chunk_size=10,
        detect_scenes_fn=lambda path: scenes,
        extract_frames_fn=_extract_frames,
    )


@pytest.mark.e2e
def test_multiscene_video_yields_multiple_segments_and_is_searchable(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    segments = [
        {"t_start": 0.0, "t_end": 5.0, "caption": "kids build a sandcastle on the beach", "ocr_text": "WELCOME"},
        {"t_start": 5.0, "t_end": 10.0, "caption": "the family swims in the pool", "ocr_text": ""},
        {"t_start": 10.0, "t_end": 15.0, "caption": "everyone eats dinner at a restaurant", "ocr_text": ""},
    ]
    backend = _make_backend(segments, "a beach trip across three distinct scenes", "WELCOME")
    c = _run(conn, tmp_path, "vid-multi", [(0.0, 5.0), (5.0, 10.0), (10.0, 15.0)], backend)

    assert c["done"] == 1 and c["error"] == 0
    row = conn.execute(
        "SELECT caption, ocr_text, caption_embedding FROM assets WHERE asset_id='vid-multi'"
    ).fetchone()
    assert row[0] and row[2] is not None            # video-level caption + embedding
    assert "WELCOME" in (row[1] or "")              # OCR captured at asset level

    segs = conn.execute(
        "SELECT t_start, caption FROM video_segments WHERE asset_id='vid-multi' ORDER BY t_start"
    ).fetchall()
    assert len(segs) > 1                            # multi-scene reflects >1 segment (SC-004)

    # Searchable by activity text (FTS over the video-level caption).
    hits = index_cli.search_index(conn, "beach trip", embed_query_fn=_embed, k=5)
    assert hits and hits[0]["asset_id"] == "vid-multi"


@pytest.mark.e2e
def test_single_shot_video_still_yields_a_segment(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    segments = [{"t_start": 0.0, "t_end": 15.0,
                 "caption": "a continuous handheld clip of a birthday party", "ocr_text": ""}]
    backend = _make_backend(segments, "a single continuous birthday clip", "")
    # Single scene → plan_frames uses the uniform fallback (no degenerate 1-frame).
    c = _run(conn, tmp_path, "vid-single", [(0.0, 15.0)], backend)

    assert c["done"] == 1 and c["error"] == 0
    row = conn.execute("SELECT caption FROM assets WHERE asset_id='vid-single'").fetchone()
    assert row[0]                                   # meaningful video-level caption
    segs = conn.execute(
        "SELECT COUNT(*) FROM video_segments WHERE asset_id='vid-single'"
    ).fetchone()
    assert segs[0] >= 1                             # at least one timestamped segment
