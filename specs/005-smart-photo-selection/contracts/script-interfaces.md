# Script Interfaces: Smart Photo & Video Selection

## search_photos.py (MODIFIED)

### New: `search_multi(session, immich_url, queries, date_range, city, country, person_names, limit) → list[dict]`

Issues multiple search queries and merges results into a deduplicated candidate list.

- **Input**: List of query strings, optional date range, location, person filters
- **Output**: List of asset dicts with basic fields (id, type, filename, mime_type, taken_at)
- **Dedup**: By asset_id across all query results

### New: `enrich_assets(session, immich_url, asset_ids) → list[dict]`

Fetches full asset detail for each ID via `GET /api/assets/{id}`.

- **Input**: List of asset UUIDs
- **Output**: List of enriched asset dicts with thumbhash, people, exifInfo, duration
- **Performance**: ~50ms per call, parallelize with ThreadPoolExecutor (max 10 threads)

---

## score_and_select.py (NEW)

### `score_candidates(candidates, must_have_keywords) → list[dict]`

Scores each candidate using the fixed-weight formula. Must-have candidates bypass scoring.

- **Input**: Enriched candidate list, list of must-have keywords
- **Output**: Same list with `score` dict added to each candidate
- **Weights**: faces=0.4, relevance=0.3, diversity=0.2, resolution=0.1

### `detect_bursts(candidates, time_threshold_sec=5) → dict[str, BurstGroup]`

Groups candidates by timestamp proximity.

- **Input**: Candidate list sorted by taken_at
- **Output**: Dict of burst_group_id → {primary, alternates, timestamp_range}

### `detect_scenes(candidates, gap_minutes=30) → list[Scene]`

Splits candidates into scenes by 30-minute time gaps.

- **Input**: Candidate list sorted by taken_at
- **Output**: List of scenes with time_range, candidate_count

### `allocate_budget(scenes, total_budget, overrides) → dict[str, int]`

Distributes total budget across scenes proportionally.

- **Input**: Scenes list, total budget, optional per-scene overrides
- **Output**: Dict of scene_id → allocated item count

### `select_timeline(candidates, burst_groups, scenes, budget_allocation, must_haves) → list[dict]`

Picks the final timeline items respecting budget, diversity, and must-haves.

- **Input**: All scored candidates, burst groups, scenes, budget per scene, must-haves
- **Output**: Ordered timeline items with position, duration, transition

---

## manage_project.py (REPLACES manage_scenario.py)

### `create_project(title, request, search_params, stories_dir) → dict`
### `show_project(project_id, stories_dir) → dict`
### `set_state(project_id, state, stories_dir) → dict`
### `set_candidate_pool(project_id, candidates, stories_dir) → dict`
### `set_timeline(project_id, timeline, stories_dir) → dict`
### `swap_item(project_id, position, new_asset_id, stories_dir) → dict`
### `remove_item(project_id, position, stories_dir) → dict`
### `reorder_items(project_id, new_order, stories_dir) → dict`
### `trim_video(project_id, position, start, end, stories_dir) → dict`
### `set_budget(project_id, total, overrides, stories_dir) → dict`

---

## preview.py (NEW)

### `fetch_thumbnail(session, immich_url, asset_id, dest_dir) → str`

Downloads asset thumbnail to local file.

- **Input**: Immich session, asset ID, destination directory
- **Output**: Path to downloaded thumbnail JPEG
- **Endpoint**: `GET /api/assets/{id}/thumbnail?size=preview`

### `create_preview_album(session, immich_url, asset_ids, title) → dict`

Creates an Immich album with the selected assets and returns album_id + share link.

- **Input**: List of asset IDs, album title
- **Output**: `{album_id, share_key, share_url}`

### `delete_preview_album(session, immich_url, album_id) → None`

Cleans up temporary preview album.

---

## assemble_video.py (MODIFIED)

### Changes:
- CRF 23 → CRF 18
- Add `-maxrate 10M -bufsize 20M`
- 25 fps → 30 fps
- Audio 128k → 192k
- `sips -s format JPEG` → `sips -s format JPEG -s formatOptions 100`
- New: Accept VIDEO type timeline items with trim_start/trim_end
- New: Handle photo-to-video and video-to-photo transitions in filter_complex
