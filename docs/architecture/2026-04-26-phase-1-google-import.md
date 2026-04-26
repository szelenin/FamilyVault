# Phase 1 Design: Google Takeout → Immich

**Date:** 2026-04-26
**Status:** Design proposed, pending implementation
**Parent design:** [`docs/architecture/2026-04-26-three-source-merge.md`](2026-04-26-three-source-merge.md)
**Manifest oracle:** [`docs/architecture/google-takeout-manifest.json`](google-takeout-manifest.json)

## Goal

Import the user's complete Google Takeout (50 zip files, 2.4 TB, ~243k media items, 138 user albums, ~22 years of history 2004–2026) into a freshly reset Immich instance. After this phase: Immich contains every Google asset with metadata applied (GPS, timestamps, descriptions, favorites, albums) and is ready for Phase 2 (identity tooling) and Phase 3 (iCloud metadata merge).

## Prerequisites locked in parent design

- **Storage roles:** Immich = canonical bytes. Google = metadata + historical breadth. iCloud = wife's curation (Phase 3, not Phase 1).
- **Identity strategy:** Strategy D cascade (deferred to Phase 2 — irrelevant for the import itself; immich-go uses content hashes for dedup).
- **Provenance:** stateless merge, no ledger.

## Architectural decisions for Phase 1

### Tool: immich-go in zip-direct mode

Single-pass import, all 49 photo-data zips (matching `takeout-*-3-*.zip`) passed to `immich-go upload from-google-photos` in one invocation. (The 50th `.zip` in the takeout folder is the small metadata-HTML zip — `archive_browser.html` — which is not photo data; we already extracted the manifest from it.) Per-zip checkpointing is NOT viable — Google scatters sidecars and Live Photo pairs across zip boundaries, and per-zip processing creates orphan sidecars and unpaired motion-photo halves.

immich-go reads zips natively; no extraction step. Server-side hash dedup handles restart-after-crash. `--pause-immich-jobs=true` defers Immich's metadata/thumbnail/ML jobs until upload completes so the upload pipe gets full CPU.

### Storage layout: only originals on RAID

Mac Mini local disk gets everything except the original photo/video bytes.

| Path on Mac Mini internal SSD | Container target | Purpose |
|---|---|---|
| `/Users/szelenin/immich-data/upload/` | `/usr/src/app/upload` | Parent of thumbs/, encoded-video/, profile/, backups/, in-flight upload/ |
| `/Users/szelenin/immich-data/postgres/` | `/var/lib/postgresql/data` | Immich DB |
| `/Users/szelenin/immich-data/model-cache/` | `/cache` | ML model weights (~2 GB) |

| Path on RAID | Container target | Purpose |
|---|---|---|
| `/Volumes/HomeRAID/immich-library/` | `/usr/src/app/upload/library` | Original photo/video bytes — the only thing on RAID |

Docker bind-mount stacking (Docker handles the nested override correctly):

```yaml
volumes:
  - /Users/szelenin/immich-data/upload:/usr/src/app/upload
  - /Volumes/HomeRAID/immich-library:/usr/src/app/upload/library
```

**Internal SSD sizing after Phase 1:**

- thumbs/ ≈ 75 GB (3 sizes × 100 KB × 250k assets)
- postgres/ ≈ 50 GB (250k+ assets, faces, embeddings)
- model-cache/ ≈ 2 GB
- other ≈ 5 GB
- **Total: ~135 GB** out of 247 GB available, ~110 GB headroom

**Video transcoding disabled** in Immich admin settings. Modern browsers play HEVC natively. Transcoding off ⇒ encoded-video/ stays empty ⇒ no surprise 2–4 TB derivative growth on internal SSD. Re-enable case-by-case later if needed.

### Single user

Initial setup creates one admin user (you). Wife user added later if/when iCloud metadata merge needs it.

### DNG: include all, audit after — Option B

The IMP-011 DNG exclusion was driven by an iCloud-specific race condition (Photos.app reported assets "downloaded" before HEIC originals arrived on disk; raw DNG indexed without HEIC sibling appeared dark). That race does not exist in static Google Takeout zips.

For Phase 1: import all 1,171 DNG files. Phase 1.5 audit checks each for a HEIC sibling and reports buckets:
- DNG with HEIC sibling → candidate for hide/archive (HEIC is preferred display)
- DNG with no sibling → keep visible (only copy of that photo)

Decision on what to do with each bucket happens after the audit, not in Phase 1.

### Validation oracle: `google-takeout-manifest.json`

Extracted from `archive_browser.html` (the single small zip). Contains:
- Total media count: 242,656 (170k photos + 73k videos, derived by summing extension counts)
- Per-extension counts (HEIC 86353, JPG 57915, PNG 22818, MP4 44249, MOV 28289, DNG 1171, NEF 106, GIF 95, WebP 9, JPEG 1637, AVI 11, 3GP 3)
- 138 user album names (full list)
- 23 year folders (Photos from 2004 through Photos from 2026)
- 203,799 JSON sidecars

Phase 1.5 audit reads this JSON and asserts Immich's actual state matches.

## Phase 0 — Immich reset and storage migration

OrbStack's Immich containers are currently stopped (CPU pressure during prior runs). We start fresh with the new storage layout.

| Step | Action | Verification |
|---|---|---|
| 0.1 | Confirm Immich containers stopped | `docker ps` shows no `immich-*` running |
| 0.2 | Snapshot pre-wipe state to `/tmp/immich-pre-wipe-state.json` (asset count, libraries, users, settings) — for the record only, not for restore | File exists |
| 0.3 | Update `setup/immich/docker-compose.yml` to use new bind-mounts (split RAID library + Mac Mini for everything else). Commit on this branch. | `git diff` clean |
| 0.4 | `mkdir -p /Users/szelenin/immich-data/{upload,postgres,model-cache}` and `mkdir -p /Volumes/HomeRAID/immich-library` | Directories exist with correct permissions |
| 0.5 | `rm -rf /Volumes/HomeRAID/immich/{upload,model-cache,postgres,api-key.txt,library-id.txt}` (entire old `immich/` subtree on RAID) — confirm with user before running | Old paths gone |
| 0.6 | Parse `archive_browser.html` from `takeout-20260403T195541Z-001.zip` → write `docs/architecture/google-takeout-manifest.json`. Commit. | JSON file exists with expected schema |
| 0.7 | Bump OrbStack CPU allocation (Mac Mini → OrbStack settings → at least 8 CPU cores; was the cause of prior pressure) | OrbStack config saved |
| 0.8 | `docker compose -f setup/immich/docker-compose.yml up -d` | All services healthy via `docker ps` |
| 0.9 | Web UI initial setup (browser → http://macmini:2283): create single admin user, generate API key, save to `/Users/szelenin/immich-data/api-key.txt`. **Disable video transcoding** (admin → Settings → Video Transcoding → Disabled). | API key works against `/api/server/statistics`; statistics returns `photos: 0, videos: 0` |

## Phase 1 — Google Takeout import

| Step | Action | Verification |
|---|---|---|
| 1.1 | Install immich-go on Mac Mini (`brew install immich-go` or download release) | `immich-go --version` works |
| 1.2 | Pre-flight: confirm RAID free space ≥ 3 TB; confirm Immich healthy; confirm `archive_browser.html` matches the zips on disk (count files in zips, compare to manifest JSON) | All checks pass |
| 1.3 | Run import in a `tmux`/`screen` session to survive SSH drops. Single command, all 49 photo-data zips: `immich-go upload from-google-photos --server=http://macmini:2283 --api-key=$(cat ~/immich-data/api-key.txt) --concurrent-tasks=4 --client-timeout=60m --pause-immich-jobs=true --on-errors=continue --session-tag=phase-1-google --log-file=/Users/szelenin/immich-data/immich-go.log /Volumes/HomeRAID/google-takeout/takeout-20260403T195541Z-3-*.zip` (the `-3-*.zip` glob excludes the metadata-only zip). | Command exits with status 0 |
| 1.4 | While 1.3 runs, monitor in a second terminal: poll `/api/server/statistics` and `/api/jobs` every 60s, log to `/Users/szelenin/immich-data/import-progress.log`. | Asset count grows steadily; no sustained job-queue stalls |

**Expected wall time:** 24–48 hours, mostly unattended. Start before a weekend.

**Restart-after-crash policy:** re-run the same `immich-go` command. Server-side hash dedup skips already-uploaded files. Local discovery phase re-runs from scratch (multi-hour cost) — so we want to avoid mid-run crashes if possible.

## Phase 1.5 — Post-import audit

The validation script reads `google-takeout-manifest.json` and asserts Immich state matches. Goes in `scripts/phase1_audit/audit.py`.

| Check | Manifest source | Immich query | Pass condition |
|---|---|---|---|
| Total asset count | `total_files_in_html - extension_counts.json - extension_counts['no-ext']` ≈ 242,656 | `GET /api/server/statistics` → `photos + videos` | within ±1% (account for genuinely-corrupt files immich-go skipped) |
| HEIC count | `extension_counts.heic` = 86,353 | `POST /api/search/metadata` filtered to `.heic` | within ±1% |
| MP4 count | `extension_counts.mp4` = 44,249 | filtered to `.mp4` | within ±1% |
| Album count | `user_album_count` = 138 | `GET /api/albums` length | exact match |
| Album names | `user_albums` (138 names) | each in `GET /api/albums` response | every manifest album present in Immich |
| Year folders NOT albums | `year_folder_count` = 23 ("Photos from YYYY") | none of these names should appear in `GET /api/albums` | zero matches |
| Year coverage | each of 2004–2026 | assets exist with `localDateTime` in that year | ≥1 asset per year (with allowance for years where Google had nothing) |
| DNG sibling check | `extension_counts.dng` = 1,171 | for each DNG asset, search Immich for HEIC/JPG with same basename | report buckets: DNG-with-sibling, DNG-only |

Audit script outputs a JSON report `/Users/szelenin/immich-data/phase-1-audit-report.json` and prints PASS/FAIL summary. We decide what to do with the DNG-only bucket after seeing the numbers.

## Acceptance criteria for Phase 1

1. Immich asset count is within ±1% of manifest's expected total (~242,656).
2. All 138 user albums exist in Immich with matching names.
3. None of the 23 "Photos from YYYY" folders became Immich albums.
4. Year coverage 2004–2026 confirmed (assets exist for each year).
5. RAID has originals only (`/Volumes/HomeRAID/immich-library/`); all derivative data is on Mac Mini internal.
6. Phase 1.5 audit report committed for the record.
7. Old RAID Immich paths (`/Volumes/HomeRAID/immich/`) removed.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Mid-run crash → multi-hour discovery re-run | Stable power, `tmux` session, RAID health check before start |
| Live Photo pairing bugs (immich-go #1298, #280) | Single-pass import (best chance for pairing); Phase 1.5 reports unpaired count |
| 24–48 h wall time | Schedule start before a weekend; monitor remotely via SSH |
| OrbStack CPU pressure mid-import | `--pause-immich-jobs=true` defers ML; bump CPU allocation in OrbStack settings before starting |
| immich-go silently dropping orphan sidecars | Phase 1.5 GPS-coverage check (compare expected GPS-bearing count from manifest vs Immich) — gross mismatch indicates dropped metadata |
| Internal SSD fills unexpectedly | Pre-flight: confirm 200+ GB free on `/`; transcoding disabled; check `df -h ~/` mid-run |

## Open follow-ups (deferred, NOT in Phase 1 scope)

1. **Live Photos byte source for the cases Google didn't preserve the MOV.** Architecture doc Open Item #6. Decide after Phase 1.5 reports unpaired-asset count.
2. **iCloud-only photos** (in iCloud, not in Google). Architecture doc Open Item #5. Phase 3 design problem.
3. **Wife's user account in Immich.** Add when Phase 3 metadata merge needs it.
4. **Re-enable video transcoding selectively** if specific videos won't play in browser. Address case-by-case.
5. **DNG bucket policy** (hide/delete DNG-with-sibling assets, or keep both). Decide after Phase 1.5 audit numbers.
