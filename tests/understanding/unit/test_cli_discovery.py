"""R101b — discovery fast-path + delta watermark in the run orchestration."""
from index.db import open_db, upsert_asset, set_watermark, get_watermark
import index_cli


def _seed_pending(conn, asset_type, n):
    for i in range(n):
        upsert_asset(conn, {"asset_id": f"{asset_type}-{i}", "type": asset_type,
                            "status": "pending", "schema_ver": 1, "source_hash": "h"})


class Recorder:
    """Stand-in for list_photo_assets/list_video_assets that records calls."""
    def __init__(self, returns=None):
        self.calls = []
        self._returns = returns or []

    def __call__(self, session, *, updated_after=None, **kw):
        self.calls.append(updated_after)
        return self._returns


def test_fast_path_skips_immich_when_pending_enough(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    _seed_pending(conn, "IMAGE", 5)
    rec = Recorder()
    todo = index_cli._discover(conn, asset_type="IMAGE", list_fn=rec, session=object(),
                               schema_ver=1, limit=3, full_scan=False)
    assert rec.calls == []
    assert len(todo) == 3


def test_delta_passes_watermark_and_advances_after_pass(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    set_watermark(conn, "IMAGE", "2026-06-16T00:00:00.000Z")
    rec = Recorder(returns=[
        {"id": "a", "type": "IMAGE", "checksum": "h", "updatedAt": "2026-06-16T05:00:00.000Z",
         "localDateTime": "2026-01-01T00:00:00.000Z", "isFavorite": False, "exifInfo": {}, "people": []},
        {"id": "b", "type": "IMAGE", "checksum": "h", "updatedAt": "2026-06-16T03:00:00.000Z",
         "localDateTime": "2026-01-01T00:00:00.000Z", "isFavorite": False, "exifInfo": {}, "people": []},
    ])
    index_cli._discover(conn, asset_type="IMAGE", list_fn=rec, session=object(),
                        schema_ver=1, limit=None, full_scan=False)
    assert rec.calls == ["2026-06-16T00:00:00.000Z"]
    assert get_watermark(conn, "IMAGE") == "2026-06-16T05:00:00.000Z"


def test_full_scan_ignores_and_resets_watermark(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    _seed_pending(conn, "IMAGE", 50)
    set_watermark(conn, "IMAGE", "2026-06-16T00:00:00.000Z")
    rec = Recorder(returns=[])
    index_cli._discover(conn, asset_type="IMAGE", list_fn=rec, session=object(),
                        schema_ver=1, limit=1, full_scan=True)
    assert rec.calls == [None]


def test_interrupted_scan_keeps_old_watermark(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    set_watermark(conn, "IMAGE", "2026-06-16T00:00:00.000Z")

    def boom(session, *, updated_after=None, **kw):
        raise RuntimeError("immich down")

    import pytest
    with pytest.raises(RuntimeError):
        index_cli._discover(conn, asset_type="IMAGE", list_fn=boom, session=object(),
                            schema_ver=1, limit=None, full_scan=False)
    assert get_watermark(conn, "IMAGE") == "2026-06-16T00:00:00.000Z"
