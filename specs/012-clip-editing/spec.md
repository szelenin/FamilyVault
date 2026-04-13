# Feature Specification: Clip Editing — Preview, Trim, Deselect in Timeline

**Feature Branch**: `012-clip-editing`  
**Created**: 2026-04-12  
**Status**: Draft  
**Input**: Screen 2 clip editing — preview photos/videos, trim videos, deselect individual items from expanded scene view.

## Context

Screen 2 (Timeline Review at `/project/{id}/timeline`) shows scenes as cards with expandable thumbnail strips. Currently the expanded view is read-only — users can see thumbnails but cannot interact with individual items. To complete the clip editing experience before AI generates the video, users need to: preview items full-screen, trim video clips, and remove (deselect) individual photos/videos they don't want.

These features exist on Screen 1's scene grid view (`/project/{id}/scene/{sceneId}`) — full-screen preview with prev/next, video playback, and select/deselect. This spec brings equivalent interactions into Screen 2's expanded scene view, plus adds video trim controls.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Item Preview (Priority: P1)

When reviewing a scene on Screen 2, the user taps a photo or video thumbnail to see it full-screen. Photos show large with close button. Videos play inline. This lets the user judge content quality before the AI generates the clip.

**Why this priority**: Without preview, users can't tell if a tiny thumbnail is worth keeping. This is the most basic interaction expected when browsing photos.

**Independent Test**: Open Screen 2 → expand a scene → tap a photo thumbnail → see full-screen preview with close button. Tap a video → see video playback.

**Acceptance Scenarios**:

1. **Given** an expanded scene on Screen 2, **When** the user taps a photo thumbnail, **Then** a full-screen preview opens showing the photo large, with a close button to return.
2. **Given** the full-screen preview, **When** the user taps close (or swipes down), **Then** they return to the expanded scene view.
3. **Given** an expanded scene with a video thumbnail, **When** the user taps it, **Then** the video plays with standard playback controls (play/pause, seek).
4. **Given** the full-screen preview showing multiple items, **When** the user swipes left/right (or taps next/prev), **Then** they navigate between items in the scene.

---

### User Story 2 — Item Deselect (Priority: P1)

From the expanded scene view or the full-screen preview, the user can deselect individual items. A deselected item is removed from the scene (added to `deselected_ids` in project.json). This gives fine-grained control beyond the scene-level remove.

**Why this priority**: Users often want to keep a scene but remove a few bad photos. Scene-level remove is too coarse — individual deselect is essential for clip quality.

**Independent Test**: Open Screen 2 → expand a scene → deselect a photo → verify it disappears from the scene and the item count decreases.

**Acceptance Scenarios**:

1. **Given** an expanded scene showing all items, **When** the user taps a deselect control on an item, **Then** the item is removed from the scene view and added to `deselected_ids`.
2. **Given** a deselected item, **When** the scene re-renders, **Then** the item count and estimated duration update.
3. **Given** the full-screen preview, **When** the user taps a deselect button, **Then** the current item is deselected and the preview advances to the next item.
4. **Given** a scene where all items are deselected, **When** the last item is removed, **Then** the scene disappears from the timeline (same as scene-level remove).

---

### User Story 3 — Video Trim (Priority: P2)

When previewing a video, the user can set start and end trim points. The AI uses only the trimmed segment when generating the clip. Trim settings are saved per video in project.json.

**Why this priority**: Trim is important for video quality but more complex to implement. Users can alternatively write trim instructions in the story field ("only use first 5 seconds") which the AI interprets. The visual trim control is a precision tool.

**Independent Test**: Open Screen 2 → expand a scene → tap a video → set start time to 0:05 and end time to 0:12 → verify trim saved in project.json.

**Acceptance Scenarios**:

1. **Given** a video playing in full-screen preview, **When** the user activates trim mode, **Then** start and end markers appear on the video timeline/scrubber.
2. **Given** trim markers, **When** the user drags start to 0:05 and end to 0:12, **Then** the trimmed segment is highlighted and only that portion plays on loop.
3. **Given** trim settings, **When** the user confirms, **Then** trim start/end are saved to project.json via the existing trim API.
4. **Given** a trimmed video in the scene, **When** the scene card renders, **Then** the video thumbnail shows a trim badge (e.g., "0:05-0:12") and the duration estimate reflects the trimmed length.

---

### Edge Cases

- What if a scene has only 1 item and the user deselects it? The scene disappears from the timeline.
- What if the user trims a video to 0 seconds (start = end)? Reject — enforce minimum 1 second.
- What if the user taps a DNG/RAW photo? Show the JPEG proxy (same as Immich thumbnail, already converted server-side).
- What if video playback fails (corrupt file, unsupported codec)? Show error state with option to deselect the item.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Tapping a thumbnail in the expanded scene view opens a full-screen preview overlay.
- **FR-002**: Full-screen preview shows photos at full resolution via the existing Immich thumbnail proxy.
- **FR-003**: Full-screen preview plays videos via the existing streaming video proxy with standard controls.
- **FR-004**: Navigation between items in the full-screen preview (swipe or next/prev buttons).
- **FR-005**: Deselect control visible on each item in expanded scene view (toggle or X button).
- **FR-006**: Deselect control available in full-screen preview.
- **FR-007**: Deselecting an item calls the existing select API, updates `deselected_ids`, and removes the item from the scene view.
- **FR-008**: Video trim mode with draggable start/end markers on the video scrubber.
- **FR-009**: Trim settings saved via the existing `/api/project/[id]/trim` endpoint.
- **FR-010**: Trimmed videos show a badge on their thumbnail in the scene view.
- **FR-011**: Duration estimate in scene card and summary bar accounts for trim settings.
- **FR-012**: Works on mobile (touch-friendly, responsive).

### Key Entities

- **Item Preview**: Full-screen overlay showing a single photo or video from a scene. Navigable within the scene's items.
- **Video Trim**: Start and end time in seconds, per asset_id. Stored in project.json `video_trims` dict. Existing API at `/api/project/[id]/trim`.
- **Deselected Item**: An asset_id added to `deselected_ids` array in project.json. Existing API at `/api/project/[id]/select`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: User can preview any photo or video in under 2 seconds from tap to full-screen display.
- **SC-002**: User can deselect 5 unwanted items from a scene in under 30 seconds.
- **SC-003**: User can set video trim points and confirm in under 15 seconds.
- **SC-004**: All interactions work on mobile with touch (no hover-dependent UI).

## Assumptions

- The existing Immich thumbnail proxy (`/api/thumbnail/[assetId]`) and video streaming proxy (`/api/video/[assetId]`) are reused — no new backend for media serving.
- The existing select API (`/api/project/[id]/select`) and trim API (`/api/project/[id]/trim`) are reused — no new backend endpoints needed.
- Screen 1's detail view (`/project/{id}/scene/{sceneId}` with full-screen preview, video playback, prev/next) provides the UI pattern to follow. The implementation can share components or replicate the pattern.
- Video trim UI uses HTML5 `<video>` element and custom range inputs — no external video player library needed.
- Playwright E2E tests validate the workflow. Not strict TDD for UI components.
