# Implementation Plan: Smart Photo & Video Selection

**Branch**: `005-smart-photo-selection` | **Date**: 2026-04-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-smart-photo-selection/spec.md`

## Summary

Replace the naive sequential photo selection in Story Engine v1 with a multi-query search pipeline that scores candidates by quality (faces, resolution, relevance), deduplicates bursts, enforces scene diversity, and presents a visual timeline preview before video generation. Also fix video output quality (CRF 18, 5+ Mbps) and eliminate lossy HEIC→JPEG conversion.

## Technical Context

**Language/Version**: Python 3.13 (on Mac Mini) + Bash (Claude Code skills)
**Primary Dependencies**: Immich REST API v2.6.3, FFmpeg 8+ (via Homebrew), `sips` (macOS native for HEIC), `pytest` 8+
**Storage**: Files on `/Volumes/HomeRAID/stories/` (project files, candidate pools)
**Testing**: pytest (unit + integration + e2e), bats-core (optional for bash)
**Target Platform**: macOS (Mac Mini M-series), Claude Code desktop + mobile
**Project Type**: CLI scripts + Claude Code skill (AI-interaction first)
**Performance Goals**: Selection pipeline < 60 seconds for 100K-asset library (SC-005)
**Constraints**: All processing local (Constitution Principle V), no raw photo bytes to external APIs
**Scale/Scope**: ~70K assets currently, growing. Trips with 200+ photos per event.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First | PASS | TDD cycle: write failing tests → implement → pass. All 4 user stories have testable acceptance scenarios. |
| II. Three-Layer Testing Pyramid | PASS | Small: scoring, dedup, budget allocation, project file. Medium: Immich API search + asset detail. Big: full pipeline search → select → preview → generate. |
| III. AI-Interaction First | PASS | Primary interface is Claude Code skill. All commands via natural language conversation. No GUI dependency. |
| IV. Simplicity / YAGNI | PASS | Hybrid scoring uses Immich metadata directly — no custom ML models. Budget formula is simple arithmetic. Project file is flat JSON. |
| V. Privacy / Local-First | PASS | All processing on Mac Mini. Photos never leave home network. Immich API is local. |

## Project Structure

### Documentation (this feature)

```text
specs/005-smart-photo-selection/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── script-interfaces.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
setup/story-engine/scripts/
├── search_photos.py       # MODIFY: multi-query search, asset detail enrichment
├── score_and_select.py    # NEW: scoring, dedup, burst detection, budget allocation
├── manage_scenario.py     # MODIFY: rename to manage_project.py, new project file format
├── assemble_video.py      # MODIFY: CRF 18, lossless HEIC, video clip support
└── preview.py             # NEW: thumbnail fetching, Immich album creation

.claude/skills/story-engine/
└── SKILL.md               # MODIFY: updated workflow with selection pipeline

tests/story-engine/
├── unit/
│   ├── test_scoring.py         # NEW: quality scoring, burst dedup, budget allocation
│   ├── test_project_file.py    # NEW: project file CRUD, state transitions
│   ├── test_search.py          # MODIFY: multi-query merge, dedup
│   ├── test_assembly.py        # MODIFY: CRF, HEIC, video clip tests
│   └── test_preview.py         # NEW: thumbnail fetch, album creation
├── integration/
│   ├── test_immich_api.py      # MODIFY: asset detail enrichment, thumbnail API
│   └── test_selection_pipeline.py  # NEW: full search → score → select against live Immich
└── e2e/
    └── test_full_story_flow.py # MODIFY: updated for new project file format
```

**Structure Decision**: Extends existing `setup/story-engine/scripts/` layout. Two new scripts (`score_and_select.py`, `preview.py`) added. `manage_scenario.py` evolves to `manage_project.py` with the new project file format. No new top-level directories needed.

## Complexity Tracking

No constitution violations. All design choices use the simplest viable approach.
