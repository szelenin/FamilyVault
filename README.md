# FamilyVault

> Your family's memories, privately owned — and brought to life by AI.

---

## The Idea

You have thousands of photos. Most of them sit unseen in iCloud or Google Photos, organized by date, buried under the sheer volume of everything you've ever shot.

FamilyVault is an **agentic system** where an AI assistant owns the entire workflow — from finding your photos to building the final video. You bring the intent. The AI does the rest.

**Example**: You tell the AI *"make a highlight clip of our Miami trip"*. It searches Immich for photos and videos from that period, discovers scenes (airport arrival, pool day, Ocean Drive at night, Edgar's first time in the ocean), scores and ranks content within each scene, opens a mobile UI for you to review and deselect anything you don't want, then assembles a video with crossfade transitions and music — all without you writing a line of code or clicking through a photo app.

The AI guides every step. You make the creative decisions; it handles everything technical.

---

## How It Works

```
You: "Make a clip of our Miami trip"
        ↓
AI searches Immich (CLIP semantic search + GPS + date range)
        ↓
AI discovers scenes, scores photos, filters garbage
        ↓
Mobile UI opens → you review scenes, deselect bad shots, trim videos
        ↓
AI assembles video: crossfades, music, correct orientation
        ↓
"Here's your Miami highlight reel: /Volumes/HomeRAID/stories/miami-2025.mp4"
```

The AI isn't a wrapper around a fixed pipeline. It probes, adapts, asks questions, and picks a different strategy for every request. A birthday clip gets different search logic than a travel recap.

---

## What Runs on Your Server

- **Immich** — self-hosted photo app: face recognition, CLIP semantic search, GPS, smart albums
- **Photo library** — ~2TB of originals, exported from iCloud via `osxphotos` with full metadata
- **Story Engine** — Python scripts the AI invokes to search, score, select, and assemble
- **Selection UI** — SvelteKit PWA (runs on your phone) for scene review and clip editing
- **FFmpeg** — video assembly: photos, video clips, crossfade transitions, audio mixing

Nothing leaves your network. No subscriptions beyond your hardware.

---

## Running the AI

This project is built for **Claude Code** — Anthropic's CLI that gives Claude direct access to your server via SSH, file system, and terminal. The recommended setup:

```bash
# On your laptop — Claude Code connects to Mac Mini over SSH
claude --ssh macmini
```

Claude reads `CLAUDE.md` (the operating instructions), `INSTALL.md` (the setup guide), and the skill files in `.claude/skills/` — and knows exactly what to do. You just talk to it.

Other options: Claude.ai with MCP tool access, any Claude-compatible agent with code execution, or any AI that can SSH into your server and run commands.

---

## Setup

The `INSTALL.md` file is a structured guide written for AI agents — every step is labeled `[AGENT]` (AI runs it) or `[USER]` (AI tells you what to do). Start a Claude Code session, point it at the repo, and say *"set up FamilyVault"*.

**Migration** (iCloud + Google Photos → RAID): [`docs/plan.md`](docs/plan.md)  
**Installation** (Immich, tools, sync cron): [`INSTALL.md`](INSTALL.md)  
**Google Takeout import**: [`docs/playbooks/google-takeout-import.md`](docs/playbooks/google-takeout-import.md)

---

## Hardware

Tested on:
- **Mac Mini M4** — home server, always-on
- **12TB RAID1** external storage (~6TB usable, ~2.5TB steady-state)
- **100+ Mbps** home internet

The iCloud export path uses `osxphotos` + Photos.app on macOS — the only approach that reliably preserves originals, HEIC, Live Photos, edited versions, and full EXIF in one pass.

---

## Tools

| Tool | Purpose |
|------|---------|
| [osxphotos](https://github.com/RhetTbull/osxphotos) | iCloud full export + incremental sync |
| [exiftool](https://exiftool.org) | Metadata embedding and verification |
| [Immich](https://immich.app) | Self-hosted photo browsing + AI search |
| [FFmpeg](https://ffmpeg.org) | Video assembly — transitions, audio, encoding |
| [SvelteKit](https://svelte.dev) | Mobile UI — scene review and clip editing |
| [rclone](https://rclone.org) | Download Google Takeout from Google Drive |
| [gpth](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper) | Fix Google Takeout metadata |
| [czkawka](https://github.com/qarmin/czkawka) | Duplicate detection across sources |

---

## Storage Budget

| | Size |
|--|--|
| iCloud export (steady state) | ~2 TB |
| Google Takeout archives (temporary) | ~2 TB |
| Immich thumbnails + cache | ~200 GB |
| Peak during migration | ~6 TB |
| RAID1 usable capacity | ~6 TB |

---

## License

MIT
