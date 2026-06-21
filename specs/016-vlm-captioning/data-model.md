# Phase 1 Data Model — IMP-018 VLM Captioning & Extraction

One SQLite database (native SSD, WAL). Tables below; full DDL is in the technical design. All entries are keyed to the **Immich asset ID** (the join key to Immich and to future signals — IMP-019/020).

## Entity: Asset index entry (`assets`)

One row per Immich asset.

| Field | Type | Notes / Validation |
|---|---|---|
| `asset_id` | TEXT PK | Immich asset UUID |
| `type` | TEXT | `IMAGE` \| `VIDEO` (required) |
| `status` | TEXT | `pending` \| `done` \| `no_preview` \| `error` (required; see state machine) |
| `caption` | TEXT | VLM description, **English (canonical)**; NULL until done |
| `ocr_text` | TEXT | extracted on-screen text, deduped; may be empty |
| `caption_embedding` | BLOB | semantic vector of the caption (multilingual model); NULL until done |
| `taken_at` | TEXT | cached from Immich (ISO) — for downstream ranking |
| `lat`, `lon` | REAL | cached from Immich |
| `city`, `country` | TEXT | cached from Immich |
| `person_ids` | TEXT | JSON array of Immich person IDs (cached; identity stays Immich's) |
| `is_favorite` | INTEGER | cached from Immich (0/1) |
| `duration` | REAL | video length (s); NULL for photos |
| `caption_model` | TEXT | provenance, e.g. `qwen3-vl:8b` \| `mlx:Qwen3-VL-8B-4bit` |
| `embed_model` | TEXT | e.g. `bge-m3` |
| `schema_ver` | INTEGER | extraction schema version (required); bump → forces re-caption |
| `source_hash` | TEXT | Immich checksum/`updatedAt` → change detection |
| `error` | TEXT | last error message (when `status=error`) |
| `indexed_at` | TEXT | ISO timestamp of last successful processing |

**Validation rules**
- `type` ∈ {IMAGE, VIDEO}; `status` ∈ enum.
- `status=done` ⇒ `caption` non-NULL and `caption_embedding` non-NULL.
- `status=no_preview` ⇒ `caption` NULL, `error` NULL (distinct from error).
- `status=error` ⇒ `error` non-NULL.
- `duration` NULL for `type=IMAGE`.

## Entity: Video segment (`video_segments`)

Zero+ rows per VIDEO asset (none for photos). Enables moment-level retrieval.

| Field | Type | Notes |
|---|---|---|
| `asset_id` | TEXT FK → assets(asset_id) ON DELETE CASCADE | |
| `t_start` | REAL | seconds into clip |
| `t_end` | REAL | seconds into clip; `t_end ≥ t_start` |
| `caption` | TEXT | per-segment description |
| `ocr_text` | TEXT | per-segment on-screen text |
| `embedding` | BLOB | per-segment vector (optional) |
| PK | (`asset_id`, `t_start`) | |

## Entity: Full-text index (`assets_fts`)

FTS5 virtual table over `caption` + `ocr_text` (contentless, `content='assets'`), kept in sync via triggers. Powers lexical/exact search (names, on-screen text).

## Entity: Run record (`runs`)

One row per batch run — observability + remediation report source.

| Field | Type | Notes |
|---|---|---|
| `run_id` | INTEGER PK | |
| `started_at`, `finished_at` | TEXT | ISO |
| `counts_json` | TEXT | `{done, no_preview, error, skipped}` |

## State machine (`assets.status`)

```
            (planned/new asset)
                  │
                  ▼
              ┌────────┐   fetch: no usable preview      ┌────────────┐
              │pending │ ───────────────────────────────▶│ no_preview │
              └────────┘                                  └────────────┘
                  │  caption+embed ok        ▲ remediated + re-run │
                  ▼                          └─────────────────────┘
              ┌────────┐
              │  done  │
              └────────┘
                  ▲  caption/model error
                  │ (recorded, retryable)
              ┌────────┐
              │ error  │──── retry ──▶ pending
              └────────┘
```

- **Re-index triggers** (back to processing): `source_hash` changed, or `schema_ver < current`, or explicit `retry`.
- **Idempotent**: `done` with unchanged `source_hash` and current `schema_ver` is skipped.

## Relationships

- `assets` 1—N `video_segments` (videos only).
- `assets` 1—1 `assets_fts` (by rowid).
- `assets.asset_id` is the external join key to Immich (person IDs, GPS, CLIP) and to future IMP-019 (audio) / IMP-020 (fusion) tables.

## Derived/regenerable

The entire DB is derived from the Immich library and the models; it can be rebuilt by re-running. A post-run file copy to the RAID is the backup.
