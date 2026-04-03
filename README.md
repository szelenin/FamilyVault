# FamilyVault

> Your family's memories, privately owned, permanently stored.

## Why

Every photo you take on your iPhone lands in iCloud. Every photo you share ends up in Google Photos. Your family's most precious memories are scattered across corporate servers, subject to pricing changes, policy changes, and account closures.

**You don't own your photos. You rent storage for them.**

FamilyVault changes that. It downloads your entire photo and video library — from iCloud, Google Photos, or both — to a home server you control, organizes everything with full metadata preserved, and keeps it in sync automatically. No subscriptions required. No third party between you and your memories.

---

## What It Does

- Downloads your full photo/video library from **iCloud** and/or **Google Photos**
- Preserves **all metadata**: EXIF, GPS, dates, albums, faces, Live Photos, edited versions
- Deduplicates across sources — no double copies
- Sets up **ongoing sync** so new photos land on your server automatically
- Optionally deploys **Immich** — a self-hosted Google Photos alternative for browsing and search

---

## Hardware

Designed for:
- **Mac Mini** (Apple Silicon) as the home server
- **12TB RAID1** external storage (~6TB usable, 2.5TB steady-state usage)
- 100+ Mbps home internet connection

The approach is macOS-native and leverages Photos.app + `osxphotos` for iCloud, which gives the best metadata fidelity of any available tool.

---

## AI-Guided Setup

FamilyVault is designed to be set up with the help of an AI assistant. The `CLAUDE.md` file contains a complete guidance prompt — paste it into any AI assistant (Claude, ChatGPT, Gemini, etc.) and it will walk you through the entire process interactively, adapting to your specific hardware, cloud accounts, and preferences.

```
# Clone the repo
git clone git@github.com:szelenin/FamilyVault.git
cd FamilyVault

# Open CLAUDE.md and paste its contents into your AI assistant of choice
# The AI will guide you through the rest
```

---

## Phases

| Phase | What happens |
|-------|-------------|
| 0 | Hardware setup — attach RAID, create folder structure |
| 0 | iCloud Shared Library — merge your family's iCloud libraries into one |
| 1 | iCloud full export — download all originals via `osxphotos` |
| 2 | Google Takeout — download archives, fix metadata, extract unique files |
| 3 | Ongoing sync — daily cron job keeps the server up to date |
| 4 | Immich — self-hosted photo app for browsing and search |
| 5 | Verification and cleanup |

See [`docs/plan.md`](docs/plan.md) for the full detailed plan with commands.

---

## Tools Used

| Tool | Purpose |
|------|---------|
| [osxphotos](https://github.com/RhetTbull/osxphotos) | iCloud/Photos.app export with full metadata |
| [exiftool](https://exiftool.org) | Metadata embedding and verification |
| [rclone](https://rclone.org) | Download Google Takeout from Google Drive |
| [gpth](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper) | Fix Google Takeout metadata |
| [czkawka](https://github.com/qarmin/czkawka) | Fast duplicate detection |
| [Immich](https://immich.app) | Self-hosted photo browsing app |

---

## Scripts

Ready-to-run scripts are in [`/scripts`](scripts/):

| Script | Purpose |
|--------|---------|
| `scripts/export-icloud.sh` | Full + incremental iCloud export |
| `scripts/download-takeout.sh` | Download Google Takeout via rclone |
| `scripts/process-takeout.sh` | Fix metadata and find Google-only delta |
| `scripts/sync.sh` | Daily incremental sync (for cron) |

---

## Storage Budget

| | Size |
|--|--|
| iCloud export (steady state) | ~2 TB |
| Google Takeout archives (temporary) | ~2 TB |
| Immich thumbnails/cache | ~200 GB |
| Peak usage during migration | ~6 TB |
| RAID1 usable capacity | ~6 TB |

---

## License

MIT
