# IMP-018 — VLM Captioning & Extraction — Technical Design

**Date:** 2026-06-13
**Status:** Design (approved in brainstorming; input for `/speckit`)
**PRD item:** IMP-018 (`docs/PRD.md`) — requirements R097–R101
**Informed by:** `docs/model-spec-intelligent-search.md`
**Target hardware:** Apple M4 Mac Mini, 24 GB RAM. Native SSD: ~124 GB free. RAID `/Volumes/HomeRAID`: ~1.6 TB free.

---

## Goal

Build the **understanding-layer index**: for every Immich asset, generate a rich VLM **caption** (what is happening), extract on-screen **text (OCR)**, and a **semantic embedding**, and store them in a local **SQLite index** keyed to the Immich asset ID. This index is the substrate that makes downstream search "intelligent" (semantic + lexical), and is consumed by IMP-020 (fusion ranking) and IMP-019 (audio).

**Identity stays with Immich.** The VLM describes "a boy"; Immich knows it's your son. Never re-identify people with the VLM — resolve "who" via Immich person IDs.

## Scope

- **In scope:** photo captioning + OCR (R097/R099), video keyframe sampling + captioning + OCR (R098), the SQLite index, **caption embeddings** (so the index supports semantic search), incremental/idempotent batch execution (R100), feeding search/timeline (R101), **environment setup + scoped preflight (`setup.sh`/`doctor`)**, and **automatic memory governance** (load only the phase's models; offload Immich/OrbStack only when measured RAM is low). Full IMP-018, built **photos-first** as a baseline, then video.
- **Out of scope (later items):** fusion ranking + multilingual-CLIP swap → **IMP-020**; audio (Whisper/CLAP) → **IMP-019**; quality signals (blur/exposure/aesthetic/expression) → **IMP-021/022**. The timeline-caption replacement (R101) is wired here but the consuming UI is elsewhere.

---

## Key Decisions (with rationale)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Full IMP-018 (photos + video), phased photos-first** | The index/VLM/OCR/embedding spine is the reusable hard part; prove it on the cheap photo path before adding video complexity. |
| D2 | **SQLite + FTS5 + vectors**, one file | An index needs fast query + full-text; one file to back up; joins cleanly to other signals by asset ID. |
| D3 | **DB on native SSD** (WAL mode), backed up to RAID after each run | Frequent reads/writes + reliable SQLite locking want fast local APFS; the index is derived/regenerable, but re-captioning is expensive, so cheap file backup to RAID. |
| D4 | **Hybrid index: lexical (FTS5) + semantic (embeddings)** + cached Immich filter fields | "Intelligent" search = semantic, not keyword. FTS5 for exact text (OCR/names); vectors for concepts; cached fields make query-time fusion fast without per-candidate Immich calls. |
| D5 | **Photos → Ollama `qwen3-vl:8b`** | Single-image captioning; reuses the existing Ollama runtime. |
| D6 | **Video → MLX-VLM** (native video) | Ollama has **no native video** and an uncertain multi-image limit; MLX-VLM on Apple Silicon ingests video natively and preserves Qwen dynamic-fps + time-aligned timestamps. |
| D7 | **Multilingual embedder `bge-m3` via Ollama** | EN/RU/UK queries must match English VLM captions cross-lingually. |
| D8 | **Manual incremental CLI batch**, resumable; cron later | Fits the offload model; safe to re-run; no full re-index per run. SQLite is the progress ledger. |
| D9 | **Immich "preview" images** (~1440–2048px) | One JPEG/asset (no HEIC convert), enough detail for most OCR; originals only as a later fallback for tiny text. |
| D10 | **Chunked fetch→caption→cleanup**, staging budget **10 GB**; offload driven by an **automatic memory governor** (not a manual flag) | Bounds staging disk to a chunk; decoupling fetch from caption lets us free RAM; governor offloads only when measured RAM is low. |
| D11 | **Hybrid video frame sampling** (scene-detect + first/mid/last + min3/max~16–24, fallback uniform 1 fps) + **two-tier OCR** (extra high-res frames) | Consensus from research: fewer-richer frames beat many-cheap; hybrid covers single-shot home clips and multi-cut trips. |
| D12 | **Aggregation: single multi-frame call**, map-reduce fallback for long clips | Best temporal reasoning in one call for the common (short) case; map-reduce only when frames exceed budget (what production systems do). |
| D13 | **`setup.sh` + scoped `doctor` preflight** — no assumed environment | A run must not start half-installed; `doctor` checks presence-on-disk scoped to `--type` and fails fast with the exact fix. |
| D14 | **Load only the phase's models; start unloaded** | "Installed" ≠ "loaded." Per-phase `REQUIRED_MODELS`; governor unloads the rest first → minimal resident RAM; partial runs don't need the other path's model. |

---

## Architecture

```
                         ┌─────────────────────────────────────────────┐
                         │              index_cli.py (batch)            │
                         │   plan → fetch → [offload] → caption → write │
                         └───────────────┬─────────────────────────────┘
              ┌─────────────────┬────────┼───────────────┬─────────────────┐
              ▼                 ▼         ▼               ▼                 ▼
        fetch/immich.py   fetch/sampling  resources.py   caption/*       index/db.py
        (Immich API,      (scene-detect   (stop/start    photo_ollama →  (SQLite: assets,
         preview dl,       hybrid +        Immich +       Ollama          video_segments,
         ffmpeg frames)    ffmpeg)         OrbStack)      qwen3-vl:8b     FTS5, vectors)
              │                                           video_mlx →
              ▼                                           MLX-VLM
        Immich REST API                                   + bge-m3 embed (Ollama)
        (preview, assets,                                       │
         person IDs, GPS)                                       ▼
                                                          SQLite index (native SSD, WAL)
                                                                │ backup
                                                                ▼
                                                          /Volumes/HomeRAID (DB copy)
```

**Module responsibilities (each independently testable):**

```
setup/understanding/
├── README.md
├── setup.sh                  # install/pull everything (models, deps); idempotent
├── config.sh                 # INDEX_DB (native), INDEX_BACKUP_DIR (RAID), IMMICH_*,
│                             # model names, STAGING_DIR, STAGING_BUDGET=10G, chunk/frame caps,
│                             # MEMORY_POLICY=auto, mem thresholds/margins
├── preflight.py              # `doctor` — verify env is ready (presence-on-disk), scoped to --type
├── index/
│   ├── db.py                 # SQLite schema + FTS5 + vectors; open/migrate; upsert/query; backup
│   └── status.py             # status enum: pending | done | no_preview | error
├── fetch/
│   ├── immich.py             # list assets, download preview, extract video frames (ffmpeg)
│   └── sampling.py           # hybrid frame sampling (scene-detect + first/mid/last + caps)
├── caption/
│   ├── base.py               # CaptionResult + captioner interface; per-phase REQUIRED_MODELS
│   ├── photo_ollama.py       # photo caption+OCR via Ollama qwen3-vl:8b
│   ├── video_mlx.py          # video caption+OCR via MLX-VLM
│   └── embed.py              # caption/query embedding via Ollama bge-m3
├── resources.py              # memory governor: measure RAM; unload models / stop Immich / stop OrbStack
├── index_cli.py              # batch entrypoint (doctor/run/status/report/retry/search)
└── tests/
```

**Installed vs loaded.** Models are *installed on disk* once (via `setup.sh`); they are *loaded into RAM* lazily, only when a phase needs them, and only one path's models are resident at a time (see Environment & Memory below).

- **`index/db.py`** is the *only* thing that touches SQLite. **`fetch/`** is the *only* thing that touches Immich/FFmpeg. **`caption/`** is the *only* thing that touches the models. This keeps each unit swappable and mockable.

---

## Environment & Setup

The pipeline does **not** assume things are installed. Two pieces guarantee a ready environment.

**`setup.sh`** (idempotent) installs/pulls everything and documents gotchas:
- `ollama pull qwen3-vl:8b`, `ollama pull bge-m3`
- `pip install mlx-vlm scenedetect` (under `python3.13`); cache the MLX model; `brew install ffmpeg`
- references `setup/local-agent/SETUP-NOTES.md` for the known gotchas (use `python3.13`, not the broken default `python3`; the Ollama formula + cask `llama-server` runner fix)

**`doctor` (preflight, run before every `run`) — fails fast with the exact fix command.** Checks **presence on disk** (not loaded into RAM) and is **scoped to `--type`** so a partial run doesn't require the other path:

| Run | Required (checked) | Skipped |
|---|---|---|
| `--type photo` | Ollama up + `qwen3-vl:8b` + `bge-m3` present (`/api/tags`); ffmpeg n/a | MLX |
| `--type video` | `mlx_vlm` importable + MLX model cached; `ffmpeg` + `scenedetect`; Ollama `bge-m3` present | Ollama `qwen3-vl:8b` |
| both | Immich reachable + API key; `python3.13`; SQLite path writable + WAL; free SSD ≥ staging budget | — |

`bge-m3` (the embedder) is required by **both** types — captions for photos and videos are both embedded.

**Disk for models:** `qwen3-vl:8b` (~6 GB, Ollama) + MLX model (~5–6 GB, HF cache) ≈ ~12 GB added, alongside existing `qwen3:14b` (9 GB). Comfortable on 124 GB free.

---

## Data Flow, Memory Governor & Model Lifecycle

Process in **chunks** so staging disk is bounded by chunk size, not library size. A **memory governor** decides automatically whether to free RAM — the user does not babysit a flag.

```
doctor:          verify env (scoped to --type) — fail fast if anything missing
plan (Phase 0):  read SQLite → assets needing work
                 (status=pending OR source_hash changed OR schema_ver<current)

repeat until done, filling up to STAGING_BUDGET (10 GB) per chunk:
   Phase 1  Fetch     [Immich UP]  preview JPEGs (photos) / sampled frames (video, ffmpeg)
                                   → STAGING_DIR on SSD.  Record no_preview / error per asset.
   Phase 2  Govern    measure free RAM vs this phase's need; free only as much as required
                      (escalation below). Ensure ONLY this phase's models are loaded.
   Phase 3  Caption                run captioners over STAGED LOCAL FILES (no Immich needed):
                                   photos → Ollama qwen3-vl:8b; video → MLX-VLM; embed (bge-m3).
                                   Write rows to SQLite incrementally (resumable).
   Phase 4  Cleanup                delete this chunk's staging files; restore whatever Govern stopped.

finally:  backup DB → RAID
```

**Memory governor (`resources.py`, automatic).** Before each caption phase it measures available RAM (`psutil`/`vm_stat`) and compares to the phase's estimated need + safety margin (photo: `qwen3-vl:8b` ~6 GB + `bge-m3` ~2 GB; video: MLX ~6 GB + ffmpeg). It frees **only as much as needed**, re-measuring after each step:

1. **Unload Ollama models not needed for this phase** (`/api/ps` → `ollama stop <model>`) — reclaims up to ~9–15 GB if the local-agent's `qwen3:14b` or the other VLM was resident. *(cheapest; usually enough on 24 GB)*
2. still short → **stop the Immich container stack** (`docker compose stop` under OrbStack)
3. still short → **stop the OrbStack VM** (`orb stop`) to reclaim its RAM

It **records exactly what it stopped** and restores those in Phase 4 (restart OrbStack → wait healthy → restart Immich). **`resources.py` is who stops OrbStack / frees memory — triggered automatically, not by the human.**

**Model lifecycle — load only what the phase needs.** `caption/base.py` declares a per-phase `REQUIRED_MODELS` set (photo = {qwen3-vl:8b, bge-m3}; video = {mlx-qwen3-vl, bge-m3}). The governor unloads any loaded model **not** in that set, then the needed model loads lazily on first request. Even `--type all` processes photos *then* video, so only one path's models are resident at a time.

**Policy override (default automatic):**
- `--memory auto` (default) — governor decides per measurement
- `--memory force` — always offload Immich/OrbStack (e.g. big overnight video batch)
- `--memory never` — never touch Immich; proceed if RAM allows, else fail with a clear message

**Decoupling fetch from caption** is what makes offload possible — by Phase 3 every image/frame is a local file, so Immich can be down.

**Staging:** budget 10 GB on the SSD (124 GB free). Per-chunk cleanup → steady-state ≈ one chunk. On failure, the current chunk's files are kept (resume without re-fetch); `--clean-staging` forces a wipe. Larger chunks = fewer Immich restarts but more staging disk.

---

## SQLite Index Schema (hybrid: lexical + semantic + fusion-ready)

```sql
-- One row per Immich asset
CREATE TABLE assets (
  asset_id          TEXT PRIMARY KEY,   -- Immich asset UUID (join key everywhere)
  type              TEXT NOT NULL,      -- IMAGE | VIDEO
  status            TEXT NOT NULL,      -- pending | done | no_preview | error
  caption           TEXT,               -- VLM description (photo: image; video: video-level)
  ocr_text          TEXT,               -- extracted on-screen text, deduped
  caption_embedding BLOB,               -- semantic vector of the caption (multilingual)
  -- cached Immich fields (refreshable) so query-time fusion needs no per-candidate Immich call
  taken_at          TEXT,
  lat               REAL, lon REAL, city TEXT, country TEXT,
  person_ids        TEXT,               -- JSON array of Immich person IDs
  is_favorite       INTEGER,
  duration          REAL,               -- video length (s); NULL for photos
  -- provenance / re-index control
  caption_model     TEXT,               -- qwen3-vl:8b | mlx:Qwen3-VL-8B-4bit
  embed_model       TEXT,               -- bge-m3
  schema_ver        INTEGER NOT NULL,   -- bump to force full re-caption on prompt/model upgrade
  source_hash       TEXT,               -- Immich checksum/updatedAt → detect changed assets
  error             TEXT,               -- last error message (status=error)
  indexed_at        TEXT
);

-- Per-video temporal detail ("find the exact moment"); video-level summary lives in assets.caption
CREATE TABLE video_segments (
  asset_id   TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
  t_start    REAL, t_end REAL,          -- seconds into the clip
  caption    TEXT,
  ocr_text   TEXT,
  embedding  BLOB,                       -- per-segment vector (optional, for moment retrieval)
  PRIMARY KEY (asset_id, t_start)
);

-- Lexical/exact search over caption + OCR (BM25); synced to `assets` via triggers
CREATE VIRTUAL TABLE assets_fts USING fts5(
  caption, ocr_text, content='assets', content_rowid='rowid'
);

-- Batch observability + remediation-report source
CREATE TABLE runs (
  run_id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT,
  counts_json TEXT                       -- {done, no_preview, error, skipped}
);
```

**Vector search:** for ~69K assets, brute-force cosine in Python (≈200 MB RAM, <100 ms) to start; swap to the `sqlite-vec` extension if it grows. **Hybrid retrieval** = FTS5 (lexical) ∪ vector (semantic), combined in IMP-020's ranker.

**Why this is "optimized for intelligent search":** (1) semantic vectors catch meaning beyond keywords; (2) FTS5 nails exact text (OCR, names); (3) cached Immich filter fields let fusion rank locally in one query; (4) `video_segments` enables moment-level retrieval. IMP-018 builds this substrate; IMP-020 ranks over it.

---

## Models — decision per case

| Case | Model | Runtime | Notes |
|---|---|---|---|
| Photo caption + OCR | **Qwen3-VL 8B (Instruct)** | **Ollama** (`qwen3-vl:8b`, ≥0.12.7) | single image → JSON {caption, ocr_text} |
| Video caption + OCR | **Qwen3-VL (mlx)** | **MLX-VLM** (`mlx-community/Qwen3-VL-8B-…-4bit`) | native video; sampled frames → {video caption, segments[], ocr} |
| Caption/query embedding | **bge-m3** (multilingual) | **Ollama** embeddings endpoint | cross-lingual EN/RU/UK |
| Faces / identity, CLIP concept | (Immich ML) | **Immich** | do NOT rebuild; join via person IDs |

Fallbacks (A/B, if a model quirk appears): Qwen2.5-VL 7B or InternVL3 8B for captioning.

---

## VLM Invocation & Extraction

**Shared captioner interface** (photo/video swappable, mockable in tests):
```python
# caption/base.py
# CaptionResult = {caption: str, ocr_text: str, segments: list|None, model: str}
# captioner.caption(paths, *, is_video: bool, ocr_frames: list|None=None) -> CaptionResult
```

**Photo path** (`photo_ollama.py`): preview JPEG → one Ollama call, structured prompt → JSON `{caption, ocr_text}`. Caption = activity/context/relationships, **no identity**. OCR deduped. Then `embed.py` → `caption_embedding`.

**Video path** (`video_mlx.py`):
1. `sampling.py`: PySceneDetect `ContentDetector` (→`AdaptiveDetector` for shaky home footage) → 1–2 frames/scene + guaranteed first/mid/last; **min 3 / max ~16–24**; fallback uniform ~1 fps if ≤1 scene.
2. Two-tier OCR: also extract 2–4 **higher-res** frames for text.
3. One MLX-VLM call over sampled frames → JSON `{caption (video-level), segments:[{t_start,t_end,caption,ocr_text}], ocr_text}`. Clips exceeding the frame budget → **map-reduce** (window→caption→merge).
4. Store `assets.caption` + `video_segments` rows; embed video-level + segment captions.

**Prompt:** structured, requests JSON; instructs the model to describe activity (not identity) and to transcribe + **de-duplicate** on-screen text.

---

## Execution, Incremental & Error Handling

**CLI (`index_cli.py`):**
- `doctor [--type photo|video|all]` — preflight env check (presence-on-disk, scoped); also auto-run at the start of `run`
- `run [--type photo|video|all] [--memory auto|force|never] [--staging-budget 10G] [--limit N] [--reindex-schema] [--clean-staging]`
- `status` — counts by status
- `report` — **missing-preview remediation**: asset IDs + the exact Immich thumbnail-regeneration `POST /api/jobs` call + instructions
- `retry [--status no_preview|error]`
- `search "query"` — quick index check

**Incremental (Phase 0):** process `status=pending` OR `source_hash` changed OR `schema_ver<current`. `done` skipped unless forced.

**Error handling:**
- **Per-asset try/except — a single failure never aborts the batch.** Record `status=error`+message, continue.
- **Missing preview** → `status=no_preview` (distinct from error). `report` lists them + the regeneration API call + steps; `--auto-regenerate` optionally triggers it and re-fetches. Re-run picks them up incrementally.
- VLM/MLX timeout/OOM → `status=error`, retryable.
- **DB backup → RAID** at end of each run.

---

## Implementation Phases

- **Phase A — Foundation + Photos (baseline):** `setup.sh` (photo set) + `preflight.py`/`doctor` (scoped); scaffolding, `config.sh`, `db.py` (schema + FTS5 + vector store + backup), `fetch/immich.py` (preview + missing-preview path), `caption/photo_ollama.py`, `caption/embed.py` (`bge-m3`), per-phase model lifecycle (unload non-needed Ollama models), `index_cli doctor/run/status/report`, incremental planning. **Deliverable: all photos captioned + OCR'd + embedded + searchable.** Proves the whole spine.
- **Phase B — Video:** extend `setup.sh`/`doctor` (MLX + ffmpeg + scenedetect); `fetch/sampling.py` (hybrid scene-detect + ffmpeg), `caption/video_mlx.py` (MLX-VLM), `video_segments`, two-tier OCR, multi-frame aggregation + map-reduce fallback.
- **Phase C — Automatic resource governance + ops:** `resources.py` memory governor (measure RAM → unload models → stop Immich → stop OrbStack, auto-restore), `--memory auto|force|never`, chunked staging, DB backup automation, `--auto-regenerate`.

---

## Testing

- **Unit (no network):** `db.py` (schema, upsert, FTS sync, vector store/search, status transitions, `source_hash` change detection); `sampling.py` (frame selection on synthetic scene lists); captioner interface against a **mock model**; **`resources.py` governor** — escalation decisions on *mocked* memory readings + `/api/ps` (unload → stop Immich → stop OrbStack) and restore of only-what-it-stopped (mocked subprocess); **`preflight.py` doctor** — pass/fail + exact-fix messages on a mocked env, scoped per `--type`.
- **Integration (opt-in):** live Immich preview fetch + missing-preview path; one live Ollama caption + `bge-m3` embed; real ffmpeg frame extraction on a short clip; MLX-VLM on one short clip.
- **E2E:** index a tiny fixture (few photos + 1 short video) → assert rows written, captions non-empty, FTS **and** vector search each return the expected asset.

---

## Risks & Notes

- **Ollama multi-image** for `qwen3-vl` is uncertain → video deliberately uses **MLX-VLM** (native video). Photo path uses single images, unaffected.
- **Two runtimes** (Ollama + MLX-VLM) to install/manage; ~12 GB extra model disk. Acceptable on 24 GB / 124 GB free.
- **OCR of tiny text** on preview-size images may be weak → fallback option to pull originals for OCR-flagged assets (deferred unless the photos baseline shows it's needed).
- **MLX-VLM model tags / mlx-vlm API** shift over time — confirm exact model + `video_generate` usage at implementation (see `docs/model-spec-intelligent-search.md`).
- **`bge-m3` size** (~2.2 GB) exceeds the model spec's ~1 GB estimate — fine on 24 GB; configurable.
