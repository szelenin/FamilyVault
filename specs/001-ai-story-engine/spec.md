# Feature Specification: AI Story Engine

**Feature Branch**: `001-ai-story-engine`
**Created**: 2026-04-04
**Status**: Draft
**Input**: User description: "I want to be able to tell AI what story or clip I want to create and it will use existing APIs (or APIs that I create) to find related content, give me scenario for the review, suggest music selection, or I can add music and then when I say generate the video it will generate the video file."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Conversational Story Request (Priority: P1)

The user describes in natural language what story or clip they want to create.
The AI searches the photo/video library using available APIs, selects relevant
content, and returns a proposed scenario (ordered list of media with captions and
a narrative) for the user to review — all through conversation, no UI navigation.

**Why this priority**: This is the entry point of the entire feature. Without the
ability to request a story and get back a reviewable scenario, nothing else works.
It delivers immediate value: the user can see what the AI found and what it plans
to make.

**Independent Test**: Can be fully tested by submitting a natural language request
("make a clip of our Miami trip") and verifying the response contains a structured
scenario with selected media items, captions, and a narrative outline. Delivers
value as a standalone "content discovery + storyboard" feature even without video
generation.

**Acceptance Scenarios**:

1. **Given** a library with tagged and captioned photos/videos, **When** the user
   says "create a story about Edgar's birthday in March 2025", **Then** the system
   returns a scenario containing: ordered list of selected media, per-item caption,
   event title, and narrative summary — all within 30 seconds.

2. **Given** a vague request like "make something about our summer", **When** the
   system cannot find a single clear event, **Then** it returns the top 2-3
   candidate events it found with a summary of each and asks the user to choose
   or refine.

3. **Given** a request for a period with no matching content, **When** the system
   finds zero relevant media, **Then** it tells the user clearly what it searched
   for and suggests adjacent time ranges or people that do have content.

---

### User Story 2 — Scenario Review and Refinement (Priority: P2)

After receiving a proposed scenario, the user reviews it conversationally. They
can request changes: swap out specific photos, reorder scenes, change the
narrative tone, shorten or lengthen the story, or remove content they don't want
included. The AI updates the scenario and shows the revised version.

**Why this priority**: A scenario that cannot be refined is not useful for
personal family stories where the user knows exactly which moments matter.
Review and refinement separates this from a fully automated "Memories" feature.

**Independent Test**: Can be tested by presenting an existing scenario and sending
refinement requests ("remove the airport photos", "make it funnier", "add the
photos from the pool"), then verifying the updated scenario reflects each change
correctly.

**Acceptance Scenarios**:

1. **Given** a proposed scenario, **When** the user says "remove the photos where
   Edgar is crying", **Then** the updated scenario no longer contains those items
   and the narrative adjusts accordingly.

2. **Given** a proposed scenario, **When** the user says "change the tone to
   something more funny and lighthearted", **Then** the captions and narrative
   summary are rewritten in that tone while the selected media stays the same.

3. **Given** a proposed scenario with 20 items, **When** the user says "make it
   shorter, max 10 photos", **Then** the system selects the 10 best shots from
   the original 20 and briefly explains the selection criteria.

---

### User Story 3 — Music Selection (Priority: P3)

After the scenario is approved, the system suggests music options that match the
mood and content of the story. The user can accept a suggestion, pick from
alternatives, or provide their own audio file. Music selection is confirmed
before video generation begins.

**Why this priority**: Music is a key part of emotional storytelling in video
clips. It can be skipped for a first version (video without music is valid) but
is important for the final product quality.

**Independent Test**: Can be tested independently by presenting a finalized
scenario and verifying that: the system offers at least 2 music suggestions with
mood descriptions, the user can specify their own file path, and the selected
music is stored with the scenario for use in generation.

**Acceptance Scenarios**:

1. **Given** an approved scenario with a "fun family vacation" narrative, **When**
   music selection is requested, **Then** the system suggests 2-3 music options
   with descriptions of mood and energy level (e.g., "upbeat acoustic, good for
   travel montages").

2. **Given** music suggestions have been presented, **When** the user says
   "I'll use my own file: /music/vacation-song.mp3", **Then** the system accepts
   the file path, confirms the file is accessible, and stores it as the selected
   track.

3. **Given** music selection, **When** the user says "skip music", **Then** the
   system confirms and marks music as none — generation proceeds without audio.

---

### User Story 4 — Video Generation (Priority: P4)

When the user is satisfied with the scenario and music selection, they give a
generation command ("generate the video", "make it", "go ahead"). The system
assembles the final video file from the approved scenario — selected media in
order, transitions, captions/narrative as text overlays or subtitles, and the
chosen audio track. The user receives a path to the finished video file.

**Why this priority**: This is the final delivery step. The previous three stories
deliver value on their own, but the video file is the end product.

**Independent Test**: Can be tested by providing a pre-approved scenario with
selected media files and music, triggering generation, and verifying: a video
file is produced at the expected path, contains all selected media in the correct
order, the audio track is present if specified, and no text overlays appear unless
the user explicitly requested them.

**Acceptance Scenarios**:

1. **Given** an approved scenario with 12 photos and a selected music file,
   **When** the user says "generate the video", **Then** the system produces a
   video file within 5 minutes, confirms the output path, and reports the
   duration and file size.

2. **Given** a generation in progress, **When** the user asks "how's it going",
   **Then** the system reports current progress (e.g., "assembling scene 7 of 12").

3. **Given** a completed video, **When** the user asks to regenerate with a
   different music track, **Then** the system reuses the approved scenario
   (no re-selection of photos) and only re-assembles the audio layer.

---

### Edge Cases

- What happens when a referenced photo file no longer exists on the RAID at
  generation time? System reports missing files before generation and asks the
  user to proceed without them or cancel.
- What happens if video generation fails mid-assembly? System retries
  automatically up to 3 times from scratch, logging each failure with the
  error reason. After 3 failed attempts it reports failure to the user with
  the log location.
- How does the system handle very large requests ("make a video of all of 2024"
  with 3,000 photos)? System caps selection at 60 items and informs the user,
  suggesting sub-events instead.
- What if the user's own music file is in an unsupported format? System reports
  the issue and asks for an alternative before proceeding.
- What happens if the library index (Immich) is unreachable during a request?
  System reports the dependency is unavailable and cannot proceed until restored.
- What if two events overlap (trip + birthday during trip)? System surfaces both
  and asks the user which framing to use.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a natural language description of a desired story
  or clip and return a structured scenario without requiring UI navigation.
- **FR-002**: System MUST search the photo/video library using available metadata
  (faces, locations, dates, captions, semantic tags) to find content relevant to
  the user's request.
- **FR-003**: A scenario MUST include: ordered list of selected media items, a
  caption per item, an event title, and a narrative summary.
- **FR-004**: System MUST support iterative refinement of a scenario through
  conversation (add/remove items, change tone, adjust length) before generation.
- **FR-005**: System MUST suggest at least 2 music options from a bundled set of
  10-20 mood-categorized royalty-free tracks, matched to the story's tone. User
  MUST always be able to substitute their own audio file instead.
- **FR-006**: System MUST accept a user-supplied audio file as an alternative to
  suggested music, or allow music to be skipped entirely.
- **FR-007**: System MUST generate a video file from an approved scenario,
  assembling media in order with transitions and the selected audio track.
  Burned-in text overlays (captions/narrative) MUST be included only when
  the user explicitly requests them; by default the video is clean (no text).
- **FR-008**: System MUST report generation progress during video assembly.
- **FR-009**: All photo and video content MUST remain on the local network;
  only non-sensitive metadata (captions, event names, descriptions) may be sent
  to external AI services.
- **FR-010**: System MUST handle unavailable content gracefully — missing files,
  unreachable dependencies, unsupported formats — with a human-readable stderr
  message naming the unavailable resource and exit code 3.
- **FR-011**: A scenario MUST be persisted as a JSON file on the RAID so
  the user can resume a session without losing approved selections. No database
  is required.
- **FR-012**: System MUST log all generation attempts, failures, and error reasons
  to a persistent log file on the RAID. Automatic retry MUST be limited to 3
  attempts before surfacing failure to the user.

### Key Entities

- **Story Request**: The user's natural language input describing the desired
  story — text, time range hints, people mentioned, mood/tone.
- **Scenario**: An ordered collection of media items with captions, an event
  title, a narrative summary, and generation parameters (music, duration target,
  tone). States: draft → reviewed → approved.
- **Media Item**: A reference to a photo or video in the library with its
  caption, metadata (date, location, people), and selection rationale.
- **Music Selection**: A system-suggested track with mood description, or a
  user-supplied file path. Can be explicitly "none".
- **Generated Video**: Output artifact — file path, duration, size, and a
  reference back to the scenario it was generated from.
- **Scenario Store**: A configurable directory (default `/Volumes/HomeRAID/stories/`) containing one subdirectory per scenario. Each subdirectory holds `scenario.json` (full scenario state: selected media, captions, narrative, music selection, approval status) and `output.mp4` (generated video, if produced). No database required.

## Clarifications

### Session 2026-04-04

- Q: Where are scenarios persisted? → A: File per scenario on RAID (JSON/YAML) — no extra dependencies.
- Q: How are captions/text included in the video? → A: Burned-in text overlays, only when explicitly requested by the user; default output is clean video with no text.
- Q: Multi-scenario management? → A: One active scenario at a time; past generated videos are listable by asking — no parallel scenarios needed.
- Q: Generation failure recovery? → A: Restart from scratch (no resume), log failures, retry automatically up to a fixed limit before reporting failure to the user.
- Q: Music catalog scope? → A: Small curated set of 10-20 royalty-free tracks organized by mood category; user can always provide their own audio file as an alternative.

### Session 2026-04-05

- Q: Where does the story engine run and what invokes it? → A: Claude Code agent running on user's machine, calling Immich REST API and Mac Mini over LAN. Claude session exposed remotely so user can trigger story generation from Claude mobile client.
- Q: What tool assembles the video? → A: FFmpeg installed on Mac Mini via brew; invoked over SSH by the Claude Code agent.
- Q: How does the Story Engine query Immich? → A: Direct Immich REST API v2.6.3 — no MCP intermediary.
- Q: Where are generated videos stored? → A: Configurable base path, default `/Volumes/HomeRAID/stories/{scenario-id}/output.mp4`.
- Q: How are HEIC photos handled during video assembly? → A: Converted to JPEG on the fly using macOS `sips`; originals untouched; temp files deleted after assembly.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from a natural language story request to a reviewable
  scenario in under 30 seconds for a library of up to 15,000 items.
- **SC-002**: A user can complete the full workflow (request → review → music →
  generate) for a 10-photo story entirely through conversation with no UI
  navigation required.
- **SC-003**: Video generation for a 30-item scenario completes in under 5 minutes
  on the target home server hardware.
- **SC-004**: The system correctly identifies the intended event in at least 90%
  of requests where a clear matching event exists in the library.
- **SC-005**: All scenario refinement changes (add/remove/reorder/tone) are
  reflected correctly in the updated scenario 100% of the time.
- **SC-006**: Generated video files are playable on standard media players without
  additional processing.

## Assumptions

- The photo/video library is indexed in Immich with face recognition and captions
  already enabled — this is a prerequisite, not in scope for this feature.
- The Story Engine queries Immich directly via its REST API (v2.6.3). Key endpoints:
  `/api/search/smart` (CLIP semantic search), `/api/people` (face lookup),
  `/api/search/metadata` (date/location filters), `/api/assets/{id}/original`
  (file download for video generation). No MCP intermediary required.
- Music suggestions are drawn from a bundled set of 10-20 royalty-free tracks
  organized by mood category (e.g., upbeat, calm, sentimental, fun). The user
  can always bypass suggestions by providing their own audio file path; licensing
  for user-supplied music is the user's responsibility.
- Video output is MP4 format — the most universally compatible for home playback.
- Video assembly uses FFmpeg (installed on Mac Mini via brew). The Claude Code agent invokes FFmpeg over SSH to assemble the final video on the server.
- HEIC photos are converted to JPEG on the fly during assembly using macOS `sips` (built-in, no install required). Originals are never modified; converted files are written to a temp directory and deleted after assembly.
- Generated videos and scenario files are stored at a configurable base path, defaulting to `/Volumes/HomeRAID/stories/`. Structure: `stories/{scenario-id}/scenario.json` and `stories/{scenario-id}/output.mp4`.
- The primary interaction surface is conversational AI (Claude Code agent); no
  standalone GUI is required for v1. The Claude session is exposed remotely
  so the user can initiate story generation from the Claude mobile client.
- A scenario contains a maximum of 60 media items to keep generation times
  predictable; larger events should be broken into sub-stories.
- The system has a single user — no multi-user access control needed in v1.
- Only one scenario is active at a time. Starting a new story request replaces
  the current draft. Past generated videos remain on disk and are listable on
  request; no separate history database is needed.
