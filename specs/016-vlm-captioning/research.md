# Phase 0 Research — IMP-018 VLM Captioning & Extraction

All decisions below were resolved during brainstorming + a dedicated research agent (see the technical design `docs/superpowers/specs/2026-06-13-imp-018-vlm-captioning-design.md` and the options spike `docs/spike/2026-04-27-local-llm-agent-options.md`). No `NEEDS CLARIFICATION` remain.

## D-R1: Video VLM backend — MLX-VLM (not Ollama)

- **Decision**: Photos use Ollama `qwen3-vl:8b`; **video uses MLX-VLM** (`mlx-community/Qwen3-VL-8B-Instruct-4bit`).
- **Rationale**: Ollama has **no native video input** (issue #12926, still open) and an uncertain one-image-per-turn limit for Qwen-VL; MLX-VLM ingests video natively on Apple Silicon and preserves Qwen's dynamic-fps + time-aligned timestamps (the "when" reasoning).
- **Alternatives**: Ollama multi-image single call (rejected: unreliable/unsupported); per-frame caption then summarize (rejected: loses temporal reasoning).

## D-R2: Frame sampling — hybrid

- **Decision**: PySceneDetect `ContentDetector` (→`AdaptiveDetector` for shaky footage) → 1–2 frames/scene + guaranteed first/mid/last, **min 3 / max ~16–24**; fall back to uniform ~1 fps when ≤1 scene.
- **Rationale**: Research consensus — fewer-richer frames beat many-cheap; hybrid covers single-shot home clips *and* multi-cut trips. Uniform alone misses cuts; scene-only degenerates on single-shot clips.
- **Alternatives**: pure uniform, pure scene-detect, keyframe/I-frame, CLIP-diversity (all weaker for this mixed corpus).

## D-R3: Aggregation — single multi-frame call, map-reduce fallback

- **Decision**: One MLX-VLM call over the sampled frames for clips within the frame budget; **map-reduce** (window→caption→merge) only for over-budget long clips.
- **Rationale**: Single call gives best temporal reasoning and lowest cost for the common (short) case; map-reduce is what production systems use for long video.

## D-R4: Embedding model — multilingual `bge-m3` via Ollama

- **Decision**: Embed each (English) caption with `bge-m3` (configurable) via Ollama's embeddings endpoint; embed queries with the same model.
- **Rationale**: Descriptions are stored in one canonical language (English); a multilingual embedder makes EN/RU/UK **queries** match English descriptions without storing translations (per spec clarification 2026-06-14).
- **Alternatives**: English-only embedder (rejected: no cross-language search); storing translations per asset (rejected: cost/complexity, YAGNI).

## D-R5: Index store — SQLite, hybrid (FTS5 + vectors)

- **Decision**: One SQLite file with `assets`, `video_segments`, `assets_fts` (FTS5), and a vector column; brute-force cosine in Python first, upgrade to `sqlite-vec` only if needed.
- **Rationale**: An index needs fast text + semantic retrieval and clean joins by asset ID; one file to back up. ~69K vectors brute-force < 100 ms (~200 MB RAM) — no extension needed initially (YAGNI).
- **Alternatives**: JSON sidecars (no query engine), write-back to Immich (pollutes Immich, lossy), dedicated vector DB (overkill for 69K).

## D-R6: Storage placement — native SSD (WAL) + RAID backup

- **Decision**: DB on native SSD in WAL mode; copy the DB file to the RAID after each run.
- **Rationale**: Frequent read/write + reliable SQLite locking favor local APFS; the index is derived/regenerable but expensive to rebuild, so a cheap file backup protects against an SSD loss.
- **Alternatives**: DB on RAID (slower random I/O, flaky SQLite locking).

## D-R7: Image input — Immich "preview"

- **Decision**: Fetch Immich preview-size images (~1440–2048px); originals only as a later fallback for tiny-text OCR if the photos baseline shows weakness.
- **Rationale**: One JPEG/asset (no HEIC convert), enough detail for most OCR; bounded staging.

## D-R8: Execution — incremental, resumable, chunked

- **Decision**: Manual CLI batch; process `pending` OR changed (`source_hash`) OR superseded (`schema_ver`); chunked fetch→caption→cleanup bounded by `STAGING_BUDGET`; SQLite is the progress ledger. Cron later.
- **Rationale**: Fits the offload model, safe to re-run, no full re-index per run.
- **Alternatives**: lazy on-first-query (rejected: incompatible with offloading Immich; query-time latency).

## D-R9: Automatic memory governance

- **Decision**: A governor measures free RAM vs the phase's need and frees only as needed, escalating: unload non-needed models (`/api/ps`→`ollama stop`) → stop Immich containers (`docker compose stop`) → stop OrbStack VM (`orb stop`); records and restores exactly what it stopped. Policy `--memory auto|force|never` (default auto). Per-phase `REQUIRED_MODELS` so only one path's models are resident.
- **Rationale**: 24 GB shared with Immich/OS; offload should be automatic and least-disruptive, not a manual flag. On 24 GB, photos rarely need to touch Immich at all.
- **Alternatives**: manual `--low-mem` flag (rejected: babysitting); always-offload (rejected: unnecessary Immich downtime).

## D-R10: Environment readiness

- **Decision**: `setup.sh` (idempotent install/pull) + `doctor` preflight that checks **presence on disk** scoped to `--type` and fails fast with the exact fix.
- **Rationale**: A long batch must not start half-installed; partial runs shouldn't require the other media type's components.

## D-R11: Identity boundary

- **Decision**: The VLM describes generically ("a boy"); "who" is resolved via Immich person IDs (cached into the index). Never re-identify people with the VLM.
- **Rationale**: Immich already solves identity; re-identifying would duplicate work and risk error (model spec + Constitution V).
