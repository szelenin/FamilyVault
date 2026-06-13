# FamilyVault — Product Requirements Document

> **Single source of truth for requirements.** This PRD spans the whole product (story engine, local agent, sync, etc.), not a single feature. Each improvement (IMP-NNN) and requirement (R-NNN) lives here; individual `specs/NNN-*/` folders implement a subset of these requirements as features/user stories. If a requirement is missing, add it here first.
>
> **"Done" means verified.** An item is only marked DONE when it has been implemented **and** verified to work end-to-end. Code that exists but is unwired, untested, or unverified is **not** done — record it as "Partial" with an explicit list of what remains to implement/verify.
>
> **Status legend:** ✅ DONE · ⚠️ PARTIAL · Not started · Parked. The **[Implementation Order](#implementation-order-recommended)** table at the bottom is the authoritative index/priority of all IMP items.
>
> **Related docs (not requirements):** `docs/story-engine.md` (product vision/concept), `docs/plan.md` (data-migration & ops plan), `docs/model-spec-intelligent-search.md` (model choices for the understanding layer). These inform the PRD but the requirements themselves live only here.
>
> Historical note: this document began as the Story Engine v2 PRD (`specs/003-story-engine-v2/prd.md`) and was promoted to the project-wide PRD at `docs/PRD.md`.

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

**Research needed before implementation**:
- How does Immich handle two files for the same photo (DNG + HEIC)? Does it show duplicates or can it stack/link them?
- If both are indexed, which one does Immich use for thumbnails and previews?
- If the story engine selects a photo, which version (DNG vs HEIC) gets used in the clip? How do we ensure the processed HEIC is used for video assembly, not the dark DNG?
- Does Immich's stacking feature (if available in v2.6.3) support linking raw + processed versions?
- If we use DNG in the video clip, does FFmpeg apply any tone mapping or does it look dark? Do we need a separate tone-mapping step in the assembler?
- What is the best Immich configuration: index both in same library, or HEIC in library + DNG in separate archive not indexed?

**Priority**: HIGH — blocks accurate location discovery, correct photo display, and video quality. Should be done before IMP-010 metadata sync.

---

### IMP-012: Assembler v2 — Project Model + FFmpeg Command Builder

**Problem**: The v1 assembler used `scenario.json` / flat `items`, treated everything as still images, had no video-clip support, and did lossy HEIC→JPEG conversion. A v2 data model and a v2 FFmpeg command builder were needed as the foundation for higher-quality, video-aware output.

**Scope (this feature)**: the **library-level** v2 building blocks — the project data model and the FFmpeg command/filter construction — independently unit-tested. (Wiring these into the runtime entry point and verifying end-to-end video generation is a separate feature: see **IMP-016**.)

**Requirements**:
- R060: v2 project file model (`manage_project.py`) — `create_project`, `show_project`, `set_state` (searching→selecting→previewing→approved→generated), `set_candidate_pool`, `set_timeline`, `swap_item`, `remove_item`, `reorder_items`, `trim_video`, `set_budget`, `set_discovery`, `set_scene_confirmation`, `set_assembly_config`.
- R061: v2 FFmpeg command/filter builder (`build_ffmpeg_cmd_v2` + `build_filter_complex`) — reads `assembly_config` (resolution, CRF 18), branches per-item `type` (IMAGE/VIDEO), applies `trim_start`/`trim_end` for VIDEO items, mixes audio (background music + video-clip audio), 30 fps, 192 kbps AAC.

**Status**: ✅ **DONE (009).** Both pieces implemented and unit-tested: `tests/story-engine/unit/test_project_file.py` (project model, all state/timeline/config functions) and `tests/story-engine/unit/test_assembly.py` (v2 command builder, video-clip filter, CRF/fps/bitrate). Scoped to the library layer; verified by unit tests.

**Not in this feature (moved to IMP-016)**: wiring the v2 builder into `main()`/`assemble()`, downloading originals (incl. video + DNG) at runtime, DNG/RAW conversion, removing the v1 `manage_scenario` dependency, runtime orientation/no-crop, and an end-to-end test that produces a playable MP4 from a v2 `project.json`.

---

### IMP-016: Assembler v2 — Runtime Wiring & End-to-End Generation

**Problem**: IMP-012 delivered the v2 project model and the v2 FFmpeg command builder, but nothing calls the builder in the runtime path — `main()` → `assemble()` still imports v1 `manage_scenario`, reads `scenario.json`'s `items`, and calls the v1 `build_ffmpeg_cmd`. `build_ffmpeg_cmd_v2` is currently dead code. There is no verified path from a v2 `project.json` to a playable `output.mp4`.

**Evidence**: Earlier Miami-trip generation failed — 15 DNG files couldn't be decoded by FFmpeg ("Tiled TIFF not allowed"), 7 videos were treated as photos (loop filter on first frame only).

**Requirements**:
- R088: v2 runtime path — `main()`/`assemble()` loads `project.json`, reads `timeline`, and calls `build_ffmpeg_cmd_v2`. No v1 `scenario.json`.
- R089: Download originals for timeline items including VIDEO (apply trim, keep original audio) and feed the v2 builder's audio mixing.
- R090: DNG/RAW conversion at runtime — `sips` with explicit output format, or ImageMagick fallback (fix "Tiled TIFF not allowed").
- R091: Remove the `manage_scenario.py` (v1) dependency from the assembler.
- R092: Apply orientation auto-detect (dominant portrait/landscape → output resolution) and the no-crop rule at runtime.
- R093: **End-to-end verification** — a passing test that generates a playable MP4 from a v2 `project.json` containing mixed IMAGE + VIDEO + DNG items.

**Priority**: HIGH — blocks v2 video generation and the local agent's `assemble_video` tool (IMP-015 R085).

---

### IMP-017: Local Agent — Goose Runtime

**Problem**: The local agent (IMP-015) runs through a custom Python loop. Goose is a production-grade, MCP-native agent runtime that can drive the same `server.py` tools — valuable as an alternate runtime for comparison and learning, and as a quicker on-ramp for new tools.

**Requirements**:
- R094: Install Goose on the Mac Mini and configure the Ollama provider (`qwen3:14b`).
- R095: Register `setup/local-agent/server.py` as a stdio MCP extension in Goose (`~/.config/goose/config.yaml`).
- R096: Validate the same workflow (search → create project → set timeline) through Goose + Ollama, and compare behavior/quality against the custom loop.

**Status**: Parked / next. Steps are ready in the Phase 1 plan (Task 7): `docs/superpowers/plans/2026-06-06-local-llm-agent-phase1.md`.

**Priority**: LOW — the custom loop (the end-goal runtime) already works end-to-end; this is an alternate runtime.

---

### IMP-014: Duplicate Detection

**Problem**: The photo library contains duplicate or near-duplicate photos from multiple sources: iCloud Shared Library creates copies (files with `(1)` suffix), Google Takeout may contain the same photos, and burst shots produce near-identical images. Users see duplicates in the selection UI and the AI includes them in clips.

**Requirements**:
- R073: Detect exact duplicates by file checksum (MD5/SHA256). Keep one, mark others as duplicates.
- R074: Detect near-duplicates by thumbhash Hamming distance (threshold ≤ 3 bits) or perceptual hash. Keep the highest quality version.
- R075: Phase 1 — photos only. Phase 2 — extend to videos (compare first frame or file hash).
- R076: During scene discovery, automatically hide duplicates from the selection UI. Show count: "5 duplicates hidden."
- R077: User can view hidden duplicates if they want to override the auto-selection.
- R078: In the generated clip, never include two versions of the same photo.

**Status**: PARTIAL. Burst grouping **by time** is implemented (`score_and_select.py::detect_bursts`, shots ≤5s apart). **Not done**: near-duplicate by visual similarity (R074 — `thumbhash` is fetched in `enrich_assets` but never compared by Hamming distance) and exact-duplicate by checksum (R073). Best-frame-within-burst selection pairs with IMP-022.

**Priority**: MEDIUM — improves selection quality and reduces clutter. Not blocking but noticeable with 313 selected items.

---

### IMP-013: Timeline Review Screen (Screen 2)

**Problem**: After selecting content in Screen 1, the user needs a way to review the AI's arrangement and add context that only they know — stories, memories, emotions tied to specific photos. This context is what transforms a slideshow into a story. Screen 1 is for fast selection; Screen 2 is for storytelling.

**User Stories**:

**US1: Review & Annotate (P1)**
- Screen 2 shows only SELECTED items from Screen 1, arranged in timeline order (40-50 items, not 313)
- User can add a voice note or text note per item. Most items get no notes — only the ones with a story.
- Notes are context for the AI: "we were waiting for the passport appointment", "Waymo taxi made an April Fools joke and my kid fell for it", "this was the first time he saw the ocean"
- Notes stored in project.json per asset_id

**US2: AI Interprets Notes (P1)**
- AI reads notes and adjusts the video: pacing (slow for "waiting"), mood (upbeat for "funny joke"), transitions (dramatic for "first time")
- AI can generate text captions from notes — shown over the photo/video in the clip
- AI can suggest sound effects or music mood changes based on note sentiment
- The interpretation is AI-driven, not rule-based — the AI decides how to use each note
- AI can ask: "You mentioned a funny moment — want me to add a caption?"

**US3: Video-Specific Controls (P2)**
- Trim video clips (start/end)
- Speed adjustment (slow-mo, fast)
- Keep/mute audio per clip
- Reorder items by drag-and-drop

**Requirements**:
- R067: Screen 2 shows only SELECTED items in timeline order. Accessible at `/project/{id}/timeline`.
- R068: Per-item voice note (speech-to-text) or text note. Stored in project.json.
- R069: AI reads notes and adjusts pacing, captions, transitions, mood — no fixed rules.
- R070: Video-specific: trim start/end, speed adjustment, keep/mute audio.
- R071: Drag-and-drop reorder.
- R072: Optional — user can skip Screen 2 and go straight to generate from Screen 1.

**Depends on**: IMP-007 (Screen 1 must be working first — DONE).

### IMP-015: Local LLM Agent (Self-Hosted AI Orchestrator)

**Problem**: Today the AI orchestrator is Claude Code + Claude API. Every request that searches photos, builds a timeline, or drives the pipeline depends on the cloud. Goal: a locally hosted LLM that runs the agent loop on the Mac Mini — for learning how agents work end-to-end, privacy (photos/captions never leave the network), and a possible future productization path.

**Approach**: D→A from the spike (`docs/spike/2026-04-27-local-llm-agent-options.md`). Build the tool logic once; run it first under an existing agent (Goose), then under a custom Python loop. The custom loop is the long-term direction (consistent with the "AI as orchestrator" philosophy); Goose is a fast validation runtime.

**Design**: `docs/spike/2026-06-06-local-llm-agent-design.md`. Plan: `docs/superpowers/plans/2026-06-06-local-llm-agent-phase1.md`. Code: `setup/local-agent/`.

**Done (Phase 1 + Phase 1b)**:
- R079: Ollama + `qwen3:14b` on the Mac Mini (Apple M4, 24GB). Tool-calling smoke test passed. (See `setup/local-agent/SETUP-NOTES.md` for the formula+cask runner workaround and `python3.13` requirement.)
- R080: Five agent tools wrapping the v2 engine — `search_photos`, `list_projects`, `create_project`, `get_project`, `set_timeline`. Shared `tools/` core. 14 unit tests.
- R081: MCP server (`server.py`, FastMCP) exposing the 5 tools — ready for any MCP client.
- R082: Custom tool-calling loop (`agent.py`) over Ollama's OpenAI-compatible endpoint. **Validated end-to-end**: a natural-language request searched the real Immich library, created a project, and wrote a positioned timeline to `project.json` — fully local.

**Next (parked / not yet implemented)**:
- R083: **Goose runtime — extracted to its own feature, IMP-017** (parked / next). See IMP-017 for requirements.
- R084: `think=false` tuning for qwen3 — suppress thinking-mode output to cut per-turn latency (~10s warm) and clean tool-call formatting.
- R085: Video assembly via the agent — deferred. Blocked on **IMP-016** (v2 assembler runtime wiring + e2e). Add an `assemble_video` tool once IMP-016 lands; drop the `approved` gate (generate anytime) and add a draft/full quality switch.
- R086: Reintroduce richer capabilities the agent currently omits — narrative/per-scene stories, photo scoring, burst dedup — once the basic loop is proven in daily use.
- R087: Context management in the loop — truncate/summarize old turns as sessions grow (currently relies on compact records + short sessions).

**Priority**: MEDIUM — independent track from the story-engine pipeline. Phase 1 complete; remaining items are enhancements.

---

## Understanding Layer — beyond what Immich extracts

Immich already provides faces/identity, CLIP semantic search, EXIF, and geolocation — **do not rebuild those**. The items below extract signals Immich does *not*. They split into two tracks: a **content-understanding** track (what is happening — VLM + audio, per `docs/model-spec-intelligent-search.md`) and a **quality** track (is this a good shot). Both follow the model spec's **ingest-vs-query split**: heavy models run at ingest (batch, per asset) and write to a FamilyVault index keyed to Immich asset/person IDs; queries hit the precomputed index. Target hardware: M4 Mac Mini (24 GB), models served via Ollama. **Future scaling** (not v1): an optional GPU box (e.g. RTX 3090/4090) for fast whole-library batch captioning and larger VLMs (Qwen3-VL 30B-A3B) — keep the Mini as always-on orchestrator, wake the GPU box only for heavy batch jobs (model spec §8). Full rationale and model choices: `docs/model-spec-intelligent-search.md`.

### IMP-018: VLM Captioning & Extraction (content)

**Problem**: CLIP gives shallow concept matches; it can't describe *what is happening* (activities, context, relationships) and can't read text in an image. This blocks queries like "videos where my son plays piano" and "the photo of the restaurant menu."

**Approach**: VLM captioning per the model spec — **Qwen3-VL 8B (Instruct)** default (~6 GB, Ollama), Qwen2.5-VL 7B / InternVL3 8B as A/B fallbacks. Combines two requested signals: keyframe captioning **and** OCR (the VLM reads text natively — no separate OCR model). **Identity stays with Immich** — the VLM describes "a boy"; Immich knows it's your son (resolve "who" via Immich person IDs; never re-identify with the VLM).

**Technical design**: `docs/superpowers/specs/2026-06-13-imp-018-vlm-captioning-design.md` (photos→Ollama, video→MLX-VLM, SQLite hybrid index with caption embeddings; photos-first phasing; chunked low-mem batch).

**Requirements**:
- R097: Ingest-time VLM captioning — generate a rich natural-language description per photo and per sampled video keyframe. Store captions in the FamilyVault index keyed to the Immich asset ID.
- R098: Video frame handling — sample frames from clips and aggregate per-frame results into a video-level caption/conclusion (the model spec's "video frame handling" pipeline logic; leverage Qwen3-VL text–timestamp alignment for "when" an event occurs).
- R099: OCR — extract visible text (signs, menus, documents) as part of the VLM extraction pass; index it for search.
- R100: Selective/scheduled execution — do not caption the whole library eagerly; caption on a schedule or on first query (heavy batch job, slow-OK at ingest).
- R101: Captions/OCR feed search and (optionally) replace hallucinated captions in timeline output.

**Priority**: HIGH (v1 of the understanding layer per the model spec). Independent track.

### IMP-019: Audio Understanding — Speech + Sound Events (content)

**Problem**: Immich indexes no audio. A still frame can't distinguish *sitting at* a piano from *playing* one — the soundtrack is often the strongest, cheapest confirmation of an activity. Speech is also unsearchable.

**Approach** (model spec §4): Whisper for speech, CLAP for sound events. Both run on the Mini (Whisper Metal-accelerated via whisper.cpp / faster-whisper).

**Requirements**:
- R102: Speech-to-text — transcribe video (and audio) with **Whisper large-v3** (or large-v3-turbo for throughput). Multilingual (EN/RU/UK) so transcripts index in-language. Store per-asset transcript in the index.
- R103: Sound-event detection — **CLAP** audio embeddings searchable by text ("piano music", "applause", "laughter"); run on every video at ingest. (PANNs/YAMNet as fixed-label alternative.)
- R104: Index transcripts + audio tags keyed to Immich asset IDs; expose to search/fusion.
- R105: Runtime budget — Whisper (~2–3 GB) + CLAP (small) resident alongside the VLM within 24 GB (model spec §7).

**Priority**: HIGH (model spec calls audio "required, not optional" for reliable activity search). v2 after IMP-018.

### IMP-020: Signal Fusion & Multilingual Search (integration)

**Problem**: The signals above are only useful when combined. "Son playing piano" = WHO (Immich person) + WHAT (VLM/CLIP) + activity (CLAP/Whisper), ranked by weighted fusion (model spec §5). Also, concept search must work across EN/RU/UK.

**Requirements**:
- R106: Multilingual concept search — switch Immich Smart Search to a **multilingual CLIP** model (Immich ML setting; one-time full re-index). Early config, not a FamilyVault model.
- R107: Fusion ranking — combine Immich identity + CLIP + VLM caption/OCR + audio (Whisper/CLAP) into a single weighted score; weights chosen dynamically by the AI based on available signals (consistent with IMP-006/008 AI-first search).
- R108: Alias/multilingual name mapping — map cross-script/misspelled names (Misha/Миша/Михаил) to one Immich person ID (application logic, not a model).

**Priority**: MEDIUM — ties IMP-018/019 together; depends on at least IMP-018.

### IMP-021: Photo Quality Scoring (quality)

**Problem**: Selection scoring uses only Immich-derivable signals (face count, resolution, CLIP relevance, duration, diversity). It can't tell a sharp, well-exposed, well-composed shot from a soft/blown/accidental one. (R002 listed blur detection as "optional" — never built.)

**Requirements**:
- R109: Blur/sharpness — Laplacian variance on the thumbnail/keyframe; down-rank soft shots. (Fulfills the deferred R002.)
- R110: Exposure — histogram-based under/over-exposure detection; down-rank too-dark/blown frames.
- R111: Composition — basic heuristics (subject placement / rule-of-thirds, horizon) to nudge ranking.
- R112: Aesthetic score — a lightweight aesthetic model (e.g. NIMA / LAION-aesthetic) for a "good photo" signal beyond face count. Run at ingest; store per-asset.

**Priority**: MEDIUM — improves selection quality; independent of the understanding layer.

### IMP-022: Face-Frame Quality — Eyes-Open / Smile / Expression (quality)

**Problem**: When several frames capture the same moment (or a burst), nothing picks the frame where everyone's eyes are open and smiling. Immich gives identity, not per-frame expression quality.

**Requirements**:
- R113: Per-face frame quality — eyes-open and smile/expression detection on detected faces (lightweight CV, e.g. landmark/EAR + a small classifier; or a VLM-assisted check). **Not identity** — Immich owns who; this scores the *frame*.
- R114: Use the signal to pick the best frame within a burst group (works with the existing time-based `detect_bursts`) and to break ties in timeline selection.

**Priority**: MEDIUM — pairs with burst grouping (IMP-014) and quality scoring (IMP-021).

---

## Implementation Order (recommended)

| Priority | Improvement | Status | Rationale |
|----------|------------|--------|-----------|
| 1 | **IMP-001**: Smart Selection | DONE (005) | Core problem fixed |
| 2 | **IMP-003**: Video Quality | DONE (005) | CRF 18, sips 100 |
| 3 | **IMP-009**: Screenshot & Garbage Filtering | DONE (006) | Quick fix, high impact |
| 4 | **IMP-006**: Smart Scene Discovery | DONE (007, 008) | Two-phase pipeline, AI-first search, probe discovery, AI-driven budget |
| 5 | **IMP-012**: Assembler v2 — Model + Cmd Builder | DONE (009) | v2 project model + FFmpeg command builder, unit-tested (library layer) |
| 6 | **IMP-007**: Selection UI (Screen 1) | DONE (010) | SvelteKit PWA, scene browsing, photo grid, select/deselect |
| 6 | **IMP-011**: osxphotos Export Fix | Not started | HIGH — GPS recovery + ProRAW HEIC export + orientation fix |
| 7 | **IMP-010**: iCloud Metadata Sync | Not started | Bridges iCloud curation (favorites, albums, tags) into Immich. Unlocks IMP-008. |
| 8 | **IMP-008**: Favorites Priority | Not started | Leverages user curation — requires IMP-010 to have favorites in Immich |
| 8 | **IMP-002**: Visual Preview | Partial (album works) | Remaining: inline thumbnails on desktop |
| 9 | **IMP-004**: Project File | Absorbed into IMP-007 | Timeline editor features |
| 10 | **IMP-005**: Music & Audio | Deferred | Polish layer |
| — | **IMP-015**: Local LLM Agent | Phase 1 DONE | Independent track. Custom loop works e2e |
| — | **IMP-016**: Assembler v2 — Runtime Wiring & E2E | Not started | HIGH — wire v2 builder into runtime; verify MP4 from v2 project.json. Unblocks IMP-015 R085 |
| — | **IMP-017**: Local Agent — Goose Runtime | Parked / next | LOW — alternate runtime; custom loop already works |
| — | **IMP-018**: VLM Captioning & Extraction (+OCR) | Not started | HIGH — content understanding (Qwen3-VL 8B). v1 of understanding layer |
| — | **IMP-019**: Audio Understanding (Whisper + CLAP) | Not started | HIGH — speech + sound events; "required" for activity search |
| — | **IMP-020**: Signal Fusion & Multilingual Search | Not started | MEDIUM — ties 018/019 together; multilingual CLIP swap |
| — | **IMP-021**: Photo Quality Scoring | Not started | MEDIUM — blur/exposure/composition/aesthetic |
| — | **IMP-022**: Face-Frame Quality (eyes/smile) | Not started | MEDIUM — best-frame selection; pairs with IMP-014 |

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
