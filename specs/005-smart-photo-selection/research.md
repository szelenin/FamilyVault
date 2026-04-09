# Research: Smart Photo & Video Selection

## R1: Immich API — Available Metadata for Scoring

**Decision**: Use per-asset detail API (`GET /api/assets/{id}`) to enrich candidates after search.

**Rationale**: Search endpoints (`/api/search/smart`, `/api/search/metadata`) return limited fields — no thumbhash, no people, no detailed EXIF. But the per-asset endpoint returns everything we need:
- `thumbhash` — perceptual hash for visual similarity (burst dedup)
- `people` — array of detected faces with names
- `exifInfo.exifImageWidth/Height` — resolution
- `exifInfo.fNumber`, `exifInfo.iso`, `exifInfo.focalLength` — camera settings
- `type` — IMAGE or VIDEO
- `duration` — for video clips

**Pipeline**: Search (broad, fast) → Enrich top candidates with detail API → Score → Dedup → Select.

**Performance concern**: Asset detail API is 1 call per candidate. For 200 candidates, that's 200 API calls. At ~50ms each (local network), ~10 seconds total. Acceptable within the 60s budget.

**Alternatives considered**:
- Batch asset detail API — not available in Immich v2.6.3
- Use only search response fields — insufficient for scoring (no face count, no thumbhash)

## R2: Burst Detection — Thumbhash vs Timestamp

**Decision**: Use timestamp proximity (< 5 seconds between shots) as the primary burst detector. Use thumbhash Hamming distance as a secondary signal for "similar scene" dedup within a 30-minute window.

**Rationale**: 
- Timestamp is fast and reliable for true bursts (holding shutter button)
- Thumbhash Hamming distance catches visually similar photos that aren't bursts (e.g., 5 sunset photos from slightly different angles over 10 minutes)
- Thumbhash is a base64-encoded perceptual hash — decode to bytes, compute Hamming distance. Threshold ≤ 3 bits = near-duplicate.

**Alternatives considered**:
- CLIP embedding cosine similarity — not available via Immich API for per-asset comparison
- Download thumbnails and compute image hash locally — too slow for 200+ candidates

## R2a: Video Scoring and Search Inclusion

**Decision**: Search without type filter to return both photos and videos. Score videos with a different weight formula than photos. Prefer video over photo when both exist from the same moment.

**Rationale**:
- User expects videos to be ~80% of final clips — they capture action, not just stills
- Videos need different scoring: faces matter less (action shots), duration matters (5-30s sweet spot)
- Photo weights: faces 40%, relevance 30%, diversity 20%, resolution 10%
- Video weights: relevance 40%, duration 25% (5-30s optimal, penalize <2s and >60s), diversity 20%, faces 15%
- When a photo and video are taken within 5 seconds of each other, the video becomes the burst group primary but photos are kept as alternates (user can swap video for photo)
- These are initial defaults — will be tuned during testing

**Alternatives considered**:
- Same weights for photos and videos — doesn't reflect that videos capture motion/action
- User-configurable per-type weights — YAGNI for now, can add if needed

## R3: HEIC Handling — sips Quality

**Decision**: Keep `sips` for HEIC→JPEG conversion but use maximum quality (`-s formatOptions 100`).

**Rationale**:
- FFmpeg on Mac Mini (Homebrew) does NOT have libheif support — cannot decode HEIC natively
- `sips -s format jpeg -s formatOptions 100` produces near-lossless JPEG (quality 100)
- Current code uses default sips quality which is ~80 — this causes visible quality loss
- Alternative: `sips -s format png` for truly lossless, but PNG files are much larger and slower for FFmpeg to process

**Fix**: Change `sips -s format JPEG` to `sips -s format JPEG -s formatOptions 100`.

## R4: FFmpeg CRF and Bitrate for Phone/Laptop Viewing

**Decision**: Use CRF 18 (down from 23) with `-maxrate 10M -bufsize 20M` to cap peak bitrate.

**Rationale**:
- CRF 18 is "visually lossless" for most content
- With still-image crossfade content, CRF 23 produces ~1 Mbps — far too low
- CRF 18 with crossfade content should produce 5-10 Mbps — appropriate for phone/laptop
- maxrate cap prevents file size explosion for high-motion video clips
- 30 fps (not 25) is standard for phone/web content

**Alternatives considered**:
- Two-pass CBR encoding — more complex, not needed for short clips
- HEVC/H.265 — better compression but less compatible with older devices

## R5: Video Clip Handling in FFmpeg

**Decision**: For video clips in the timeline, download the original file, trim with `-ss`/`-to` flags, then concatenate with the still-image xfade pipeline using FFmpeg concat demuxer or filter_complex.

**Rationale**:
- Video clips have audio; photos don't — need to handle audio mixing
- The `xfade` filter works for photo-to-photo transitions
- For photo-to-video and video-to-photo transitions, overlay the transition in filter_complex
- Video audio is preserved; during photo segments, audio is silent (or music if set)

**Approach**: Two-phase assembly:
1. Prepare all segments as individual clips (photos as 4s h264 clips, videos trimmed)
2. Concatenate with transitions using filter_complex

## R6: Preview via Immich Album

**Decision**: Always create an Immich shared album as the preview mechanism, regardless of desktop or mobile. Provide the share link as plain text.

**Rationale**:
- Claude Code doesn't expose an environment variable to detect desktop vs mobile — no reliable way to know
- Immich album works everywhere (phone, laptop, tablet) — user opens the link in any browser
- Simpler than trying to fetch thumbnails and render inline (which may or may not work depending on client)
- Already proven: we used this approach for the v1 video upload share link
- Album is temporary — user can delete after review, or skill can clean up old preview albums

**Alternatives considered**:
- Inline thumbnails in Claude Code terminal — works on desktop only, can't detect if we're on desktop, adds complexity
- Ask user once and remember preference — extra friction, Immich album just works everywhere

## R7: Scene Detection for Budget Allocation

**Decision**: Define a "scene" as a group of photos separated by a gap of ≥ 30 minutes. Count scenes per day, allocate budget proportionally.

**Rationale**:
- 30-minute gap is a standard heuristic in photo management (used by Google Photos, Apple Photos)
- Simple to implement: sort by timestamp, split at 30-min gaps
- No ML or clustering needed — just timestamp arithmetic
- Within each scene, pick the top-scored candidates up to the scene's budget allocation
