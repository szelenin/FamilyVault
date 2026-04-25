# Research: iCloud Shared Library Metadata Propagation

**Date**: 2026-04-25
**Trigger**: User question — does iCloud Shared Library propagate Alice's metadata
to my library automatically?

## TL;DR

**iCloud Shared Photo Library propagates ALL metadata between participants.**
The original premise of spec 013 (*"Alice's metadata, especially GPS, isn't shared
with me"*) is **factually wrong**. Spec 013 in its current form is unnecessary.

The IMP-011 v1 result (37 UUID matches → 24 files updated) was almost certainly a
**sync race condition** — Alice's library happened to have GPS my library hadn't
caught up on yet. Two days later, my library has caught up perfectly.

## Investigation Method

### Hypothesis

If iCloud Shared Library propagates metadata, then for the same set of shared
library photos, Alice's library and my library should have:

1. The **same count** of GPS-having photos
2. The **same count** of favorited photos
3. The **same count** of titled / described photos
4. The **same actual GPS values** on the same photos

If propagation is partial or absent, we'd see counts differ, or we'd find specific
photos where Alice has GPS but I don't.

### Test setup

- **Alice's library**: `/Volumes/HomeRAID/alice/Photos Library.photoslibrary/database/Photos.sqlite`
  (after merging the 39 GB WAL into main DB — see §"WAL caveat")
- **My library**: `/Volumes/HomeRAID/Photos Library.photoslibrary/database/Photos.sqlite`
- **Filter**: shared-library scope only (`ZLIBRARYSCOPESHARESTATE != 0`); excludes
  Alice's personal-only photos (3,897 of them) which don't exist in my library by
  definition.

## Findings

### 1. Metadata counts are identical between libraries (shared scope)

| Metric | My library | Alice's library | Δ |
|--------|-----------|-----------------|---|
| Shared assets | 79,853 | 79,882 | 29 (sync lag) |
| **Shared with GPS** | **6,663** | **6,663** | **0** |
| **Favorited (shared)** | **1,885** | **1,885** | **0** |
| **Title set (shared)** | 0 | 0 | 0 |
| **Description set (shared)** | 223 | 223 | 0 |

### 2. UUIDs differ across libraries even for shared photos

A 50-photo sample of UUIDs from Alice's shared+GPS set: **0/50 found in my
library by UUID**. Each library assigns its own local CoreData identifiers.
The shared photos themselves are the same logical assets (same capture date,
same GPS, same content) but the local row identifiers differ.

This is why `apply-wife-metadata.py` v1 used a date-bridge instead of UUID
match.

### 3. GPS values are byte-for-byte identical (date-bridge sample)

Sampled 30 of Alice's shared+GPS photos by capture date; for each, found the
matching photo in my library by date (within ±0.5s tolerance) and compared
GPS values:

```
30 GPS values IDENTICAL  ← perfect match
 0 differ
 0 missing in mine
```

### 4. Exhaustive coverage check: no gaps in either direction

Took every shared+GPS capture date in each library and computed set differences:

- Shared captures where **Alice has GPS but I don't**: **0**
- Shared captures where **I have GPS but Alice doesn't**: **0**

This is conclusive: there is no GPS gap to fill.

### 5. Library → export file is in sync (no library-vs-file gap)

Sampled 100 random shared+GPS photos from MY library; for each, looked up the
exported file via `.osxphotos_export.db` and read EXIF GPS via exiftool:

```
100 / 100  files have GPS in EXIF
  0 / 100  files missing GPS
  0 / 100  not exported
```

`osxphotos --update --exiftool` (the daily sync via launchd) successfully
re-writes EXIF GPS into export files when the library state changes. There
is no library-vs-export gap either.

## WAL caveat

When this investigation started, Alice's main `Photos.sqlite` was a stale
snapshot from Apr 23. The recent metadata (4,300+ GPS values added over 2 days
via iCloud back-fill) lived in a 39 GB `Photos.sqlite-wal` because Photos.app
was actively writing analysis data and never checkpointed.

**Reading the main DB alone showed only 543 GPS photos**; reading with the WAL
applied shows the true 6,776. Spec 013's earlier reasoning about "Alice has
GPS my library doesn't" was based on the un-checkpointed snapshot, which was
misleading.

After we logged Alice out and applied a `PRAGMA wal_checkpoint(TRUNCATE)`, the
main DB became authoritative (3.0 GB, instant queries) and the comparison
above became possible.

## What back-fills metadata?

iCloud is the source of asynchronous metadata enrichment:

1. **GPS back-fill** — iCloud reverse-geocodes photos using cell-tower data,
   cached lookups, and cross-device hints. When one of Alice's devices resolves
   a location, iCloud propagates that GPS to *all* her synced devices, and
   from there into the shared library on my Mac.
2. **Favorite / title / description** — these are user actions on her devices
   that sync the same way.

By capture year (Alice's library), GPS additions in the last 2 days alone:

| Year | Old DB (Apr 23) | New DB (today) | Added via WAL |
|------|-----------------|----------------|----------------|
| 2026 | 19 | 224 | +205 |
| 2025 | 128 | 1,371 | **+1,243** |
| 2024 | 249 | 1,935 | **+1,686** |
| 2023 | 77 | 1,560 | **+1,483** |
| 2022 | 20 | 1,505 | **+1,485** |

These are existing photos (not new captures) receiving GPS values years after
the photo was taken.

## Implications for spec 013

The current spec is built on a rejected premise. Three sensible responses:

1. **Kill spec 013.** Remove the branch and feature folder; rely on iCloud
   sync + daily `osxphotos --update` for metadata. Keep `apply-wife-metadata.py`
   as it stands (idempotent, no harm running occasionally as a defensive
   bootstrap if a sync race ever happens again).
2. **Repurpose spec 013** to address a different real gap, e.g. Alice's
   *personal-library-only* photos (3,897 of them) that never appear in my
   library at all — but the user already declared this out of scope (Q3 = A,
   shared photos only).
3. **Keep spec 013 as a defensive script** — accept that it should rarely
   touch any file, but exist as a safety net for future sync regressions.

**Recommendation: option 1 — kill spec 013.** iCloud Shared Library does the
work for free. Adding a script we don't need adds maintenance cost without
delivering user value.

## Note on personal-library photos

Alice has 3,897 personal-only photos (not in shared library). These do NOT
sync to my library by design — shared library is opt-in per photo. If we ever
wanted to include those in the home archive, that would be a different
project: it needs to copy media files from her library (which is in
optimize-storage mode, so files aren't even on disk) before any metadata
import would matter.
