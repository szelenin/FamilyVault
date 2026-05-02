# Three-Source Merge Architecture

**Date:** 2026-04-26
**Status:** Phase 1 complete (2026-04-30); Phases 2–4 not yet started
**Supersedes:** Earlier "iCloud as primary" architecture in `docs/plan.md`

## Why we are pivoting

The original FamilyVault architecture (see `docs/plan.md` and `CLAUDE.md`) treated **iCloud as the primary source of truth**: full osxphotos export → Immich External Library pointed at the iCloud filesystem → Google Takeout used only as a one-time delta for the small set of photos absent from iCloud. iCloud held the bytes; Immich was a viewer.

Three findings collected over the previous weeks forced a rethink.

**1. iCloud GPS coverage is structurally poor.** The 2026-04-26 Google-vs-iCloud GPS spike (`scripts/spike_google_icloud_gps/`, results in `docs/spike/`) measured GPS coverage on the user's actual archive:

- Google Takeout sidecars: ~76% have GPS.
- iCloud (`Photos.sqlite` `ZLATITUDE`): ~8.3% have GPS (6,692 of 80,258 assets).
- Root cause: iPhone's Camera-app Location Services was OFF for years, so historical photos have no GPS at the source. iCloud also strips GPS from shared-library "(1)" copies.

Backfilling iCloud GPS from Google was the original plan, but reversing the priority — Google as GPS authority, iCloud as fallback — is dramatically simpler.

**2. Wife uses Apple Photos for manual curation.** Tags, favorites, edits, and album organization happen in Apple Photos, not Google. These are essential metadata for clip-making and have no equivalent in Google Takeout. Whatever architecture wins, it must capture wife's curation as a first-class metadata source.

**3. Cost reconsideration.** $20/mo Google (kept for Gmail) + $30/mo iCloud prompted a question of whether iCloud is worth the additional cost. Given Google's GPS lead and the existence of the Immich mobile app (which can in principle replace iCloud Photos as the phone-sync mechanism), the architecture should be designed so that iCloud is *removable* — kept for now, but possible to drop later without rebuilding.

The pivot: **Immich becomes the canonical store of original photo bytes.** Google Takeout contributes its rich metadata (especially GPS) and historical breadth. iCloud contributes wife's manual curation. The architecture supports **ongoing reconciliation** until iCloud is potentially cut off in the future.

## Spike artifacts

The following files document the GPS measurement that triggered the pivot. Originally developed on branch `spike-google-icloud-gps`, merged to main on 2026-04-26 (commit `236e1a9`). All paths below resolve normally on this branch.

- `docs/spike/2026-04-26-google-vs-icloud-gps-design.md` — spike design doc and hypothesis statement.
- `docs/spike/2026-04-26-google-vs-icloud-gps-plan.md` — phased implementation plan for the spike.
- `docs/spike/2026-04-26-google-vs-icloud-gps-results.csv` — 2,367 candidate match rows with composite confidence.
- `docs/spike/2026-04-26-google-vs-icloud-gps-report.md` — auto-generated baseline summary.
- `docs/spike/2026-04-26-google-vs-icloud-gps-review.csv` — 60 stratified samples for manual review.
- `scripts/spike_google_icloud_gps/` — Python implementation: `parser.py`, `stats.py`, `signals.py`, `matcher.py`, `reporter.py`, `sampler.py`, `__main__.py`.
- `tests/spike_google_icloud_gps/` — 44 unit tests covering parser, stats, signals, matcher, reporter, sampler.

## Architecture

```
                         ┌─────────────┐
                         │   Immich    │  canonical: bytes + merged metadata
                         └──────▲──────┘
                                │
        ┌───────────────────────┼────────────────────────┐
        │ bytes & metadata      │ metadata               │ bytes & metadata
   ┌────┴─────┐           ┌─────┴──────┐           ┌─────┴─────┐
   │  Google  │           │   iCloud   │           │  Immich   │
   │  Takeout │           │  (Photos   │           │  Mobile   │
   │  (zips)  │           │  .sqlite)  │           │  Upload   │
   └──────────┘           └────────────┘           └───────────┘
```

**Bytes** flow into Immich from any of three sources:

- Google Takeout (historical era; primary for the pre-mobile-pilot archive).
- osxphotos export from iCloud (selectively, for photos with edits, Live Photos, or photos that exist only in iCloud).
- Immich mobile app (going forward, for current phone uploads).

**Metadata** is merged into Immich from Google JSON sidecars + iCloud `Photos.sqlite`, applied to whichever Immich asset matches via the identity strategy below.

**Immich's own ML** (face clustering, CLIP) runs on the bytes and contributes additional metadata (people clusters, smart-search embeddings).

## Merge policy (per field)

| Field | Source priority |
|---|---|
| Favorites | iCloud only |
| Tags / keywords | Union (Google ∪ iCloud) |
| GPS | Google → iCloud → embedded EXIF |
| People / faces | Immich clusters; Google/iCloud names map onto them |
| Albums | iCloud only |
| Captions / descriptions | iCloud only |
| Photo taken time | EXIF → Google sidecar → iCloud Photos.sqlite |

**Why GPS is Google-first:** spike showed Google has ~76% coverage vs iCloud's ~8.3%.

**Why iCloud-only fields:** these reflect wife's manual curation, which has no Google equivalent.

**iCloud-cutoff semantics:** when iCloud is dropped later, the iCloud-only fields stop receiving updates. Past contributions persist in Immich (we do not scrub on removal).

## Identity strategy — Strategy D cascade

To link "the same photo" across Google, iCloud, and Immich:

1. **Tier 1 — SHA-256 exact match.** O(1) hash lookup. Catches byte-identical files (Immich-mobile uploads that match an existing Google Takeout file, etc.).
2. **Tier 2 — Filename + photo_taken_time (±24h) + size + dimensions.** All four must agree. Catches the easy iCloud↔Google cases.
3. **Tier 3 — pHash distance ≤ threshold** (only on the residual that didn't match in Tier 1 or 2). Robust to re-encoding, resizing, minor edits, HEIC↔JPEG conversion.

**Why a cascade:** Tiers 1 and 2 are cheap and high-precision. Tier 3 is expensive (~50 ms/photo) but only runs on the ~10% residual. Total one-time cost: ~1.5 hours on Mac Mini. The spike showed that filename-only or filename+date matching alone produces too many false positives because iPhone's IMG_NNNN counter cycles every ~10k photos (422 of 2,367 candidate matches in the spike were false positives by filename alone).

**Date semantics:** the matcher uses **photo_taken_time** (capture date), NOT file modification time. Wife's edits change file mtime but capture date is stable across original and edited versions. This is the key adjustment that lets us link an edited iCloud HEIC to its Google Takeout sibling.

## Edit handling

Wife's edits in Apple Photos are non-destructive (Apple keeps both original and edited). For Immich:

- **Import the edited version only.** This is wife's curated final image and is what clip-making should use.
- **Discard the original.** Apple Photos still holds the original on her iCloud for revisit if needed.
- **On future edit** (sync detects a newer edit), overwrite the Immich asset's bytes with the new edited version.

Result: one asset per photo in Immich, always reflecting the latest edit.

## Provenance — stateless merge

No persistent provenance ledger. Each merge run reads all three sources fresh and recomputes the merged result.

- Per-field merge rules are deterministic, so the output is reproducible from inputs.
- **iCloud removal** = stop running osxphotos. Past iCloud contributions persist in Immich.
- **Tag deletion** in Apple Photos: on next merge run, the tag disappears from the union (it's no longer in either source). Correct behavior.

## Phasing

The architecture decomposes into phases. Each phase produces working, testable software. The 3-source merge is broken into subphases that can be tested on Google-imported assets before iCloud sync is wired up.

### Phase 1 — Google Takeout → Immich import

**Pre-step (1.0): detach the existing iCloud External Library from Immich.** The iCloud filesystem at `/Volumes/HomeRAID/icloud-export/` and the daily `sync.sh` cron stay in place — they continue to be the read source for `Photos.sqlite`-driven metadata in Phase 3. Only Immich's pointer to the iCloud filesystem is removed. This guarantees Phase 1 starts with a clean Immich showing zero iCloud-derived assets, so Google imports can be tested in isolation.

- 1.0 — Detach iCloud External Library in Immich (admin → Libraries → delete the icloud-export entry; bytes on disk are untouched). Confirm Immich asset count drops to ~0.
- 1.1 — Pick tooling (immich-go, gpth + Immich filesystem import, or custom).
- 1.2 — Import the user's Takeout (49 photo-data zips + 1 metadata-HTML zip = 50 total `.zip` files; target ~243k media items per the manifest).
- 1.3 — Verify: photo counts, GPS preservation, sidecar metadata, Live Photo handling.
- **Acceptance:** Immich shows only Google-imported assets, with Google's metadata intact and no iCloud duplicates.

### Phase 1.5 — Immich mobile pilot (1-week test)

- Install Immich mobile app on iPhone.
- Enable background upload to Mac Mini Immich server.
- Leave iCloud Photos ON as a safety net.
- **Acceptance:** 1 week of phone photos uploaded with no losses; dedup against Google-imported assets working.

### Phase 2 — Identity tooling

Build the merge primitive without doing any merging yet.

- Implement Strategy D cascade (SHA-256, filename + capture date + size + dim, pHash on residual).
- Test it against the Google-imported Immich library: re-running Phase 1 must not create duplicates; new mobile uploads must dedup correctly.
- **Acceptance:** given two photo paths, the matcher returns "match" or "no match" with measurable precision/recall on a labeled test set.

### Phase 3 — Metadata merge tool (subphases)

Each subphase adds one metadata field. Each is independently testable on Google-imported photos before iCloud is wired in.

- **3a — GPS merge.** Inputs: Google JSON sidecars. Targets: matched Immich assets without GPS. Test: GPS-less assets get coordinates.
- **3b — Tags / keywords union.** Inputs: Google sidecar `people` + iCloud `Photos.sqlite` person/album/keyword tables. Test: union appears as Immich tags.
- **3c — Favorites.** Inputs: iCloud `ZFAVORITE`. Test: favorited assets get the Immich star.
- **3d — Albums.** Inputs: iCloud album hierarchy. Test: albums recreated in Immich.
- **3e — Captions.** Inputs: iCloud captions. Test: appears in Immich descriptions.
- **3f — People / faces mapping.** (Most complex — defer until 3a-3e are stable.) Inputs: Google `people[].name` + iCloud person tables → mapped onto Immich's face clusters.

### Phase 4 — Cutover decision

After Phases 1-3 work and the Phase 1.5 mobile pilot has proven Immich mobile is reliable:

- Decision: keep iCloud (full $30/mo), downgrade iCloud (e.g., 2 TB tier), or drop iCloud Photos (50 GB minimum for non-photo iPhone backup).
- Whichever choice: continue iCloud sync at chosen cadence until decision day.

## Open research items

These need investigation, not design decisions, before implementation.

1. ~~**Live Photos in Immich.** Does Immich pair HEIC + MOV automatically? Does Google Takeout preserve the MOV? If Immich does not pair them, iCloud osxphotos becomes the Live Photos byte source. Probe required during Phase 1.~~ **RESOLVED (Phase 1, 2026-04-30):** Immich pairs HEIC + MP4 motion photos automatically during metadataExtraction. After the queue drained, ~41k MP4 assets were absorbed into their HEIC Live Photo counterparts (total dropped 207k → 195k). Google Takeout does preserve the MOV/MP4 component. No iCloud byte source needed for Live Photos.
2. **immich-go vs alternatives.** Is immich-go's dedup robust? Does it handle Google Takeout's broken sidecars? Spike: import 100 photos from one zip and verify GPS, tags, datetime survive.
3. **Merge cadence.** Daily 2 AM cron? Continuous? Affects how much delta there is per run.
4. **Two Google accounts.** The user has accounts 1 and 2 in `/Volumes/HomeRAID/google-takeout/`. Phase 1 starts with account 1; account 2 import is a Phase 1 follow-up.
5. **iCloud-only photos (in iCloud, not in Google Takeout).** Phase 3 metadata merge reads `Photos.sqlite` and matches against Immich assets via Strategy D. Any iCloud row that has no Immich match has nowhere to apply its metadata. Two options for Phase 3 design:
   - **Skip:** the photo is not in Immich, so wife's tagging of it is lost.
   - **Selective byte import:** when an iCloud row has no Immich match, import the original bytes from the iCloud filesystem into Immich as a managed asset (not as External Library). This preserves wife's curation but means Immich grows by the iCloud-only count. Recommended.
6. ~~**Live Photos byte source.** If Immich does not pair HEIC + MOV from Google Takeout, the MOV component is lost. Possible fix: selectively import the MOV from the iCloud filesystem (osxphotos-exported) for any photo where the Google import lost it. Decision deferred to Phase 1 research probe.~~ **RESOLVED:** See item 1. Pairing works; no action needed.
