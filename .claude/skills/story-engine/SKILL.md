# Story Engine Skill

You help the user create, refine, and generate family video stories from their Immich photo library.

## Environment

- Scripts live at: `~/projects/takeout/takeout/setup/story-engine/scripts/`
- All scripts run on Mac Mini via SSH: `ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/<script>.py ..."`
- Config: `setup/story-engine/config.sh` (source before running, or set env vars)
- Stories stored at: `/Volumes/HomeRAID/stories/{scenario-id}/scenario.json`
- FFmpeg: `/opt/homebrew/bin/ffmpeg`

## US1 — Conversational Story Request

**Trigger**: User describes a story in natural language (e.g., "make a clip of our Miami trip in March 2025").

**Workflow**:

1. **Parse the request** — extract from the user's message:
   - Semantic query (e.g., "birthday party", "beach vacation")
   - Person name if mentioned (e.g., "Edgar")
   - Date range if mentioned (after/before as YYYY-MM-DD)
   - City or country if mentioned

2. **Search Immich** via `search-photos.py`:
   ```bash
   ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/search_photos.py \
     --query 'birthday party' \
     --person 'Edgar' \
     --after 2025-03-01 --before 2025-03-31 \
     --limit 30"
   ```
   - Exit 2 = no results → tell user clearly what was searched, suggest alternatives
   - Exit 0 = results as JSON array

3. **Select top N assets** — from the results JSON, pick the best 10–20 items based on:
   - Variety of moments (not 10 near-identical shots)
   - Key moments first (birthday cake, group shots, smiling faces)
   - Chronological order by `taken_at`

4. **Generate captions and narrative** — for each selected asset write a short caption (1 sentence). Write a 2–3 sentence narrative summary for the overall story.

5. **Create the scenario** via `manage-scenario.py`:
   ```bash
   ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/manage_scenario.py \
     create --title 'Edgar Birthday Miami' --request 'birthday march 2025'"
   ```
   Save the returned `id`.

6. **Add items** — for each selected asset (in order):
   ```bash
   ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/manage_scenario.py \
     add-item SCENARIO_ID \
     --asset-id ASSET_UUID \
     --caption 'Blowing out the candles'"
   ```

7. **Set narrative**:
   ```bash
   ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/manage_scenario.py \
     set-narrative SCENARIO_ID --text 'Edgar celebrated his 5th birthday...'"
   ```

8. **Present to user** — show a table:
   ```
   Scenario: Edgar Birthday Miami (ID: 2025-03-15-edgar-birthday-miami)
   State: draft | Items: 12 | Created: 2025-03-15

   #  | Caption                        | Date       | File
   ---|--------------------------------|------------|----------------------
   1  | Blowing out the candles        | 2025-03-15 | birthday_cake.jpg
   2  | Everyone at the party          | 2025-03-15 | birthday_party.heic
   ...

   Narrative: Edgar celebrated his 5th birthday at a Miami beach house...

   Would you like to refine this scenario, select music, or generate the video?
   ```

**Edge cases**:
- Zero results → tell user what was searched, suggest broader query or different date range
- Vague request matches multiple events → show top 2–3 candidate sets and ask user to choose
- >60 items available → select best 60 and mention the cap

---

## US2 — Scenario Review and Refinement

**Trigger**: User asks to change the scenario (e.g., "remove airport photos", "make it funnier", "add pool photos", "max 10 photos").

**Command mapping**:

| User request | Script command |
|---|---|
| "Remove item at position 3" | `remove-item SCENARIO_ID --position 3` |
| "Remove airport photos" | Search for matching items by caption/filename, then `remove-item` for each |
| "Add pool photos" | Run `search-photos.py --query 'pool'`, select best, `add-item` each |
| "Move photo 5 to position 1" | `reorder SCENARIO_ID --order 5,1,2,3,4,...` |
| "Make it funnier / more upbeat" | Rewrite captions and narrative, then `set-narrative` |
| "Max 10 photos" | `remove-item` for positions 11+ keeping the best 10 |

**After each change**: Show the updated scenario table (re-run `show` to get current state).

---

## US3 — Music Selection

**Trigger**: User asks about music, or after scenario is reviewed.

**Available moods**: upbeat, calm, sentimental (4 tracks each, CC0 royalty-free)

**Workflow**:

1. **Detect mood** from narrative (fun/energetic → upbeat, peaceful/nostalgic → calm/sentimental)
2. **Suggest 2 tracks**:
   ```
   Based on your fun family birthday story, I suggest:
   1. Upbeat / track1 — energetic acoustic, great for celebration montages
   2. Upbeat / track2 — cheerful ukulele, light and playful

   Or say "use my own file: /path/to/song.mp3" or "skip music".
   ```
3. **Set music** based on user choice:
   ```bash
   # Bundled:
   ssh macmini "python3 .../manage_scenario.py set-music SCENARIO_ID --type bundled --mood upbeat --track track1"
   # User file:
   ssh macmini "python3 .../manage_scenario.py set-music SCENARIO_ID --type user --file /Music/song.mp3"
   # Skip:
   ssh macmini "python3 .../manage_scenario.py set-music SCENARIO_ID --type none"
   ```

---

## US4 — Video Generation

**Trigger**: User says "generate", "make it", "go ahead", or similar.

**Workflow**:

1. **Advance state to approved**:
   ```bash
   ssh macmini "python3 .../manage_scenario.py set-state SCENARIO_ID --state reviewed"
   ssh macmini "python3 .../manage_scenario.py set-state SCENARIO_ID --state approved"
   ```

2. **Run assembly** (up to 3 retries on failure):
   ```bash
   ssh macmini "python3 ~/projects/takeout/takeout/setup/story-engine/scripts/assemble_video.py SCENARIO_ID --progress"
   ```

3. **Report progress** — relay FFmpeg progress lines to the user during assembly.

4. **On success** — upload to Immich, add to the "Story Engine" album, and create a share link:

   a. Upload the video:
   ```bash
   ssh macmini "curl -s -X POST http://localhost:2283/api/assets \
     -H 'x-api-key: $(cat /Volumes/HomeRAID/immich/api-key.txt)' \
     -F 'assetData=@/Volumes/HomeRAID/stories/SCENARIO_ID/output.mp4' \
     -F 'deviceAssetId=SCENARIO_ID' \
     -F 'deviceId=story-engine' \
     -F 'fileCreatedAt=$(date -u +%Y-%m-%dT%H:%M:%SZ)' \
     -F 'fileModifiedAt=$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
   ```
   Save the returned `id` field as ASSET_ID.

   b. Add to the "Story Engine" album (album ID: b613c358-175e-4998-85db-cd968e74abf4):
   ```bash
   ssh macmini "curl -s -X PUT http://localhost:2283/api/albums/b613c358-175e-4998-85db-cd968e74abf4/assets \
     -H 'x-api-key: $(cat /Volumes/HomeRAID/immich/api-key.txt)' \
     -H 'Content-Type: application/json' \
     -d '{\"ids\": [\"ASSET_ID\"]}'"
   ```

   c. Create a share link (no expiry):
   ```bash
   ssh macmini "curl -s -X POST http://localhost:2283/api/shared-links \
     -H 'x-api-key: $(cat /Volumes/HomeRAID/immich/api-key.txt)' \
     -H 'Content-Type: application/json' \
     -d '{\"type\": \"INDIVIDUAL\", \"assetIds\": [\"ASSET_ID\"], \"allowDownload\": true}'"
   ```
   Extract the `key` field from the response.

   d. Report to user — output the share URL as plain text with NO markdown formatting (no bold, no backticks wrapping the URL):

   Video is ready. Find it in Immich under Albums > Story Engine, or open directly:
   http://macmini:2283/share/KEY

   Duration: 52s | Size: 4.7 MB

   IMPORTANT: Always output the share URL as a bare URL on its own line. Never wrap it in ** or ` characters. The format must be exactly:
   http://macmini:2283/share/KEY
   with no surrounding markdown.

5. **On failure** — show error from ffmpeg.log, retry automatically (max 3x), then surface failure with log path.
