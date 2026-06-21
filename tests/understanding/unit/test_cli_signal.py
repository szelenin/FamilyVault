"""Termination-signal handling for `run`: SIGTERM must restore the governor.

The governor's restore runs in a per-chunk `finally`, so it already fires on
normal completion, exceptions, and SIGINT (Ctrl-C raises KeyboardInterrupt and
unwinds the stack). SIGTERM, however, terminates the process via Python's
default handler WITHOUT unwinding — skipping `finally`, leaving Immich/OrbStack
stopped. The fix installs a SIGTERM handler that raises KeyboardInterrupt so the
existing `finally` restore path runs. These tests pin both halves:

  1. `_install_termination_handler` registers a SIGTERM handler that raises.
  2. A KeyboardInterrupt mid-caption still triggers `governor.restore` (the
     behavior the converted SIGTERM relies on).
"""
import signal
from array import array

import pytest

from index.db import open_db
from caption.base import CaptionResult
from resources import StoppedState
import index_cli


# ---------------------------------------------------------------------------
# 1. SIGTERM handler installation + behavior
# ---------------------------------------------------------------------------

class _FakeSignal:
    """Records signal.signal() registrations without touching real handlers."""

    SIGTERM = signal.SIGTERM
    SIGINT = signal.SIGINT

    def __init__(self):
        self.registered = {}

    def signal(self, sig, handler):
        prev = self.registered.get(sig)
        self.registered[sig] = handler
        return prev


def test_install_termination_handler_registers_sigterm():
    fake = _FakeSignal()
    index_cli._install_termination_handler(signal_mod=fake)
    assert signal.SIGTERM in fake.registered
    assert callable(fake.registered[signal.SIGTERM])


def test_termination_handler_raises_keyboardinterrupt():
    fake = _FakeSignal()
    index_cli._install_termination_handler(signal_mod=fake)
    handler = fake.registered[signal.SIGTERM]
    with pytest.raises(KeyboardInterrupt):
        handler(signal.SIGTERM, None)


def test_install_termination_handler_leaves_sigint_to_default():
    # SIGINT already raises KeyboardInterrupt by default; we must not override it.
    fake = _FakeSignal()
    index_cli._install_termination_handler(signal_mod=fake)
    assert signal.SIGINT not in fake.registered


# ---------------------------------------------------------------------------
# 2. KeyboardInterrupt mid-caption still restores the governor
# ---------------------------------------------------------------------------

def _photo_asset(aid, checksum="h1"):
    return {"id": aid, "type": "IMAGE", "localDateTime": "2025-01-01T00:00:00.000Z",
            "checksum": checksum, "isFavorite": False, "exifInfo": {}, "people": []}


class _Resp:
    def __init__(self, items=None, content=b"", status=200, next_page=None):
        self._items, self.content, self.status_code, self._next = items, content, status, next_page

    def json(self):
        return {"assets": {"items": self._items, "nextPage": self._next}}


class _Session:
    def __init__(self, assets):
        self._assets = assets

    def post(self, url, json=None):
        return _Resp(items=self._assets, next_page=None)

    def get(self, url, params=None):
        return _Resp(content=b"imgbytes", status=200)


class _Governor:
    def __init__(self):
        self.restored = 0

    def free_for_phase(self, required, *, policy, need_gb):
        return StoppedState([], False, False)

    def restore(self, state):
        self.restored += 1


def _embed(text):
    return array("f", [1.0]).tobytes()


class _InterruptCaptioner:
    def caption(self, paths, *, is_video, ocr_frames=None, frame_times=None):
        raise KeyboardInterrupt()


def test_restore_called_when_caption_interrupted(tmp_path):
    # A KeyboardInterrupt (what the SIGTERM handler raises) propagates out of
    # run_photos but the per-chunk `finally` must still restore the governor.
    conn = open_db(str(tmp_path / "i.db"))
    gov = _Governor()
    with pytest.raises(KeyboardInterrupt):
        index_cli.run_photos(
            conn, session=_Session([_photo_asset("a")]),
            captioner=_InterruptCaptioner(), embed_fn=_embed,
            staging_dir=str(tmp_path / "s"), chunk_size=10, governor=gov,
        )
    assert gov.restored == 1
    conn.close()
