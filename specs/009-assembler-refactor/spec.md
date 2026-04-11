# Feature Specification: Assembler Refactor

**Feature Branch**: `009-assembler-refactor`  
**Created**: 2026-04-11  
**Status**: Draft  
**Input**: IMP-012 from PRD — v2 project.json support, video clips, DNG handling, orientation, no-crop

## Clarifications

### Session 2026-04-11

- Q: How to handle mixed portrait/landscape photos? → A: AI decides based on target device/platform. If user says "for Instagram" → AI knows the format. If "for phone" → portrait. If "for YouTube" → landscape. If unclear, AI asks. No fixed rule — AI acts as experienced video editor.
- Q: What fills empty space when photo doesn't match frame exactly? → A: AI decides based on content. Black bars, blurred background, or color matching — whatever looks best for each specific photo. The AI is the video editor, not an algorithm.
- Q: How does the AI pass assembly config to the assembler script? → A: Through project.json. The AI writes assembly config (orientation, resolution, padding strategy) to the project file via a `set_assembly_config()` function. The assembler reads everything from project.json — only needs the project ID as argument. All decisions are persisted for re-generation.

## Design Philosophy

The assembler should be a tool the AI uses, not a rigid pipeline. The AI decides:
- Output orientation and resolution based on target platform
- How to handle each photo's aspect ratio (padding strategy)
- How to include video clips (full, trimmed, with audio)
- How to handle problematic formats (DNG, RAW)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — v2 Project File Support (Priority: P1)

The assembler reads from `project.json` (v2 format) directly, using the timeline with asset IDs, types, and durations. No bridge to v1 `scenario.json` needed.

**Why this priority**: Currently requires a manual hack to create v1 scenario from v2 project. This is the foundation — everything else builds on it.

**Independent Test**: Create a v2 project with timeline → run assembler → video generated without creating a v1 scenario.

**Acceptance Scenarios**:

1. **Given** a v2 project with timeline of 20 photo items, **When** the assembler runs, **Then** it reads `project.json`, downloads assets, and generates output.mp4.
2. **Given** a v2 project, **When** the assembler completes, **Then** it updates the project state to "generated."

---

### User Story 2 — DNG/RAW File Support (Priority: P1)

DNG and RAW files from iPhone are properly converted to JPEG before FFmpeg processing. No corrupt TIFF output.

**Why this priority**: 15 out of 46 Miami trip items were DNG — the assembler crashed trying to process them. This blocks a significant portion of content.

**Independent Test**: Timeline with DNG files → assembler converts them successfully → they appear in the video.

**Acceptance Scenarios**:

1. **Given** a timeline item pointing to a .DNG file, **When** the assembler processes it, **Then** it converts to JPEG using sips with explicit format options and includes it in the video.
2. **Given** a conversion fails, **When** the assembler encounters the error, **Then** it skips that item, logs a warning, and continues with remaining items.

---

### User Story 3 — Video Clip Inclusion (Priority: P1)

Video clips in the timeline are included as actual video segments — not as still images. They retain their original audio. Transitions between photos and videos are smooth.

**Why this priority**: 7 speedboat and restaurant videos were skipped entirely. Videos are critical for trip clips — the user said they expect 80% video content.

**Independent Test**: Timeline with mixed photos and videos → output seamlessly interleaves both with crossfade transitions.

**Acceptance Scenarios**:

1. **Given** a VIDEO timeline item with duration 15s, **When** the assembler processes it, **Then** it downloads the original video, includes 15 seconds of it with original audio.
2. **Given** a VIDEO item with trim_start=5 and trim_end=10, **When** processed, **Then** only seconds 5-10 are included.
3. **Given** a sequence [PHOTO, VIDEO, PHOTO], **When** assembled, **Then** crossfade transitions connect all three smoothly.
4. **Given** a video with audio followed by a photo (no audio), **When** assembled, **Then** the audio fades out during the transition.

---

### User Story 4 — Smart Orientation & No-Crop Display (Priority: P2)

The AI determines the output video orientation and resolution based on the target platform and content. Photos are NEVER cropped — the full original content is always visible.

**Why this priority**: The Miami trip video showed tiny cropped photos in a landscape frame because most photos were portrait. The video was technically 1920×1080 but looked terrible.

**Independent Test**: Mostly portrait photos → AI selects portrait output → photos fill the frame without cropping.

**Acceptance Scenarios**:

1. **Given** the user says "make a clip for my phone", **When** the AI configures the assembler, **Then** it outputs portrait video (1080×1920).
2. **Given** the user says "for YouTube", **When** configured, **Then** it outputs landscape (1920×1080).
3. **Given** the user says "for Instagram Reels", **When** configured, **Then** it outputs 9:16 (1080×1920).
4. **Given** a portrait photo in a portrait video with slightly different aspect ratio, **When** processed, **Then** the photo is NOT cropped. The AI decides what fills the small gaps (black, blur, color) based on the photo content.
5. **Given** the user doesn't specify a platform, **When** the AI decides, **Then** it analyzes the dominant orientation of timeline photos and selects accordingly, or asks the user.

---

### Edge Cases

- What if a DNG conversion produces a 0-byte file? Skip the item, log warning, continue.
- What if a video clip is corrupted or can't be downloaded? Skip, log, continue. Never crash the whole assembly.
- What if the timeline has only 1 item? Generate a single-item video (no transitions needed).
- What if all items are videos? The assembler should handle an all-video timeline.
- What if the target platform changes mid-conversation? The AI re-configures and re-generates.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Assembler MUST read from `project.json` (v2 format). The `manage_scenario.py` dependency is removed.
- **FR-002**: Assembler MUST handle DNG/RAW files — convert via sips with `-s format JPEG -s formatOptions 100` explicitly. If sips fails, try ImageMagick (`convert`) as fallback.
- **FR-003**: Assembler MUST handle VIDEO timeline items — download original, apply trim_start/trim_end via FFmpeg `-ss`/`-to`, preserve original audio.
- **FR-004**: Assembler MUST handle photo-to-video and video-to-photo transitions using crossfade. Audio fades during transitions.
- **FR-005**: The AI determines output orientation and resolution based on target platform. No hardcoded 1920×1080 default.
- **FR-006**: Photos MUST NOT be cropped. Full original content always visible. The AI decides the padding/background strategy per photo.
- **FR-007**: Assembler MUST be resilient — skip items that fail to download or convert, log warnings, continue with remaining items. Never crash on a single bad item.
- **FR-008**: The `build_filter_complex()` function MUST accept `input_types` parameter (already partially implemented) to apply correct processing per item type.

### Key Entities

- **Assembly Config**: Target platform, orientation, resolution, CRF, fps — determined by the AI per request and passed to the assembler.
- **Timeline Item**: From project.json — asset_id, type (IMAGE/VIDEO), duration, trim_start, trim_end, transition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A 46-item timeline with mixed HEIC, DNG, and video files generates successfully without errors.
- **SC-002**: Video clips in the output play with original audio and smooth transitions to/from photos.
- **SC-003**: Portrait photos in a portrait video fill most of the frame — no more tiny photos with huge black bars.
- **SC-004**: Assembly completes within 5 minutes for a 50-item timeline.

## Assumptions

- FFmpeg 8+ on Mac Mini supports all needed filter operations (xfade, trim, audio mixing).
- sips can convert DNG to JPEG reliably with explicit format options.
- The AI skill (SKILL.md) is updated to pass orientation/resolution config to the assembler.
- TDD applies for the assembler code (unlike 008-intelligent-search, this is actual Python code, not AI reasoning).
- The v1 `manage_scenario.py` can be deprecated after this refactor. Existing v1 scenarios are not migrated.
