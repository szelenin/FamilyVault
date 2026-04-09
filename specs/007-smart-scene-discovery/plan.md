# Implementation Plan: Smart Scene Discovery

**Branch**: `007-smart-scene-discovery` | **Date**: 2026-04-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/007-smart-scene-discovery/spec.md`

## Summary

Refactor the selection pipeline into a two-phase architecture: Phase A (Scene Discovery) finds all content and presents all scenes to the user; Phase B (Selection) applies budget after user confirmation. Replace exact city filtering with broad CLIP-first search. Add must-have scene verification. Scene labels generated dynamically by the AI skill from raw metadata + user prompt context.

## Technical Context

**Language/Version**: Python 3.13 (Mac Mini) + Python 3.9 (local tests)
**Primary Dependencies**: Immich REST API v2.6.3 (search/smart, search/metadata, assets/{id})
**Storage**: Project files on `/Volumes/HomeRAID/stories/`
**Testing**: pytest (unit + integration)
**Target Platform**: macOS (Mac Mini), Claude Code skill
**Performance Goals**: Phase A < 90 seconds for 100K library, 200+ trip photos
**Constraints**: No CLIP descriptions per asset — Immich only uses CLIP internally for search ranking. Labels rely on city, people, time, filename, and AI prompt context.

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First | PASS | TDD for new discovery functions |
| II. Three-Layer Pyramid | PASS | Unit: scene discovery, broad search, must-have verification. Integration: full Phase A against live Immich. |
| III. AI-Interaction First | PASS | Phase A → confirm → Phase B is a conversational workflow |
| IV. Simplicity / YAGNI | PASS | Only trip mode implemented. Extension point is a simple enum. No custom ML. |
| V. Privacy / Local-First | PASS | All Immich calls are local network |

## Research

### R1: CLIP Description Availability

**Finding**: Immich v2.6.3 does NOT expose CLIP descriptions or tags per asset. `smartInfo` and `tags` fields return None/empty. CLIP is used internally for search ranking only.

**Impact**: Scene labels cannot use CLIP descriptions. Labels generated from: city, people names, time-of-day, and AI's prompt-matching context.

### R2: Broad Search Strategy

**Decision**: Run CLIP search with no city filter (primary), plus metadata search by date range only (supplementary). Merge and dedup. Do NOT filter by city at search time — let scene detection group by location naturally.

**Rationale**: CLIP search finds semantically relevant content across cities. Metadata search by date range catches everything in the trip window regardless of content. Combined, this ensures no neighborhood is missed.

### R3: Detection Mode Architecture

**Decision**: Simple string enum (`trip`, `person-timeline`, `general`) stored in project file. Only `trip` mode implemented now. The `discover_scenes()` function accepts a mode parameter and dispatches to the appropriate clustering function.

**Rationale**: YAGNI — trip mode is the only current need. The dispatch pattern is trivial to extend later without refactoring.

## Project Structure

### Source Code

```text
setup/story-engine/scripts/
├── search_photos.py         # MODIFY: add search_broad() — CLIP + date-range, no city filter
├── score_and_select.py      # MODIFY: add discover_scenes() wrapper, must-have verification
├── manage_project.py        # MODIFY: add discovery field, scene_confirmation field to project
└── preview.py               # MODIFY: create discovery preview album with all candidates

.claude/skills/story-engine/
└── SKILL.md                 # MODIFY: two-phase workflow, scene presentation, confirm step

tests/story-engine/
├── unit/
│   ├── test_scoring.py      # MODIFY: add discovery tests, must-have verification tests
│   └── test_project_file.py # MODIFY: add discovery/confirmation field tests
└── integration/
    └── test_selection_pipeline.py  # MODIFY: add broad search + discovery integration test
```

**Structure Decision**: No new files. Extends existing scripts with new functions. The two-phase workflow is orchestrated by the AI skill, not a new script.
