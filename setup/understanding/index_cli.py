"""index_cli — CLI orchestrator for the FamilyVault understanding-layer indexer.

Public API (injectable, testable without network/models):
  run_photos(conn, *, session, captioner, embed_fn, staging_dir, schema_ver,
             chunk_size=50, backup_dir=None, limit=None) -> dict
  status(conn) -> dict
  search_index(conn, query, *, embed_query_fn=None, k=5) -> list[dict]
  main(argv=None) -> None  (argparse entrypoint; sys.exit codes 0/2/3)

Design principle: all external boundaries (Immich, VLM, embedder) are injected.
Real defaults are built lazily only when a CLI invocation omits them.

Exit codes:
  0  — success
  2  — nothing-to-do (no matches for search, nothing pending for run)
  3  — precondition error (bad args, DB open failure, etc.)
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import shutil

from index.db import (
    CURRENT_SCHEMA_VER,
    backup,
    counts,
    index_state,
    open_db,
    plan,
    search,
    set_status,
    upsert_asset,
    upsert_segments,
)
from index.status import Status
from fetch.immich import (
    asset_filter_fields,
    download_preview,
    download_video,
    extract_frames,
    list_photo_assets,
    list_video_assets,
)
from fetch.sampling import detect_scenes, plan_frames
from caption.base import REQUIRED_MODELS
from resources import MemoryGovernor

# ---------------------------------------------------------------------------
# Default / lazy helpers (not imported until needed, so tests avoid real deps)
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = os.environ.get(
    "FAMILYVAULT_DB",
    os.path.expanduser("~/.familyvault/index/familyvault.db"),
)

_DEFAULT_STAGING_DIR = os.environ.get(
    "FAMILYVAULT_STAGING",
    os.path.expanduser("~/.familyvault/staging"),
)

_DEFAULT_CHUNK_SIZE = 50

# Per-phase memory need (GB) used by the governor to decide when to free RAM.
PHOTO_NEED_GB = float(os.environ.get("PHOTO_NEED_GB", "9"))
VIDEO_NEED_GB = float(os.environ.get("VIDEO_NEED_GB", "12"))


# Canonical key-file path provisioned by setup/immich/scripts/provision-api-key.sh
# (also used by setup/story-engine). The CLI reads the key from here when the
# IMMICH_API_KEY env var is not set, so no manual `export` is required.
DEFAULT_API_KEY_FILE = "/Volumes/HomeRAID/immich/api-key.txt"


def _resolve_api_key(*, env=None) -> str:
    """Resolve the Immich API key: IMMICH_API_KEY env wins, else the key file.

    The key file path comes from IMMICH_API_KEY_FILE (default
    DEFAULT_API_KEY_FILE). Returns "" if neither is available.
    """
    env = os.environ if env is None else env
    key = env.get("IMMICH_API_KEY", "")
    if key:
        return key
    key_file = env.get("IMMICH_API_KEY_FILE", DEFAULT_API_KEY_FILE)
    try:
        return Path(key_file).read_text().strip()
    except OSError:
        return ""


def _lazy_session():
    """Build a real requests.Session with the x-api-key header."""
    import requests

    api_key = _resolve_api_key()
    session = requests.Session()
    if api_key:
        session.headers["x-api-key"] = api_key
    return session


def _lazy_captioner():
    """Build the default photo captioner (real Ollama)."""
    from caption.photo_ollama import PhotoOllamaCaptioner

    return PhotoOllamaCaptioner()


def _lazy_video_captioner():
    """Build the default video captioner (real MLX-VLM)."""
    from caption.video_mlx import VideoMLXCaptioner

    return VideoMLXCaptioner()


def _lazy_embed_fn():
    """Return the default embed callable."""
    from caption.embed import embed

    return embed


def _lazy_embed_query_fn():
    """Return the default embed_query callable."""
    from caption.embed import embed_query

    return embed_query


# ---------------------------------------------------------------------------
# Reconciliation helpers
# ---------------------------------------------------------------------------


def _reconcile(conn, fields: dict, stored: dict, schema_ver: int) -> None:
    """Upsert a stub 'pending' row if the asset is new or outdated.

    Leaves 'done' rows with an unchanged source_hash and current schema_ver
    untouched so their captions are not clobbered.

    Args:
        conn:       Open SQLite connection.
        fields:     Output of asset_filter_fields() for this Immich asset.
        stored:     Dict from index_state() for this asset_id, or None.
        schema_ver: Current schema version.
    """
    if stored is None:
        # New asset — insert a pending stub with the filter fields
        stub = dict(fields)
        stub.update(
            status="pending",
            schema_ver=schema_ver,
            caption=None,
            ocr_text=None,
            caption_embedding=None,
            caption_model=None,
            embed_model=None,
            indexed_at=None,
            error=None,
        )
        upsert_asset(conn, stub)
        return

    hash_changed = stored["source_hash"] != fields.get("source_hash")
    schema_outdated = (stored["schema_ver"] or 0) < schema_ver

    if hash_changed or schema_outdated:
        # Re-index: reset to pending, update cached fields + source_hash
        stub = dict(fields)
        stub.update(
            status="pending",
            schema_ver=schema_ver,
            caption=None,
            ocr_text=None,
            caption_embedding=None,
            caption_model=None,
            embed_model=None,
            indexed_at=None,
            error=None,
        )
        upsert_asset(conn, stub)
        return

    # stored status='done', hash unchanged, schema current → leave it alone
    # (also handles no_preview / error — they remain as-is for this pass)


# ---------------------------------------------------------------------------
# run_photos
# ---------------------------------------------------------------------------


def run_photos(
    conn,
    *,
    session=None,
    captioner=None,
    embed_fn=None,
    staging_dir,
    schema_ver: int = CURRENT_SCHEMA_VER,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    backup_dir=None,
    limit: Optional[int] = None,
    governor=None,
    memory_policy: str = "auto",
    need_gb: Optional[float] = None,
    clean_staging: bool = False,
) -> dict:
    """Index all Immich photo assets using injected dependencies.

    Steps:
      1. List Immich assets via session.
      2. Reconcile each asset against the index (change-detection).
      3. Build todo list via plan(); apply limit.
      4. Process assets in chunks (bounds staging dir usage).
         Per-asset: download preview → caption → embed → upsert done.
         On any error: set_status(error); continue (per-asset isolation).
         After each chunk: delete staged preview files.
      5. Optional backup.
      6. Return counts().

    Args:
        conn:         Open SQLite connection.
        session:      Requests-like session (injected or built lazily).
        captioner:    Object with .caption(paths, *, is_video) -> CaptionResult.
        embed_fn:     Callable text -> bytes (caption embedding).
        staging_dir:  Directory for temporary preview files.
        schema_ver:   Current schema version (default CURRENT_SCHEMA_VER).
        chunk_size:   Number of assets to process before cleaning staging.
        backup_dir:   If set, copy the DB here after processing.
        limit:        Max number of assets to process (None = all pending).

    Returns:
        dict from counts(conn): {pending, done, no_preview, error}.
    """
    # Resolve lazy defaults only if not injected
    if session is None:
        session = _lazy_session()
    if captioner is None:
        captioner = _lazy_captioner()
    if embed_fn is None:
        embed_fn = _lazy_embed_fn()

    staging_dir = Path(staging_dir)
    if clean_staging and staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: List Immich assets
    raw_assets = list_photo_assets(session)

    # Step 2: Reconcile each asset against the index
    current_state = index_state(conn)
    for raw_asset in raw_assets:
        fields = asset_filter_fields(raw_asset)
        asset_id = fields["asset_id"]
        stored = current_state.get(asset_id)
        _reconcile(conn, fields, stored, schema_ver)

    # Step 3: Get todo list, apply limit
    todo = plan(conn, type="IMAGE", schema_ver=schema_ver)
    if limit is not None:
        todo = todo[:limit]

    # Step 4: Process in chunks. Each chunk runs in two phases so the memory
    # governor can free RAM (incl. stopping Immich) for captioning WITHOUT
    # breaking the fetch phase, which needs Immich:
    #   pass 1: fetch previews (Immich up) → pass 2: govern → caption → restore.
    for chunk_start in range(0, max(len(todo), 1), chunk_size):
        chunk = todo[chunk_start : chunk_start + chunk_size]
        chunk_staged: list[Path] = []
        ready: list[tuple] = []  # (asset_id, preview_path) that fetched OK

        # --- pass 1: fetch (Immich required) ---
        for item in chunk:
            asset_id = item["asset_id"]
            dest_path = staging_dir / f"{asset_id}.jpg"
            try:
                prev = download_preview(session, asset_id, dest_path)
                if prev is None:
                    set_status(conn, asset_id, Status.NO_PREVIEW)
                    continue
                chunk_staged.append(Path(prev))
                ready.append((asset_id, prev))
            except Exception as exc:  # per-asset isolation
                set_status(conn, asset_id, Status.ERROR, error=str(exc))

        # --- govern the caption phase (Immich no longer needed) ---
        state = None
        if governor is not None:
            state = governor.free_for_phase(
                REQUIRED_MODELS["photo"],
                policy=memory_policy,
                need_gb=need_gb if need_gb is not None else PHOTO_NEED_GB,
            )
        try:
            # --- pass 2: caption + embed + write (no Immich) ---
            for asset_id, prev in ready:
                try:
                    cr = captioner.caption([prev], is_video=False)
                    emb = embed_fn(cr.caption)
                    row_raw = conn.execute(
                        "SELECT * FROM assets WHERE asset_id=?", (asset_id,)
                    ).fetchone()
                    row = dict(row_raw) if row_raw else {"asset_id": asset_id}
                    row.update(
                        caption=cr.caption,
                        ocr_text=cr.ocr_text,
                        caption_embedding=emb,
                        caption_model=cr.model,
                        embed_model="bge-m3",
                        schema_ver=schema_ver,
                        status="done",
                        error=None,
                        indexed_at=datetime.now(timezone.utc).isoformat(),
                    )
                    upsert_asset(conn, row)
                except Exception as exc:  # per-asset isolation: never abort batch
                    set_status(conn, asset_id, Status.ERROR, error=str(exc))
        finally:
            if governor is not None and state is not None:
                governor.restore(state)

        # After each chunk: delete staged preview files
        for staged_file in chunk_staged:
            try:
                staged_file.unlink(missing_ok=True)
            except OSError:
                pass

    # Step 5: Backup
    if backup_dir is not None:
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup(conn, str(backup_dir))

    # Step 6: Return counts
    return counts(conn)


# ---------------------------------------------------------------------------
# run_videos
# ---------------------------------------------------------------------------


def run_videos(
    conn,
    *,
    session=None,
    captioner=None,
    embed_fn=None,
    staging_dir,
    schema_ver: int = CURRENT_SCHEMA_VER,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    backup_dir=None,
    limit: Optional[int] = None,
    detect_scenes_fn=None,
    extract_frames_fn=None,
    runner=None,
    governor=None,
    memory_policy: str = "auto",
    need_gb: Optional[float] = None,
    clean_staging: bool = False,
) -> dict:
    """Index Immich VIDEO assets: sample frames → caption (video-level + segments)
    → embed → write asset row + video_segments.

    Same incremental/chunked/error-isolated shape as run_photos. External seams
    (session, captioner, embed_fn, scene detection, frame extraction) are injected
    so the pipeline is testable without ffmpeg/scenedetect/MLX.
    """
    if session is None:
        session = _lazy_session()
    if captioner is None:
        captioner = _lazy_video_captioner()
    if embed_fn is None:
        embed_fn = _lazy_embed_fn()
    if detect_scenes_fn is None:
        detect_scenes_fn = detect_scenes
    if extract_frames_fn is None:
        extract_frames_fn = extract_frames

    staging_dir = Path(staging_dir)
    if clean_staging and staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Discover + reconcile (change detection) — same as photos.
    current_state = index_state(conn)
    for raw_asset in list_video_assets(session):
        fields = asset_filter_fields(raw_asset)
        _reconcile(conn, fields, current_state.get(fields["asset_id"]), schema_ver)

    todo = plan(conn, type="VIDEO", schema_ver=schema_ver)
    if limit is not None:
        todo = todo[:limit]

    # Two-phase chunks (same rationale as run_photos): download with Immich up,
    # then govern + caption (Immich not needed for ffmpeg/scenedetect/MLX).
    for chunk_start in range(0, max(len(todo), 1), chunk_size):
        chunk = todo[chunk_start : chunk_start + chunk_size]
        chunk_staged: list[Path] = []
        ready: list[tuple] = []  # (asset_id, vpath)

        # --- pass 1: download videos (Immich required) ---
        for item in chunk:
            asset_id = item["asset_id"]
            video_path = staging_dir / f"{asset_id}.mp4"
            try:
                vpath = download_video(session, asset_id, str(video_path))
                if vpath is None:
                    set_status(conn, asset_id, Status.NO_PREVIEW)
                    continue
                chunk_staged.append(Path(vpath))
                ready.append((asset_id, vpath))
            except Exception as exc:  # per-asset isolation
                set_status(conn, asset_id, Status.ERROR, error=str(exc))

        # --- govern the caption phase (Immich no longer needed) ---
        state = None
        if governor is not None:
            state = governor.free_for_phase(
                REQUIRED_MODELS["video"],
                policy=memory_policy,
                need_gb=need_gb if need_gb is not None else VIDEO_NEED_GB,
            )
        try:
            # --- pass 2: sample → extract → caption → embed → write ---
            for asset_id, vpath in ready:
                frames_dir = staging_dir / asset_id
                try:
                    row_raw = conn.execute(
                        "SELECT * FROM assets WHERE asset_id=?", (asset_id,)
                    ).fetchone()
                    fields = dict(row_raw) if row_raw else {"asset_id": asset_id}

                    scenes = detect_scenes_fn(vpath)
                    duration = fields.get("duration") or (scenes[-1][1] if scenes else 10.0)
                    splan = plan_frames(scenes, duration)

                    frames_dir.mkdir(parents=True, exist_ok=True)
                    chunk_staged.append(frames_dir)
                    # Clamp seek times just inside the clip: ffmpeg cannot seek to
                    # exactly the duration (no frame there) and writes nothing.
                    end_cap = max(0.0, duration - 0.1)
                    seek_times = sorted({min(t, end_cap) for t in splan.caption_frames})
                    extra = {"runner": runner} if runner is not None else {}
                    raw_frames = extract_frames_fn(
                        vpath, seek_times, str(frames_dir), **extra
                    )
                    # Keep only frames ffmpeg actually wrote; the captioner derives
                    # each frame's timestamp from its filename, so they stay aligned.
                    frames = [p for p in raw_frames if os.path.exists(p)]
                    if not frames:
                        raise RuntimeError("no frames could be extracted from the video")

                    cr = captioner.caption(frames, is_video=True)
                    emb = embed_fn(cr.caption)

                    row = dict(fields)
                    row.update(
                        caption=cr.caption,
                        ocr_text=cr.ocr_text,
                        caption_embedding=emb,
                        caption_model=cr.model,
                        embed_model="bge-m3",
                        schema_ver=schema_ver,
                        status="done",
                        error=None,
                        indexed_at=datetime.now(timezone.utc).isoformat(),
                    )
                    upsert_asset(conn, row)
                    upsert_segments(conn, asset_id, cr.segments or [])
                except Exception as exc:  # per-asset isolation: never abort the batch
                    set_status(conn, asset_id, Status.ERROR, error=str(exc))
        finally:
            if governor is not None and state is not None:
                governor.restore(state)

        for staged in chunk_staged:
            try:
                if staged.is_dir():
                    shutil.rmtree(staged, ignore_errors=True)
                else:
                    staged.unlink(missing_ok=True)
            except OSError:
                pass

    if backup_dir is not None:
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup(conn, str(backup_dir))

    return counts(conn)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def status(conn) -> dict:
    """Print and return index counts (pending/done/no_preview/error).

    Returns:
        dict from counts(conn).
    """
    c = counts(conn)
    total = sum(c.values())
    print(f"Index status  (total: {total})")
    print(f"  pending:    {c['pending']}")
    print(f"  done:       {c['done']}")
    print(f"  no_preview: {c['no_preview']}")
    print(f"  error:      {c['error']}")
    return c


# ---------------------------------------------------------------------------
# search_index
# ---------------------------------------------------------------------------


def search_index(
    conn,
    query: str,
    *,
    embed_query_fn=None,
    k: int = 5,
) -> list[dict]:
    """Hybrid search (FTS + vector) against the index.

    Embeds *query* (any language supported by bge-m3) then calls db.search().
    Prints results to stdout and returns them.

    Args:
        conn:           Open SQLite connection.
        query:          Search query string (any language).
        embed_query_fn: Callable text -> bytes (injected or lazy default).
        k:              Max results to return.

    Returns:
        List of hit dicts: {asset_id, score, snippet}.
    """
    if embed_query_fn is None:
        embed_query_fn = _lazy_embed_query_fn()

    query_vec = embed_query_fn(query)
    hits = search(conn, query_vec, query, k=k)

    if not hits:
        print(f"No results for: {query!r}")
    else:
        print(f"Search results for: {query!r}  ({len(hits)} hit(s))")
        for i, hit in enumerate(hits, 1):
            snippet = hit.get("snippet", "")[:120]
            print(f"  {i}. [{hit['score']:.3f}] {hit['asset_id']}  {snippet!r}")

    return hits


# ---------------------------------------------------------------------------
# main (argparse entrypoint)
# ---------------------------------------------------------------------------


def main(argv=None) -> None:
    """Argparse entrypoint.  Subcommands: run, status, search.

    Exit codes:
      0  — success / results found
      2  — nothing-to-do (nothing pending, no search matches)
      3  — precondition error
    """
    parser = argparse.ArgumentParser(
        prog="fv-index",
        description="FamilyVault understanding-layer indexer CLI",
    )
    parser.add_argument(
        "--db",
        default=_DEFAULT_DB_PATH,
        help="Path to the SQLite index DB (default: %(default)s)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    run_p = sub.add_parser("run", help="Run the indexer for a given asset type.")
    run_p.add_argument(
        "--type",
        dest="asset_type",
        choices=["photo", "video"],
        required=True,
        help="Asset type to index.",
    )
    run_p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N assets (default: all pending).",
    )
    run_p.add_argument(
        "--backup-dir",
        default=None,
        help="Copy DB to this directory after run.",
    )
    run_p.add_argument(
        "--staging-dir",
        default=_DEFAULT_STAGING_DIR,
        help="Directory for temporary preview files (default: %(default)s).",
    )
    run_p.add_argument(
        "--chunk-size",
        type=int,
        default=_DEFAULT_CHUNK_SIZE,
        help="Assets per chunk (bounds staging usage; default: %(default)s).",
    )
    run_p.add_argument(
        "--memory",
        dest="memory_policy",
        choices=["auto", "force", "never"],
        default="auto",
        help="Memory governor policy: auto frees RAM only when low (default); "
        "force always offloads Immich/OrbStack; never touches neither and stops "
        "with a clear message if RAM is insufficient.",
    )
    run_p.add_argument(
        "--clean-staging",
        action="store_true",
        help="Wipe the staging dir before starting.",
    )

    # --- status ---
    sub.add_parser("status", help="Print index counts.")

    # --- search ---
    search_p = sub.add_parser("search", help="Search the index.")
    search_p.add_argument("query", help="Search query (any language).")
    search_p.add_argument(
        "-k",
        type=int,
        default=5,
        help="Max results to return (default: %(default)s).",
    )

    args = parser.parse_args(argv)

    # Open DB
    db_path = args.db
    try:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        conn = open_db(db_path)
    except Exception as exc:
        print(f"ERROR: cannot open DB at {db_path!r}: {exc}", file=sys.stderr)
        sys.exit(3)

    try:
        if args.command == "run":
            run_fn = run_photos if args.asset_type == "photo" else run_videos
            result = run_fn(
                conn,
                staging_dir=args.staging_dir,
                schema_ver=CURRENT_SCHEMA_VER,
                chunk_size=args.chunk_size,
                backup_dir=args.backup_dir,
                limit=args.limit,
                governor=MemoryGovernor(),
                memory_policy=args.memory_policy,
                clean_staging=args.clean_staging,
            )
            print(
                f"Run complete — done={result['done']} "
                f"pending={result['pending']} "
                f"no_preview={result['no_preview']} "
                f"error={result['error']}"
            )
            if result["pending"] > 0 and result["done"] == 0:
                sys.exit(2)
            sys.exit(0)

        elif args.command == "status":
            c = status(conn)
            if sum(c.values()) == 0:
                sys.exit(2)
            sys.exit(0)

        elif args.command == "search":
            hits = search_index(conn, args.query, k=args.k)
            sys.exit(0 if hits else 2)

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(3)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
