# Story Engine Skill (v2)

You help the user create, refine, and generate family video stories from their Immich photo library using smart photo/video selection with quality scoring and deduplication.

## Environment

- Scripts live at: `~/projects/takeout/takeout/setup/story-engine/scripts/`
- All scripts run on Mac Mini via SSH: `ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/<script>.py ..."`
- Config: `setup/story-engine/config.sh` (source before running, or set env vars)
- Projects stored at: `/Volumes/HomeRAID/stories/{project-id}/project.json`
- FFmpeg: `/opt/homebrew/bin/ffmpeg`
- Story Engine album in Immich: `b613c358-175e-4998-85db-cd968e74abf4`

## US1 — Smart Story Request

**Trigger**: User describes a story in natural language (e.g., "make a clip of our Miami trip. Speed boat, vizcaya garden, sunset must have").

**Workflow**:

1. **Parse the request** — extract from the user's message:
   - Semantic queries (e.g., "miami trip", "beach vacation")
   - Must-have keywords (e.g., "speed boat, vizcaya garden, sunset" — items after "must have")
   - Person names if mentioned
   - Date range if mentioned (after/before as YYYY-MM-DD)
   - City or country if mentioned

2. **Create project**:
   ```python
   from scripts.manage_project import create_project
   project = create_project(title="Miami Trip March 2026", request="original prompt",
                            search_params={"queries": [...], "city": "Miami", ...},
                            stories_dir="/Volumes/HomeRAID/stories")
   ```

3. **Multi-query search** via `search_photos.py`:
   ```python
   from scripts.search_photos import make_session, search_multi, enrich_assets
   session = make_session(immich_url, api_key_file)
   assets = search_multi(session=session, immich_url=immich_url,
                         queries=["miami trip", "speed boat", "vizcaya garden", "sunset"],
                         city="Miami", after="2026-03-28", before="2026-04-02", limit=200)
   enriched = enrich_assets(session, immich_url, assets)
   ```

4. **Score, dedup, select** via `score_and_select.py`:
   ```python
   from scripts.score_and_select import (
       score_candidates, detect_bursts, detect_scenes,
       allocate_budget, select_timeline, extract_must_have_keywords,
       generate_caption
   )
   must_haves = extract_must_have_keywords(user_prompt)
   scored = score_candidates(enriched, must_have_keywords=must_haves)
   bursts = detect_bursts(scored)
   scenes = detect_scenes(scored)
   budget = allocate_budget(scenes, total_budget=10 + 5 * trip_days)
   timeline = select_timeline(scored, bursts, scenes, budget, must_haves=must_have_assets)
   ```

5. **Save to project**:
   ```python
   from scripts.manage_project import set_candidate_pool, set_timeline, set_state
   set_candidate_pool(project_id, scored, stories_dir=stories_dir)
   set_timeline(project_id, timeline, stories_dir=stories_dir)
   set_state(project_id, "selecting", stories_dir=stories_dir)
   set_state(project_id, "previewing", stories_dir=stories_dir)
   ```

6. **Create preview album** and present to user:
   ```python
   from scripts.preview import create_preview_album
   asset_ids = [item["asset_id"] for item in timeline]
   preview = create_preview_album(session, immich_url, asset_ids, title="Preview: Miami Trip")
   ```
   Report to user as plain text (NO markdown wrapping on URLs):

   Here's your selection (15 photos, 3 videos, ~90 seconds):
   Preview album: http://macmini:2283/share/KEY

   Scenes detected:
   1. Airport arrival (2 items)
   2. Speed boat tour (4 items, includes must-have)
   3. Vizcaya Gardens (3 items, includes must-have)
   4. Sunset at beach (2 items, includes must-have)
   5. Dinner (2 items)
   6. Hotel pool (2 items)

   Say "generate" to create the video, or refine:
   - "replace #3" — swap with an alternate
   - "remove #7" — remove an item
   - "more boat tour photos" — increase scene budget
   - "make it shorter" — reduce total items
   - "trim video #4 to first 5 seconds"

**Edge cases**:
- Zero results → tell user what was searched, suggest broader query
- Must-have keyword not found → warn user, try fuzzy variations
- >60 items → budget cap enforced, mention the cap

---

## US2 — Scenario Review and Refinement

**Trigger**: User asks to change the selection (e.g., "replace #3", "remove airport photos", "more sunset").

**Command mapping**:

| User request | Action |
|---|---|
| "Replace #3" | Show 2-3 alternates from burst group, let user pick |
| "Remove #7 and #8" | `remove_item(project_id, 7)`, `remove_item(project_id, 8)` |
| "More boat tour photos" | `set_budget(project_id, overrides={"scene-002": 6})` then re-run `select_timeline` |
| "Make it shorter" / "only 10 photos" | Reduce total budget, re-run selection |
| "Move #5 to position 1" | `reorder_items(project_id, [5,1,2,3,4,...])` |
| "Trim video #4 to first 5 seconds" | `trim_video(project_id, 4, 0.0, 5.0)` |

**After each change**: Re-create preview album and show updated share link.

---

## US3 — Video Generation

**Trigger**: User says "generate", "make it", "go ahead".

**Workflow**:

1. **Advance state to approved**:
   ```python
   set_state(project_id, "approved", stories_dir=stories_dir)
   ```

2. **Run assembly** (the assembler reads the project file timeline):
   ```bash
   ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/assemble_video.py PROJECT_ID --progress"
   ```

3. **On success** — upload to Immich, add to Story Engine album, create share link:

   a. Upload the video:
   ```bash
   ssh macmini "curl -s -X POST http://localhost:2283/api/assets \
     -H 'x-api-key: $(cat /Volumes/HomeRAID/immich/api-key.txt)' \
     -F 'assetData=@/Volumes/HomeRAID/stories/PROJECT_ID/output.mp4' \
     -F 'deviceAssetId=PROJECT_ID' \
     -F 'deviceId=story-engine' \
     -F 'fileCreatedAt=$(date -u +%Y-%m-%dT%H:%M:%SZ)' \
     -F 'fileModifiedAt=$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
   ```

   b. Add to Story Engine album (ID: b613c358-175e-4998-85db-cd968e74abf4):
   ```bash
   ssh macmini "curl -s -X PUT http://localhost:2283/api/albums/b613c358-175e-4998-85db-cd968e74abf4/assets \
     -H 'x-api-key: $(cat /Volumes/HomeRAID/immich/api-key.txt)' \
     -H 'Content-Type: application/json' \
     -d '{\"ids\": [\"ASSET_ID\"]}'"
   ```

   c. Create share link and report:

   Video is ready. Find it in Immich under Albums > Story Engine, or open directly:
   http://macmini:2283/share/KEY

   Duration: 90s | Size: 45 MB | Quality: 1080p CRF 18

   IMPORTANT: Always output the share URL as a bare URL on its own line. Never wrap it in ** or ` characters.

4. **On failure** — show error, retry up to 3x, then surface failure with log path.

---

## Scoring Details

**Photo weights**: faces (40%), content relevance (30%), timestamp diversity (20%), resolution (10%)
**Video weights**: content relevance (40%), duration (25%, sweet spot 5-30s), diversity (20%), faces (15%)

When a photo and video exist from the same moment (within 5 seconds), the video is the default primary pick but the photos are kept as alternates for user swaps.

**Budget formula**: base 10 + 5 per day of trip, capped at 60 items. Distributed proportionally across scenes. User can override per-scene.

**Diversity cap**: No more than 30% of selected items from any single scene.

**Must-haves**: Extracted from prompt (e.g., "speed boat, vizcaya must have"), searched with multiple variations for typo tolerance, guaranteed slots in timeline.
