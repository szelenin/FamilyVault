# Contract — `index_cli.py` (operator + AI interface)

The understanding-layer indexer is operated via CLI (AI-invocable per Constitution III). All commands read config from `config.sh`/env. Exit codes: `0` success, `2` nothing-to-do/empty, `3` precondition/error.

## `doctor [--type photo|video|all]`

Preflight environment check (presence-on-disk, scoped to `--type`). Auto-runs at the start of `run`.

- **Checks** (per type): Ollama up + required models present (`/api/tags`); for video: `mlx_vlm` importable + MLX model cached, `ffmpeg`, `scenedetect`; both: Immich reachable + API key, `python3.13`, SQLite path writable + WAL, free SSD ≥ staging budget.
- **Output**: per-check `OK`/`FAIL`; each FAIL includes the exact remediation command.
- **Exit**: `0` all pass; `3` any fail (names missing component + fix). MUST complete in ~seconds (before heavy work).

## `run [--type photo|video|all] [--memory auto|force|never] [--staging-budget 10G] [--limit N] [--reindex-schema] [--clean-staging]`

Incremental, resumable, chunked batch.

- **Selects** assets where `status=pending` OR `source_hash` changed OR `schema_ver<current` (or all matching `--reindex-schema`), scoped to `--type`, capped by `--limit`.
- **Per chunk** (≤ staging budget): fetch → govern memory → caption+embed → write rows → clean staging.
- **`--memory`**: `auto` (default; governor frees RAM only when low), `force` (always offload Immich/OrbStack), `never` (never touch Immich; fail clearly if RAM insufficient).
- **Resilience**: per-asset failure recorded (`status=error`), batch continues. Crash-safe (SQLite ledger). Backs up DB → RAID at end.
- **Output**: progress per chunk; final counts `{done, no_preview, error, skipped}`.
- **Exit**: `0` completed (even with some per-asset errors recorded); `3` precondition failure (doctor failed, Immich unreachable, etc.).

## `status`

Print index counts by status (`pending/done/no_preview/error`) and per-type totals. Exit `0`.

## `report`

Missing-preview remediation: list `no_preview` asset IDs + the exact Immich thumbnail-regeneration call (`POST /api/jobs`) + steps. Exit `0` (or `2` if none).

## `retry [--status no_preview|error]`

Re-queue the given status back to processing (set to `pending`) so the next `run` re-attempts. Exit `0`.

## `search "<query>"`

Smoke-level index check (build verification, not the tuned ranker — see spec SC-002/003). Embeds the query with the multilingual embedder, runs basic hybrid retrieval (FTS5 ∪ vector), prints top matches (asset_id, type, snippet, score). Supports non-English queries. Exit `0` (or `2` if no matches).
