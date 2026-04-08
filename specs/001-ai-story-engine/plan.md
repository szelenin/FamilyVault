# Implementation Plan: AI Story Engine

**Branch**: `001-ai-story-engine` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-ai-story-engine/spec.md`

## Summary

A Claude Code agent skill that lets the user describe a family story in natural
language, searches the Immich library via REST API, proposes an ordered scenario
for review, selects music, and assembles a final MP4 via FFmpeg on the Mac Mini —
all through conversation, with no GUI required. Accessible from the Claude mobile
client via a remotely-exposed Claude session.

## Technical Context

**Language/Version**: Python 3.13 (on Mac Mini) + Bash (Claude Code skills)
**Primary Dependencies**: FFmpeg 7+ (Mac Mini, brew), Immich REST API v2.6.3, `sips` (built-in macOS), `pytest` 8+
**Storage**: Files on `/Volumes/HomeRAID/stories/` (configurable via `STORIES_DIR` env var)
**Testing**: pytest (unit + integration), bats-core for skill shell tests
**Target Platform**: macOS (Mac Mini server — Apple Silicon); Claude Code agent on user's machine / mobile
**Project Type**: Claude Code skill + server-side Python scripts
**Performance Goals**: Scenario generation <30s for 15K-item library (SC-001); video assembly <5min for 30 items (SC-003)
**Constraints**: Photo/video bytes NEVER sent to Claude API (FR-009); only captions/descriptions/metadata sent externally

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First | ✅ PASS | Tests defined in spec acceptance scenarios; test tasks precede implementation tasks |
| II. Three-Layer Testing | ✅ PASS | Unit: search/scenario/assembly logic; Integration: live Immich API; E2E: full story flow |
| III. AI-Interaction First | ✅ PASS | Core interaction surface is Claude Code agent; no GUI required |
| IV. Simplicity/YAGNI | ✅ PASS | Direct API calls, no extra services, no framework; Python scripts + Claude skill |
| V. Privacy/Local-First | ✅ PASS | Only captions/metadata to Claude API; photo bytes stay on LAN |

All 5 principles pass. No complexity justification required.

## Project Structure

### Documentation (this feature)

```text
specs/001-ai-story-engine/
├── plan.md              # This file
├── research.md          # API details, FFmpeg patterns
├── data-model.md        # Scenario JSON schema
├── quickstart.md        # How to use the story engine
├── contracts/
│   └── scenario-schema.json   # JSON Schema for scenario files
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
setup/story-engine/
├── config.sh                  # Configuration defaults (IMMICH_URL, STORIES_DIR, etc.)
├── scripts/
│   ├── search-photos.py       # Immich API: smart search + metadata search + person lookup
│   ├── manage-scenario.py     # Scenario CRUD: create, update, read, list, delete
│   └── assemble-video.py      # FFmpeg orchestrator: HEIC→JPEG via sips + slideshow assembly
├── music/                     # Bundled royalty-free tracks organized by mood
│   ├── upbeat/
│   ├── calm/
│   └── sentimental/
└── README.md

.claude/skills/story-engine/
└── SKILL.md                   # Claude Code skill: story creation workflow instructions

tests/story-engine/
├── unit/
│   ├── test_search.py         # Search logic, result ranking, query construction
│   ├── test_scenario.py       # Scenario state machine, JSON serialization
│   └── test_assembly.py       # FFmpeg command generation, HEIC detection, timing math
└── integration/
    └── test_immich_api.py     # Live Immich API calls (requires running Immich)
```

**Structure Decision**: Single project layout. Scripts live in `setup/story-engine/` alongside other setup components (consistent with `setup/immich/`). Claude Code skill in `.claude/skills/story-engine/SKILL.md`. No separate service or daemon — scripts are invoked by Claude over SSH.

## Complexity Tracking

No violations requiring justification. All design decisions are at minimum complexity for the requirements.
