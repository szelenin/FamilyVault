# Quickstart: Sync Script Metadata Flags + Consolidation

**Branch**: `014-sync-metadata-flags`

This is a developer quickstart for implementing and validating spec 014.
It assumes the spec, plan, and research files are already read.

---

## Prerequisites

```sh
# 1. Confirm you're on the feature branch
git branch --show-current
# expected: 014-sync-metadata-flags

# 2. Confirm tools are installed
osxphotos --version       # expect 0.75.6+
exiftool -ver             # expect 13.x
bats --version            # expect 1.10+ (or install: brew install bats-core)

# 3. Confirm you have a populated export to test against
ls -la /Volumes/HomeRAID/icloud-export/.osxphotos_export.db
# expected: file exists, sized in MB

# 4. Confirm Photos library is queryable
sqlite3 -readonly "/Volumes/HomeRAID/Photos Library.photoslibrary/database/Photos.sqlite" \
  "SELECT COUNT(*) FROM ZASSET WHERE ZTRASHEDSTATE=0;"
# expected: 80000+
```

---

## Implementation order (test-first per Constitution Principle I)

### Step 1 — Write failing tests first

Create `scripts/tests/sync-metadata.bats` with the 8 scenarios from spec.md
(T1..T8). Create `scripts/tests/helpers.sh` for fixture-discovery utilities.
Create `scripts/tests/run.sh` as the runner entrypoint.

Run them:

```sh
./scripts/tests/run.sh
```

**Expected**: most or all scenarios FAIL on the current export. T1
(favorite-rating), T3 (person-keyword), T4 (album-keyword), T5 (XMP sidecar),
T6 (JSON sidecar), T8 (idempotency post-fix) will fail. T2 (non-favorite
rating=0) and T7 (GPS no-regression) may already pass on some files.

This is the **failing-first** state Constitution I requires. Commit at this
point so the failing-state is checked into git as the test-driving baseline.

### Step 2 — Modify the canonical script

Update `scripts/sync.sh` with the flags from research.md R4:

```sh
osxphotos export "$EXPORT_DIR" \
  --library "$LIBRARY" \
  --directory "{folder_album}" \
  --exiftool --exiftool-option '-m' \
  --sidecar xmp --sidecar json \
  --person-keyword \
  --album-keyword \
  --favorite-rating \
  --update --update-errors \
  --touch-file \
  --fix-orientation \
  --report "$EXPORT_DIR/sync-report-${TIMESTAMP}.csv" \
  --verbose \
  2>&1 | tee "$EXPORT_DIR/osxphotos-sync-${TIMESTAMP}.log"
```

### Step 3 — Delete the deprecated script

```sh
git rm scripts/export-icloud.sh
```

### Step 4 — Update INSTALL.md

Replace any `export-icloud.sh` references in INSTALL.md (Step 1.4) with
`sync.sh`. Document that `sync.sh` is the single canonical entry point.

### Step 5 — Run one full sync to backfill

This is FR-014. Expect 2,000-5,000 files modified (favorites + person tags +
album tags + sidecars). Will take several hours.

```sh
./scripts/sync.sh
```

Monitor:

```sh
tail -f /Volumes/HomeRAID/icloud-export/osxphotos-sync-*.log
```

### Step 6 — Re-run the test suite

```sh
./scripts/tests/run.sh
```

**Expected**: all 8 scenarios PASS, exit 0.

### Step 7 — Idempotency check

```sh
./scripts/sync.sh
# inspect the report:
LATEST_REPORT=$(ls -t /Volumes/HomeRAID/icloud-export/sync-report-*.csv | head -1)
grep -c "^updated\|^exported" "$LATEST_REPORT"
# expected: 0 (or near 0)
```

### Step 8 — Re-deploy to RAID

```sh
cp scripts/sync.sh /Volumes/HomeRAID/scripts/sync.sh
chmod +x /Volumes/HomeRAID/scripts/sync.sh
```

The launchd job will pick this up at the next 2 AM run.

### Step 9 — Update docs

- `docs/plan.md`: Phase 5 (sync) — note that sync.sh now writes
  favorites/persons/albums/sidecars; reference spec 014 research.
- `INSTALL.md`: confirm Step 1.4 and Step 3 align.

### Step 10 — Commit and merge

```sh
git add scripts/sync.sh scripts/tests/ INSTALL.md docs/plan.md
git rm scripts/export-icloud.sh
git commit -m "feat(014): consolidate sync scripts; add favorite/person/album/sidecar flags"
git push origin 014-sync-metadata-flags
```

Merge to main when test suite passes and one-shot full sync completes.

---

## Testing the failure path

To prove the test suite catches regressions: temporarily remove `--favorite-rating`
from sync.sh, re-run sync, re-run tests. T1 should report FAIL with a clear
message naming the missing field. Restore the flag.

---

## Rollback

If the change ships and produces unexpected results, the rollback is:

1. `git revert <merge-commit>` on main
2. `cp scripts/sync.sh /Volumes/HomeRAID/scripts/sync.sh` to redeploy the
   pre-feature script
3. The metadata written into files during this feature stays — it's correct,
   just no longer being maintained. The next osxphotos full re-export
   would clear the new tags only if you forced it.

No data loss path exists. The change is additive.
