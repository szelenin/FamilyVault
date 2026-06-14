# Contract — Captioner interface & key module APIs

Internal contracts that keep the model backends swappable and unit-testable (mock the model, not SQLite).

## Captioner (`caption/base.py`)

```python
# CaptionResult: structured extraction output
CaptionResult = {
    "caption": str,            # English (canonical) description; required, non-empty on success
    "ocr_text": str,           # deduped on-screen text; "" if none
    "segments": list | None,   # video only: [{"t_start": float, "t_end": float,
                               #               "caption": str, "ocr_text": str}]; None for photos
    "model": str,              # provenance, e.g. "qwen3-vl:8b" | "mlx:Qwen3-VL-8B-4bit"
}

# Captioner protocol (both backends implement it)
def caption(paths: list[str], *, is_video: bool, ocr_frames: list[str] | None = None) -> CaptionResult: ...
```

- `photo_ollama.caption([preview_jpg], is_video=False)` → single-image call (Ollama `qwen3-vl:8b`).
- `video_mlx.caption(frame_paths, is_video=True, ocr_frames=[…])` → multi-frame MLX-VLM call; map-reduce when frames exceed budget; populates `segments`.
- Errors raise a typed exception the CLI maps to `status=error` (never crashes the batch).

## Per-phase model requirements (`caption/base.py`)

```python
REQUIRED_MODELS = {
    "photo": {"ollama": ["qwen3-vl:8b", "bge-m3"], "mlx": []},
    "video": {"ollama": ["bge-m3"], "mlx": ["mlx-community/Qwen3-VL-8B-Instruct-4bit"]},
}
```
The governor loads only the current phase's set and unloads the rest.

## Embedder (`caption/embed.py`)

```python
def embed(text: str) -> bytes: ...      # multilingual vector (bge-m3) serialized to BLOB
def embed_query(text: str) -> bytes: ... # same model; used by `search`
```

## Index API (`index/db.py`) — the only module that touches SQLite

```python
open_db(path) -> Connection           # creates/migrates schema, enables WAL
plan(conn, *, type, schema_ver) -> list[AssetRef]   # assets needing work (incremental)
upsert_asset(conn, row) -> None       # write/replace one asset entry (atomic per asset)
upsert_segments(conn, asset_id, segments) -> None
set_status(conn, asset_id, status, *, error=None) -> None
search(conn, query_vec, query_text, *, k) -> list[Hit]   # hybrid FTS ∪ vector (smoke-level)
counts(conn) -> dict                  # {pending, done, no_preview, error} for `status`
backup(conn, dest_dir) -> path        # copy DB file to RAID
```

## Memory governor (`resources.py`)

```python
free_for_phase(required_models, *, policy) -> StoppedState   # measure → escalate as needed
restore(stopped_state) -> None                               # restart exactly what was stopped
```
- `policy` ∈ {auto, force, never}. Escalation: unload non-required Ollama models → stop Immich containers → stop OrbStack VM. All external commands are injected/mockable for unit tests.
