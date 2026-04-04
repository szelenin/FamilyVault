# FamilyVault Story Engine

## The Idea

Your photo library contains thousands of moments — trips, birthdays, holidays, ordinary Tuesdays. The Story Engine turns those moments into narratives: written stories, highlight reels, and video clips — automatically, using AI.

Nobody has built this for self-hosted photo libraries yet. The pieces exist; the assembly doesn't.

---

## How It Works

```
RAID (raw files)
    ↓
Immich (face recognition, CLIP search, GPS, captions)
    ↓
ImmichMCP  ←──── Claude ────→  Story Engine
    ↓                                   ↓
  metadata,                    generates narrative,
  captions,                    selects best shots,
  face IDs,                    assembles clips/reels/stories
  locations
```

The Story Engine doesn't solve image understanding — that's delegated to Immich and existing tools. It takes **already-understood data** and turns it into stories.

---

## Components

### 1. Event Detector
Groups photos into coherent life events automatically.

- Clusters photos by date gaps, GPS location, and people present
- Names events based on location + people + date ("Miami — March 2025", "Edgar's Birthday")
- Handles overlapping events (trip + birthday during trip)
- No manual tagging required

### 2. Caption Ingestion
Pulls rich per-photo descriptions from Immich via MCP.

Leverages existing tools:
- **ImmichMCP** — face IDs, location names, album membership, CLIP semantic tags
- **immich-ai-describe** (Claude backend) — natural language captions per photo/video

No new image understanding needed — reads what's already indexed.

### 3. Shot Selector
Picks the best photos for each scene within an event.

Scoring criteria:
- Sharpness and exposure (EXIF + blur detection)
- Faces visible and eyes open
- Composition (subject centering, rule of thirds)
- Emotional content (from caption — "laughing", "hugging")
- Diversity — avoids selecting 5 nearly identical shots

### 4. Story Generator
Claude reads the event's selected photos, captions, locations, faces, and timeline — then writes a narrative.

Outputs:
- **Written story** — prose narrative with embedded photos ("It started with a flight to Miami. Edgar immediately spotted the pool...")
- **Slide captions** — short per-photo captions for reels
- **Chapter titles** — for longer events broken into scenes

### 5. Media Assembler
Takes selected photos + narrative and produces the final output.

- **Photo story** — HTML/PDF with photos and generated text
- **Slideshow reel** — ffmpeg-based video with transitions and music
- **Short clip** — tighter edit for sharing (30-60 seconds)
- Future: AI video generation (Runway, Kling) for animated transitions

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Photo metadata | ImmichMCP → Claude |
| Per-photo captions | immich-ai-describe (Claude backend) |
| Event detection | Python clustering (DBSCAN on GPS + time) |
| Story generation | Claude API (claude-sonnet) |
| Shot scoring | Python + OpenCV (blur, face detection) |
| Media assembly | ffmpeg |
| Serving | Simple web app or CLI |

All processing runs locally on the Mac Mini (Apple Silicon). No photos leave your network.

---

## What Makes This Different

| Feature | Google Photos | iCloud | Story Engine |
|---------|--------------|--------|-------------|
| Auto-generated stories | Basic "Memories" | Basic "Memories" | Full narrative, your family's voice |
| Custom narrative style | No | No | Yes — prompt tunable |
| Video reels | Auto only | Auto only | Curated + AI-selected shots |
| Runs on your data | No | No | Yes — private, local |
| Extensible | No | No | Yes — open, hackable |

---

## Phased Build Plan

### Phase 1 — Foundation (start here)
- [ ] Connect to ImmichMCP, query photos for a date range
- [ ] Pull captions from immich-ai-describe
- [ ] Basic event detection by date gap
- [ ] Generate a simple written story for one event via Claude API

### Phase 2 — Shot Selection
- [ ] Score photos by sharpness and face quality
- [ ] Select top N photos per event
- [ ] Filter near-duplicates

### Phase 3 — Media Output
- [ ] ffmpeg slideshow from selected photos
- [ ] Embed generated narrative as subtitles or voiceover text
- [ ] Export as MP4

### Phase 4 — Polish
- [ ] Web UI to browse generated stories
- [ ] Style/tone controls ("funny", "sentimental", "documentary")
- [ ] Manual override — accept/reject shots, edit narrative
- [ ] Music selection based on event mood

---

## Open Questions

- Output format priority: written story first, or video reel first?
- Should stories be generated automatically (new event detected → story created) or on demand?
- Voice narration — text-to-speech overlay on reels, or text only?
- Sharing — keep private on home server, or option to export/share?
