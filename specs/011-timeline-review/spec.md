# Feature Specification: Timeline Review Screen (Screen 2)

**Feature Branch**: `011-timeline-review`  
**Created**: 2026-04-12  
**Status**: Draft  
**Input**: IMP-013 from PRD — review selected items, add notes, AI interprets for storytelling.

## Clarifications

### Session 2026-04-12

- Q: How does "Generate Now" communicate with Claude? → A: Per core philosophy (CLAUDE.md): UI is a tool, AI is the orchestrator, project.json is shared state. The button writes state to project.json. The user returns to the AI conversation. The AI reads project.json and proceeds. No direct API call or webhook needed.
- Q: Do we need Web Speech API for voice notes? → A: No. A text field is enough — mobile keyboards (iOS/Android) have built-in mic button for speech-to-text. No custom voice recording needed. FR-005 removed.

## Context

After the user selects photos/videos in Screen 1, they need a way to add stories and context to their moments. Traditional editors (Premiere, CapCut) show individual items on a timeline — too complex for regular users. We do the opposite: the user tells STORIES about MOMENTS, the AI translates that into individual photo durations, transitions, and effects.

**Screen 2 shows scenes/moments, not individual photos.** The user adds a story to "the speedboat moment" — not to "photo #17." The AI decides which photos, how long, what transitions.

**After annotation, the AI generates a quick 480p preview.** The user watches and gives feedback in conversation. The AI adjusts and generates the final HD version.

**This is a new page in the existing Selection UI** (SvelteKit app at `http://macmini:3000`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Scene-Level Storytelling (Priority: P1)

Screen 2 shows the user's trip as a list of MOMENTS/SCENES — not individual photos. Each scene shows a thumbnail strip, the AI's plan for that section, and a place to add a story. The user adds context to the moments that matter.

**Why this priority**: Users think in moments ("the speedboat tour", "waiting for the passport"), not individual photos. Scene-level stories are natural and fast — 10 scenes to review, not 50 photos.

**Independent Test**: Open Screen 2 → see 10 scenes → tap "Add your story" on the speedboat scene → type "highlight of the trip!" → save → verify in project.json.

**Acceptance Scenarios**:

1. **Given** the user's selection spans 10 scenes, **When** they open Screen 2, **Then** they see a vertical list of scenes with: thumbnail strip (first 5 photos), scene label, item count, estimated duration, and the AI's plan for that section.

2. **Given** a scene, **When** the user taps "Add your story", **Then** a text field opens where they type their memory/context. Mobile keyboard mic handles voice-to-text.

3. **Given** the user types "We waited 2 hours for the passport appointment, kid was bored then super excited when it was done", **When** they save, **Then** the note is stored in project.json per scene_id and a story icon appears on the scene card.

4. **Given** a scene the user doesn't want, **When** they tap remove, **Then** the scene disappears with undo toast. All its items go to deselected_ids.

5. **Given** 10 scenes, **When** the user adds stories to 3 and removes 1, **Then** Claude reads the 9 remaining scenes with stories from project.json.

6. **Given** a scene card, **When** the user taps the thumbnail strip, **Then** it expands to show all photos/videos in that scene for quick review (not editing — just viewing).

---

### User Story 2 — AI Interprets Notes for Storytelling (Priority: P1)

The AI reads the user's notes and adjusts the video generation: pacing, captions, transitions, and mood. The AI reasons about each note — it's not a fixed mapping.

**Why this priority**: This is where the magic happens. The note "Waymo made an April Fools joke and my kid fell for it" should make the AI: show that segment longer, maybe add a text caption, use a lighter transition, increase energy.

**Independent Test**: Add note "funny moment" → generate clip → verify that segment has different pacing/treatment than segments without notes.

**Acceptance Scenarios**:

1. **Given** a note "we were waiting for the appointment", **When** the AI generates the clip, **Then** it shows those photos with slower pacing (longer duration per photo) to convey waiting.

2. **Given** a note "Waymo taxi made an April Fools joke and my kid fell for it — very funny", **When** the AI generates, **Then** it can add a text caption overlay, use an upbeat transition, and show the segment slightly longer.

3. **Given** a note "this was our first view of the ocean", **When** the AI generates, **Then** it can use a dramatic reveal transition and longer hold on that photo.

4. **Given** most items have no notes, **When** the AI generates, **Then** those items get standard treatment — the AI focuses its creativity on annotated items.

5. **Given** notes on 5 items, **When** the AI generates, **Then** it tells the user what it did: "Added caption on the Waymo joke, slowed down the passport waiting scene, held the ocean view for 6 seconds."

---

### User Story 3 — Scene Reorder + Remove (Priority: P1)

The user can reorder scenes and remove scenes they don't want.

**Why this priority**: The AI orders scenes chronologically by default, which is usually right. But the user might want to rearrange for storytelling ("end with the sunset, not the airport").

**Acceptance Scenarios**:

1. **Given** the scene list, **When** the user drags a scene to a different position, **Then** the order updates and persists.
2. **Given** a scene, **When** the user taps remove, **Then** undo toast, scene disappears, items go to deselected_ids.

---

### User Story 5 — Quick Preview (Priority: P1, Phase 2)

After the user adds stories, the AI generates a quick low-quality preview (480p, fast encoding). The user watches it and gives feedback in conversation. The AI adjusts and generates the final HD version.

**Why this priority**: Users need to SEE the result, not imagine it from a plan. A 30-second preview at 480p can be generated in under a minute. This is the fastest feedback loop.

**Note**: This is Phase 2 of this improvement — implement after Scene-Level Storytelling works.

**Acceptance Scenarios**:

1. **Given** the user tells Claude "ready for preview", **When** the AI generates, **Then** it creates a 480p fast-encoded preview video in under 60 seconds.
2. **Given** the user watches the preview, **When** they say "make speedboat longer", **Then** the AI adjusts and regenerates the preview.
3. **Given** the user is happy with the preview, **When** they say "looks good, generate final", **Then** the AI generates the full HD version.

---

### User Story 4 — Summary Bar + Navigation (Priority: P2)

Both Screen 1 and Screen 2 show a sticky summary bar at the bottom with the current selection count and estimated video duration. Screen 1 has a link to Screen 2. Screen 2 has a link back to Screen 1. The user can switch freely between them. No generate button — the AI guides generation through conversation.

**Why this priority**: The user needs to see the impact of their selections at all times, and navigate freely between selecting (Screen 1) and reviewing/annotating (Screen 2).

**Independent Test**: Open Screen 1 → see summary bar with count + duration → tap "Review Timeline" → Screen 2 opens → tap "Back to Selection" → Screen 1.

**Acceptance Scenarios**:

1. **Given** the user is on Screen 1 or Screen 2, **When** items are selected, **Then** a sticky bottom bar shows: total selected count, estimated video duration, and a link to the other screen.

2. **Given** the summary bar, **When** it shows "42 photos, 8 videos · ~3:20 estimated", **Then** the duration is calculated from: photos × 4s + video durations − crossfade overlaps.

3. **Given** the user is on Screen 1, **When** they tap "Review Timeline →", **Then** Screen 2 opens.

4. **Given** the user is on Screen 2, **When** they tap "← Back to Selection", **Then** Screen 1 opens.

5. **Given** 0 items selected, **When** the summary bar renders, **Then** it shows "No items selected."

---

### Edge Cases

- What if the user adds a very long note (500+ characters)? Truncate display, store full text. AI reads the full text.
- What if speech-to-text fails? Fall back to text input. Show "Could not transcribe — please type instead."
- What if the browser doesn't support speech-to-text? Hide the voice button, show text only.
- What if the user reorders items across scenes? Allow it — the timeline is the user's creative choice, not bound by scene order.
- What if the user skips Screen 2? That's fine — notes are optional. AI generates with standard treatment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Screen 2 accessible at `/project/{id}/timeline` in the Selection UI app.
- **FR-002**: Shows SCENES (not individual items) as a vertical scrollable list.
- **FR-003**: Each scene card shows: thumbnail strip (first 5 items), scene label, item count, estimated duration, story indicator (if user added a note).
- **FR-004**: Tap "Add your story" opens text field. Mobile keyboard mic handles voice-to-text.
- **FR-005**: Stories stored in project.json as `"scene_notes": {"scene_id": "text..."}` dict.
- **FR-006**: AI reads scene notes during video generation and adjusts pacing, captions, transitions per scene.
- **FR-007**: Tap thumbnail strip expands to show all items in that scene (view only).
- **FR-008**: Drag-and-drop reorder of scenes.
- **FR-009**: Remove scene with undo toast (items go to deselected_ids).
- **FR-010**: Works on mobile (touch-friendly, responsive).
- **FR-011**: Sticky summary bar on both screens: selected count, estimated duration, link to the other screen. No generate button — AI guides generation through conversation.
- **FR-012**: Quick preview: AI generates 480p fast-encoded preview for user feedback before final HD. (Phase 2)

### Key Entities

- **Scene Story**: Text note associated with a scene_id. Stored in project.json `scene_notes` dict. The AI interprets this for pacing, captions, mood.
- **Scene Order**: Array of scene_ids in user-determined order. Stored in project.json.
- **AI Plan**: Not shown in UI. The AI builds its plan during generation based on scene notes. The user can discuss the plan with Claude in conversation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: User can review 10 scenes and add 3 stories in under 3 minutes on mobile.
- **SC-002**: AI-generated clip with scene notes has noticeably different treatment on annotated scenes vs non-annotated.
- **SC-003**: Drag-and-drop scene reorder works on mobile (touch drag).
- **SC-004**: Quick 480p preview generates in under 60 seconds. (Phase 2)

## Assumptions

- The existing Selection UI app (SvelteKit at macmini:3000) hosts Screen 2 as a new route.
- Mobile keyboard handles voice-to-text natively — no Web Speech API needed.
- The AI (Claude) interprets scene notes — no fixed mapping rules. Notes are passed as context during generation.
- The AI builds its plan during generation — reads scene notes from project.json and reasons about pacing, captions, transitions. No plan shown in the UI.
- Screen 2 is optional — the user can skip it and generate directly from Screen 1 selection.
- TDD not required for UI components — Playwright E2E tests validate the workflow.
