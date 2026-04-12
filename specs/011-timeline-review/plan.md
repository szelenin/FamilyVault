# Implementation Plan: Timeline Review Screen (Screen 2)

**Branch**: `011-timeline-review` | **Date**: 2026-04-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-timeline-review/spec.md`

## Summary

Add Screen 2 to the existing Selection UI. Shows SCENES (not individual items) as cards with thumbnail strips. User adds stories/instructions per scene, reorders scenes, removes scenes, and trims individual videos. The story field is a unified text input — handles stories, AI commands, trim requests, mood. The AI reads scene_notes from project.json during generation and interprets them for pacing, captions, transitions. No AI plan shown in the UI. Quick 480p preview via Immich link is Phase 2.

## Design Philosophy

Per CLAUDE.md: AI orchestrates, UI is a tool, project.json is shared state. Screen 2 collects stories — the AI interprets them. No generate button — AI guides via conversation. User switches freely between Screen 1 and Screen 2.

## Technical Context

**Language/Version**: TypeScript, SvelteKit (existing app at `setup/selection-ui/`)
**Primary Dependencies**: Existing SvelteKit app + Immich API proxy + project.json
**Storage**: project.json — add `scene_notes` dict, `scene_order` array, video trim settings
**Testing**: Playwright E2E
**Target Platform**: Mobile-first, responsive
**Project Type**: New route in existing web app

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| III. AI-Interaction First | PASS | Stories feed into AI's generation reasoning |
| IV. Simplicity / YAGNI | PASS | Scene cards + text field + remove + reorder. No AI plan UI. |
| V. Privacy / Local-First | PASS | All local, stories in project.json |

## Project Structure

```text
setup/selection-ui/src/routes/
├── project/[id]/
│   ├── +page.svelte              # MODIFY: add summary bar + link to Screen 2
│   ├── +page.server.ts           # MODIFY: calculate estimated duration
│   └── timeline/
│       ├── +page.svelte          # NEW: scene-level story collection
│       └── +page.server.ts       # NEW: load scenes with notes + selected items

setup/selection-ui/src/routes/api/
├── project/[id]/notes/+server.ts # NEW: read/write scene_notes
└── project/[id]/order/+server.ts # NEW: update scene order
└── project/[id]/trim/+server.ts  # NEW: save video trim settings

setup/selection-ui/src/lib/
└── project.ts                    # MODIFY: add scene_notes, scene_order, trim functions

.claude/skills/story-engine/
└── SKILL.md                      # MODIFY: AI reads scene_notes, guides full flow
```

## Implementation Steps

### Step 1: Data layer
Add to project.ts: `saveSceneNotes()`, `saveSceneOrder()`, `saveVideoTrim()`.
Add API routes for each. project.json gets `scene_notes`, `scene_order`, `video_trims` fields.

### Step 2: Timeline page — scene cards (US1)
New route `/project/[id]/timeline`. Vertical list of scene cards with:
- Thumbnail strip (first 5 items from each scene)
- Scene label, item count, estimated duration
- "Add your story" text field (unified — stories, AI commands, trim requests)
- Story indicator when note exists
- Expand thumbnail strip to see all items

### Step 3: Remove scenes (US1/US3)
Remove button per scene card. Undo toast. Items go to deselected_ids.

### Step 4: Drag-and-drop reorder (US3)
Touch-friendly scene drag. Saves order to project.json.

### Step 5: Video trim (US3)
In expanded thumbnail view, tap video → start/end sliders. Saves trim to project.json.

### Step 6: Summary bar + navigation (US4)
Sticky bottom bar on both Screen 1 and Screen 2:
- Selected count + estimated duration
- Link to the other screen

### Step 7: SKILL.md update (US2 + FR-013)
AI reads `scene_notes` during generation. Guidance on interpreting stories for pacing, captions, mood. AI guides full flow: Screen 1 link → Screen 2 link → preview link → feedback → final.

### Step 8: Playwright tests
E2E tests: open timeline, add story, remove scene, reorder, summary bar, video trim.

### Phase 2 (later): Quick preview (US5)
AI generates 480p preview, shares via Immich link. User watches, gives feedback, AI adjusts.
