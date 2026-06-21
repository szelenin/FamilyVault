"""T016 — end-to-end photo indexing: tiny fixture → run --type photo → search.

Drives the REAL spine (reconcile → plan → caption → embed → SQLite → FTS+vector
search). Only the two external boundaries are faked: the Immich HTTP session and
the VLM/embedder. This is the constitution's "end-to-endish" ideal — no network,
no models, but every internal module is exercised for real.

Covers SC-001 (every photo done with caption+embedding), SC-002 (meaning + exact
text retrieval), SC-005 (idempotent re-run), and the language-agnostic query
*plumbing* for SC-003. The genuine multilingual-semantic assertion (real bge-m3)
lives in tests/understanding/integration/test_crosslang.py (opt-in).
"""
from array import array

import pytest

from index.db import open_db, counts
import index_cli


# --- fakes for the two external boundaries ---------------------------------


class _Resp:
    def __init__(self, *, json_data=None, status_code=200, content=b""):
        self._json = json_data
        self.status_code = status_code
        self.content = content

    def json(self):
        return self._json


class FakeImmich:
    """Fake requests.Session: serves a fixed asset list + preview bytes."""

    def __init__(self, assets, preview=b"\xff\xd8\xff\xe0JPEGBYTES"):
        self._assets = assets
        self._preview = preview
        self.headers = {}

    def post(self, url, json=None):  # /api/search/metadata
        return _Resp(json_data={"assets": {"items": self._assets, "nextPage": None}})

    def get(self, url, params=None):  # /api/assets/{id}/thumbnail
        return _Resp(status_code=200, content=self._preview)


# Deterministic stand-in for a multilingual embedder. Maps text -> a 3-d vector
# by concept keyword (EN, a semantic synonym, and RU all land on the same axis),
# serialized in the canonical array('f') wire format the index expects.
def fake_embed(text):
    t = text.lower()
    if any(w in t for w in ("piano", "keyboard", "пианино", "playing")):
        v = [1.0, 0.0, 0.0]          # "piano" concept axis
    elif any(w in t for w in ("menu", "carbonara", "trattoria")):
        v = [0.0, 1.0, 0.0]          # "menu" concept axis
    else:
        v = [0.0, 0.0, 1.0]
    return array("f", v).tobytes()


class CountingCaptioner:
    """Returns a canned English CaptionResult per asset; counts invocations."""

    def __init__(self, captions):
        self._captions = captions          # asset_id -> (caption, ocr_text)
        self.calls = 0
        self._seen = []

    def caption(self, paths, *, is_video, ocr_frames=None):
        from caption.base import CaptionResult

        self.calls += 1
        # The staged path is <asset_id>.jpg — recover the id for the canned reply.
        asset_id = paths[0].rsplit("/", 1)[-1].removesuffix(".jpg")
        self._seen.append(asset_id)
        cap, ocr = self._captions[asset_id]
        return CaptionResult(caption=cap, ocr_text=ocr, segments=None, model="fake-vlm")


# --- fixture ----------------------------------------------------------------


PIANO = "piano-asset-0001"
MENU = "menu-asset-0002"


def _immich_asset(asset_id, checksum):
    return {
        "id": asset_id,
        "type": "IMAGE",
        "originalFileName": f"{asset_id}.jpg",
        "fileCreatedAt": "2025-03-15T14:30:00.000Z",
        "localDateTime": "2025-03-15T14:30:00.000Z",
        "isFavorite": False,
        "checksum": checksum,
        "exifInfo": {"city": "Miami", "country": "United States",
                     "latitude": 25.7, "longitude": -80.1},
        "people": [{"id": "person-uuid-1", "name": "DoNotStoreThisName"}],
    }


@pytest.fixture
def fixture(tmp_path):
    assets = [_immich_asset(PIANO, "hash-piano-v1"),
              _immich_asset(MENU, "hash-menu-v1")]
    captions = {
        PIANO: ("a young child seated at a grand piano in a living room", ""),
        MENU: ("a printed dinner menu lying on a restaurant table",
               "Trattoria Roma\nSpaghetti Carbonara $18"),
    }
    return {
        "session": FakeImmich(assets),
        "captioner": CountingCaptioner(captions),
        "db": str(tmp_path / "index.db"),
        "staging": str(tmp_path / "staging"),
        "assets": assets,
    }


def _run(f):
    conn = open_db(f["db"])
    counts_out = index_cli.run_photos(
        conn,
        session=f["session"],
        captioner=f["captioner"],
        embed_fn=fake_embed,
        staging_dir=f["staging"],
        chunk_size=1,
    )
    return conn, counts_out


# --- tests ------------------------------------------------------------------


@pytest.mark.e2e
def test_every_photo_done_with_caption_and_embedding(fixture):
    """SC-001: each processable photo ends 'done' with caption + embedding."""
    conn, c = _run(fixture)
    assert c["done"] == 2 and c["error"] == 0 and c["no_preview"] == 0
    rows = conn.execute(
        "SELECT asset_id, status, caption, caption_embedding FROM assets"
    ).fetchall()
    assert len(rows) == 2
    for r in rows:
        assert r["status"] == "done"
        assert r["caption"] and r["caption"].strip()
        assert r["caption_embedding"] is not None


@pytest.mark.e2e
def test_privacy_person_name_not_stored(fixture):
    """FR-007: cached person data is IDs only — the Immich name never lands."""
    conn, _ = _run(fixture)
    row = conn.execute(
        "SELECT person_ids FROM assets WHERE asset_id=?", (PIANO,)
    ).fetchone()
    assert "person-uuid-1" in row["person_ids"]
    assert "DoNotStoreThisName" not in row["person_ids"]


@pytest.mark.e2e
def test_exact_onscreen_text_search(fixture):
    """SC-002 (exact text): on-screen text is retrievable via FTS."""
    conn, _ = _run(fixture)
    hits = index_cli.search_index(conn, "Carbonara", embed_query_fn=fake_embed, k=5)
    assert hits, "expected an FTS hit for on-screen menu text"
    assert hits[0]["asset_id"] == MENU


@pytest.mark.e2e
def test_meaning_based_search_with_different_words(fixture):
    """SC-002 (meaning): a query using different words than the caption still
    finds the photo via the vector path (caption says 'child seated at a grand
    piano'; query says 'kid at the keyboard' — no lexical overlap)."""
    conn, _ = _run(fixture)
    hits = index_cli.search_index(conn, "a kid at the keyboard",
                                  embed_query_fn=fake_embed, k=5)
    assert hits and hits[0]["asset_id"] == PIANO


@pytest.mark.e2e
def test_cross_language_query_plumbing(fixture):
    """SC-003 (plumbing): a non-English (Russian) query flows through the search
    path and returns the asset whose description is English. The genuine
    multilingual-semantic proof (real bge-m3) is the opt-in integration test."""
    conn, _ = _run(fixture)
    hits = index_cli.search_index(conn, "ребёнок играет на пианино",
                                  embed_query_fn=fake_embed, k=5)
    assert hits and hits[0]["asset_id"] == PIANO


@pytest.mark.e2e
def test_rerun_is_idempotent(fixture):
    """SC-005: re-running with no source changes processes zero assets."""
    conn, _ = _run(fixture)
    calls_after_first = fixture["captioner"].calls
    assert calls_after_first == 2

    # Re-run against the same connection + unchanged Immich state.
    c2 = index_cli.run_photos(
        conn,
        session=fixture["session"],
        captioner=fixture["captioner"],
        embed_fn=fake_embed,
        staging_dir=fixture["staging"],
        chunk_size=1,
    )
    assert fixture["captioner"].calls == calls_after_first  # nothing re-captioned
    assert c2["done"] == 2 and c2["pending"] == 0
