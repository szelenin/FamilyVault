"""T033/T034 — memory governor integration + staging/resume in run_photos.

Governance must wrap ONLY the caption phase: fetch (Immich up) → free_for_phase
(may stop Immich) → caption from staged files → restore. Verified via an ordered
event log across the faked session / captioner / governor.
"""
from array import array

from index.db import open_db
from caption.base import CaptionResult, REQUIRED_MODELS
from resources import StoppedState
import index_cli


def _photo_asset(aid, checksum="h1"):
    return {"id": aid, "type": "IMAGE", "localDateTime": "2025-01-01T00:00:00.000Z",
            "checksum": checksum, "isFavorite": False, "exifInfo": {}, "people": []}


class _Resp:
    def __init__(self, items=None, content=b"", status=200, next_page=None):
        self._items, self.content, self.status_code, self._next = items, content, status, next_page

    def json(self):
        return {"assets": {"items": self._items, "nextPage": self._next}}


class EventSession:
    def __init__(self, assets, log):
        self._assets, self.log = assets, log

    def post(self, url, json=None):
        return _Resp(items=self._assets, next_page=None)

    def get(self, url, params=None):
        self.log.append("fetch")
        return _Resp(content=b"imgbytes", status=200)


class EventCaptioner:
    def __init__(self, log):
        self.log, self.calls = log, 0

    def caption(self, paths, *, is_video, ocr_frames=None, frame_times=None):
        self.log.append("caption")
        self.calls += 1
        return CaptionResult(caption="a caption", ocr_text="", segments=None, model="m")


class EventGovernor:
    def __init__(self, log):
        self.log, self.freed, self.restored = log, [], 0

    def free_for_phase(self, required, *, policy, need_gb):
        self.log.append("govern")
        self.freed.append((required, policy, need_gb))
        return StoppedState([], False, False)

    def restore(self, state):
        self.log.append("restore")
        self.restored += 1


def _embed(text):
    return array("f", [1.0]).tobytes()


def test_governor_wraps_caption_phase_after_fetch(tmp_path):
    log = []
    conn = open_db(str(tmp_path / "i.db"))
    gov = EventGovernor(log)
    index_cli.run_photos(
        conn, session=EventSession([_photo_asset("a"), _photo_asset("b")], log),
        captioner=EventCaptioner(log), embed_fn=_embed,
        staging_dir=str(tmp_path / "s"), chunk_size=10,
        governor=gov, memory_policy="auto",
    )
    # All fetches (Immich up) → one govern → all captions → restore.
    assert log == ["fetch", "fetch", "govern", "caption", "caption", "restore"]
    required, policy, need = gov.freed[0]
    assert required == REQUIRED_MODELS["photo"]
    assert policy == "auto" and need > 0
    assert gov.restored == 1


def test_no_governor_means_no_governance(tmp_path):
    log = []
    conn = open_db(str(tmp_path / "i.db"))
    index_cli.run_photos(
        conn, session=EventSession([_photo_asset("a")], log),
        captioner=EventCaptioner(log), embed_fn=_embed,
        staging_dir=str(tmp_path / "s"), chunk_size=10,
    )
    assert "govern" not in log and "restore" not in log


def test_restore_called_even_if_caption_errors(tmp_path):
    log = []
    conn = open_db(str(tmp_path / "i.db"))
    gov = EventGovernor(log)

    class Boom(EventCaptioner):
        def caption(self, *a, **k):
            self.log.append("caption")
            raise RuntimeError("boom")

    index_cli.run_photos(
        conn, session=EventSession([_photo_asset("a")], log),
        captioner=Boom(log), embed_fn=_embed,
        staging_dir=str(tmp_path / "s"), chunk_size=10, governor=gov,
    )
    assert gov.restored == 1                       # restored despite per-asset error
    assert conn.execute("SELECT status FROM assets WHERE asset_id='a'").fetchone()[0] == "error"


def test_clean_staging_wipes_dir(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    stg = tmp_path / "s"
    stg.mkdir()
    (stg / "leftover.jpg").write_bytes(b"x")
    index_cli.run_photos(
        conn, session=EventSession([], []), captioner=EventCaptioner([]),
        embed_fn=_embed, staging_dir=str(stg), chunk_size=10, clean_staging=True,
    )
    assert not (stg / "leftover.jpg").exists()


def test_resume_skips_done_on_rerun(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    cap = EventCaptioner([])
    s = EventSession([_photo_asset("a"), _photo_asset("b")], [])
    common = dict(captioner=cap, embed_fn=_embed,
                  staging_dir=str(tmp_path / "s"), chunk_size=10)
    index_cli.run_photos(conn, session=s, **common)
    after_first = cap.calls
    index_cli.run_photos(conn, session=s, **common)   # unchanged source
    assert cap.calls == after_first                   # nothing re-captioned (resume/idempotent)
