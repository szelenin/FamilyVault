# Implementation Plan: Clip Editing — Preview, Trim, Deselect

**Branch**: `012-clip-editing` | **Date**: 2026-04-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-clip-editing/spec.md`

## Summary

Add item-level interactions to Screen 2's expanded scene view: full-screen preview (photos + video playback), individual item deselect with X button + undo, and video trim controls with start/end markers. All backend APIs already exist — this is purely UI work on the timeline page.

## Technical Context

**Language/Version**: TypeScript, SvelteKit (existing app at `setup/selection-ui/`)
**Primary Dependencies**: Existing SvelteKit app + Immich API proxy + project.json APIs
**Storage**: project.json — uses existing `deselected_ids` array and `video_trims` dict
**Testing**: Playwright E2E
**Target Platform**: Mobile-first, responsive
**Project Type**: Enhancement to existing route (`/project/[id]/timeline`)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First | WAIVED | Per tasks.md: "Not strict TDD for UI." Playwright E2E tests cover workflows. |
| II. Three-Layer Testing | PARTIAL | E2E tests (big). Unit tests for project.ts exist from 011. No new backend logic. |
| III. AI-Interaction First | PASS | Deselect/trim update project.json which AI reads. No AI-only path needed — these are visual editing tools. |
| IV. Simplicity / YAGNI | PASS | Reuses Screen 1 pattern inline. No shared component abstraction (only 2 pages use it). |
| V. Privacy / Local-First | PASS | All local, photos served via local Immich proxy. |

## Design Decision: Inline vs Shared Component

Screen 1's detail view is 200 lines inline in `+page.svelte`. Extracting a shared component would require:
- Prop-drilling for scene data, selection state, navigation callbacks
- Different behavior in each context (Screen 1 has favorites, Screen 2 has trim)
- Only 2 consumers

**Decision**: Replicate the pattern inline in Screen 2's `+page.svelte`. Simpler, no abstraction overhead, each page owns its behavior. If a third consumer appears, extract then.

## Project Structure

```text
setup/selection-ui/src/routes/
├── project/[id]/
│   └── timeline/
│       ├── +page.svelte          # MODIFY: add detail overlay, deselect X, trim controls
│       └── +page.server.ts       # MODIFY: load item types (IMAGE/VIDEO) + video durations

setup/selection-ui/tests/e2e/
└── timeline.test.ts              # MODIFY: add preview, deselect, trim tests
```

No new files. No new API routes. No new lib functions.

## Implementation Steps

### Step 1: Server — load item types and durations

Modify `+page.server.ts` to fetch asset details (type, duration) for each selected item per scene. Currently only passes `selectedIds` (string array). Change to pass objects with `{ asset_id, type, duration }` so the client knows which items are videos.

Use Immich API: `GET /api/assets/{assetId}` via the existing `getAssetDetail()` from `$lib/immich.ts`.

**Optimization**: Fetching detail for every asset is slow (N API calls). Instead, batch by checking if the asset_id appears in the scene's `asset_ids` from discovery, which already has type info. The discovery scene data includes `photo_count` and `video_count` but not per-item types. Two options:
- (A) Fetch detail for all items on page load (slow for 100+ items)
- (B) Fetch detail lazily when a scene is expanded

**Choose (B)**: Add a client-side fetch when expanding a scene. The collapsed view doesn't need types.

### Step 2: Expanded grid — make thumbnails tappable + add X button

In the expanded scene view, change each thumbnail from a plain `<img>` to a container with:
- Tap on image → open detail overlay (like Screen 1)
- X button overlay in corner → deselect item

Pattern from Screen 1's grid (scene/[sceneId]/+page.svelte lines 120-150):
- Thumbnail with overlay controls
- X button: `position: absolute; top: 2px; right: 2px`
- Video badge: show ▶ + duration on video thumbnails

### Step 3: Detail overlay — full-screen preview

Add the detail overlay to `+page.svelte` (same pattern as Screen 1 lines 155-201):
- State: `detailItem`, `detailIndex`, `detailSceneId`
- Fixed overlay: `fixed inset-0 bg-black z-50`
- Top bar: close button, item counter, deselect button
- Media: photo `<img>` or video `<video>` with controls
- Bottom bar: prev/next navigation
- Keyboard: Escape=close, Left/Right=navigate, Space=deselect

### Step 4: Deselect with undo

When user taps X (grid) or deselect (detail):
1. Remove item from `scene.selectedIds` array (reactive update)
2. Show brief undo toast (3 seconds, same pattern as scene remove)
3. After timeout, persist to API: fetch current project, merge deselected_ids, POST
4. If all items removed from scene, scene disappears from timeline
5. Update item count and duration in scene card + summary bar

### Step 5: Video trim controls (US3, P2)

In the detail overlay, when viewing a video:
- Add "Trim" button in the bottom bar
- Tapping it reveals start/end range inputs below the video
- Two `<input type="range">` sliders: start (min=0, max=duration) and end (min=start, max=duration)
- Display formatted times: "0:05 — 0:12"
- Preview: when trimming, `video.currentTime = start` and loop between start/end
- Save button: POST to `/api/project/{id}/trim` with `{ asset_id, start, end }`
- Load existing trims from project.json on page load (pass through server data)

### Step 6: Trim badge on thumbnails

In the expanded grid, videos with trim settings show a small badge:
- "0:05-0:12" or "trimmed" indicator
- Duration estimate uses trimmed duration instead of full video duration

### Step 7: Playwright E2E tests

Add tests to `timeline.test.ts`:
- Expand scene → tap thumbnail → detail overlay opens
- Detail: close button returns to timeline
- Detail: prev/next navigation works
- Detail: video plays (video element exists)
- Expanded grid: X button deselects item → count updates
- Detail: deselect button works → item removed
- Video trim: set start/end → verify saved (check via API)
- Trim badge visible on trimmed video

### Phase 2 (if needed): Lazy loading optimization
If fetching asset details on expand is too slow, add a loading skeleton and fetch in batches.

## MVP: Steps 1-4 + 7 (preview + deselect + tests)

Preview and deselect are P1. Video trim (Steps 5-6) is P2 and can ship separately.
