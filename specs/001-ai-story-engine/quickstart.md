# Quickstart: AI Story Engine

## Prerequisites

- Immich running at `http://immich-immich-server-1.orb.local` (or configure `IMMICH_URL`)
- API key at `/Volumes/HomeRAID/immich/api-key.txt`
- FFmpeg installed on Mac Mini: `brew install ffmpeg`
- Stories directory: `mkdir -p /Volumes/HomeRAID/stories`

## Installation

```bash
# On Mac Mini
ssh macmini "
  brew install ffmpeg
  mkdir -p /Volumes/HomeRAID/stories
  pip3 install requests  # only stdlib + requests needed
"
```

## How to Use (Conversational)

Start a conversation with Claude Code (local or mobile client) and describe what you want:

### Create a story
> "Create a story about Edgar's birthday in Miami in March 2025"

Claude will:
1. Search Immich for matching photos/videos
2. Propose an ordered scenario with captions and narrative
3. Ask you to review

### Refine the scenario
> "Remove the airport photos"
> "Make the narrative more fun and lighthearted"
> "Add the photos from the pool"
> "Shorten it to 10 photos max"

### Select music
> "What music do you suggest?"
> "Use the upbeat option"
> "I'll use my own file: /Music/vacation.mp3"
> "Skip music"

### Generate the video
> "Generate the video"
> "Go ahead"
> "Make it"

Claude will run the assembly on the Mac Mini and report the output path.

---

## Scripts (Direct CLI Usage)

### Search for photos
```bash
ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/search-photos.py \
  --query 'birthday party' \
  --person 'Edgar' \
  --after 2025-03-01 --before 2025-03-31"
```

### Create and manage a scenario
```bash
# Create
ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/manage-scenario.py \
  create --title 'Edgar Birthday Miami' --request 'birthday march 2025'"

# List
ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/manage-scenario.py list"

# Add item
ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/manage-scenario.py \
  add-item 2026-04-05-edgar-birthday-miami \
  --asset-id 550e8400-e29b-41d4-a716-446655440000 \
  --caption 'Blowing out the candles'"
```

### Assemble video
```bash
ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/assemble-video.py \
  2026-04-05-edgar-birthday-miami --progress"
```

---

## Configuration

Override defaults via environment variables:

```bash
export IMMICH_URL="http://macmini:2283"
export STORIES_DIR="/Volumes/HomeRAID/stories"
export IMAGE_DURATION=5
export FADE_DURATION=1
export TRANSITION=dissolve
```

Or set in `setup/story-engine/config.sh` for persistent defaults.

---

## Output

Generated video: `/Volumes/HomeRAID/stories/{scenario-id}/output.mp4`

Access from your laptop:
```bash
# Copy to local machine
scp macmini:/Volumes/HomeRAID/stories/2026-04-05-edgar-birthday-miami/output.mp4 ~/Desktop/

# Or watch directly over SMB if RAID is shared
open smb://macmini/HomeRAID/stories/2026-04-05-edgar-birthday-miami/output.mp4
```
