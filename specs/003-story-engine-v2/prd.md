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

### IMP-006: Smart Scene Discovery (from testing feedback)

**Problem**: Current pipeline combines search and scene detection into one pass. Scenes get missed because: (a) city filter is too narrow (Coconut Grove ≠ Miami in metadata), (b) no way to show ALL detected scenes before applying budget, (c) scene detection algorithm is hardcoded to "trip" mode — doesn't support other prompt types like "how my son grows." Additionally, the search requires hardcoded date ranges — the system can't discover trip dates from a vague prompt like "our Miami trip."

**Status**: Partially implemented (007-smart-scene-discovery). Two-phase architecture, broad CLIP search, scene discovery, must-have verification, and detection modes are done. **Remaining**: intelligent probe-based search (date discovery, location expansion, multi-signal scoring), and bug fixes (must-have extraction, source_query dedup).

**Implemented requirements (done)**:
- R027: Two-phase architecture: Phase A (Scene Discovery) shows ALL scenes with no budget limits. Phase B (Selection & Budget) applies after user confirms which scenes matter.
- R028: Prompt-aware scene detection modes: trip, person-timeline, general. AI evaluates the initial prompt and selects the appropriate detection algorithm.
- R029: Broad CLIP search without city filter. Metadata search by date range as supplement.
- R030: Must-have keywords cross-referenced against detected scenes. Missing must-haves reported.
- R031: Exclude story-engine clips and screenshots automatically (done in IMP-009).

**Remaining requirements (not yet implemented)**:
- R050: Intelligent probe search — when user provides no date range, the system runs a small CLIP probe search (e.g., "Miami trip", limit 50), analyzes the returned timestamps to discover the trip date cluster, then expands to a full search using the discovered date range.
- R051: Location discovery via GPS clustering — after broad search, cluster candidate GPS coordinates to discover all trip locations (neighborhoods, landmarks). Use the cluster center + radius to catch unlabeled assets nearby. No hardcoded city lists.
- R052: Multi-signal confidence scoring — each candidate scored by: CLIP relevance, temporal fit (within discovered trip dates), GPS proximity (near trip cluster center), people presence (trip companions). Combined score determines inclusion.
- R053: Iterative search expansion — if probe search returns few results, the system automatically tries broader queries, wider date ranges, or different search terms. Reports what it tried.
- R054: Fix Bug 1 — must-have keyword extraction drops the first keyword in "X, Y, Z must have" pattern when X is preceded by the main prompt sentence.
- R055: Fix Bug 2 — search_broad() dedup loses source_query for all but the first CLIP query. Track all matching queries per candidate (list, not single string) so must-have verification can check which queries found each asset.

**Known bugs (from E2E testing)**:
- Bug 1: `extract_must_have_keywords("make a clip of our Miami trip. Speedboat, vizcaya garden, sunset walk must have")` returns `['vizcaya garden', 'sunset walk']` — misses "speedboat" because it's concatenated with the prompt sentence after comma-split.
- Bug 2: `search_broad(queries=["miami trip", "speedboat", "vizcaya garden"])` tags ALL candidates with `source_query="miami trip"` — the first query finds everything, subsequent queries find only already-seen IDs, so no candidate gets tagged with "speedboat" or "vizcaya garden".

---

### IMP-007: Timeline Editing UX (absorbs IMP-004 remainder)

**Problem**: Users reference photos by position number (#3) which is fragile and unfriendly. No way to mark photos easily. Preview album gets recreated on every change, losing the share link.

**Requirements**:
- R032: Combined content referencing — accept any of: position (#3), filename (IMG_7338), time (6:44pm photo), scene+position (photo 3 from Vizcaya), description, or Immich link. AI disambiguates.
- R033: Update existing preview album instead of recreating — use `PUT /api/albums/{id}/assets` to add and `DELETE /api/albums/{id}/assets` to remove. Share link remains stable.
- R034: Show rich identifiers in timeline output: position, thumbnail link, time, city, scene name, filename — so user can reference by whichever is easiest.
- R035: AI notices potential issues (screenshots, low-score items, duplicates) and suggests fixes with specific content references ("IMG_7280 in Scene 4 looks like a screenshot — remove?").

---

### IMP-008: Favorites Priority (from testing feedback)

**Problem**: User has already marked favorite photos in Photos.app/Immich but the selection pipeline ignores them.

**Requirements**:
- R036: Favorited photos (`isFavorite: true` in Immich) get absolute priority — guaranteed slot in timeline, suggested first within each scene.
- R037: Cluster of favorited photos helps scene detection — if user starred 5 photos from Vizcaya, that cluster signals "important scene" even before user mentions it.
- R038: Search pipeline queries `isFavorite: true` as an additional signal alongside CLIP and metadata search.

---

### IMP-009: Screenshot & Garbage Filtering (quick fix)

**Problem**: Screenshots and non-photo content (screen recordings, app exports) slip through despite filename filtering.

**Requirements**:
- R039: Filter screenshots by multiple signals: filename patterns (Screenshot, IMG_*.PNG from specific apps), resolution aspect ratio (exact screen dimensions like 1170x2532), EXIF make/model (no camera info = likely screenshot).
- R040: Filter out story-engine generated assets by `deviceId=story-engine`.

---

### IMP-010: iCloud Metadata Sync to Immich

**Problem**: iCloud Photos has rich metadata (favorites, albums, keywords, ratings, people names) that osxphotos can access via its Python API. However, none of this metadata reaches Immich: osxphotos writes to XMP sidecars which Immich's external library scanner ignores, and there is no sync script to bridge the gap. This means user curation in Photos.app (years of starring favorites, organizing albums) is invisible to the story engine.

**Metadata available in iCloud (via osxphotos Python API)**:
- Favorites (liked photos)
- Albums and smart albums
- Keywords and tags
- People/face names (mapped by osxphotos, independent of Immich face detection)
- Ratings (if set)
- Hidden/archived status
- Edited versions

**Immich API endpoints available for writing**:
- `PUT /api/assets/{id}` — set `isFavorite`, `isArchived`, `rating`
- `POST /api/albums` + `PUT /api/albums/{id}/assets` — create albums and add assets
- `POST /api/tags` + tag assignment — create and assign tags
- `PUT /api/people/{id}` — update person names (align with iCloud face names)

**Requirements**:
- R041: Post-export sync script that queries osxphotos Python API for all metadata per exported photo (favorites, albums, keywords, ratings, people names).
- R042: Asset mapping — match each exported file to its Immich asset ID by filename, checksum, or original path.
- R043: Sync favorites — set `isFavorite: true` on Immich assets that are favorited in iCloud.
- R044: Sync albums — create Immich albums matching iCloud album structure, populate with correct assets.
- R045: Sync keywords/tags — create Immich tags from iCloud keywords and assign to corresponding assets.
- R046: Sync people names — map osxphotos person names to Immich detected faces where possible (match by face position or manual mapping).
- R047: Sync ratings — set Immich rating field from iCloud ratings.
- R048: Incremental sync — only process changes since last sync run (track sync state in a local manifest file).
- R049: Run as part of the daily cron alongside `osxphotos export --update`.

**Dependencies**: Requires osxphotos export (Phase 1) to be complete, and Immich external library to be indexed. Enables IMP-008 (Favorites Priority) to be immediately useful.

---

### IMP-011: osxphotos Export Fix — GPS, ProRAW, Orientation

**Problem**: The current osxphotos export has multiple data quality issues that affect the entire pipeline:

1. **Missing GPS** — iCloud Shared Photo Library strips GPS from shared copies. 80%+ of trip photos have no GPS.
2. **Dark ProRAW photos** — DNG (raw) files exported WITHOUT the processed HEIC version. 977 DNG files look dark because they're unprocessed raw data. Photos.app shows the processed version which looks correct.
3. **Flipped photos/videos** — Some shared library exports have incorrect EXIF orientation.
4. **Missing processed HEIC** — osxphotos exported DNG + sidecars but NOT the processed HEIC alongside it. Immich only has the raw version.

**Root causes**:
- iCloud Shared Photo Library strips GPS from shared copies (files with `(1)` suffix)
- Photos.app has GPS in its database but exported file EXIF doesn't contain it
- osxphotos export command didn't include processed versions alongside raw DNG
- EXIF orientation may be wrong on shared library copies

**Evidence**: 
- 16/20 sampled Miami trip assets had no GPS (all iPhone 15 Pro shared copies)
- 977 DNG files = dark photos (17% of library), processed HEIC missing from disk
- IMG_5909: DNG exists, HEIC sidecars exist, but HEIC file itself not exported

**Requirements**:
- R056: osxphotos export MUST export both the processed HEIC AND the raw DNG for ProRAW photos. Immich should index the HEIC (looks correct) while DNG is preserved as archive.
- R057: Use `--exiftool` flag to write Photos.app GPS data into exported files' EXIF. If Photos.app doesn't have GPS for shared copies, implement GPS inference from nearby photos (same time = same location).
- R058: Verify correct EXIF orientation on all exported files. Fix flipped files with exiftool if needed.
- R059: After re-export, re-trigger Immich library scan to re-index updated files.
- R060: Separate storage paths: processed files → Immich library, DNG/raw → archive folder (not indexed by Immich to avoid duplicates).
- R061: Verify fix by checking a sample of previously dark/GPS-missing/flipped assets.

**Priority**: HIGH — blocks accurate location discovery, correct photo display, and video quality. Should be done before IMP-010 metadata sync.

---

### IMP-012: Assembler Refactor (v2 pipeline)

**Problem**: The video assembler (`assemble_video.py`) still uses the v1 `scenario.json` format and `manage_scenario.py`. It doesn't support: (a) the v2 `project.json` format, (b) video clips in the timeline (treats everything as still images), (c) DNG/RAW files (sips conversion produces corrupt TIFF). This requires a manual bridge (create v1 scenario from v2 project) and excludes all videos and DNG files from the output.

**Evidence**: Miami trip generation failed — 15 DNG files couldn't be decoded by FFmpeg ("Tiled TIFF not allowed"), 7 videos were treated as photos (loop filter on first frame only).

**Requirements**:
- R060: Assembler MUST read from `project.json` (v2 format) directly, not `scenario.json`.
- R061: Assembler MUST handle VIDEO timeline items — download original video, apply trim_start/trim_end, include with original audio. Photo-to-video and video-to-photo crossfade transitions.
- R062: Assembler MUST handle DNG/RAW files — convert to JPEG via `sips` with explicit output format, or use ImageMagick as fallback.
- R063: Remove dependency on `manage_scenario.py` — the v1 scenario system is deprecated.
- R064: Each timeline item's `type` field (IMAGE/VIDEO) determines how FFmpeg processes it — no more treating everything as still images.
- R065: Auto-detect dominant photo orientation (portrait vs landscape) and set video output orientation accordingly. If most photos are portrait → output portrait video (1080×1920) for phone viewing. If mixed → ask user.
- R066: NEVER crop photos. Preserve the full original content of every photo. The user must see everything that was in the original photo — no edges cut off. Clarifying questions about aspect ratio handling to be asked during spec phase.

**Priority**: HIGH — blocks video generation with the new v2 pipeline.

---

### IMP-013: Timeline Review Screen (Screen 2)

**Problem**: After selecting content in Screen 1, the user needs a way to review the AI's arrangement, add notes/tags, trim videos, adjust speed, and provide detailed instructions per item. This is too detailed for the scene selection grid (Screen 1) and too complex for Claude's text interface.

**Requirements**:
- R067: Screen 2 shows only SELECTED items from Screen 1, arranged in timeline order.
- R068: Per-item controls: voice note, text note, star/priority, custom tags.
- R069: Video-specific: trim start/end, speed adjustment (slow-mo, fast), keep/mute audio.
- R070: AI interprets annotations to build the final video — notes become instructions ("hero shot" → longer duration, "slow-mo" → speed reduction).
- R071: User can reorder items by drag-and-drop.
- R072: Optional — skip Screen 2 entirely and go straight to generate from Screen 1.

**Depends on**: IMP-007 (Screen 1 must be working first).

---

## Implementation Order (recommended)

| Priority | Improvement | Status | Rationale |
|----------|------------|--------|-----------|
| 1 | **IMP-001**: Smart Selection | DONE (005) | Core problem fixed |
| 2 | **IMP-003**: Video Quality | DONE (005) | CRF 18, sips 100 |
| 3 | **IMP-009**: Screenshot & Garbage Filtering | DONE (006) | Quick fix, high impact |
| 4 | **IMP-006**: Smart Scene Discovery | DONE (007, 008) | Two-phase pipeline, AI-first search, probe discovery, AI-driven budget |
| 5 | **IMP-012**: Assembler Refactor | Not started | HIGH — v2 project.json support, video clips, DNG handling |
| 6 | **IMP-007**: Timeline Editing UX | Not started | Better referencing, stable preview links |
| 6 | **IMP-011**: GPS Recovery | Not started | HIGH PRIORITY — 80% of trip photos have no GPS due to iCloud Shared Library stripping. Blocks location discovery. |
| 7 | **IMP-010**: iCloud Metadata Sync | Not started | Bridges iCloud curation (favorites, albums, tags) into Immich. Unlocks IMP-008. |
| 8 | **IMP-008**: Favorites Priority | Not started | Leverages user curation — requires IMP-010 to have favorites in Immich |
| 8 | **IMP-002**: Visual Preview | Partial (album works) | Remaining: inline thumbnails on desktop |
| 9 | **IMP-004**: Project File | Absorbed into IMP-007 | Timeline editor features |
| 10 | **IMP-005**: Music & Audio | Deferred | Polish layer |

**Notes**:
- IMP-009 (Screenshot filter) is a quick win — spec and implement first.
- IMP-006 (Scene Discovery) is the biggest architectural change.
- IMP-010 (Metadata Sync) is blocked by iCloud download completing but should be specced early since it's foundational for IMP-008.
- IMP-008 (Favorites Priority) depends on IMP-010 having synced favorites into Immich.

---

## Resolved Questions

1. **Clip duration**: Auto-determine based on available good content, then let user refine ("make it shorter", "extend to 2 minutes").
2. **Video clip previews**: Short animated previews preferred over static thumbnails.
3. **Dedup aggressiveness**: Two tiers — (a) Aggressive for bursts: same moment, <5 seconds apart, keep sharpest, store 2-3 alternates. (b) Moderate for similar scenes: same location/composition within 30 minutes, keep most distinct, store alternates. Avoids 5 beach sunset photos but keeps meaningfully different moments.
