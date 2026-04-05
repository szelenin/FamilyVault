# Script Interface Contracts

The Claude Code agent calls these scripts over SSH. Each script is a CLI tool
with explicit inputs/outputs. This is the contract the tests verify.

---

## search-photos.py

**Purpose**: Query Immich and return matching assets as JSON.

```
python3 search-photos.py [OPTIONS]

Options:
  --query TEXT          Natural language search (CLIP)
  --person TEXT         Person name (resolved to ID via /api/search/person)
  --after DATE          ISO date: takenAfter filter (e.g. 2025-03-01)
  --before DATE         ISO date: takenBefore filter (e.g. 2025-03-31)
  --city TEXT           City filter
  --country TEXT        Country filter
  --type [IMAGE|VIDEO]  Asset type filter (default: both)
  --limit INT           Max results (default: 60)
  --format [json|ids]   Output format (default: json)
```

**Exit codes**:
- `0` — success, results written to stdout
- `1` — Immich unreachable or API error (error message on stderr)
- `2` — no results found (empty array on stdout, message on stderr)

**Output (--format json)**:
```json
[
  {
    "asset_id": "uuid",
    "type": "IMAGE",
    "original_filename": "IMG_4521.HEIC",
    "mime_type": "image/heic",
    "date": "2025-03-15T14:30:00",
    "location": "Miami, FL",
    "people": ["Edgar"],
    "duration_s": null
  }
]
```

**Output (--format ids)**: one UUID per line.

---

## manage-scenario.py

**Purpose**: Create, read, update, and list scenarios.

```
python3 manage-scenario.py COMMAND [ARGS]

Commands:
  create   --title TEXT --request TEXT [--id TEXT]
             → Writes scenario.json, prints scenario ID to stdout

  show     SCENARIO_ID
             → Prints full scenario.json to stdout

  list     [--state draft|reviewed|approved|generated]
             → Prints table: id | title | state | items | created_at

  add-item SCENARIO_ID --asset-id UUID --caption TEXT [--position INT]
             → Adds item to scenario, prints updated item count

  remove-item SCENARIO_ID --position INT
             → Removes item, renumbers positions

  reorder  SCENARIO_ID --positions "1,3,2,4"
             → Reorders items by new position list

  set-narrative SCENARIO_ID --text TEXT
             → Updates narrative field

  set-music SCENARIO_ID --type bundled|user|none [--path TEXT] [--mood TEXT]
             → Sets music selection

  set-state SCENARIO_ID --state reviewed|approved|generated
             → Advances state (forward-only)

  delete   SCENARIO_ID [--confirm]
             → Deletes scenario directory (requires --confirm flag)
```

**Exit codes**:
- `0` — success
- `1` — scenario not found
- `2` — validation error (message on stderr)
- `3` — state transition invalid

---

## assemble-video.py

**Purpose**: Generate MP4 from an approved scenario.

```
python3 assemble-video.py SCENARIO_ID [OPTIONS]

Options:
  --dry-run       Print FFmpeg command without executing
  --progress      Print progress updates to stderr
```

**Preconditions** (validated before starting):
- Scenario state must be `approved`
- All `asset_id` values must resolve in Immich
- Music path must exist (if type != none)
- FFmpeg must be available
- Temp dir `/tmp/story-{id}/` must be writable

**Execution steps**:
1. Download originals for all IMAGE assets via `GET /api/assets/{id}/original`
2. Convert HEIC → JPEG via `sips` for any `image/heic` assets
3. Build FFmpeg `filter_complex` with xfade timing
4. Execute FFmpeg, write to `$STORIES_DIR/{id}/output.mp4`
5. Write FFmpeg log to `$STORIES_DIR/{id}/ffmpeg.log`
6. Advance scenario state to `generated`
7. Clean up `/tmp/story-{id}/`

**Progress output (stderr)**:
```
[1/12] Downloading IMG_4521.HEIC...
[2/12] Converting IMG_4521.HEIC → JPEG...
...
[12/12] Assembling video with FFmpeg...
Done: /Volumes/HomeRAID/stories/2026-04-05-edgar-birthday/output.mp4 (47s, 50MB)
```

**Exit codes**:
- `0` — success, output path printed to stdout
- `1` — precondition failed (message on stderr)
- `2` — FFmpeg error (see ffmpeg.log)
- `3` — download error (asset not available)

**Retry behavior**: Claude Code agent handles retry (up to 3 attempts per FR-012);
the script itself does not retry — it exits with code 2 on FFmpeg failure.
