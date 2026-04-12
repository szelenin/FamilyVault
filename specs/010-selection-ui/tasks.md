# Tasks: Scene-Based Selection UI

**Input**: Design documents from `/specs/010-selection-ui/`
**Prerequisites**: plan.md, spec.md

**Tests**: E2E browser tests primary. Not strict TDD for UI components.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Install Node.js on Mac Mini: `brew install node`
- [X] T002 Scaffold SvelteKit project in `setup/selection-ui/`: `npx sv create` with TypeScript, Tailwind CSS
- [X] T003 Install dependencies: `@vite-pwa/sveltekit`, Tailwind CSS
- [X] T004 Configure vite.config.ts with PWA plugin
- [X] T005 Verify dev server runs: `npm run dev` accessible at `http://macmini:3000`

---

## Phase 2: Server-Side API Routes

- [X] T006 [P] Create `src/lib/immich.ts` — Immich API client: thumbnail proxy, asset detail, favorite toggle. Reads API key from filesystem.
- [X] T007 [P] Create `src/lib/project.ts` — project.json read/write: load project, get scenes, get selection state, update deselected_ids.
- [X] T008 Create `src/routes/api/thumbnail/[assetId]/+server.ts` — proxy Immich thumbnail (avoids CORS)
- [X] T009 Create `src/routes/api/project/[id]/+server.ts` — read project.json, return scenes + selection
- [X] T010 Create `src/routes/api/project/[id]/select/+server.ts` — POST to update deselected_ids in project.json
- [X] T011 Create `src/routes/api/favorite/[assetId]/+server.ts` — PUT to toggle isFavorite via Immich API

---

## Phase 3: US1 — Scene List + Thumbnail Grid (MVP)

- [X] T012 [US1] Create `src/routes/project/[id]/+page.server.ts` — load project scenes with counts
- [X] T013 [US1] Create `src/routes/project/[id]/+page.svelte` — scene list: label, date, thumbnail, photo/video counts, selected/total indicator, include/exclude toggle
- [X] T014 [US1] Create `src/routes/project/[id]/scene/[sceneId]/+page.server.ts` — load scene assets
- [X] T015 [US1] Create `src/routes/project/[id]/scene/[sceneId]/+page.svelte` — thumbnail grid: tap to select/deselect, play icon on videos, duration badge, favorite heart, dimming for deselected
- [X] T016 [US1] Wire selection state: tapping a thumbnail calls `/api/project/[id]/select` to update deselected_ids
- [X] T017 [US1] Add selected count display per scene and total at top

**Checkpoint**: User can open link on phone, browse scenes, tap to select/deselect, selections persist.

---

## Phase 4: US2 + US4 — Batch Operations + Scene Management

- [X] T018 [US2] Add batch action bar to scene grid: "Select All", "Deselect All", "Photos Only", "Videos Only"
- [X] T019 [US4] Add include/exclude toggle on scene list — tapping dims the scene and deselects all its items
- [X] T020 Mobile polish: touch-friendly tap targets (min 44px), responsive grid (3 columns on phone, 5 on desktop)

---

## Phase 5: US3 — Photo Detail View

- [X] T021 [US3] Create detail view overlay: full-screen photo from Immich preview API
- [X] T022 [US3] Add swipe left/right navigation between photos in the scene
- [X] T023 [US3] Add select/deselect and favorite toggles in detail view

---

## Phase 6: US5 — Favorites

- [X] T024 [US5] Show Immich favorite indicator (heart icon) on thumbnails
- [X] T025 [US5] Tap heart to toggle favorite — calls Immich API

---

## Phase 7: PWA + Polish

- [X] T026 Create PWA manifest.json with app name, icons, theme color
- [X] T027 Add service worker for asset caching (thumbnails)
- [X] T028 Update SKILL.md: Claude gives selection UI link after scene discovery
- [X] T029 E2E test: open Miami trip project URL on phone → browse → select → verify project.json updated
- [X] T030 Commit and push

---

## Dependencies

- Phase 1: No dependencies
- Phase 2: Depends on Phase 1
- Phase 3: Depends on Phase 2 (needs API routes)
- Phase 4-6: Depend on Phase 3 (need the base grid)
- Phase 7: After all features work

## MVP: Phase 1 + 2 + 3 (17 tasks)
User can browse scenes and select/deselect. Everything else is polish.
