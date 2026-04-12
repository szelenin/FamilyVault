# Implementation Plan: Timeline Review Screen

**Branch**: `011-timeline-review` | **Date**: 2026-04-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-timeline-review/spec.md`

## Summary

Add Screen 2 to the existing Selection UI (SvelteKit app). Shows the AI's timeline as a vertical list. User can add text notes, remove items, reorder, and trim videos. Notes stored in project.json — the AI reads them during generation to adjust pacing, captions, and transitions. Guided transition from Screen 1 with summary bar.

## Design Philosophy

Per CLAUDE.md: UI is a tool, AI orchestrates. Screen 2 writes to project.json. The AI reads it. No direct AI↔UI communication.

## Technical Context

**Language/Version**: TypeScript, SvelteKit (existing app at `setup/selection-ui/`)
**Primary Dependencies**: Existing SvelteKit app + Immich API proxy
**Storage**: project.json — add `notes` dict and `timeline_order` array
**Testing**: Playwright E2E
**Project Type**: New route in existing web app

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First | PARTIAL | Playwright E2E validates workflow. No unit tests for Svelte components. |
| III. AI-Interaction First | PASS | Notes feed into AI's video generation reasoning |
| IV. Simplicity / YAGNI | PASS | Text field + remove button + reorder. No custom voice recording. |
| V. Privacy / Local-First | PASS | All local, notes in project.json |

## Project Structure

```text
setup/selection-ui/src/routes/
├── project/[id]/
│   ├── +page.svelte              # MODIFY: add sticky summary bar (US4)
│   ├── +page.server.ts           # MODIFY: calculate estimated duration
│   └── timeline/
│       ├── +page.svelte          # NEW: timeline review (US1, US3)
│       └── +page.server.ts       # NEW: load timeline items with notes

setup/selection-ui/src/routes/api/
├── project/[id]/notes/+server.ts # NEW: read/write notes
└── project/[id]/order/+server.ts # NEW: update timeline order

setup/selection-ui/src/lib/
└── project.ts                    # MODIFY: add notes + order functions

.claude/skills/story-engine/
└── SKILL.md                      # MODIFY: AI reads notes during generation
```

## Implementation Steps

### Step 1: Data layer — notes + order in project.json
Add `saveNotes()`, `saveTimelineOrder()` to `project.ts`. API routes for reading/writing.

### Step 2: Summary bar on Screen 1 (US4)
Sticky bottom bar with selected count, estimated duration, "Add Notes →" and "Generate Now" buttons.

### Step 3: Timeline page (US1)
Vertical list of timeline items with thumbnails, positions, scene labels. Tap to open annotation panel with text field.

### Step 4: Remove items (US1)
Remove button per item. Undo toast. Updates deselected_ids in project.json.

### Step 5: Drag-and-drop reorder (US3)
Touch-friendly drag to reorder items. Saves new order to project.json.

### Step 6: Video trim controls (US3)
For video items: start/end time inputs. Saves trim settings to project.json timeline.

### Step 7: SKILL.md update (US2)
AI reads `notes` from project.json during generation. SKILL.md guidance on how to interpret notes for pacing, captions, transitions.

### Step 8: Playwright tests + polish
E2E tests for: open timeline, add note, remove item, reorder, summary bar.
