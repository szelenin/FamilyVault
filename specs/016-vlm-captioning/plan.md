# Implementation Plan: IMP-018 VLM Captioning & Extraction

**Branch**: `016-vlm-captioning` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-vlm-captioning/spec.md`
**Technical design**: [docs/superpowers/specs/2026-06-13-imp-018-vlm-captioning-design.md](../../docs/superpowers/specs/2026-06-13-imp-018-vlm-captioning-design.md) (authoritative for HOW)

## Summary

Build an understanding-layer batch indexer: for every Immich asset, produce a VLM caption (what is happening) + OCR + a multilingual semantic embedding, stored in a local SQLite hybrid index (FTS5 + vectors + cached Immich filter fields) keyed to the asset ID. Photos run via Ollama `qwen3-vl:8b`; video via MLX-VLM (hybrid scene-detect sampling, two-tier OCR, multi-frame aggregation with map-reduce fallback); embeddings via Ollama `bge-m3`. The indexer is an incremental, resumable, chunked CLI with a `doctor` preflight, missing-preview remediation, and an automatic memory governor (load only the phase's models; escalate unload → stop Immich → stop OrbStack only when RAM is low; auto-restore). Delivered photos-first (Phase A), then video (Phase B), then automatic resource governance (Phase C).

## Technical Context

**Language/Version**: Python 3.13 (`/opt/homebrew/bin/python3.13` on the Mac Mini — default `python3` is broken; see `setup/local-agent/SETUP-NOTES.md`)
**Primary Dependencies**: Ollama (`qwen3-vl:8b`, `bge-m3`); MLX-VLM (`mlx-community/Qwen3-VL-8B-Instruct-4bit`); FFmpeg; PySceneDetect; `openai` SDK (Ollama OpenAI-compatible endpoint); `requests` (Immich); `psutil` (memory); stdlib `sqlite3` (FTS5 + vectors)
**Storage**: SQLite on native SSD (WAL mode) at `~/.familyvault/index/familyvault.db` (configurable); backup copy to `/Volumes/HomeRAID`; bounded staging dir on SSD (`STAGING_BUDGET` default 10 GB)
**Testing**: `pytest` (3 layers: unit / integration / e2e), run under `python3.13`
**Target Platform**: macOS (Apple M4 Mac Mini, 24 GB); Immich under OrbStack
**Project Type**: Single-project CLI tool (understanding-layer indexer) + library modules
**Performance Goals**: Batch/ingest job (slow-OK). Throughput is secondary; correctness, resumability, and not crashing the host are primary. Embedding a caption is milliseconds; vector search over ~69K assets < 100 ms (brute-force)
**Constraints**: 24 GB RAM shared with Immich/OS → automatic memory governance; staging disk ≤ budget; fully local (no external network for media); identity never re-derived from pixels
**Scale/Scope**: ~69K Immich assets (photos + videos); incremental — a run processes only what needs work

No `NEEDS CLARIFICATION` remain — the technical design and the spec clarifications resolved all open decisions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|---|---|---|
| **I. Test-First (NON-NEGOTIABLE)** | `/speckit-tasks` will order failing tests before implementation for every unit; TDD cycle enforced per task. | ✅ Pass (committed) |
| **II. Three-Layer Testing Pyramid** | Unit (db, sampling, governor, captioner-with-mock, doctor — no network); Integration (live Immich preview/missing-preview, one live Ollama caption+embed, real ffmpeg, MLX on a short clip); E2E (index a tiny fixture → FTS **and** vector search return the expected asset). Mocking policy honored: **real temp-dir SQLite** (not mocked); mocks only for the external model/Immich calls. | ✅ Pass |
| **III. AI-Interaction First** | The indexer is a CLI (AI-invocable); its output (the index) is the substrate the agent searches over (IMP-020). No GUI-only capability. | ✅ Pass |
| **IV. Simplicity & YAGNI** | One SQLite file; brute-force vectors first (no extension) — upgrade to `sqlite-vec` only if needed; map-reduce only for over-budget clips. Two model runtimes (Ollama + MLX) is the one justified complexity — see Complexity Tracking. | ✅ Pass (1 tracked item) |
| **V. Privacy & Local-First** | All inference is local (Ollama + MLX on-device); media never leaves the network; SQLite on-prem; no external API. This feature *strengthens* local-first (removes any reliance on cloud VLM). | ✅ Pass (strong) |

**Gate result: PASS.** One justified complexity tracked below; no unjustified violations.

## Project Structure

### Documentation (this feature)

```text
specs/016-vlm-captioning/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI + module interface contracts)
│   ├── cli.md
│   └── captioner.md
├── checklists/
│   └── requirements.md  # from /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
setup/understanding/             # new module (sibling of setup/story-engine, setup/local-agent)
├── README.md
├── setup.sh                     # install/pull models + deps (idempotent)
├── config.sh                    # INDEX_DB, INDEX_BACKUP_DIR, IMMICH_*, model names,
│                                # STAGING_DIR, STAGING_BUDGET=10G, MEMORY_POLICY=auto, caps
├── preflight.py                 # `doctor` — presence-on-disk checks, scoped to --type
├── index/
│   ├── __init__.py
│   ├── db.py                    # SQLite schema + FTS5 + vectors; open/migrate; upsert/query; backup
│   └── status.py                # status enum: pending|done|no_preview|error
├── fetch/
│   ├── __init__.py
│   ├── immich.py                # list assets, download preview, extract video frames (ffmpeg)
│   └── sampling.py              # hybrid frame sampling (scene-detect + first/mid/last + caps)
├── caption/
│   ├── __init__.py
│   ├── base.py                  # CaptionResult + captioner interface; per-phase REQUIRED_MODELS
│   ├── photo_ollama.py          # photo caption+OCR via Ollama qwen3-vl:8b
│   ├── video_mlx.py             # video caption+OCR via MLX-VLM
│   └── embed.py                 # caption/query embedding via Ollama bge-m3
├── resources.py                 # memory governor (measure → unload → stop Immich → stop OrbStack)
├── index_cli.py                 # entrypoint: doctor/run/status/report/retry/search
└── (pyproject.toml or pytest via repo config)

tests/understanding/             # matches repo convention (tests/story-engine, tests/immich)
├── unit/                        # db, sampling, governor (mocked mem/subprocess), captioner (mock model), doctor
├── integration/                 # live Immich / Ollama / ffmpeg / MLX (opt-in markers)
└── e2e/                         # tiny fixture → index → FTS+vector search
```

**Structure Decision**: New self-contained module `setup/understanding/` (mirrors `setup/local-agent` and `setup/story-engine`). Tests live under `tests/understanding/{unit,integration,e2e}` to match the dominant repo convention (`tests/story-engine/…`) and the constitution's three-layer naming, with a `conftest.py` adding `setup/understanding` to `sys.path` (same pattern as `tests/story-engine/conftest.py`).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Two model runtimes (Ollama + MLX-VLM)** | Ollama has no native video input (and an uncertain multi-image limit); MLX-VLM ingests video natively on Apple Silicon and preserves temporal timestamps. Photos stay on the already-used Ollama. | Single-runtime (Ollama-only) rejected: video temporal understanding would be degraded or impossible; forcing per-frame photo-style calls loses "when" reasoning. Confirmed by the design's research (Ollama issue #12926, still open). |
