"""SQLite index core for the FamilyVault understanding layer.

This is the ONLY module that touches SQLite. All other modules interact with
the index exclusively through the public API defined here.

Wire format for embeddings: array('f', list_of_floats).tobytes()
"""
import math
import os
import shutil
import sqlite3
from array import array
from typing import Any, Optional

from index.status import Status

# Current schema version. Bump this when the schema changes to trigger re-indexing.
CURRENT_SCHEMA_VER = 1

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cosine_similarity(a: bytes, b: bytes) -> float:
    """Compute cosine similarity between two array('f') BLOBs.

    Returns 0.0 if either vector is zero-length or has zero norm.
    """
    va = array("f")
    va.frombytes(a)
    vb = array("f")
    vb.frombytes(b)
    if len(va) != len(vb) or len(va) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(va, vb))
    norm_a = math.sqrt(sum(x * x for x in va))
    norm_b = math.sqrt(sum(x * x for x in vb))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Schema DDL — kept as individual statements to avoid splitting on ';' inside
# trigger bodies. executescript() is used so each statement is atomic.
# ---------------------------------------------------------------------------

_DDL_STATEMENTS = [
    # Core tables
    """
    CREATE TABLE IF NOT EXISTS assets (
        asset_id          TEXT PRIMARY KEY,
        type              TEXT,
        status            TEXT,
        caption           TEXT,
        ocr_text          TEXT,
        caption_embedding BLOB,
        taken_at          TEXT,
        lat               REAL,
        lon               REAL,
        city              TEXT,
        country           TEXT,
        person_ids        TEXT,
        is_favorite       INTEGER,
        duration          REAL,
        caption_model     TEXT,
        embed_model       TEXT,
        schema_ver        INTEGER,
        source_hash       TEXT,
        error             TEXT,
        indexed_at        TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS video_segments (
        asset_id  TEXT  NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
        t_start   REAL  NOT NULL,
        t_end     REAL,
        caption   TEXT,
        ocr_text  TEXT,
        embedding BLOB,
        PRIMARY KEY (asset_id, t_start)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at  TEXT,
        finished_at TEXT,
        counts_json TEXT
    )
    """,
    # FTS5 virtual table — standalone (no content= link).
    # We store asset_id as an UNINDEXED column so results can be filtered by it.
    # Sync is managed explicitly in upsert_asset and the asset-delete helper
    # rather than via triggers (FTS5 DELETE inside triggers is unreliable in
    # SQLite when the FTS table is in the same transaction as the base table).
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(
        asset_id UNINDEXED,
        caption,
        ocr_text
    )
    """,
    # Mapping table: asset_id -> FTS5 rowid.
    # Needed because FTS5 DELETE inside a trigger fired from the assets table
    # is unreliable in SQLite. Instead we use a two-stage trigger chain:
    #   AFTER DELETE on assets → delete from asset_fts_rowid
    #   AFTER DELETE on asset_fts_rowid → delete from assets_fts
    # Deleting from FTS5 inside a trigger on a *different* table works fine.
    """
    CREATE TABLE IF NOT EXISTS asset_fts_rowid (
        asset_id TEXT PRIMARY KEY,
        fts_rowid INTEGER
    )
    """,
    # Stage 1: when an asset is deleted, remove its FTS rowid mapping.
    """
    CREATE TRIGGER IF NOT EXISTS assets_del_fts_map
    AFTER DELETE ON assets BEGIN
        DELETE FROM asset_fts_rowid WHERE asset_id = old.asset_id;
    END
    """,
    # Stage 2: when the mapping row is deleted, remove the FTS5 entry.
    """
    CREATE TRIGGER IF NOT EXISTS fts_map_del
    AFTER DELETE ON asset_fts_rowid BEGIN
        DELETE FROM assets_fts WHERE rowid = old.fts_rowid;
    END
    """,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def open_db(path) -> sqlite3.Connection:
    """Open (or create) the SQLite index at *path*, migrate schema, enable WAL.

    Returns an open sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    path = str(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    # Enable WAL for better concurrent read/write performance.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Apply DDL statements individually so CREATE IF NOT EXISTS is idempotent.
    # Using explicit list avoids splitting on ';' inside trigger bodies.
    for stmt in _DDL_STATEMENTS:
        conn.execute(stmt)
    conn.commit()
    return conn


def _fts_delete(conn: sqlite3.Connection, asset_id: str) -> None:
    """Remove the FTS5 entry for asset_id if one exists.

    Deletes from asset_fts_rowid, which triggers fts_map_del to remove the
    FTS5 row. Direct DELETE on assets_fts from inside a transaction on the
    assets table is unreliable in SQLite; the two-stage trigger chain avoids it.
    """
    conn.execute("DELETE FROM asset_fts_rowid WHERE asset_id=?", (asset_id,))


def _fts_insert(conn: sqlite3.Connection, asset_id: str, caption, ocr_text) -> None:
    """Insert an FTS5 entry and track the new rowid in asset_fts_rowid."""
    conn.execute(
        "INSERT INTO assets_fts(asset_id, caption, ocr_text) VALUES (?,?,?)",
        (asset_id, caption, ocr_text),
    )
    fts_rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT OR REPLACE INTO asset_fts_rowid(asset_id, fts_rowid) VALUES (?,?)",
        (asset_id, fts_rowid),
    )


def upsert_asset(conn: sqlite3.Connection, row: dict) -> None:
    """Insert or replace one asset row.

    *row* is a dict keyed by column name. Missing columns default to None.
    Also keeps assets_fts in sync by removing the old FTS entry and inserting
    a new one (trigger-based sync is unreliable for FTS5 with INSERT OR REPLACE).
    """
    asset_id = row.get("asset_id")
    columns = [
        "asset_id", "type", "status", "caption", "ocr_text", "caption_embedding",
        "taken_at", "lat", "lon", "city", "country", "person_ids", "is_favorite",
        "duration", "caption_model", "embed_model", "schema_ver", "source_hash",
        "error", "indexed_at",
    ]
    vals = [row.get(col) for col in columns]
    placeholders = ", ".join("?" * len(columns))
    col_names = ", ".join(columns)

    # Remove old FTS entry first (must be done before the row is replaced).
    _fts_delete(conn, asset_id)

    conn.execute(
        f"INSERT OR REPLACE INTO assets ({col_names}) VALUES ({placeholders})",
        vals,
    )

    # Add the new FTS entry.
    _fts_insert(conn, asset_id, row.get("caption"), row.get("ocr_text"))
    conn.commit()


def upsert_segments(
    conn: sqlite3.Connection, asset_id: str, segments: list
) -> None:
    """Replace all video segments for *asset_id*.

    *segments* is a list of dicts with keys: t_start, t_end, caption,
    ocr_text, and optionally embedding (BLOB).
    """
    conn.execute(
        "DELETE FROM video_segments WHERE asset_id=?", (asset_id,)
    )
    for seg in segments:
        conn.execute(
            "INSERT INTO video_segments (asset_id, t_start, t_end, caption, ocr_text, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                asset_id,
                seg.get("t_start"),
                seg.get("t_end"),
                seg.get("caption"),
                seg.get("ocr_text"),
                seg.get("embedding"),
            ),
        )
    conn.commit()


def set_status(
    conn: sqlite3.Connection,
    asset_id: str,
    status: Status,
    *,
    error: Optional[str] = None,
) -> None:
    """Update the status (and optionally error text) for an asset.

    If *status* is not ERROR, the error column is cleared to None.
    """
    if status is Status.ERROR:
        conn.execute(
            "UPDATE assets SET status=?, error=? WHERE asset_id=?",
            (status.value, error, asset_id),
        )
    else:
        conn.execute(
            "UPDATE assets SET status=?, error=NULL WHERE asset_id=?",
            (status.value, asset_id),
        )
    conn.commit()


def plan(
    conn: sqlite3.Connection,
    *,
    type: Optional[str],
    schema_ver: int,
) -> list:
    """Return assets that need (re-)processing.

    Selects assets where:
      - status = 'pending', OR
      - schema_ver stored in DB < *schema_ver* (schema bumped since last index)

    The `type` parameter filters by asset type (IMAGE/VIDEO); None means all.

    Returns a list of dicts with at least asset_id and type.
    """
    if type is not None:
        base_q = """
            SELECT asset_id, type FROM assets
            WHERE ((status = 'pending') OR (schema_ver < ?))
              AND type = ?
        """
        params: list = [schema_ver, type]
    else:
        base_q = """
            SELECT asset_id, type FROM assets
            WHERE (status = 'pending')
               OR (schema_ver < ?)
        """
        params = [schema_ver]

    cur = conn.execute(base_q, params)
    return [dict(row) for row in cur.fetchall()]


def counts(conn: sqlite3.Connection) -> dict:
    """Return per-status counts as a dict: {pending, done, no_preview, error}."""
    result = {"pending": 0, "done": 0, "no_preview": 0, "error": 0}
    cur = conn.execute(
        "SELECT status, COUNT(*) FROM assets GROUP BY status"
    )
    for status_val, n in cur.fetchall():
        if status_val in result:
            result[status_val] = n
    return result


def search(
    conn: sqlite3.Connection,
    query_vec: bytes,
    query_text: str,
    *,
    k: int,
) -> list:
    """Hybrid search: FTS5 lexical UNION brute-force cosine vector ranking.

    Returns up to *k* hits as list of dicts: {asset_id, score, snippet}.

    Strategy:
      1. FTS5 candidates: rows matching *query_text* (if non-empty).
      2. Vector candidates: all rows with caption_embedding (cosine similarity).
      3. Union by asset_id, take top-k by score descending.
    """
    hits: dict[str, dict] = {}  # asset_id -> best hit dict

    # --- FTS pass ---
    if query_text and query_text.strip():
        try:
            fts_rows = conn.execute(
                """
                SELECT assets_fts.asset_id,
                       snippet(assets_fts, 1, '<b>', '</b>', '...', 10) AS snip
                FROM assets_fts
                WHERE assets_fts MATCH ?
                """,
                (query_text,),
            ).fetchall()
            for fts_row in fts_rows:
                aid = fts_row["asset_id"]
                # FTS score: fixed bonus so text matches are visible in results.
                if aid not in hits:
                    hits[aid] = {
                        "asset_id": aid,
                        "score": 0.5,  # FTS bonus
                        "snippet": fts_row["snip"] or "",
                    }
                else:
                    hits[aid]["score"] = max(hits[aid]["score"], 0.5)
        except sqlite3.OperationalError:
            # Malformed FTS query — skip the FTS pass gracefully.
            pass

    # --- Vector pass (brute-force cosine) ---
    if query_vec:
        vec_rows = conn.execute(
            "SELECT asset_id, caption_embedding, caption FROM assets WHERE caption_embedding IS NOT NULL"
        ).fetchall()
        for vrow in vec_rows:
            aid = vrow["asset_id"]
            sim = _cosine_similarity(query_vec, vrow["caption_embedding"])
            cap = vrow["caption"] or ""
            snippet_text = cap[:80] + ("..." if len(cap) > 80 else "")
            if aid not in hits:
                hits[aid] = {"asset_id": aid, "score": sim, "snippet": snippet_text}
            else:
                # Combine: keep max of existing score vs cosine sim.
                hits[aid]["score"] = max(hits[aid]["score"], sim)
                if not hits[aid]["snippet"]:
                    hits[aid]["snippet"] = snippet_text

    # Sort by score descending, return top k.
    ranked = sorted(hits.values(), key=lambda h: h["score"], reverse=True)
    return ranked[:k]


def backup(conn: sqlite3.Connection, dest_dir: str) -> str:
    """Copy the DB file into *dest_dir* using SQLite's backup API.

    Returns the destination path as a string.
    """
    # Retrieve the database filename from the connection.
    db_path = conn.execute("PRAGMA database_list").fetchone()["file"]
    filename = os.path.basename(db_path)
    dest_path = os.path.join(dest_dir, filename)

    # Use SQLite's online backup API for a consistent snapshot.
    dest_conn = sqlite3.connect(dest_path)
    conn.backup(dest_conn)
    dest_conn.close()

    return dest_path
