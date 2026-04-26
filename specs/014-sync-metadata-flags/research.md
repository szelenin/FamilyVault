# Phase 0 Research: Sync Script Metadata Flags + Consolidation

**Date**: 2026-04-25 | **Branch**: `014-sync-metadata-flags`

This document captures the technical decisions that came out of Phase 0 research.
Each section uses the format **Decision / Rationale / Alternatives considered**.

---

## R1 — Test framework

**Decision**: bats-core

**Rationale**:
- Already used in this project for `002-immich-setup` (per `CLAUDE.md`'s
  "Active Technologies" list). Reusing it keeps the project's test surface
  homogeneous and avoids a new dependency.
- bats reads naturally for shell-script testing, with `@test` blocks, `setup` /
  `teardown` hooks, and `assert_*` helpers. The test scenarios for this feature
  are inherently "run a shell command, then check the output" — bats's sweet spot.
- bats works fine without root, supports parallel test execution if ever needed,
  and integrates with stdout-friendly CI outputs.

**Alternatives considered**:
- **Plain bash with manual assertions**: works but reinvents bats's reporting,
  setup/teardown, and TAP output. No reason to write less infrastructure.
- **pytest**: would require introducing a Python test layer for what is a
  fundamentally shell-script verification. The metadata read-back is best
  expressed as `exiftool ... | grep -q ...` not as Python.
- **No tests, manual verification**: explicitly rejected by Constitution
  Principle I (test-first, non-negotiable).

---

## R2 — Test fixture selection

**Decision**: Dynamic at test time, queried from Photos.sqlite + .osxphotos_export.db.

**Rationale**:
- The library's UUIDs are private to each install; hardcoded UUIDs in the
  test file would not be portable and would rot as the library changes.
- The test queries Photos.sqlite for "10 favorited photos in shared scope" /
  "10 photos with named persons" / "10 photos in user-created albums" using
  `ORDER BY ZDATECREATED DESC LIMIT 10`. Each run picks a slightly different
  set, but the *predicate* is fixed, which is what matters for regression
  detection.
- The bats test resolves each UUID to its exported file via the export DB,
  then runs `exiftool` on the file. This lets the test work on any clone
  of the project that has a populated export.

**Alternatives considered**:
- **Static UUID list**: portable across runs of the same library only;
  requires per-install setup. Brittle if Photos.app reassigns UUIDs (which
  did happen during the IMP-011 cross-library investigation).
- **Generated fixture export**: build a tiny synthetic library on the fly.
  Possible with osxphotos, but adds 30-60 seconds of setup per test and is
  overkill for the small fixture sets (10 per scenario) needed here.

---

## R3 — How osxphotos picks up metadata-only changes (FR-014 backfill)

**Decision**: Use osxphotos's existing `--update` + the new flags; this triggers
re-export of files whose written-metadata payload differs from the last run.

**Rationale**:
- osxphotos's `--update` already detects when the metadata it would write into
  a file differs from what's tracked in `.osxphotos_export.db`. When we add
  `--favorite-rating`, `--person-keyword`, `--album-keyword` to the flag set,
  osxphotos sees that the *intended* output now includes new fields for many
  files. It treats this as "metadata changed" and re-exports the file.
- Verified empirically: spec 013 research showed that osxphotos `--update`
  with `--exiftool` re-writes EXIF when the underlying metadata changes (the
  100/100 GPS round-trip test was positive).
- For FR-014 ("one full re-run … backfill"), one invocation of the new
  sync.sh against the existing export folder will touch ~1,900 files
  (favorites) + however many photos have person tags + however many are in
  user-created albums. Estimated 2,000-5,000 files modified on this single
  one-shot run.

**Alternatives considered**:
- **`--force-update` or `--ignore-signature`**: would force re-export of
  every file regardless of change. Unnecessary; touches ~80k files for no
  reason; very slow.
- **Custom exiftool batch outside osxphotos**: would bypass osxphotos's
  state tracking and create a divergence between `.osxphotos_export.db`
  and on-disk reality. Hard maintain.

---

## R4 — Exact osxphotos flag set for the canonical sync.sh

**Decision**: The canonical sync.sh runs:

```text
osxphotos export <export-dir>
  --library <library-path>
  --directory "{folder_album}"
  --exiftool --exiftool-option '-m'
  --sidecar xmp --sidecar json
  --person-keyword
  --album-keyword
  --favorite-rating
  --update --update-errors
  --touch-file
  --fix-orientation
  --report <export-dir>/sync-report-<timestamp>.csv
  --verbose
```

**Rationale per added flag**:
- `--favorite-rating` — writes `XMP:Rating=5` for favorites and `XMP:Rating=0`
  for non-favorites (per Q1 clarification). Required by FR-002.
- `--person-keyword` — adds named-person tags to `IPTC:Keywords` and
  `XMP:Subject`. Required by FR-003. Auto-detected unnamed persons are NOT
  included (osxphotos only writes named ones).
- `--album-keyword` — adds album-membership names as keywords. Required by
  FR-004. osxphotos writes user-created albums; smart albums (auto-generated
  like "Last 30 Days") are not exposed via this flag.
- `--sidecar xmp --sidecar json` — produces `.xmp` and `.json` sidecars next
  to each media file. Required by FR-005. osxphotos's default sidecar
  behavior writes a sidecar only when its metadata differs from what's
  already on disk, satisfying Q3 (refresh only when source changed).

**Already-present flags (from current sync.sh) that stay**:
- `--update --update-errors` — incremental + retry previously-failed files
- `--touch-file` — sets mtime to capture date
- `--fix-orientation` — corrects EXIF rotation
- `--exiftool-option '-m'` — ignores minor exiftool warnings

**Alternatives considered**:
- **Drop `--exiftool` and rely solely on sidecars**: simpler from osxphotos's
  perspective, but sidecars only — embedded EXIF would not have the new
  fields. Immich and most photo tools read embedded first; sidecar is
  fallback. Both is the right answer.
- **Use `--keyword-template "{album}"` and `--keyword-template "{person}"`
  instead of `--album-keyword` / `--person-keyword`**: gives more control
  over the keyword format but is more code with no behavioral upside for
  this feature.

---

## R5 — Sidecar refresh semantics

**Decision**: Trust osxphotos's default `--sidecar` behavior.

**Rationale**:
- osxphotos with `--sidecar xmp` (or `--sidecar json`) writes a fresh sidecar
  only when the metadata payload it would write differs from what's already
  on disk. This is exactly the behavior Q3 selected.
- osxphotos uses the `.osxphotos_export.db` to track the last-written sidecar
  signature; a sync run that finds the signature unchanged for a file leaves
  the sidecar in place and does not touch its mtime.
- This matches FR-006 (idempotency): a re-run with no library changes
  produces zero file modifications including zero sidecar writes.

**Alternatives considered**:
- **Always refresh** (`--force-update` or post-process): unnecessary disk
  churn; daily runs would touch all 80k sidecars every day, triggering
  Immich re-index for no reason.
- **Skip if sidecar exists** (write-once): leaves sidecars stale when
  library metadata changes; defeats the purpose of writing them in the
  first place.

---

## R6 — Tests strategy: how to provide failing tests before implementation

**Decision**: Write the bats tests against the **current** state first; expect
them to FAIL on the existing export (which lacks favorites, person/album
keywords, and sidecars). Apply the sync.sh changes; re-run; expect tests to
PASS. This satisfies Constitution Principle I (test-first) literally.

**Rationale**:
- The current export was produced by the un-fixed sync.sh, so files have NO
  `XMP:Rating`, NO person-keyword, NO album-keyword, NO `.xmp` / `.json`
  sidecars. A test that asks "does this favorited file have `XMP:Rating=5`?"
  reliably fails today. That's the failing-first state.
- After the flag fix and one-shot full sync, the same fixtures get the new
  metadata. Re-running the bats suite then passes.
- This avoids the chicken-and-egg of "write a test for code that doesn't
  exist." The code (osxphotos invocation) exists; only the flag set needs
  changing.

**Alternatives considered**:
- **Write tests against a synthetic mini-library** that already passes,
  then port to production: extra ceremony for no real test coverage win.
- **Skip the failing-first step and write tests after the fix**:
  violates Constitution I.

---

## R7 — Deployment of the canonical sync.sh to /Volumes/HomeRAID/scripts/

**Decision**: Manual `cp` after each repo update, documented in INSTALL.md
Step 3.1 (already does this).

**Rationale**:
- Existing pattern from IMP-011: `cp ~/projects/takeout/takeout/scripts/sync.sh
  /Volumes/HomeRAID/scripts/sync.sh && chmod +x`. The launchd plist points to
  the deployed RAID copy, not the repo copy.
- Adding a deployment automation (post-merge hook, makefile target, cron) for
  a single-file copy violates Constitution IV (YAGNI — abstraction at 1 use
  site, not 3+).
- The single deployment step is documented; if the user changes sync.sh and
  forgets to redeploy, the daily 2 AM run uses the stale copy. Acceptable
  trade-off for a solo project.

**Alternatives considered**:
- **Symlink `/Volumes/HomeRAID/scripts/sync.sh -> ~/projects/takeout/takeout/scripts/sync.sh`**:
  removes the redeploy step but couples the launchd job to the repo location
  and requires the repo to be present and sound at every 2 AM run. Acceptable
  but introduces a coupling that's not currently there.
- **Git hook that auto-cps on each commit**: introduces machinery for a
  one-line operation. YAGNI rejection.

---

## Summary

All technical questions from spec 014 are resolved. No NEEDS CLARIFICATION
items remain. Phase 1 (data-model.md, contracts, quickstart) can proceed.
