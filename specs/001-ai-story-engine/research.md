# Research: AI Story Engine

## 1. Immich v2.6.3 Search API

### Decision
Use the Immich REST API directly. No MCP intermediary.

### Rationale
All 5 story engine search requirements map cleanly to v2.6.3 endpoints. Community ImmichMCP servers are immature (max 5 GitHub stars, single maintainer).

### Key Endpoints

#### Person lookup (name → UUID)
```bash
GET /api/search/person?name=Alice&withHidden=false
# Returns: array of { id, name, thumbnailPath, ... }
# Usage: extract id from .[0].id
```

#### Semantic / natural language search
```bash
POST /api/search/smart
{
  "query": "birthday party",
  "personIds": ["uuid"],
  "takenAfter": "2025-03-01T00:00:00Z",
  "takenBefore": "2025-03-31T23:59:59Z",
  "type": "IMAGE",
  "page": 1,
  "size": 100,
  "withExif": true
}
# Response: { "assets": { "count": N, "items": [...], "nextPage": "2" } }
```

#### Structured metadata search
```bash
POST /api/search/metadata
{
  "city": "Miami",
  "takenAfter": "2024-06-01T00:00:00Z",
  "takenBefore": "2024-08-31T23:59:59Z",
  "withPeople": true,
  "withExif": true,
  "size": 100
}
```

#### Asset response key fields
```json
{
  "id": "uuid",
  "type": "IMAGE|VIDEO",
  "originalFileName": "IMG_4521.HEIC",
  "originalMimeType": "image/heic",
  "localDateTime": "2025-03-15T14:30:00",
  "duration": "0:00:15.123000",
  "exifInfo": {
    "dateTimeOriginal": "2025-03-15T14:30:00",
    "latitude": 25.7617,
    "longitude": -80.1918,
    "city": "Miami",
    "country": "United States",
    "description": ""
  },
  "people": [{ "id": "uuid", "name": "Edgar" }]
}
```

#### Download original file
```bash
GET /api/assets/{id}/original
# Header: x-api-key: $API_KEY
# Response: binary stream (name file yourself from originalFileName)
```

### Authentication
Use `x-api-key` header throughout. API key stored at `/Volumes/HomeRAID/immich/api-key.txt`.

---

## 2. FFmpeg Video Assembly

### Decision
Python script (`assemble-video.py`) generates FFmpeg `filter_complex` dynamically and executes via `subprocess`. Hardware acceleration via `h264_videotoolbox` on Apple Silicon.

### Rationale
Writing `filter_complex` by hand is error-prone for variable-length slideshows. Python handles the timing math (xfade offsets) and input list construction cleanly.

### Core FFmpeg Pattern

```python
# For N inputs with crossfade duration F=1s:
# offset[i] = sum(durations[0..i]) - F * (i+1)
# total = sum(durations) - F * (N-1)
```

Scale/pad filter (handles portrait HEIC, landscape JPEG, any aspect ratio):
```
scale=1920:1080:force_original_aspect_ratio=decrease,
pad=1920:1080:-1:-1:color=black,fps=30,format=yuv420p
```

Audio: loop MP3, trim to video duration, fade out last 2s:
```
[N:a]atrim=0:{total},asetpts=PTS-STARTPTS,afade=t=out:st={total-2}:d=2[aout]
```

Encoding:
- **Quality**: `-c:v libx264 -crf 23 -preset medium` (software, consistent quality)
- **Speed**: `-c:v h264_videotoolbox -b:v 4M` (Apple Silicon GPU, ~3x faster, slightly larger)
- **Default**: Use `h264_videotoolbox` on Mac Mini; fall back to `libx264` if unavailable
- **Audio**: `-c:a aac -b:a 192k`

### HEIC Handling
Convert with `sips` before passing to FFmpeg:
```bash
sips -s format jpeg -s formatOptions 90 input.HEIC --out /tmp/story-{id}/converted.jpg
```
Temp dir: `/tmp/story-{scenario_id}/` — created before assembly, deleted after.

### xfade Transitions
Default: `fade` (universal, looks professional). Available options for user customization: `dissolve`, `fadeblack`, `zoomin`, `smoothleft`, `smoothright`.

---

## 3. Scenario File Design

### Decision
One directory per scenario under `$STORIES_DIR/{scenario-id}/`:
- `scenario.json` — full scenario state
- `output.mp4` — generated video (if produced)

### Rationale
Directory-per-scenario allows adding output files, logs, and temp artifacts without cluttering a flat file layout. Simple filesystem operations, no database.

### Scenario ID Format
`{YYYY-MM-DD}-{slug}` e.g. `2026-04-05-edgar-birthday-miami` — human-readable, sortable by date, unique enough for single-user system.

---

## 4. Music Library

### Decision
Bundle 10-20 royalty-free tracks in `setup/story-engine/music/` organized by mood: `upbeat/`, `calm/`, `sentimental/`.

### Sources
- Pixabay Music (pixabay.com/music) — CC0 license, no attribution required
- Free Music Archive (freemusicarchive.org) — CC licenses
- YouTube Audio Library — free for any use

### Mood Categories
| Category | Typical use |
|----------|-------------|
| `upbeat` | Vacations, birthdays, celebrations |
| `calm` | Nature, quiet moments, baby photos |
| `sentimental` | Milestones, graduations, anniversaries |

---

## 5. Alternatives Considered

| Decision | Alternative | Rejected Because |
|----------|-------------|-----------------|
| Direct Immich REST API | ImmichMCP | Immature (5 stars max), fragile dependency |
| Python scripts | Bash only | Complex JSON/API logic too brittle in bash |
| FFmpeg xfade | Simple concat | Abrupt cuts look unprofessional |
| h264_videotoolbox | libx264 only | Apple Silicon GPU gives 3x speedup for SC-003 |
| sips for HEIC | ffmpeg libheif | sips is built-in, no install, proven on macOS |
| File-per-scenario | SQLite | No extra dependency, simpler backup |
