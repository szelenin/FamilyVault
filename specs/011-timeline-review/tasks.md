# Tasks: Timeline Review Screen (Screen 2)

**Input**: Design documents from `/specs/011-timeline-review/`
**Prerequisites**: plan.md, spec.md

**Tests**: Playwright E2E. Not strict TDD for UI components.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Data Layer

**Purpose**: Add scene_notes, scene_order, video_trims to project.json and API routes.

- [x] T001 [P] Add `saveSceneNotes(projectId, sceneId, note)`, `getSceneNotes(projectId)`, `saveSceneOrder(projectId, order)`, `saveVideoTrim(projectId, assetId, start, end)` to `setup/selection-ui/src/lib/project.ts`
- [x] T002 [P] Create `src/routes/api/project/[id]/notes/+server.ts` — POST to save scene note, GET to read all notes
- [x] T003 [P] Create `src/routes/api/project/[id]/order/+server.ts` — POST to save scene order
- [x] T004 [P] Create `src/routes/api/project/[id]/trim/+server.ts` — POST to save video trim settings

---

## Phase 2: US1 — Scene-Level Storytelling (P1) MVP

**Goal**: Scene cards with thumbnail strips, story text field, expand to view items.

- [x] T005 [US1] Create `src/routes/project/[id]/timeline/+page.server.ts` — load active scenes (non-deselected) with notes, item counts, thumbnail asset IDs
- [x] T006 [US1] Create `src/routes/project/[id]/timeline/+page.svelte` — vertical list of scene cards: thumbnail strip (first 5 items), scene label, item count, estimated duration, story indicator
- [x] T007 [US1] Add "Add your story" text field per scene card — tap to expand, type anything (stories, AI commands, trim requests, mood), save to API on blur/submit
- [x] T008 [US1] Add expand/collapse on thumbnail strip — tap to show all items in scene grid (view only, not editing)
- [x] T009 [US1] Add story indicator — small icon on scene card when note exists

**Checkpoint**: User opens Screen 2, sees scenes, adds stories, saves to project.json.

---

## Phase 3: US3 — Scene Reorder + Remove + Video Trim (P1)

**Goal**: Remove scenes, drag to reorder, trim videos.

- [x] T010 [US3] Add remove button per scene card — undo toast for 5 seconds, items go to deselected_ids
- [ ] T011 [US3] Add drag-and-drop scene reorder — touch-friendly drag handle (≡), saves order to project.json via API
- [ ] T012 [US3] In expanded scene view, tap video thumbnail → show trim control with start/end time inputs or sliders. Save to project.json via trim API. Show play icon + duration badge on video thumbnails.

---

## Phase 4: US4 — Summary Bar + Navigation (P2)

**Goal**: Sticky bottom bar on both screens with counts and cross-navigation.

- [x] T013 [US4] Add sticky summary bar to Screen 2 (`/timeline`): total selected count, estimated video duration, "← Selection" link
- [x] T014 [US4] Add sticky summary bar to Screen 1 (`/project/[id]`): total selected count, estimated duration, "Review Timeline →" link
- [x] T015 [US4] Calculate estimated duration: photos × 4s + sum of video durations − crossfade overlaps

---

## Phase 5: US2 — AI Interprets Notes (P1) + FR-013 Guidance

**Goal**: SKILL.md update so AI reads scene_notes and guides the full flow.

- [x] T016 [US2] Update SKILL.md: AI reads `scene_notes` from project.json during generation. Guidance on interpreting stories for pacing, captions, transitions, mood per scene.
- [x] T017 [US2] Update SKILL.md: AI guides full flow via conversation — at each step tells user what to do: Screen 1 link → Screen 2 link → "tell me when ready" → preview/generate.
- [x] T018 [US2] Update SKILL.md: document how AI adjusts video based on notes — "waiting" = slower, "funny" = upbeat/longer, "first time" = dramatic reveal. These are guidance patterns, not fixed rules.

---

## Phase 6: Playwright Tests + Polish

- [x] T019 Write Playwright test: navigate to `/project/{id}/timeline` → see scene cards
- [x] T020 Write Playwright test: add story to a scene → verify note indicator appears
- [x] T021 Write Playwright test: remove a scene → verify undo toast → verify scene gone
- [x] T022 Write Playwright test: summary bar shows count + duration on both screens
- [x] T023 Write Playwright test: expand scene thumbnail strip → see all items
- [x] T024 Run all Playwright tests — selection UI + timeline
- [ ] T025 Update docs per playbook (`docs/playbooks/update-docs.md`)
- [ ] T026 Commit and push

---

## Dependencies

- **Phase 1**: No dependencies — start immediately
- **Phase 2 (US1)**: Depends on Phase 1 (needs API routes)
- **Phase 3 (US3)**: Depends on Phase 2 (needs scene cards to add reorder/remove/trim)
- **Phase 4 (US4)**: Independent — can run parallel with Phase 3
- **Phase 5 (US2)**: Independent — SKILL.md update, no UI dependency
- **Phase 6**: After all phases

## MVP: Phase 1 + 2 + 5 (9 tasks)
Scene cards with stories + AI reads them. User can add stories and AI interprets.

## Implementation Strategy

**Phase 1**: Build in parallel — all 4 API routes at once. ~30 min.
**Phase 2**: The main UI work. Scene cards + story field + expand. ~2 hours.
**Phase 3**: Reorder + remove + trim. ~1.5 hours.
**Phase 4**: Summary bar on both screens. ~1 hour.
**Phase 5**: SKILL.md update. ~30 min.
**Phase 6**: Tests + docs. ~1 hour.

**Total: ~26 tasks, ~6-7 hours.**

### Phase 2 (later): Quick Preview (US5)
Not in this task list — separate implementation after Screen 2 works.
