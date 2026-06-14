"""Integration — genuine cross-language semantic retrieval with the real bge-m3.

This is the honest verification of FR-004 / SC-003: an English caption is indexed,
and a query in Russian (and Ukrainian) — with NO lexical overlap and NO stored
translation — retrieves it via the multilingual embedding space.

Opt-in (marker `integration`); skips automatically if Ollama + bge-m3 are not
reachable, so the default unit/e2e suite stays offline and fast. Run with:

    python3.13 -m pytest tests/understanding/integration/test_crosslang.py -m integration -q
"""
import pytest

from index.db import open_db, upsert_asset

pytestmark = pytest.mark.integration


def _embed_or_skip():
    """Return caption/embed.embed/embed_query, or skip if Ollama/bge-m3 is down."""
    try:
        from caption.embed import embed, embed_query
        # Probe: a real call. Any failure (no server, model missing) → skip.
        embed("connectivity probe")
    except Exception as exc:  # noqa: BLE001 — any failure means "env not ready"
        pytest.skip(f"Ollama/bge-m3 not available: {exc}")
    return embed, embed_query


def _seed(conn, embed):
    # English-only captions; identity/translation never stored.
    rows = {
        "piano-en": "a young child is playing the piano at home",
        "beach-en": "a family building a sandcastle on a sunny beach",
    }
    for asset_id, caption in rows.items():
        upsert_asset(conn, {
            "asset_id": asset_id, "type": "IMAGE", "status": "done",
            "caption": caption, "ocr_text": "",
            "caption_embedding": embed(caption),
            "schema_ver": 1, "source_hash": asset_id,
        })
    conn.commit()


@pytest.mark.parametrize("query, expected", [
    ("ребёнок играет на пианино", "piano-en"),     # Russian: child plays piano
    ("дитина грає на піаніно", "piano-en"),         # Ukrainian: child plays piano
    ("семья на пляже", "beach-en"),                 # Russian: family at the beach
])
def test_non_english_query_matches_english_caption(tmp_path, query, expected):
    import index_cli

    embed, embed_query = _embed_or_skip()
    conn = open_db(str(tmp_path / "index.db"))
    _seed(conn, embed)

    hits = index_cli.search_index(conn, query, embed_query_fn=embed_query, k=2)
    assert hits, f"no hits for cross-language query {query!r}"
    assert hits[0]["asset_id"] == expected, (
        f"{query!r} should retrieve the English caption {expected!r}, "
        f"got {hits[0]['asset_id']!r}"
    )
