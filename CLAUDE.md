# FamilyVault — AI Setup Guide

You are helping a user set up FamilyVault: a self-hosted photo and video archive that downloads their entire family photo library from iCloud and/or Google Photos to a home server, preserves all metadata, and keeps it in sync automatically.

## Design Philosophy — AI-First

**The AI is the orchestrator. Everything else is a tool.**

- The AI (Claude) drives the entire workflow — from understanding intent, to searching photos, to building timelines, to generating video. The AI reasons, decides, adapts, and asks questions.
- **UI is a tool**, not the product. The Selection UI, Immich, and any future screens exist to simplify specific steps that are hard to do in text (browsing photos, selecting content). The AI owns the flow; the UI assists specific steps.
- **Scripts/utilities are data access tools**, not the algorithm. Python scripts fetch data from Immich, run FFmpeg, read/write project.json. The AI decides when and how to use them.
- **project.json is the shared state**. All communication between AI, UI, and scripts flows through the project file. The AI writes to it, the UI reads/writes to it, scripts read from it.
- **The user guides, the AI executes.** The user provides intent ("make a clip of our Miami trip"), makes creative decisions (which scenes, which photos), and adds context (notes, stories). The AI handles everything else — search strategy, scoring, budgeting, assembly, effects.
- **No fixed pipelines.** The AI picks the approach per request. Different prompts get different strategies. The AI can create temporary scripts, adjust parameters, retry with different approaches.

When making design decisions, always ask: "Does this keep the AI as the driver, or does it push intelligence into fixed code?" Choose the former.

## Your role

Guide the user interactively through the entire setup process. Adapt to their specific situation — do not assume anything about their hardware, cloud accounts, or technical experience.

## How to start

Before doing anything, ask the user clarifying questions to understand their setup. Ask **5 questions at a time**, wait for answers, then ask the next 5 if needed. Continue until you have enough clarity to build a tailored plan.

Key things to discover:
- What cloud services do they use? (iCloud, Google Photos, both, others)
- Do they have a family sharing setup? (e.g., spouse/partner with separate account)
- What is their home server hardware and OS?
- What storage do they have available?
- What is their end goal? (archive only, self-hosted photo app like Immich, ongoing sync)
- How important is metadata preservation? (EXIF, GPS, albums, faces, edits)
- What is their internet speed and is it metered?
- Have they tried any export tools before? Any issues?
- One-time migration or ongoing sync?

## Key decisions to guide

### iCloud vs Google Photos as primary source

For iPhone/Mac users: **iCloud is almost always the better primary source.**
- iCloud preserves originals, HEIC, Live Photos, edits + originals, embedded EXIF
- Google Photos API was removed March 2025. Only Takeout works, and it strips EXIF into broken JSON sidecars
- Only iCloud supports automated ongoing sync (via osxphotos --update)

Recommended strategy: **full iCloud export as primary → Google Takeout only for delta (unique files not in iCloud)**

### Family photo libraries

If the user has a spouse/partner with a separate iCloud account: recommend **iCloud Shared Photo Library** (Settings → Photos → Shared Library). This merges both libraries into one, which osxphotos exports in a single pass.

For Google Photos: shared photos from a partner often appear in the user's own library, so one Takeout may be sufficient.

## Phases to guide through

Work through these phases in order. Check off each one as you complete it.

### Phase 0: Hardware
1. Attach and format external storage (APFS recommended for macOS)
2. Create folder structure on the storage volume:
   ```
   /Volumes/<your-raid>/
   ├── icloud-export/
   ├── google-takeout/
   ├── google-processed/
   ├── google-delta/
   └── immich/
   ```
3. Set up iCloud Shared Photo Library if applicable

### Phase 1: iCloud export
1. Move Photos Library to external storage (if internal drive is too small)
2. Enable "Download Originals to this Mac" in Photos.app → Settings → iCloud
3. Wait for full download (can take days for large libraries)
4. Install tools: `brew install exiftool rclone && pip install osxphotos`
5. Run full export:
   ```bash
   osxphotos export /Volumes/<raid>/icloud-export \
     --directory "{folder_album}" \
     --exiftool \
     --sidecar xmp --sidecar json \
     --person-keyword --album-keyword \
     --update --ramdb \
     --touch-file \
     --fix-orientation \
     --exiftool-option '-m' \
     --verbose
   ```
6. Verify: spot-check metadata, albums, Live Photos, file counts

### Phase 2: Google Takeout (if applicable)
1. Request Takeout at takeout.google.com → Google Photos only → 50GB zips → deliver to Google Drive
2. Configure rclone Google Drive remote: `rclone config`
3. Download: `rclone copy gdrive:Takeout /Volumes/<raid>/google-takeout/ --progress --transfers 4 --retries 10`
4. Extract archives, run gpth to fix metadata:
   ```bash
   gpth --input /Volumes/<raid>/google-takeout \
        --output /Volumes/<raid>/google-processed
   ```
5. Use czkawka to find Google-only files (not in iCloud export)
6. Merge delta into main library

### Phase 3: Ongoing sync
Set up a daily cron job or launchd plist:
```bash
osxphotos export /Volumes/<raid>/icloud-export \
  --directory "{folder_album}" \
  --exiftool \
  --exiftool-option '-m' \
  --update --ramdb \
  --touch-file \
  --fix-orientation
```

### Phase 4: Immich (optional)
Install Docker, deploy Immich, point external library at icloud-export/.

### Phase 5: Verify and clean up
- Compare file counts vs cloud
- Spot-check metadata across different years
- Delete Takeout archives from Google Drive
- Decide on cloud subscription cancellation

## Scripts available

Ready-to-run scripts are in the `/scripts` folder. Use them directly or adapt as needed.

## Tips

- Use SSH to manage the home server remotely throughout setup
- Run long operations (iCloud download, osxphotos export, rclone) in the background or in a tmux session
- Always verify before deleting cloud copies
- Track progress through the phases with a task list
- Google Takeout takes 2-5 days to prepare — submit it early and work on other phases while waiting

## Active Technologies
- Bash (macOS-native, no runtime dependency) + Docker Compose (via OrbStack), Immich v2.6.3, bats-core (testing) (002-immich-setup)
- PostgreSQL (managed by Immich Docker Compose), Redis, files on `/Volumes/HomeRAID/immich` (002-immich-setup)
- Python 3.13 (on Mac Mini) + Bash (Claude Code skills) + FFmpeg 7+ (Mac Mini, brew), Immich REST API v2.6.3, `sips` (built-in macOS), `pytest` 8+ (001-ai-story-engine)
- Files on `/Volumes/HomeRAID/stories/` (configurable via `STORIES_DIR` env var) (001-ai-story-engine)
- Python 3.13 (on Mac Mini) + Bash (Claude Code skills) + Immich REST API v2.6.3, FFmpeg 8+ (via Homebrew), `sips` (macOS native for HEIC), `pytest` 8+ (005-smart-photo-selection)
- Files on `/Volumes/HomeRAID/stories/` (project files, candidate pools) (005-smart-photo-selection)
- Python 3.13 (Mac Mini) + Python 3.9 (local tests) + None new — operates on enriched candidate dicts from existing pipeline (006-screenshot-filter)
- N/A — filter is stateless, operates in-memory (006-screenshot-filter)
- Python 3.13 (Mac Mini) + Python 3.9 (local tests) + Immich REST API v2.6.3 (search/smart, search/metadata, assets/{id}) (007-smart-scene-discovery)
- Project files on `/Volumes/HomeRAID/stories/` (007-smart-scene-discovery)
- Python 3.13 (Mac Mini) for utilities, SKILL.md (natural language) for the AI workflow + Immich REST API v2.6.3, existing utility functions from 005/006/007 (008-intelligent-search)
- Python 3.13 (Mac Mini) + Python 3.9 (local tests) + FFmpeg 8+ (HEVC decode, xfade, audio mixing), sips (DNG→JPEG), Immich REST API (009-assembler-refactor)
- TypeScript, SvelteKit, Node.js (needs installing on Mac Mini) + SvelteKit, @immich/ui, @vite-pwa/sveltekit, Tailwind CSS (010-selection-ui)
- Reads/writes project.json on filesystem, reads thumbnails from Immich API (010-selection-ui)
- TypeScript, SvelteKit (existing app at `setup/selection-ui/`) + Existing SvelteKit app + Immich API proxy (011-timeline-review)
- project.json — add `scene_notes` dict, `scene_order` array (011-timeline-review)
- TypeScript, SvelteKit (existing app at `setup/selection-ui/`) + Existing SvelteKit app + Immich API proxy + project.json (012-clip-editing)
- project.json — video trim settings (`trim_start`, `trim_end` per asset), deselect from timeline (012-clip-editing)

## Recent Changes
- 012-clip-editing: Full-screen preview, video trim with filmstrip handles, deselect items in timeline expanded view.
- 011-timeline-review: Screen 2 — scene cards with stories, reorder, remove scenes, expandable thumbnail strips.
- 010-selection-ui: SvelteKit PWA at macmini:3000 for scene-based photo/video selection. Browse scenes, tap to select, full-screen preview, video playback, favorites, batch operations.
- 009-assembler-refactor: v2 project.json support, DNG/RAW conversion, video clips with audio sync, portrait/landscape orientation, no-crop display.
- 008-intelligent-search: AI-first probe search for date discovery, GPS location expansion, AI-driven budget allocation.
- 007-smart-scene-discovery: Two-phase workflow (discover all → confirm), broad CLIP search, must-have verification.
- 006-screenshot-filter: Multi-signal garbage filtering (screenshots, story-engine clips, non-photo content).
- 005-smart-photo-selection: Quality scoring, burst dedup, scene detection, budget allocation.
- 001-ai-story-engine: Full story engine v1 — search, scenario management, music selection, FFmpeg assembly.
- 002-immich-setup: Bash + Docker Compose (via OrbStack), Immich v2.6.3, bats-core (testing)
