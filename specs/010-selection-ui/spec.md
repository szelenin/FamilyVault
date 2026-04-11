# Feature Specification: Scene-Based Selection UI

**Feature Branch**: `010-selection-ui`  
**Created**: 2026-04-11  
**Status**: Draft  
**Input**: IMP-007 from PRD — Timeline Editing UX. Custom web app for scene-based photo/video selection.

## Context

The AI creates scenes and presents them to the user via text. The user needs to browse actual photos/videos, select/deselect items within each scene, and confirm the selection — all from their phone or desktop. Claude's text interface can't do this well. Immich's native album UI works but isn't designed for scene-based curation.

**Solution**: A lightweight SvelteKit PWA hosted on the Mac Mini that talks to Immich API and reads/writes project.json. The user gets a link from Claude, opens it, curates their scenes, and tells Claude "done."

## Architecture

```
User's phone/browser
    ↓
http://macmini:3000/project/PROJECT_ID
    ↓
SvelteKit PWA (our app)
    ├── reads Immich API (thumbnails, asset details)
    ├── reads/writes project.json (scene data, selections)
    └── served from Mac Mini (dev: node, prod: Docker)
```

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Browse Scenes and Select Content (Priority: P1)

The user receives a link from Claude (e.g., `http://macmini:3000/project/2026-04-11-miami-trip`). They open it on their phone. They see all scenes listed with thumbnails, tap into a scene, see all photos/videos, and tap to select/deselect items. When done, they tell Claude "selection is ready."

**Why this priority**: This is the core UX problem — the user can't easily communicate photo selections to Claude. Everything else builds on this.

**Independent Test**: Open the link on a phone → see scenes → tap into a scene → deselect 3 photos → go back → see updated count → tell Claude "done" → Claude reads the updated selection.

**Acceptance Scenarios**:

1. **Given** a project with 11 scenes, **When** the user opens the project URL on their phone, **Then** they see a list of all scenes with: label, date/time, thumbnail of the first photo, photo count, video count, and a selected/total indicator.

2. **Given** the user taps on a scene, **When** the scene view opens, **Then** they see a grid of all photos/videos in that scene as thumbnails. Each item shows a selection checkbox. All items are selected by default.

3. **Given** the user taps a photo thumbnail, **When** it toggles, **Then** the item is visually marked as deselected (dimmed/crossed out) and the scene's selected count updates.

4. **Given** the user has deselected 5 photos in a scene, **When** they go back to the scene list, **Then** the scene shows "12/17 selected" (not "17 items").

5. **Given** the user is done selecting, **When** Claude reads the project, **Then** it sees which items are selected/deselected and builds the timeline from only selected items.

---

### User Story 2 — Quick Actions (Priority: P2)

The user can perform batch operations within a scene: select all, deselect all, select only photos, select only videos.

**Why this priority**: A scene like Vizcaya has 194 items — tapping each one individually is tedious. Batch operations make this manageable.

**Independent Test**: Open a 194-item scene → tap "Deselect All" → tap specific 20 photos to select → go back → scene shows "20/194 selected."

**Acceptance Scenarios**:

1. **Given** a scene with 50 items, **When** the user taps "Deselect All", **Then** all items become deselected and the count shows "0/50 selected."
2. **Given** all items deselected, **When** the user taps specific photos, **Then** only those become selected.
3. **Given** a scene with mixed photos and videos, **When** the user taps "Videos Only", **Then** only videos are selected, photos are deselected.

---

### User Story 3 — Photo Detail View (Priority: P2)

The user can tap a photo to see it full-screen (loaded from Immich). This helps them decide whether to keep or remove it.

**Why this priority**: Thumbnails may not show enough detail to decide. The user needs to zoom in to check if a photo is blurry, a duplicate, or worth keeping.

**Acceptance Scenarios**:

1. **Given** the user taps a thumbnail, **When** the detail view opens, **Then** they see the full-resolution photo from Immich with a select/deselect toggle.
2. **Given** the user swipes left/right in detail view, **When** navigating, **Then** they move to the next/previous photo in the scene.

---

### User Story 4 — Scene Management (Priority: P3)

The user can include/exclude entire scenes from the scene list view, and reorder scenes.

**Why this priority**: The user might decide to skip an entire scene ("skip the airport photos"). This is faster than deselecting items one by one.

**Acceptance Scenarios**:

1. **Given** the scene list, **When** the user swipes a scene or taps an exclude button, **Then** the entire scene is marked as excluded and visually dimmed.
2. **Given** an excluded scene, **When** the user taps it again, **Then** it's re-included.

---

### Edge Cases

- What if the project has no scenes yet? Show "No scenes discovered. Ask Claude to search for content."
- What if Immich is unreachable? Show cached thumbnails if available, or "Cannot connect to photo server."
- What if the user opens an old/invalid project URL? Show "Project not found."
- What if 2 people open the same project URL? Last write wins — no concurrent editing protection needed for a solo user.
- What if a scene has 500+ items? Paginate or virtual scroll — don't load all thumbnails at once.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST display all scenes from a project's discovery/timeline data, showing scene label, date/time, thumbnail, and item counts.
- **FR-002**: The app MUST display a grid of photo/video thumbnails within each scene, loaded from Immich's thumbnail API.
- **FR-003**: Each item MUST have a select/deselect toggle. All items selected by default.
- **FR-004**: Selection state MUST be persisted to project.json so Claude can read it.
- **FR-005**: The app MUST support batch operations: select all, deselect all, select photos only, select videos only.
- **FR-006**: The app MUST work on mobile (responsive design, touch-friendly).
- **FR-007**: The app MUST be a PWA (manifest + service worker) so it can be added to the home screen.
- **FR-008**: The app MUST authenticate with Immich using the same API key (no separate login).
- **FR-009**: The app MUST support full-screen photo viewing via Immich's preview API.
- **FR-010**: The app MUST show selection counts per scene and total.
- **FR-011**: The app MUST handle large scenes (100+ items) without performance issues — use virtual scrolling or pagination.

### Key Entities

- **Project View**: The main page showing all scenes for a project. URL: `/project/{project-id}`
- **Scene View**: Grid of thumbnails for one scene. URL: `/project/{project-id}/scene/{scene-id}`
- **Selection State**: Per-item selected/deselected status, stored in project.json alongside the timeline.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: User can browse and select photos for a 46-item, 11-scene project in under 3 minutes on a phone.
- **SC-002**: The selection UI loads within 2 seconds on mobile (scene list with thumbnails).
- **SC-003**: Thumbnail grid scrolls smoothly for scenes with 200+ items.
- **SC-004**: Claude correctly reads the selection state and uses only selected items for the timeline.

## Assumptions

- SvelteKit + @immich/ui + @vite-pwa is the tech stack (per research).
- The app runs on the Mac Mini alongside Immich, accessible at `http://macmini:3000`.
- Immich API key is stored in `/Volumes/HomeRAID/immich/api-key.txt` (same as story engine).
- Project.json is the shared state between the selection UI and Claude.
- Development starts directly on Mac Mini (node), Dockerized later when stable.
- The user has the Immich mobile app installed but the selection UI is a separate web app.
