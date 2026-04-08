# Quickstart: Smart Photo & Video Selection

## Prerequisites

- Mac Mini with Python 3.13, FFmpeg 8+ (`/opt/homebrew/bin/ffmpeg`)
- Immich v2.6.3 running locally
- API key at `/Volumes/HomeRAID/immich/api-key.txt`
- Stories directory at `/Volumes/HomeRAID/stories/`

## Usage via Claude Code Skill

Ask Claude to create a clip:

```
Make a clip of our Miami trip in March. Speed boat, vizcaya garden, sunset must have.
```

The skill will:
1. Parse your request → extract must-haves and search params
2. Search Immich with multiple queries → build candidate pool
3. Score, dedup, detect scenes → allocate budget
4. Present visual timeline preview (thumbnails on desktop, album link on mobile)
5. Wait for your approval or refinement
6. Generate video on approval

## Refinement Commands

```
Replace #3                    → show alternates for position 3
Remove #7 and #8              → remove items, renumber
More boat tour photos         → increase scene budget
Make it shorter               → reduce total budget
Trim video #4 to first 5s    → set trim points
Move #5 to position 2        → reorder
```

## Direct Script Usage (SSH)

```bash
# Multi-query search
ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/search_photos.py \
  --query 'miami trip' --query 'speed boat' --query 'vizcaya garden' \
  --city Miami --after 2026-03-28 --before 2026-04-02 --limit 200"

# Score and select
ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/score_and_select.py \
  PROJECT_ID --must-have 'speed boat' --must-have 'vizcaya garden' --must-have 'sunset'"

# Preview thumbnails
ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/preview.py \
  PROJECT_ID --create-album"

# Assemble video
ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/assemble_video.py \
  PROJECT_ID --progress"
```

## Testing

```bash
# Unit tests (no network)
pytest tests/story-engine/unit/ -v

# Integration tests (requires live Immich)
IMMICH_URL=http://macmini:2283 pytest tests/story-engine/integration/ -v

# E2E test (requires Immich + FFmpeg)
IMMICH_URL=http://macmini:2283 FFMPEG_BIN=/opt/homebrew/bin/ffmpeg \
  pytest tests/story-engine/e2e/ -v
```
