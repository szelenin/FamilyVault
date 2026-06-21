"""T028 unit — `run --type video` orchestration, all external boundaries faked
(Immich session, scene detection, frame extraction, MLX captioner, embedder)."""
import os
from unittest.mock import MagicMock

from index.db import open_db
from caption.base import CaptionResult
import index_cli


def _video_asset(aid, checksum="h1"):
    return {
        "id": aid, "type": "VIDEO", "localDateTime": "2025-01-01T00:00:00.000Z",
        "checksum": checksum, "duration": "0:00:30.000000", "isFavorite": False,
        "exifInfo": {}, "people": [],
    }


class _Resp:
    def __init__(self, items=None, content=b"", status=200, next_page=None):
        self._items, self.content, self.status_code, self._next = items, content, status, next_page

    def json(self):
        return {"assets": {"items": self._items, "nextPage": self._next}}


def _session(assets, video_bytes=b"VIDEOBYTES"):
    s = MagicMock()
    s.post.return_value = _Resp(items=assets, next_page=None)
    s.get.return_value = _Resp(content=video_bytes, status=200)
    return s


def _fake_detect_scenes(path):
    return [(0.0, 5.0), (5.0, 10.0)]          # two scenes


def _fake_extract_frames(video_path, timestamps, dest_dir, *, runner=None):
    paths = []
    for i, t in enumerate(timestamps):
        p = os.path.join(dest_dir, f"frame_{i}_{t}.jpg")
        with open(p, "wb") as fh:
            fh.write(b"f")
        paths.append(p)
    return paths


class _FakeVideoCaptioner:
    def caption(self, paths, *, is_video, ocr_frames=None, frame_times=None):
        segs = [
            {"t_start": 0.0, "t_end": 5.0, "caption": "scene one", "ocr_text": "SIGN"},
            {"t_start": 5.0, "t_end": 10.0, "caption": "scene two", "ocr_text": ""},
        ]
        return CaptionResult(caption="a multi-scene clip", ocr_text="SIGN",
                             segments=segs, model="mlx:test")


def _fake_embed(text):
    from array import array
    return array("f", [1.0, 0.0]).tobytes()


def _run(conn, tmp_path, session, captioner):
    return index_cli.run_videos(
        conn, session=session, captioner=captioner, embed_fn=_fake_embed,
        staging_dir=str(tmp_path / "stg"), chunk_size=10,
        detect_scenes_fn=_fake_detect_scenes, extract_frames_fn=_fake_extract_frames,
    )


def test_video_done_with_caption_embedding_and_segments(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    c = _run(conn, tmp_path, _session([_video_asset("v1")]), _FakeVideoCaptioner())
    assert c["done"] == 1 and c["error"] == 0 and c["no_preview"] == 0
    row = conn.execute(
        "SELECT status, caption, caption_embedding FROM assets WHERE asset_id='v1'"
    ).fetchone()
    assert row[0] == "done" and row[1] and row[2] is not None
    segs = conn.execute(
        "SELECT t_start, t_end, caption FROM video_segments WHERE asset_id='v1' ORDER BY t_start"
    ).fetchall()
    assert len(segs) == 2 and segs[0][2] == "scene one"


def test_missing_video_sets_no_preview(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    s = _session([_video_asset("v1")])
    s.get.return_value = _Resp(content=b"", status=404)
    c = _run(conn, tmp_path, s, _FakeVideoCaptioner())
    assert c["no_preview"] == 1
    assert conn.execute(
        "SELECT status FROM assets WHERE asset_id='v1'"
    ).fetchone()[0] == "no_preview"


def test_per_asset_error_isolation(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))

    class _FailFirst:
        def __init__(self):
            self.n = 0

        def caption(self, paths, *, is_video, ocr_frames=None, frame_times=None):
            self.n += 1
            if self.n == 1:
                from caption.video_mlx import CaptionError
                raise CaptionError("boom")
            return CaptionResult(caption="ok", ocr_text="",
                                 segments=[{"t_start": 0.0, "t_end": 1.0,
                                            "caption": "s", "ocr_text": ""}],
                                 model="mlx:test")

    c = _run(conn, tmp_path,
             _session([_video_asset("v1"), _video_asset("v2", checksum="h2")]),
             _FailFirst())
    assert c["error"] == 1 and c["done"] == 1   # one fails, batch still finishes the other


def test_unextractable_frame_is_dropped(tmp_path):
    """Regression: extract_frames may return a path ffmpeg never wrote (e.g. a
    seek past the last frame). run_videos must drop missing files and still
    caption from the survivors — never hand a nonexistent path to the model."""
    import os

    def partial_extract(video_path, timestamps, dest_dir, *, runner=None):
        paths = []
        for i, t in enumerate(timestamps):
            p = os.path.join(dest_dir, f"frame_{i}_{t}.jpg")
            if i != 0:                       # simulate ffmpeg failing the first seek
                with open(p, "wb") as fh:
                    fh.write(b"f")
            paths.append(p)                  # returns ALL paths, incl. the missing one
        return paths

    class CapRec:
        def __init__(self):
            self.got = None
            self.all_existed_at_call = None

        def caption(self, paths, *, is_video, ocr_frames=None, frame_times=None):
            # Record existence AT CALL TIME (staging is cleaned after the run).
            self.got = list(paths)
            self.all_existed_at_call = all(os.path.exists(p) for p in paths)
            return CaptionResult(caption="ok", ocr_text="",
                                 segments=[{"t_start": 0.0, "t_end": 1.0,
                                            "caption": "s", "ocr_text": ""}],
                                 model="m")

    conn = open_db(str(tmp_path / "i.db"))
    cap = CapRec()
    c = index_cli.run_videos(
        conn, session=_session([_video_asset("v1")]), captioner=cap, embed_fn=_fake_embed,
        staging_dir=str(tmp_path / "stg"), chunk_size=10,
        detect_scenes_fn=_fake_detect_scenes, extract_frames_fn=partial_extract,
    )
    assert c["done"] == 1 and c["error"] == 0
    assert cap.got and cap.all_existed_at_call            # every frame handed to the model existed
    assert not any(p.endswith("frame_0_0.0.jpg") for p in cap.got)  # the unwritten frame was dropped
