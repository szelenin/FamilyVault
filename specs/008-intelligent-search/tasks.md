# Tasks: Intelligent Search

**Input**: Design documents from `/specs/008-intelligent-search/`
**Prerequisites**: plan.md (required), spec.md (required)

**Tests**: TDD NOT required per spec assumptions. Core intelligence is AI reasoning in SKILL.md, validated by E2E conversation testing. Utility functions may have optional unit tests.

**Organization**: Tasks grouped by user story. This feature is 90% SKILL.md rewrite (AI skill workflow) and 10% utility code.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Utility Functions)

**Purpose**: Add the two small helper functions the AI needs for data access.

- [X] T001 [P] Add `probe_search(session, immich_url, queries, limit=50)` to `setup/story-engine/scripts/search_photos.py` — thin wrapper: CLIP search with no date/city filter, returns raw assets with timestamps for AI analysis
- [X] T002 [P] Add `haversine_distance(lat1, lon1, lat2, lon2)` to `setup/story-engine/scripts/score_and_select.py` — returns distance in km between two GPS coordinates using the Haversine formula. Pure math, ~10 lines.

---

## Phase 2: User Story 1 — AI-Driven Search (Priority: P1) MVP

**Goal**: The AI analyzes the user's prompt, discovers trip dates via probe search, runs full broad search, and presents all scenes. No hardcoded parameters — the AI reasons about each request.

**Independent Test**: "make a clip of our Miami trip" with no dates → AI discovers March 28 - April 2 via probe → presents all scenes.

- [X] T003 [US1] Rewrite SKILL.md US1 section: Replace fixed pipeline with AI-first workflow. Structure as intent analysis → probe search → date discovery → full search → enrich + filter → scene discovery → present all scenes → user confirms. Each step describes what the AI should REASON about, not exact code to execute. File: `.claude/skills/story-engine/SKILL.md`
- [X] T004 [US1] Add intent analysis guidance to SKILL.md: How to determine request type (trip, person timeline, event, thematic) from natural language. How to extract location hints, temporal hints ("recent", "last month", "in March"), person names, and must-have keywords. Not regex rules — reasoning patterns.
- [X] T005 [US1] Add probe search and date discovery guidance to SKILL.md: When to run a probe (no dates in prompt), how to interpret returned timestamps (look for date clusters), how to handle multiple clusters (ask user if ambiguous, auto-select if "recent"/"last" hint), how to handle too few results (ask user for more details).
- [X] T006 [US1] Add example AI reasoning blocks to SKILL.md showing how the AI thinks through a probe result: "I see 45 photos clustered March 28 - April 2 and 3 stray photos from 2024. The March cluster is the recent trip. Using March 28 - April 2 as the date range."

**Checkpoint**: AI can discover trip dates from a vague prompt and run the full search without hardcoded parameters.

---

## Phase 3: User Story 2 — Location Discovery (Priority: P1)

**Goal**: AI discovers all trip locations by analyzing GPS coordinates, not by city name filtering.

**Independent Test**: Search "Miami trip" → AI reports discovering Miami, Coconut Grove, Miami Beach from GPS clusters.

- [X] T007 [US2] Add GPS location discovery guidance to SKILL.md: How to analyze GPS coordinates from enriched candidates (use haversine_distance to group nearby photos), how to identify location clusters, how to report discovered locations to user, how to handle photos with no GPS (include via date range).
- [X] T008 [US2] Add location edge case guidance to SKILL.md: Day trips to distant locations (include as separate location group), road trips with no home base (present as sequential stops), null island GPS (0,0) filtering.

**Checkpoint**: AI discovers neighborhoods and landmarks the user didn't mention.

---

## Phase 4: User Story 3 — Conversational Refinement (Priority: P2)

**Goal**: AI handles feedback and adjusts its strategy on the fly.

**Independent Test**: User says "skip March 28" or "more speedboat" → AI adjusts and re-presents.

- [X] T009 [US3] Add conversational refinement guidance to SKILL.md: How to handle "more of X" (targeted search + add to results), "skip Y" (remove scenes/date ranges), "I don't see Z" (targeted search for missing content), "that's not our trip" (re-probe or ask for dates), "start over" (reset project). How to re-present scenes after adjustment without recreating the preview album.

**Checkpoint**: AI can iterate with user to refine results across multiple turns.

---

## Phase 5: Strategy Patterns + Utilities Reference

**Purpose**: Add strategy guidance for non-trip request types and document all available utilities.

- [X] T010 [P] Add strategy patterns to SKILL.md for non-trip request types: person timeline ("how Edgar grows" → person search across all dates, group by months/years), event ("birthday party" → probe for single day, short scene gaps), thematic ("sunset photos" → CLIP only, no date/location constraints). Mark as starting points the AI adapts.
- [X] T011 [P] Add available utilities reference section to SKILL.md: List all utility functions with one-line descriptions and when to use them. Include note that the AI can write temporary Python scripts via SSH when utilities don't fit the request.
- [X] T012 Update SKILL.md US2 (Refinement) and US3 (Generation) sections to be consistent with the new AI-first workflow. Preserve share URL output rules (plain text, no markdown wrapping).

---

## Phase 6: Validation + Commit

**Purpose**: E2E conversation testing and commit.

- [X] T013 E2E test: Invoke story-engine skill with "make a clip of our Miami trip" (no dates) → verify AI discovers date range via probe, presents all scenes with preview album link
- [X] T014 E2E test: Invoke with "Miami trip. Speedboat, vizcaya garden, sunset walk must have" → verify all 3 must-haves identified in scene list
- [X] T015 E2E test: Refinement — respond "skip March 28" then "more speedboat content" → verify AI adjusts scenes
- [X] T016 Run full unit test suite to confirm no regressions: `pytest tests/story-engine/unit/ -v` — all 148 tests pass
- [X] T017 Commit and push all changes to `008-intelligent-search` branch

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (US1)**: Can start in parallel with Phase 1 (SKILL.md doesn't depend on code existing yet)
- **Phase 3 (US2)**: Depends on Phase 2 (builds on SKILL.md foundation)
- **Phase 4 (US3)**: Depends on Phase 2
- **Phase 5 (Patterns)**: Independent of Phases 3-4
- **Phase 6 (Validation)**: Requires all phases complete + live Immich

### Parallel Opportunities

- T001 + T002 (utilities) can run in parallel
- T010 + T011 (strategy patterns + utilities ref) can run in parallel
- Phase 2 and Phase 1 can run in parallel (different files)

---

## Implementation Strategy

### MVP First (Phase 1 + 2)

1. Add utility functions (T001-T002)
2. Rewrite SKILL.md US1 with AI-first workflow (T003-T006)
3. Test with "our Miami trip" → verify probe date discovery works

### Full (all phases): 17 tasks

Adds location discovery, conversational refinement, strategy patterns, E2E tests.

### What makes this feature different

Most tasks are SKILL.md writing — teaching the AI how to think. Not Python code. The E2E test is a live conversation, not a pytest run.

---

## Notes

- This feature deviates from Constitution Principle I (TDD) — justified in plan.md Complexity Tracking
- SKILL.md is the primary deliverable, not Python code
- E2E testing = run the skill in Claude Code and verify the conversation flow
- Utility functions are optional helpers — the AI may or may not use them
