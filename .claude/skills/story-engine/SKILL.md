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

1. **Parse the request** — extract:
   - Semantic queries (e.g., "miami trip", "beach vacation")
   - Must-have keywords (e.g., "speed boat, vizcaya garden, sunset" — items after "must have")
   - Person names if mentioned
   - Date range if mentioned (after/before as YYYY-MM-DD)
   - Detect mode: use `detect_mode_from_prompt()` — "trip" (location+date), "person-timeline" (person+time), or "general"

2. **Create project**:
   ```python
   from scripts.manage_project import create_project, set_discovery, set_scene_confirmation
   project = create_project(title="Miami Trip March 2026", request="original prompt",
                            search_params={"queries": [...], "after": "2026-03-28", "before": "2026-04-02"},
                            stories_dir="/Volumes/HomeRAID/stories")
   ```

3. **Phase A — Broad search + Scene Discovery**:
   ```python
   from scripts.search_photos import make_session, search_broad, enrich_assets
   from scripts.score_and_select import (
       filter_garbage, discover_scenes, verify_must_haves,
       detect_mode_from_prompt, extract_must_have_keywords
   )
   session = make_session(immich_url, api_key_file)
   
   # Broad search: CLIP + date range, NO city filter
   assets, raw_count = search_broad(session=session, immich_url=immich_url,
       queries=["miami trip", "speed boat", "vizcaya garden", "sunset"],
       after="2026-03-28", before="2026-04-02")
   
   # If >500 candidates, ask user: proceed or refine?
   if raw_count > 500:
       # Report count and ask user
       pass
   
   enriched = enrich_assets(session, immich_url, assets)
   candidates, filtered, filter_summary = filter_garbage(enriched)
   # Report: "Filtered 5 screenshots, 1 story-engine clip"
   
   # Discover ALL scenes (no budget)
   mode = detect_mode_from_prompt(user_prompt)
   discovery = discover_scenes(candidates, mode=mode)
   
   # Verify must-haves
   must_have_keywords = extract_must_have_keywords(user_prompt)
   if must_have_keywords:
       mh_result = verify_must_haves(must_have_keywords, discovery["scenes"], candidates)
       # Report: "Found: speedboat (Scene 3), vizcaya (Scene 8). Missing: parasailing"
   ```

4. **Create discovery preview album** (one album with ALL content):
   ```python
   from scripts.preview import create_preview_album
   all_asset_ids = [aid for c in candidates for aid in [c.get("asset_id") or c.get("id")]]
   preview = create_preview_album(session, immich_url, all_asset_ids, title="Discovery: Miami Trip")
   discovery["preview"] = {"album_id": preview["album_id"], "share_key": preview["share_key"]}
   set_discovery(project_id, discovery, stories_dir=stories_dir)
   ```

5. **Present ALL scenes to user** — use the prompt to generate labels dynamically:

   Found 268 photos and videos from March 28 - April 2.
   Filtered 8 screenshots, 1 generated clip.
   
   Discovered 12 scenes:
   1. Arrival evening (Mar 28, 7-9pm) — 5 photos, 2 videos · Miami
   2. Morning walk (Mar 29, 8-9am) — 3 photos · Miami
   3. Speedboat tour (Mar 31, 3-4pm) — 8 photos, 6 videos · Miami Beach [MUST-HAVE]
   4. Coconut Grove sunset walk (Mar 31, 6-7pm) — 4 photos, 1 video · Coconut Grove
   5. Vizcaya Gardens (Apr 1, 11am-1pm) — 20 photos, 3 videos [MUST-HAVE]
   6. Passport office (Apr 1, 2-3pm) — 3 photos · Miami [MUST-HAVE]
   ...
   
   Preview all content:
   http://macmini:2283/share/KEY
   
   Say "include all" or select scenes: "include 1,3,4,5,6" or "skip 2"

6. **User confirms scenes** → Phase B:
   ```python
   set_scene_confirmation(project_id, confirmation, stories_dir=stories_dir)
   # Then apply scoring + budget only to confirmed scenes
   from scripts.score_and_select import score_candidates, detect_bursts, allocate_budget, select_timeline
   confirmed_candidates = [c for c in candidates if c meets confirmation criteria]
   scored = score_candidates(confirmed_candidates, must_have_keywords=must_have_keywords)
   bursts = detect_bursts(scored)
   scenes = detect_scenes(scored)
   budget = allocate_budget(scenes, total_budget=10 + 5 * trip_days)
   timeline = select_timeline(scored, bursts, scenes, budget)
   ```

7. **Present timeline and offer refinement**:
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
