# Feature Specification: Intelligent Search

**Feature Branch**: `008-intelligent-search`  
**Created**: 2026-04-10  
**Status**: Draft  
**Input**: IMP-006 remaining requirements R050-R053: probe-based date discovery, GPS location expansion, multi-signal scoring, iterative expansion.

## Clarifications

### Session 2026-04-11

- Q: How should multi-signal confidence weights be determined? → A: Dynamically by the AI based on available data. If GPS data is missing, redistribute GPS weight to other signals. If no people detected, redistribute people weight. The AI decides the weighting strategy per search based on what data is actually available — no fixed formula.
- Q: How should date clustering gap threshold work? → A: The AI builds the clustering approach from the user's intent, not the other way around. "Weekend trip" needs different clustering than "trip to Europe" or "my son plays tennis over the years." The AI is the driver — utilities are helpers it may or may not use. The AI can also create temporary utility functions on the fly if existing ones don't fit.

## Design Philosophy

**AI-First, Not Algorithm-First.**

The intelligence lives in the AI skill (Claude), not in Python functions. The current industry approach (Google Photos, Apple Photos) uses fixed algorithms with parameters. We go further: the AI **reasons about the user's intent** and **decides what strategy to use**, adapting on the fly through conversation.

The system provides:
1. **Data access** — Immich API for search, asset details, GPS, faces, CLIP
2. **Utility functions** — optional helpers the AI may use (haversine distance, date sorting, etc.)
3. **Conversational workflow** — the AI drives a multi-step dialogue to discover, present, refine
4. **Strategy guidance** — the SKILL.md teaches the AI how to approach different request types

The AI is NOT a parameter-filler for a fixed pipeline. It reasons, adapts, asks questions, tries different approaches, and explains its decisions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — AI-Driven Search for Any Request Type (Priority: P1)

The user makes a request in natural language. The AI analyzes the intent, decides what search strategy to use, executes it (possibly in multiple steps), and presents results. The AI adapts its approach based on what it finds — if the first search returns too few results, it tries something different. If it finds multiple possible interpretations, it asks the user.

**Why this priority**: This is the core capability. Everything else builds on the AI's ability to interpret intent and drive the search.

**Independent Test**: Give various prompt types → AI correctly identifies intent and produces relevant results for each.

**Acceptance Scenarios**:

1. **Given** "make a clip of our Miami trip", **When** the AI has no dates in context, **Then** it runs a probe CLIP search ("Miami trip", limit 50), examines the timestamps, discovers the date cluster, and uses it for the full search. It tells the user: "Found your Miami trip: March 28 - April 2, 2026 (267 photos and videos)."

2. **Given** "make a clip of how Edgar grows up", **When** the AI recognizes this as a person-timeline request, **Then** it searches for Edgar by person name across all dates, groups results by significant time intervals (months or years), and presents a timeline of growth moments.

3. **Given** "our weekend trip to the mountains last month", **When** the AI recognizes temporal hints ("last month", "weekend"), **Then** it narrows the search to the correct 2-3 day window without asking the user for exact dates.

4. **Given** a probe search returns photos from 2 different Miami trips (2024 and 2026), **When** the AI detects multiple date clusters, **Then** it asks: "Found 2 Miami trips. March 2026 (245 items) or July 2024 (38 items)?"

5. **Given** the AI's first search strategy returns too few results, **When** it detects < 10 candidates, **Then** it automatically tries broader queries, explains what it tried, and offers options.

---

### User Story 2 — Location Discovery Without City Filtering (Priority: P1)

The AI discovers all trip locations by analyzing GPS coordinates from search results — not by filtering on city name metadata. It finds neighborhoods, suburbs, landmarks, and day-trip destinations that the user didn't explicitly mention.

**Why this priority**: City metadata filtering missed entire scenes in testing (Coconut Grove walk). GPS-based discovery is more reliable and complete.

**Independent Test**: Search for "Miami trip" → results include content from Coconut Grove, Miami Beach, Coral Gables without the user mentioning them.

**Acceptance Scenarios**:

1. **Given** trip photos span Miami, Coconut Grove, and Miami Beach, **When** the AI analyzes GPS coordinates, **Then** it identifies all location clusters and includes content from all of them.

2. **Given** some photos have no GPS, **When** the AI encounters them, **Then** it includes them if they fall within the trip date range (temporal signal compensates for missing spatial signal).

3. **Given** a day trip to Key West (distant from Miami), **When** the AI detects an outlier GPS cluster, **Then** it includes it and mentions: "Also found photos from Key West on March 30."

---

### User Story 3 — Conversational Refinement Loop (Priority: P2)

After presenting initial results, the AI engages in a back-and-forth with the user to refine the selection. The user can ask for more of something, less of something, or redirect the search entirely. The AI adjusts its strategy on the fly.

**Why this priority**: The interactive loop is what differentiates this from a static algorithm. The AI learns from each interaction what the user actually wants.

**Independent Test**: Present initial results → user gives feedback → AI adjusts and presents improved results.

**Acceptance Scenarios**:

1. **Given** the AI shows 35 scenes, **When** the user says "I want more speedboat content", **Then** the AI runs a targeted search for speedboat-related content and adds it to the results.

2. **Given** the AI included March 28 photos that aren't from the user's trip, **When** the user says "March 28 isn't our trip, skip it", **Then** the AI adjusts the date range and removes those scenes.

3. **Given** the user says "I don't see the sunset walk in Coconut Grove", **When** the AI can't find it in current results, **Then** it runs a targeted search (by time, location, and CLIP query) and adds the missing content.

---

### Edge Cases

- Probe search returns 0 results → AI asks for more details (date hint, different wording).
- GPS coordinates at (0,0) or null island → AI filters these out automatically.
- Road trip with no home base → AI detects a chain of locations, presents as sequential stops.
- Library has no GPS data at all → AI falls back to date-only grouping, skips spatial analysis.
- Two trips overlap in location → AI uses temporal clustering to separate them.
- User changes their mind mid-conversation → AI starts fresh with new intent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The AI MUST analyze the user's prompt to determine search intent (trip, person timeline, event, general) and select an appropriate search strategy. No hardcoded mode dispatch — the AI reasons about each request.
- **FR-002**: When the user provides no date range, the AI MUST run a probe search (CLIP, small limit) and analyze returned timestamps to discover the relevant date range. The AI decides the probe queries and interprets the results.
- **FR-003**: When multiple date clusters are found, the AI MUST present options to the user for disambiguation. If temporal hints exist in the prompt ("recent", "last", month names), the AI uses them to auto-select.
- **FR-004**: The AI MUST discover trip locations by analyzing GPS coordinates from results — not by filtering on exact city names. The AI decides how to cluster and what constitutes "nearby."
- **FR-005**: The AI MUST compute a confidence assessment for each candidate using available signals (CLIP relevance, temporal fit, GPS proximity, people presence). The weight of each signal is determined by the AI based on data availability and request context.
- **FR-006**: When search returns too few results (< 10), the AI MUST automatically try alternative strategies (broader queries, wider date range, different search terms) and report what it tried.
- **FR-007**: The AI MUST engage in conversational refinement — accepting feedback like "more of X", "skip Y", "I don't see Z" and adjusting its strategy accordingly.
- **FR-008**: The AI MAY create temporary utility functions (Python scripts run via SSH) when existing utilities don't fit the specific request. These are one-off helpers, not permanent additions.
- **FR-009**: Probe search MUST complete in under 10 seconds. Full search pipeline MUST complete in under 90 seconds for 500 candidates.

### Available Utilities (helpers, not requirements)

The AI has these utilities available but is not required to use them:

- `search_broad()` — CLIP + metadata search, returns candidates
- `search_multi()` — multi-query search with dedup
- `enrich_assets()` — fetch full asset detail (GPS, faces, thumbhash)
- `filter_garbage()` — remove screenshots, story-engine clips
- `detect_scenes()` — 30-minute gap clustering
- `discover_scenes()` — full scene discovery with enrichment
- `score_candidates()` — quality scoring with photo/video weights
- `detect_bursts()` — burst group detection
- `allocate_budget()` — proportional budget distribution
- `select_timeline()` — timeline builder with diversity cap
- `verify_must_haves()` — cross-reference keywords against scenes
- `haversine_distance()` — GPS distance calculation (to be added)
- Any temporary Python script the AI writes and runs via SSH

### Key Entities

- **Search Strategy**: The AI's plan for how to find content for this specific request. Not a fixed enum — the AI describes its strategy in natural language and executes it.
- **Probe Result**: A small initial search to discover parameters (dates, locations). The AI decides what to probe for and how to interpret results.
- **Confidence Assessment**: The AI's judgment of how relevant each candidate is, considering all available signals. Not a fixed formula.
- **Conversational State**: The accumulated context from the user's feedback across the conversation. The AI uses this to adjust its strategy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When given "our Miami trip" with no dates, the AI correctly discovers the trip date range and presents relevant scenes in a single conversation turn.
- **SC-002**: The AI discovers trip locations that the user didn't mention (e.g., Coconut Grove when user said "Miami").
- **SC-003**: Different prompt types produce different search strategies (trip vs person timeline vs event).
- **SC-004**: The full search pipeline completes in under 90 seconds for 500 candidates.
- **SC-005**: After user feedback ("skip March 28", "more speedboat"), the AI adjusts and presents improved results in the next turn.

## Assumptions

- Most trip photos have GPS coordinates embedded (iPhone photos do). Photos without GPS still participate via date range.
- CLIP probe search returns enough results (≥5) to infer trip dates for most trips.
- The AI (Claude) has sufficient reasoning capability to interpret prompts, analyze search results, and adapt strategies without hardcoded rules.
- Existing utility functions provide the data access layer. The AI orchestrates them.
- TDD is NOT required for this feature. The core intelligence lives in the AI skill workflow (prompt interpretation, search orchestration, adaptive decisions), which is best validated by E2E conversation testing rather than unit tests. Utility functions (haversine, clustering) may have unit tests but are not mandated.

## Strategy Guidance for AI Skill

The SKILL.md should include guidance (not rigid rules) for common request patterns:

**Trip requests** ("Miami trip", "vacation in Paris"):
- Probe with location keywords → discover date cluster → broad search in date range → GPS expansion → scene discovery

**Person timeline** ("how Edgar grows", "my daughter through the years"):
- Search by person name across all dates → group by significant time gaps (months/years) → select representative moments per period

**Event requests** ("birthday party", "wedding"):
- Probe with event keywords → find date cluster (likely 1 day) → broad search that day → scene detection with shorter gaps (15 min)

**Thematic requests** ("sunset photos", "food we ate"):
- CLIP search with theme keywords → no date/location constraints → group by visual similarity or chronology

The AI uses these as starting points and adapts based on what it finds.
