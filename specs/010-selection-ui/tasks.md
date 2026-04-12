# Tasks: Scene-Based Selection UI

**Input**: Design documents from `/specs/010-selection-ui/`
**Prerequisites**: plan.md, spec.md

**Tests**: E2E browser tests primary. Not strict TDD for UI components.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Install Node.js on Mac Mini: `brew install node`
- [ ] T002 Scaffold SvelteKit project in `setup/selection-ui/`: `npx sv create` with TypeScript, Tailwind CSS
- [ ] T003 Install dependencies: `@vite-pwa/sveltekit`, Tailwind CSS
- [ ] T004 Configure vite.config.ts with PWA plugin
- [ ] T005 Verify dev server runs: `npm run dev` accessible at `http://macmini:3000`

---

## Phase 2: Server-Side API Routes

- [ ] T006 [P] Create `src/lib/immich.ts` — Immich API client: thumbnail proxy, asset detail, favorite toggle. Reads API key from filesystem.
- [ ] T007 [P] Create `src/lib/project.ts` — project.json read/write: load project, get scenes, get selection state, update deselected_ids.
- [ ] T008 Create `src/routes/api/thumbnail/[assetId]/+server.ts` — proxy Immich thumbnail (avoids CORS)
- [ ] T009 Create `src/routes/api/project/[id]/+server.ts` — read project.json, return scenes + selection
- [ ] T010 Create `src/routes/api/project/[id]/select/+server.ts` — POST to update deselected_ids in project.json
- [ ] T011 Create `src/routes/api/favorite/[assetId]/+server.ts` — PUT to toggle isFavorite via Immich API

---

## Phase 3: US1 — Scene List + Thumbnail Grid (MVP)

- [ ] T012 [US1] Create `src/routes/project/[id]/+page.server.ts` — load project scenes with counts
- [ ] T013 [US1] Create `src/routes/project/[id]/+page.svelte` — scene list: label, date, thumbnail, photo/video counts, selected/total indicator, include/exclude toggle
- [ ] T014 [US1] Create `src/routes/project/[id]/scene/[sceneId]/+page.server.ts` — load scene assets
- [ ] T015 [US1] Create `src/routes/project/[id]/scene/[sceneId]/+page.svelte` — thumbnail grid: tap to select/deselect, play icon on videos, duration badge, favorite heart, dimming for deselected
- [ ] T016 [US1] Wire selection state: tapping a thumbnail calls `/api/project/[id]/select` to update deselected_ids
- [ ] T017 [US1] Add selected count display per scene and total at top

**Checkpoint**: User can open link on phone, browse scenes, tap to select/deselect, selections persist.

---

## Phase 4: US2 + US4 — Batch Operations + Scene Management

- [ ] T018 [US2] Add batch action bar to scene grid: "Select All", "Deselect All", "Photos Only", "Videos Only"
- [ ] T019 [US4] Add include/exclude toggle on scene list — tapping dims the scene and deselects all its items
- [ ] T020 Mobile polish: touch-friendly tap targets (min 44px), responsive grid (3 columns on phone, 5 on desktop)

---

## Phase 5: US3 — Photo Detail View

- [ ] T021 [US3] Create detail view overlay: full-screen photo from Immich preview API
- [ ] T022 [US3] Add swipe left/right navigation between photos in the scene
- [ ] T023 [US3] Add select/deselect and favorite toggles in detail view

---

## Phase 6: US5 — Favorites

- [ ] T024 [US5] Show Immich favorite indicator (heart icon) on thumbnails
- [ ] T025 [US5] Tap heart to toggle favorite — calls Immich API

---

## Phase 7: PWA + Polish

- [ ] T026 Create PWA manifest.json with app name, icons, theme color
- [ ] T027 Add service worker for asset caching (thumbnails)
- [ ] T028 Update SKILL.md: Claude gives selection UI link after scene discovery
- [ ] T029 E2E test: open Miami trip project URL on phone → browse → select → verify project.json updated
- [ ] T030 Commit and push

---

## Dependencies

- Phase 1: No dependencies
- Phase 2: Depends on Phase 1
- Phase 3: Depends on Phase 2 (needs API routes)
- Phase 4-6: Depend on Phase 3 (need the base grid)
- Phase 7: After all features work

## MVP: Phase 1 + 2 + 3 (17 tasks)
User can browse scenes and select/deselect. Everything else is polish.
