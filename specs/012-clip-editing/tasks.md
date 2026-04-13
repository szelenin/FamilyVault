# Tasks: Clip Editing — Preview, Trim, Deselect

**Input**: Design documents from `/specs/012-clip-editing/`
**Prerequisites**: plan.md, spec.md

**Tests**: Playwright E2E. Not strict TDD for UI components.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Data Layer

**Purpose**: Load item types and durations so the client knows which items are videos.

- [x] T001 [P] Add client-side `fetchSceneDetails(sceneId, assetIds)` function in `+page.svelte` — calls `/api/thumbnail/{assetId}?size=preview` to warm cache, and fetches asset type/duration via a new lightweight API endpoint or inline Immich proxy
- [x] T002 [P] Create `/api/asset/[assetId]/info/+server.ts` — returns `{ type, duration }` from Immich `GET /api/assets/{assetId}` (reuses `getAssetDetail` from `$lib/immich.ts`)

---

## Phase 2: US1 — Item Preview (P1)

**Goal**: Tap thumbnail in expanded scene → full-screen preview with photo/video.

- [x] T003 [US1] Add detail overlay state to `+page.svelte`: `detailItem`, `detailIndex`, `detailSceneId`, `sceneItems` (array of `{asset_id, type, duration}`)
- [x] T004 [US1] Fetch asset details when scene expands — call info API for each `selectedId`, store in `sceneItems` map keyed by scene id
- [x] T005 [US1] Make expanded thumbnails tappable — tap opens detail overlay at that index. Show video badge (▶ + duration) on video thumbnails.
- [x] T006 [US1] Build detail overlay: fixed fullscreen, top bar (close + counter), media area (photo `<img>` or video `<video>` with controls), bottom bar (prev/next)
- [x] T007 [US1] Add keyboard navigation: Escape=close, ArrowLeft=prev, ArrowRight=next

**Checkpoint**: User expands scene, taps photo → full-screen preview. Taps video → plays. Prev/next works.

---

## Phase 3: US2 — Item Deselect (P1)

**Goal**: X button on thumbnails and deselect in preview, with undo.

- [x] T008 [US2] Add X button overlay on each thumbnail in expanded grid — positioned top-right, tap triggers deselect
- [x] T009 [US2] Implement deselect logic: remove item from `scene.selectedIds`, update counts/duration, show undo toast (3s)
- [x] T010 [US2] Persist deselect after undo timeout: fetch project, merge `deselected_ids`, POST to `/api/project/{id}/select`
- [x] T011 [US2] Add deselect button in detail overlay top bar — deselects current item, advances to next (or closes if last)
- [x] T012 [US2] Handle empty scene: when all items deselected, remove scene from timeline

**Checkpoint**: User taps X on thumbnail → item gone, count updates, undo available. Same from detail view.

---

## Phase 4: US3 — Video Trim (P2)

**Goal**: Set start/end trim points on videos in the detail overlay.

- [x] T013 [US3] Add "Trim" button in detail overlay bottom bar — visible only for video items
- [x] T014 [US3] Build trim UI: two range sliders (start/end) below video, time display ("0:05 — 0:12"), preview loops trimmed segment
- [x] T015 [US3] Save trim: POST to `/api/project/{id}/trim` with `{asset_id, start, end}`. Load existing trims on page load.
- [x] T016 [US3] Show trim badge on video thumbnails in expanded grid ("0:05-0:12")
- [ ] T017 [US3] Duration estimate accounts for trimmed videos (use trim duration instead of default 8s)

---

## Phase 5: Playwright Tests + Polish

- [x] T018 Write Playwright test: expand scene → tap thumbnail → detail overlay opens
- [x] T019 Write Playwright test: detail overlay close button returns to timeline
- [x] T020 Write Playwright test: detail overlay prev/next navigation
- [x] T021 Write Playwright test: X button on thumbnail deselects item → count decreases
- [x] T022 Write Playwright test: deselect from detail view → item removed
- [ ] T023 Write Playwright test: video trim — set start/end → verify via API
- [x] T024 Run all Playwright tests — selection UI + timeline + clip editing
- [ ] T025 Commit and push

---

## Dependencies

- **Phase 1**: No dependencies — start immediately
- **Phase 2 (US1)**: Depends on Phase 1 (needs asset type/duration data)
- **Phase 3 (US2)**: Depends on Phase 2 (needs expanded grid + detail overlay)
- **Phase 4 (US3)**: Depends on Phase 2 (needs detail overlay for trim UI)
- **Phase 5**: After all phases

## MVP: Phase 1 + 2 + 3 + 5 (18 tasks)
Preview items and deselect unwanted ones. User can fine-tune scenes before AI generates.

## Implementation Strategy

**Phase 1**: Asset info endpoint + client fetch. ~30 min.
**Phase 2**: Detail overlay (replicate Screen 1 pattern). ~1.5 hours.
**Phase 3**: Deselect with X button + undo. ~1 hour.
**Phase 4**: Video trim UI. ~1.5 hours.
**Phase 5**: Tests. ~1 hour.

**Total: ~25 tasks, ~5-6 hours.**
