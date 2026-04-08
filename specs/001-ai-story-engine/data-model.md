# Data Model: AI Story Engine

## Entities

### Scenario

The central entity. Persisted as `$STORIES_DIR/{scenario-id}/scenario.json`.

**Identity**: `id` — format `{YYYY-MM-DD}-{slug}` e.g. `2026-04-05-edgar-birthday-miami`

**State machine**: `draft` → `reviewed` → `approved` → `generated`

```json
{
  "id": "2026-04-05-edgar-birthday-miami",
  "title": "Edgar's Birthday in Miami",
  "state": "draft",
  "created_at": "2026-04-05T14:30:00Z",
  "updated_at": "2026-04-05T15:00:00Z",
  "request": "Create a story about Edgar's birthday in Miami March 2025",
  "narrative": "A warm spring afternoon in Miami celebrating Edgar's fifth birthday...",
  "items": [ /* ordered array of MediaItem */ ],
  "music": { /* MusicSelection */ },
  "generation": { /* GenerationResult, null if not generated */ },
  "config": {
    "stories_dir": "/Volumes/HomeRAID/stories",
    "immich_url": "http://immich-immich-server-1.orb.local",
    "max_items": 60,
    "image_duration_s": 4,
    "fade_duration_s": 1,
    "output_resolution": "1920:1080",
    "transition": "fade"
  }
}
```

---

### MediaItem

An ordered entry in a scenario. References an Immich asset by ID.

```json
{
  "position": 1,
  "asset_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "IMAGE",
  "original_filename": "IMG_4521.HEIC",
  "mime_type": "image/heic",
  "caption": "Edgar blowing out the candles",
  "date": "2025-03-15T14:30:00",
  "location": "Miami, FL",
  "people": ["Edgar", "Alice"],
  "duration_s": 4,
  "selection_rationale": "Key moment — birthday cake"
}
```

For VIDEO type, `duration_s` is set from `asset.duration` (native clip length).

**Constraints**:
- `position` is 1-based, unique within scenario
- `asset_id` must resolve to an asset in Immich at generation time
- Maximum 60 items per scenario (SC-001, edge case spec)

---

### MusicSelection

```json
{
  "type": "bundled",
  "path": "/path/to/setup/story-engine/music/upbeat/track1.mp3",
  "name": "Summer Breeze",
  "mood": "upbeat",
  "duration_s": 180
}
```

Or user-supplied:
```json
{
  "type": "user",
  "path": "/Users/szelenin/Music/vacation-song.mp3",
  "name": "vacation-song.mp3",
  "mood": null,
  "duration_s": null
}
```

Or skipped:
```json
{
  "type": "none"
}
```

---

### GenerationResult

Added to scenario after video generation completes.

```json
{
  "output_path": "/Volumes/HomeRAID/stories/2026-04-05-edgar-birthday-miami/output.mp4",
  "duration_s": 47,
  "file_size_bytes": 52428800,
  "generated_at": "2026-04-05T16:00:00Z",
  "attempts": 1,
  "ffmpeg_log": "/Volumes/HomeRAID/stories/2026-04-05-edgar-birthday-miami/ffmpeg.log"
}
```

---

## Filesystem Layout

```text
$STORIES_DIR/                                   # default: /Volumes/HomeRAID/stories/
└── 2026-04-05-edgar-birthday-miami/
    ├── scenario.json                           # Full scenario state
    ├── output.mp4                              # Generated video (if state=generated)
    └── ffmpeg.log                              # Generation log (if generated)
```

Temp files during assembly (cleaned up after generation):
```text
/tmp/story-{scenario-id}/
├── 001_IMG_4521.jpg       # HEIC→JPEG converted (sips)
├── 002_IMG_4522.jpg
└── 003_clip.mp4           # symlink to original video
```

---

## Validation Rules

| Rule | Where enforced |
|------|---------------|
| `items` length ≤ 60 | `manage-scenario.py` add_item() |
| `position` unique within scenario | `manage-scenario.py` reorder() |
| `asset_id` non-empty UUID | `manage-scenario.py` add_item() |
| `music.path` file exists (if type != none) | `manage-scenario.py` set_music() |
| State transitions only forward (`draft→reviewed→approved→generated`) | `manage-scenario.py` set_state() |
| `config.stories_dir` must be writable | `manage-scenario.py` create() |

---

## Config

All configuration via environment variables with defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `IMMICH_URL` | `http://immich-immich-server-1.orb.local` | Immich base URL |
| `IMMICH_API_KEY_FILE` | `/Volumes/HomeRAID/immich/api-key.txt` | API key file path |
| `STORIES_DIR` | `/Volumes/HomeRAID/stories` | Scenario and output storage |
| `FFMPEG_BIN` | `ffmpeg` | FFmpeg binary path |
| `IMAGE_DURATION` | `4` | Seconds each photo is shown |
| `FADE_DURATION` | `1` | Crossfade duration in seconds |
| `OUTPUT_RESOLUTION` | `1920:1080` | Output video resolution |
| `TRANSITION` | `fade` | xfade transition type |
