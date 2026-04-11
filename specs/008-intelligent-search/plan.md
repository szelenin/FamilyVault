# Implementation Plan: Intelligent Search

**Branch**: `008-intelligent-search` | **Date**: 2026-04-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-intelligent-search/spec.md`

## Summary

Rewrite the Story Engine skill to use an AI-first search approach. The AI reasons about the user's intent, discovers trip dates via probe search, expands locations via GPS analysis, and adapts its strategy through conversation. Minimal new Python code — mostly SKILL.md workflow redesign plus one utility function (haversine).

## Design Philosophy

This is primarily an **AI skill update**, not a code feature. The intelligence lives in SKILL.md — teaching Claude how to think about search requests. Python utilities are data access helpers, not the algorithm.

## Technical Context

**Language/Version**: Python 3.13 (Mac Mini) for utilities, SKILL.md (natural language) for the AI workflow
**Primary Dependencies**: Immich REST API v2.6.3, existing utility functions from 005/006/007
**Storage**: Project files on `/Volumes/HomeRAID/stories/`
**Testing**: E2E conversation testing (not TDD — per spec assumptions)
**Project Type**: AI skill workflow + 1 utility function

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First | DEVIATION | TDD not required per spec. AI reasoning is tested via E2E conversation, not unit tests. Utility functions (haversine) may have optional unit tests. |
| II. Three-Layer Pyramid | PARTIAL | E2E conversation test validates the full flow. No mandatory unit/integration layer for AI reasoning. |
| III. AI-Interaction First | PASS | This IS the AI interaction — the entire feature is about the AI driving the workflow. |
| IV. Simplicity / YAGNI | PASS | Minimal code. SKILL.md teaches strategies; AI adapts. No overengineering. |
| V. Privacy / Local-First | PASS | All Immich calls are local. No external AI API calls for photo data. |

## Complexity Tracking

| Deviation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| TDD not enforced | Core intelligence is AI reasoning in SKILL.md, not testable via unit tests | Unit tests for prompt parsing would create brittle regex-based code that's worse than AI reasoning |

## Project Structure

### Source Code

```text
setup/story-engine/scripts/
├── search_photos.py       # MODIFY: add probe_search() wrapper (~15 lines)
├── score_and_select.py    # MODIFY: add haversine_distance() (~10 lines)
└── (no new files)

.claude/skills/story-engine/
└── SKILL.md               # MAJOR REWRITE: AI-first workflow with strategy guidance

tests/story-engine/
└── (no mandatory new tests — E2E conversation testing)
```

**Structure Decision**: 90% SKILL.md rewrite, 10% utility code. No new Python files.

## Research

### R1: Probe Search Implementation

**Decision**: `probe_search()` is a thin wrapper — CLIP search with small limit, no date/city filter. Returns raw assets with timestamps for the AI to analyze.

**Rationale**: The AI needs raw data to reason about. A fixed `detect_date_clusters()` function would impose a specific algorithm. The AI reads timestamps and reasons about them directly.

### R2: Haversine Distance

**Decision**: Add `haversine_distance(lat1, lon1, lat2, lon2)` to score_and_select.py. Pure math, ~10 lines. Returns distance in km.

**Rationale**: Actual math the AI can't do accurately in its head. A utility makes sense here.

### R3: SKILL.md Architecture

**Decision**: Structure as a strategy guide with sections:
1. How to analyze user intent
2. How to run probe search and interpret results (date discovery, multiple trip disambiguation)
3. How to discover locations from GPS data
4. Strategy patterns for common request types (trip, person, event, thematic)
5. How to present scenes and handle refinement
6. When to ask the user vs auto-decide
7. Available utilities and when to use them

The AI reads these strategies and applies judgment per request — not a rigid pipeline.

## Implementation Steps

### Step 1: Utility functions (~25 lines total)
- `probe_search()` in search_photos.py — thin wrapper around CLIP search
- `haversine_distance()` in score_and_select.py — GPS distance calc

### Step 2: SKILL.md rewrite
- Replace fixed pipeline with AI-first workflow
- Add intent analysis guidance
- Add probe search + date discovery examples
- Add GPS location expansion guidance
- Add strategy patterns for trip/person/event/thematic
- Add conversational refinement patterns
- Document all available utilities

### Step 3: E2E validation
- "make a clip of our Miami trip" (no dates) → date discovery
- "Miami trip. Speedboat, vizcaya, sunset walk must have" → must-haves
- Refinement: "skip March 28", "more speedboat" → AI adapts
