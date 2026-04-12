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

After the user selects photos/videos in Screen 1 (310+ items narrowed to ~40-50 by AI budget), they need a way to:
- Review the AI's timeline arrangement
- Add context that only they know — stories, memories, emotions
- The AI uses these notes to transform a slideshow into a story

Screen 1 is for fast scanning and picking. Screen 2 is for storytelling.

**This is a new page in the existing Selection UI** (SvelteKit app at `http://macmini:3000`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Review & Annotate (Priority: P1)

After the AI builds a timeline from the user's selection, the user opens Screen 2 to review items in order. They can add a voice note or text note to any item. Most items get no notes — only the 5-10 with a story worth telling.

**Why this priority**: Notes are the core differentiator — they turn "photos in order" into "a story with meaning." Without notes, the AI just makes a slideshow.

**Independent Test**: Open timeline → see items in order → tap an item → type "we were waiting for the passport" → save → verify note persisted in project.json.

**Acceptance Scenarios**:

1. **Given** the AI built a 45-item timeline, **When** the user opens Screen 2, **Then** they see a vertical scrollable list of items in timeline order with: thumbnail, position number, scene label, and duration.

2. **Given** an item in the timeline, **When** the user taps it, **Then** an annotation panel opens with: larger preview, text input field, voice record button, and current note (if any).

3. **Given** the user types "we were waiting for the passport appointment" on a photo, **When** they close the panel, **Then** the note is saved to project.json and a small note icon appears on the item's thumbnail.

4. **Given** the user taps the voice record button, **When** they speak, **Then** the audio is transcribed to text (speech-to-text) and saved as the note. The original audio is NOT stored — only the transcription.

5. **Given** an item in the timeline the user doesn't want, **When** they swipe or tap a remove button, **Then** the item is removed from the timeline and added to deselected_ids. The list renumbers. Undo toast for 5 seconds.

6. **Given** 45 items in the timeline, **When** the user adds notes to 5 of them and removes 3, **Then** Claude reads the final 42 items with notes from project.json.

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

### User Story 3 — Video Controls (Priority: P2)

The user can trim video clips, adjust speed, mute audio, and reorder items in the timeline.

**Why this priority**: Fine-tuning. Most users skip this — the AI's default arrangement is good enough. Power users who want control get it here.

**Independent Test**: Drag item #5 to position #2 → verify order updated. Trim video to 5 seconds → verify in project.json.

**Acceptance Scenarios**:

1. **Given** a video clip showing 15 seconds, **When** the user sets trim to 3s-8s, **Then** only that 5-second segment is used in the clip.
2. **Given** the timeline, **When** the user drags item #5 to position #2, **Then** the order updates and persists.
3. **Given** a video with audio, **When** the user taps "mute", **Then** that clip's audio is silent in the generated video.

---

### User Story 4 — Guided Transition from Screen 1 to Screen 2 (Priority: P1)

When the user finishes selecting in Screen 1, the UI guides them to the next step — either Screen 2 (annotate) or generate directly. Both options show a summary with estimated video duration.

**Why this priority**: Without this, the user finishes selecting and doesn't know what to do next. They have to go back to Claude and say "done." The UI should guide the flow.

**Independent Test**: Finish selecting → see summary bar → shows "42 items, ~3 min video" → two buttons: "Add Notes" and "Generate Now."

**Acceptance Scenarios**:

1. **Given** the user is on Screen 1 (scene list), **When** items are selected, **Then** a sticky bottom bar shows: total selected count, estimated video duration, and two action buttons.

2. **Given** the summary bar, **When** it shows "42 photos, 8 videos · ~3:20 estimated", **Then** the duration is calculated from: photos × 4s + video durations − crossfade overlaps.

3. **Given** the user taps "Add Notes →", **When** Screen 2 opens, **Then** it shows the timeline with their selected items ready for annotation.

4. **Given** the user taps "Generate Now", **When** Claude receives the signal, **Then** it skips Screen 2 and builds the video directly from the selection.

5. **Given** 0 items selected, **When** the summary bar renders, **Then** it shows "No items selected" and both buttons are disabled.

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
- **FR-002**: Shows selected items in timeline order as a vertical scrollable list.
- **FR-003**: Each item shows: thumbnail, position, scene label, duration, note indicator (if note exists).
- **FR-004**: Tap item opens annotation panel: larger preview, text input field. Mobile keyboard's built-in mic handles speech-to-text natively.
- **FR-005**: Notes stored in project.json as `"notes": {"asset_id": "text..."}` dict.
- **FR-007**: AI reads notes during video generation and adjusts pacing, captions, transitions.
- **FR-008**: Video trim controls: start/end sliders or time inputs.
- **FR-009**: Drag-and-drop reorder of timeline items.
- **FR-010**: Mute toggle per video clip.
- **FR-011**: "Generate" button at the bottom. Also "Skip to generate" link to bypass Screen 2.
- **FR-012**: Works on mobile (touch-friendly, responsive).

### Key Entities

- **Annotation**: Text note associated with an asset_id. Stored in project.json `notes` dict.
- **Timeline Order**: Array of asset_ids in user-determined order. Stored in project.json.
- **Trim Settings**: Per-video start/end times. Stored in project.json timeline items.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: User can review 45 items and add 5 notes in under 3 minutes on mobile.
- **SC-002**: Voice-to-text transcription works on iOS Safari and Chrome.
- **SC-003**: AI-generated clip with notes has noticeably different treatment on annotated items vs non-annotated.
- **SC-004**: Drag-and-drop reorder works on mobile (touch drag).

## Assumptions

- The existing Selection UI app (SvelteKit at macmini:3000) hosts Screen 2 as a new route.
- Browser Speech Recognition API (Web Speech API) is available on iOS Safari and Chrome. Not available on Firefox.
- The AI (Claude) interprets notes — no fixed mapping rules. Notes are passed as context during generation.
- Screen 2 is optional — the user can skip it and generate directly from Screen 1 selection.
- TDD not required for UI components — Playwright E2E tests validate the workflow.
