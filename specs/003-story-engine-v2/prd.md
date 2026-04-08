# Story Engine v2 — Product Requirements Document

## Context

Story Engine v1 (spec 001) is functional but produces low-quality results:
- **Video output**: 1 Mbps bitrate at 1080p — visibly compressed, especially during crossfade transitions
- **Photo selection**: No quality scoring, no deduplication, no diversity. Returns sequential photos from Immich search with generic AI-generated captions that don't reflect actual content
- **No preview**: User sees captions but never the actual photos before generation
- **No video clips**: Only still images, no support for trip videos
- **HEIC handling**: Unnecessary lossy HEIC→JPEG conversion via sips before FFmpeg

## User Profile

- Primary viewer: phone (mobile), sometimes laptop
- Photo library: 69K+ assets in Immich, hundreds per trip with many burst/duplicate shots
- Wants: high-quality family trip clips with smart auto-selection and ability to refine

---

## Improvements

### IMP-001: Smart Photo & Video Selection

**Problem**: Current search grabs the first N results from Immich smart search. No quality scoring, no dedup, no diversity. User got "garbage images" — accidental sky shots, unclear frames, near-identical bursts.

**Requirements**:
- R001: Multi-query search — AI skill issues multiple searches (by date range, location, people, semantic query) and merges results into a candidate pool
- R002: Quality scoring — score each candidate using Immich metadata: face count, resolution, CLIP confidence, and optionally blur detection (Laplacian variance via FFmpeg/sips)
- R003: Burst deduplication — detect near-identical shots (by timestamp proximity + thumbhash similarity) and auto-pick the best; keep 2-3 alternates in memory for user swaps
- R004: Diversity enforcement — ensure selected photos span different moments/scenes across the trip, not clustered from one 5-minute window
- R005: Video clip inclusion — include trip videos in the candidate pool, auto-detect "interesting" segments (movement, faces, audio peaks)
- R006: Candidate pool stored on filesystem — save the full scored candidate set as a project file (JSON) so the skill can reference it across conversation turns

**Scoring approach — Immich-based vs independent**:

| Approach | Pros | Cons |
|----------|------|------|
| **Immich metadata only** (faces, CLIP, thumbhash, resolution) | No extra processing, instant, uses existing ML | No blur detection, no exposure analysis, limited to what Immich indexes |
| **Independent scoring** (Laplacian blur, histogram exposure, face sharpness via sips/ffprobe) | More accurate quality assessment | Requires downloading each candidate's thumbnail, slower, more code |
| **Hybrid** (Immich for initial filter + independent for top candidates) | Best quality with acceptable speed | More complex, two-phase pipeline |

**Recommendation**: Hybrid — use Immich metadata to build and rank the candidate pool (fast, covers 80% of cases), then run independent blur/exposure checks only on the top ~50 candidates before final selection.

---

### IMP-002: Visual Timeline Preview

**Problem**: User only sees text captions before generation. No way to verify photo selection matches expectations. Captions are AI-hallucinated and don't reflect actual photo content.

**Requirements**:
- R007: Show photo/video thumbnails inline in Claude Code (desktop) using Immich thumbnail API
- R008: For mobile Claude, generate an Immich shared album with the selected photos as a preview, provide share link
- R009: Timeline view — show selected items in chronological order with position numbers, timestamps, and durations
- R010: Swap interface — user can say "replace #3" and see 2-3 similar alternates (from R003 burst dedup memory) to choose from
- R011: Drag-style reorder — user can say "move #5 to position 2" or "remove #7"
- R012: Caption generation — use Immich's AI descriptions or CLIP-based scene tags instead of hallucinated captions

---

### IMP-003: Video Output Quality

**Problem**: Output video is 1 Mbps at 1080p — visibly compressed. HEIC→JPEG conversion adds unnecessary quality loss. Transitions look choppy.

**Requirements**:
- R013: Target bitrate appropriate for viewing device — phone: 1080p at 5-8 Mbps, laptop: 1080p at 8-12 Mbps (or 4K option)
- R014: Lower CRF value (18-20 instead of 23) for higher quality, especially during transitions
- R015: Eliminate HEIC→JPEG conversion — use FFmpeg's native HEIC decoding or pipe through `heif-convert` at maximum quality
- R016: Improve audio quality — 192 kbps AAC (up from 128 kbps) when music is included
- R017: Standard frame rate — 30 fps (phone/web standard) instead of 25 fps
- R018: Smooth transitions — Ken Burns effect (slow zoom/pan) on still images to add motion, configurable per-photo

---

### IMP-004: Project File & Timeline Editor Model

**Problem**: Current scenario.json is a flat list of asset IDs with captions. No support for video clips (start/end times), no alternate candidates, no timeline metadata.

**Requirements**:
- R019: Extended project file format — JSON with:
  - Candidate pool (all scored candidates with quality metrics)
  - Selected timeline (ordered items with position, type, duration)
  - Per-item metadata: start/end time (for video clips), transition type, Ken Burns params
  - Alternate candidates per slot (for swap UI)
  - Project state: searching → selecting → previewing → approved → generated
- R020: Video clip trimming — store start/end timestamps per video clip, user can adjust via conversation ("trim video #4 to first 5 seconds")
- R021: Transition customization — per-item transition type (crossfade, cut, wipe) and duration
- R022: Export presets — phone (1080p/5Mbps), laptop (1080p/10Mbps), TV (4K/20Mbps)

---

### IMP-005: Music & Audio (deferred)

**Problem**: Music integration exists but is basic. No auto-sync to beat, no volume ducking for video clips with audio.

**Requirements** (to be specified later):
- R023: Auto-select music mood based on trip content
- R024: Beat-sync transitions to music tempo
- R025: Volume ducking — lower music when video clip has meaningful audio
- R026: Multiple music segments for longer clips

---

## Implementation Order (recommended)

| Priority | Improvement | Rationale |
|----------|------------|-----------|
| 1 | **IMP-001**: Smart Selection | Fixes the core problem — bad photo selection |
| 2 | **IMP-003**: Video Quality | Quick wins — CRF, bitrate, HEIC handling |
| 3 | **IMP-002**: Visual Preview | Enables user feedback loop before generation |
| 4 | **IMP-004**: Project File | Foundation for timeline editing, needed for IMP-002 swap feature |
| 5 | **IMP-005**: Music & Audio | Polish layer, deferred per user request |

**Note**: IMP-001 and IMP-004 are closely related — the project file (IMP-004) is needed to store candidates and alternates from smart selection (IMP-001). Consider implementing R019 (project file format) as part of IMP-001.

---

## Resolved Questions

1. **Clip duration**: Auto-determine based on available good content, then let user refine ("make it shorter", "extend to 2 minutes").
2. **Video clip previews**: Short animated previews preferred over static thumbnails.
3. **Dedup aggressiveness**: Two tiers — (a) Aggressive for bursts: same moment, <5 seconds apart, keep sharpest, store 2-3 alternates. (b) Moderate for similar scenes: same location/composition within 30 minutes, keep most distinct, store alternates. Avoids 5 beach sunset photos but keeps meaningfully different moments.
