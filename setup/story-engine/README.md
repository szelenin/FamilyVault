# Story Engine

AI-powered video story creation from your Immich photo library. Uses Claude Code as the conversational interface to search, curate, and assemble family video clips.

## Prerequisites

- Immich running at `http://immich-immich-server-1.orb.local` (or configure `IMMICH_URL`)
- Immich API key at `/Volumes/HomeRAID/immich/api-key.txt`
- FFmpeg 8.x installed on Mac Mini: `brew install ffmpeg`
- Python 3.9+ with `requests`: `pip3 install requests`
- Stories directory: `/Volumes/HomeRAID/stories` (created automatically)

## Installation

```bash
# On Mac Mini
ssh macmini "
  /opt/homebrew/bin/brew install ffmpeg
  mkdir -p /Volumes/HomeRAID/stories
  pip3 install requests
"
```

## How to Use (Conversational)

Start a conversation with Claude Code and describe what you want:

### Create a story
> "Create a story about Edgar's birthday in Miami in March 2025"

Claude will search Immich, select the best photos, propose a scenario with captions and narrative.

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

Claude assembles the MP4 on the Mac Mini and reports the output path.

---

## Scripts (Direct CLI Usage)

All scripts live in `setup/story-engine/scripts/`.

### Search for photos

```bash
python3 setup/story-engine/scripts/search_photos.py \
  --query 'birthday party' \
  --person 'Edgar' \
  --after 2025-03-01 --before 2025-03-31

# Exit 0 → JSON array of assets
# Exit 2 → no results (empty array)
# Exit 3 → error (Immich unreachable, bad API key)
```

Options: `--query`, `--person`, `--after`, `--before`, `--city`, `--country`, `--type IMAGE|VIDEO`, `--limit N`, `--format json|ids`

### Manage scenarios

```bash
# Create
python3 setup/story-engine/scripts/manage_scenario.py \
  create --title 'Edgar Birthday Miami' --request 'birthday march 2025'

# Show
python3 setup/story-engine/scripts/manage_scenario.py show SCENARIO_ID

# List all
python3 setup/story-engine/scripts/manage_scenario.py list

# Add item
python3 setup/story-engine/scripts/manage_scenario.py add-item SCENARIO_ID \
  --asset-id 550e8400-e29b-41d4-a716-446655440000 \
  --caption 'Blowing out the candles'

# Add at position
python3 setup/story-engine/scripts/manage_scenario.py add-item SCENARIO_ID \
  --asset-id UUID --caption 'Caption' --position 1

# Remove item
python3 setup/story-engine/scripts/manage_scenario.py remove-item SCENARIO_ID --position 3

# Reorder (comma-separated new order of current positions)
python3 setup/story-engine/scripts/manage_scenario.py reorder SCENARIO_ID --order 3,1,2

# Set narrative
python3 setup/story-engine/scripts/manage_scenario.py set-narrative SCENARIO_ID \
  --text 'A fun family birthday in Miami...'

# Set music (bundled)
python3 setup/story-engine/scripts/manage_scenario.py set-music SCENARIO_ID \
  --type bundled --mood upbeat --track track1

# Set music (user file)
python3 setup/story-engine/scripts/manage_scenario.py set-music SCENARIO_ID \
  --type user --file /Music/song.mp3

# Skip music
python3 setup/story-engine/scripts/manage_scenario.py set-music SCENARIO_ID --type none

# List bundled tracks
python3 setup/story-engine/scripts/manage_scenario.py list-music

# Advance state
python3 setup/story-engine/scripts/manage_scenario.py set-state SCENARIO_ID --state reviewed
python3 setup/story-engine/scripts/manage_scenario.py set-state SCENARIO_ID --state approved
```

### Assemble video

```bash
# Dry run (print FFmpeg command without executing)
python3 setup/story-engine/scripts/assemble_video.py SCENARIO_ID --dry-run

# Assemble with progress output
python3 setup/story-engine/scripts/assemble_video.py SCENARIO_ID --progress
```

Scenario must be in `approved` state before assembly.

---

## Configuration

Override defaults via environment variables or by editing `setup/story-engine/config.sh`:

| Variable | Default | Description |
|----------|---------|-------------|
| `IMMICH_URL` | `http://immich-immich-server-1.orb.local` | Immich server URL |
| `IMMICH_API_KEY_FILE` | `/Volumes/HomeRAID/immich/api-key.txt` | Path to API key file |
| `STORIES_DIR` | `/Volumes/HomeRAID/stories` | Base directory for scenarios |
| `FFMPEG_BIN` | `ffmpeg` | FFmpeg binary path |
| `IMAGE_DURATION` | `4` | Seconds each image is displayed |
| `FADE_DURATION` | `1` | Crossfade duration in seconds |
| `OUTPUT_RESOLUTION` | `1920:1080` | Output video resolution |
| `TRANSITION` | `fade` | FFmpeg xfade transition type |

```bash
# Source config defaults
source setup/story-engine/config.sh

# Or override inline
IMMICH_URL=http://macmini:2283 IMAGE_DURATION=5 python3 .../assemble_video.py SCENARIO_ID
```

---

## Output

Generated videos: `/Volumes/HomeRAID/stories/{scenario-id}/output.mp4`

```bash
# Copy to local machine
scp macmini:/Volumes/HomeRAID/stories/SCENARIO_ID/output.mp4 ~/Desktop/

# Or open over SMB
open smb://macmini/HomeRAID/stories/SCENARIO_ID/output.mp4
```

---

## State Machine

Scenarios follow a forward-only state progression:

```
draft → reviewed → approved → generated
```

`set-state` rejects backward transitions with exit code 3.

---

## Tests

```bash
# All unit tests (no network required)
python3 -m pytest tests/story-engine/unit/ -v

# Integration tests (requires live Immich)
IMMICH_URL=http://immich-immich-server-1.orb.local \
  python3 -m pytest tests/story-engine/integration/ -v

# E2E test (requires live Immich + FFmpeg on Mac Mini)
python3 -m pytest tests/story-engine/e2e/ -v
```
