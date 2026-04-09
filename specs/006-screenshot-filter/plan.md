# Implementation Plan: Screenshot & Garbage Filtering

**Branch**: `006-screenshot-filter` | **Date**: 2026-04-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-screenshot-filter/spec.md`

## Summary

Add a garbage filter function to the selection pipeline that excludes screenshots, story-engine generated clips, and non-photo content. Runs on already-enriched candidate data — no new API calls. Pure local logic, ~50 lines of code.

## Technical Context

**Language/Version**: Python 3.13 (Mac Mini) + Python 3.9 (local tests)
**Primary Dependencies**: None new — operates on enriched candidate dicts from existing pipeline
**Storage**: N/A — filter is stateless, operates in-memory
**Testing**: pytest (unit tests with mock candidates)
**Target Platform**: macOS (Mac Mini)
**Project Type**: New function in existing script
**Performance Goals**: < 1 second for 500 candidates
**Constraints**: Zero false positives for camera photos

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First | PASS | Write filter tests first, then implement |
| II. Three-Layer Pyramid | PASS | Unit tests cover all filter rules. Integration test verifies against live Immich. |
| III. AI-Interaction First | PASS | Filter is automatic — no UI needed |
| IV. Simplicity / YAGNI | PASS | Single function, no abstractions |
| V. Privacy / Local-First | PASS | Filter runs on local data only |

## Project Structure

### Source Code

```text
setup/story-engine/scripts/
├── score_and_select.py    # MODIFY: add filter_garbage() function, call it before scoring
└── search_photos.py       # MODIFY: enrich_assets() fetches deviceId field

tests/story-engine/
├── unit/
│   └── test_scoring.py    # MODIFY: add garbage filter tests
└── integration/
    └── test_selection_pipeline.py  # MODIFY: verify no screenshots in pipeline output
```

**Structure Decision**: No new files. The filter is a single function added to `score_and_select.py` since it operates on scored/enriched candidates. The `enrich_assets()` function needs to fetch `deviceId` from the asset detail response.
