"""T031 — integration: a run under simulated low free-RAM frees memory
(escalating to stopping the photo server) and restores it afterward.

Wires the actual run_photos pipeline to a real MemoryGovernor. Service control
and the memory reading are injected with safe recording stubs (nothing real is
stopped), so this is deterministic and safe to run anywhere; the `integration`
marker keeps it opt-in-categorized alongside the live-model tests.
"""
from array import array
from unittest.mock import MagicMock

import pytest

from index.db import open_db
from caption.base import CaptionResult
from resources import MemoryGovernor
import index_cli

pytestmark = pytest.mark.integration


class _Resp:
    def __init__(self, items=None, content=b"", status=200, next_page=None):
        self._items, self.content, self.status_code, self._next = items, content, status, next_page

    def json(self):
        return {"assets": {"items": self._items, "nextPage": self._next}}


def _session():
    s = MagicMock()
    s.post.return_value = _Resp(
        items=[{"id": "a", "type": "IMAGE", "localDateTime": "2025-01-01T00:00:00.000Z",
                "checksum": "h", "isFavorite": False, "exifInfo": {}, "people": []}],
        next_page=None,
    )
    s.get.return_value = _Resp(content=b"img", status=200)
    return s


class _Captioner:
    def caption(self, paths, *, is_video, ocr_frames=None, frame_times=None):
        return CaptionResult(caption="a photo", ocr_text="", segments=None, model="m")


def test_low_ram_frees_memory_and_restores_photo_server(tmp_path):
    events = []
    # Available RAM stays low through the model-unload step, then jumps up once
    # Immich is stopped — so the governor must escalate to stopping Immich.
    reads = iter([1.0, 1.0, 50.0])

    def available_gb():
        try:
            return next(reads)
        except StopIteration:
            return 50.0

    gov = MemoryGovernor(
        available_gb_fn=available_gb,
        list_loaded_fn=lambda: ["a-stale-model"],
        unload_fn=lambda m: events.append(("unload", m)),
        stop_immich_fn=lambda: events.append("stop_immich"),
        start_immich_fn=lambda: events.append("start_immich"),
        stop_orbstack_fn=lambda: events.append("stop_orbstack"),
        start_orbstack_fn=lambda: events.append("start_orbstack"),
    )

    conn = open_db(str(tmp_path / "i.db"))
    counts = index_cli.run_photos(
        conn, session=_session(), captioner=_Captioner(),
        embed_fn=lambda t: array("f", [1.0]).tobytes(),
        staging_dir=str(tmp_path / "s"), chunk_size=10,
        governor=gov, memory_policy="auto", need_gb=10.0,
    )

    assert counts["done"] == 1
    # Escalated least-disruptive first: unloaded a stale model, then stopped Immich.
    assert ("unload", "a-stale-model") in events
    assert "stop_immich" in events
    # ...and the photo server was restored afterward.
    assert "start_immich" in events
    assert "stop_orbstack" not in events          # stopped escalating once RAM sufficed
