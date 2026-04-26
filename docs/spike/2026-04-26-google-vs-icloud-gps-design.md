# Spike Design: Google Takeout vs iCloud — GPS Coverage Comparison

**Date**: 2026-04-26
**Status**: Design — implementation not yet started
**Author**: User + Claude (brainstorm)

## Hypothesis

Google's archive contains GPS coordinates for photos that iCloud's archive
does NOT. Reasoning: Google has its own location pipeline (Web/Android
Location History, Maps timeline, cross-account web traffic) that can
back-fill location even when EXIF was stripped. Apple's pipeline only
reads location from the device's Location Services at capture time.

Anecdotal trigger: in the Google Photos mobile app, Map view shows many
photos placed on the map. iCloud's Places view shows fewer.

This spike will prove or reject the hypothesis with one Google Takeout
archive, before committing to processing all 50 archives.

## Scope

### In scope

- Extract one Takeout archive (`takeout-20260403T195541Z-001.zip`,
  account 1, the smallest / first one)
- Parse all `.json` sidecars in the extracted archive
- Run a fixed list of matching algorithms against the iCloud library
- Compute per-signal scores AND a composite confidence per match
- Produce a per-photo output table
- Conduct stratified manual review of ~100 entries
- Quantify the GPS gap: "Of N photos in this Takeout, X have GPS that
  iCloud lacks"

### Explicitly out of scope (this spike)

- Back-filling iCloud export files with Google's GPS — that becomes a
  separate spec if the gap is meaningful
- Running on more than one archive — extend in a follow-up only if Phase A
  doesn't reject the hypothesis
- Account 2 (the wife's Google account) — defer until Account 1 result
  is in
- Videos — focus on still photos for the spike; videos use different
  EXIF/QuickTime tag layouts that complicate matching

## Pipeline

### Phase A — Pre-flight sanity (no matching, ~30 min)

Sequential steps; each produces input for the next.

| # | Step | Notes |
|---|------|-------|
| A1 | Extract `takeout-...001.zip` to `/Volumes/HomeRAID/google-extracted/account1/` | Existing playbook directory |
| A2 | Parse all `*.json` sidecars into an in-memory dict keyed by Google's `title` | Standard Google Takeout JSON shape |
| A3 | Compute baseline stats: total photos / videos; # with `geoData` lat/lon set; # where `geoData` differs from `geoDataExif` (= Google's net contribution beyond original EXIF) | Cheap, all in-memory |
| A4 | Decision gate: if `geoData ≈ geoDataExif` for everything, hypothesis is rejected. Write spike report and stop. Otherwise proceed to Phase B+C. | This is the cheapest possible exit |

### Phase B+C — Per-photo evaluation (~1–2 hours, merged)

For each Google photo:

1. Find candidate iCloud matches via filename lookup. May yield 0..N candidates.
2. For each candidate (or once for "no candidates"), evaluate **every** signal independently. Skip a signal **only** when it is provably useless (e.g., sha256 on a clearly compressed copy); record the skip explicitly so it is visible in the table.

The signal set:

| ID | Signal | Computation | When to skip |
|----|--------|-------------|--------------|
| s1 | `name_match` | Lowercased filename equality | never |
| s2 | `date_diff_seconds` | absolute difference in capture timestamps | never |
| s3 | `size_match` | `abs(google_size - icloud_size) / icloud_size <= 0.01` | never |
| s4 | `dim_match` | width × height equal | never (read from EXIF; cheap) |
| s5 | `is_original` | derived from s3 + s4: True / False / Unknown | always computed |
| s6 | `hash_db_match` | osxphotos `ZORIGINALSTABLEHASH` lookup against Google file's hash | skip when `is_original = False` (guaranteed mismatch) |
| s7 | `sha256_match` | byte-for-byte SHA-256 equality | skip when `is_original = False` (guaranteed mismatch) |
| s8 | `phash_distance` | perceptual hash Hamming distance | never (works on both originals and compressed) |
| s9 | `composite_confidence` | weighted sum over s1..s8 (formula below) | never |

#### Composite confidence formula

Initial proposal — refined after manual review (Phase D) finds the right weights:

```
confidence = clamp(
  +0.10 * s1                       # filename match
  +0.15 * (1 - min(1, s2/2))       # capture date within ±2s saturates to full credit
  +0.10 * s3                       # size match
  +0.10 * s4                       # dimension match
  +0.30 * s6                       # hash_db
  +0.30 * s7                       # sha256 (overlaps with s6 since both are byte-identical signals;
                                   #         in practice both fire together for originals)
  +0.20 * (1 - min(1, s8/8))       # phash distance ≤ 8 = saturates to full credit
  - 0.30 if any positive signal contradicts another
, 0, 1)
```

Buckets:
- `0.85 ≤ confidence` → high
- `0.50 ≤ confidence < 0.85` → medium
- `confidence < 0.50` → low
- `confidence == 0` → unmatched (Google-only candidate)

### Phase D — Stratified manual review (~1 hour)

The output table from Phase B+C may have 1,000+ rows. Manual review of all of them is unrealistic. Stratified sample of ~100:

- 30 random **high-confidence** (verifies the formula is not over-rewarding)
- 30 random **medium-confidence** (these need it most)
- All **low-confidence** rows (likely a small set; if >30, sample 30)
- 30 random **unmatched** Google photos (some may genuinely belong; spot-check)

For each sampled row, the user records: `correct match` | `wrong match` | `should be unmatched`. We then compute the per-bucket precision and update the formula weights if needed.

### Phase E — Decision

Three outcomes:

| Outcome | Trigger | Next step |
|---------|---------|-----------|
| **Hypothesis rejected** | Phase A's `geoData ≈ geoDataExif`, OR Phase B+C produces ~0 high-confidence rows where Google has GPS that iCloud lacks | Close the spike; report findings |
| **Hypothesis confirmed, gap is small** | <500 photos affected | Document but skip back-fill (cost > value) |
| **Hypothesis confirmed, gap is large** | ≥500 photos with high-confidence Google-GPS-but-no-iCloud-GPS | Spawn a separate spec for the back-fill pipeline (extract all 50 archives, run matcher at scale, patch GPS into iCloud export files via direct exiftool — same pattern as `apply-favorites.py`) |

## Output format

### Per-photo evaluation table — `docs/spike/2026-04-26-google-vs-icloud-gps-results.csv`

CSV (markdown table is too large for ~3,000 rows). Columns:

```
google_path
icloud_candidate_uuid
icloud_candidate_path
name_match
date_diff_seconds
size_match
dim_match
is_original
hash_db_match
sha256_match
phash_distance
composite_confidence
google_geoData_lat
google_geoData_lon
icloud_lat
icloud_lon
gps_gap                # True if Google has GPS and iCloud doesn't
```

One Google photo can produce multiple rows when several candidates exist; each row is one (Google, iCloud-candidate) pair.

### Spike report — `docs/spike/2026-04-26-google-vs-icloud-gps-report.md`

Human-readable summary built from the CSV:

- Phase A baseline stats
- Algorithm-by-algorithm summary (how often each signal fired, how often each agreed with composite consensus)
- Stratified sample manual-review results (per-bucket precision)
- The headline number: "Of N Google photos in this archive, X have GPS that iCloud lacks (high-confidence)"
- Recommendation: close spike, or open back-fill spec

## Tooling

- **Python 3.13** for the matcher (already on Mac Mini for osxphotos)
- **`exiftool`** subprocess for reading EXIF / dimensions on Google files
- **`sqlite3`** Python stdlib for reading Photos.sqlite and `.osxphotos_export.db` (read-only)
- **`Pillow` + `imagehash`** for perceptual hashing (install if missing)
- **No `gpth`** for now — we are not lifting Google's metadata into the
  exported files in this spike. We are only **comparing**. `gpth` becomes
  relevant if Phase E spawns a back-fill spec.

Why pure Python and not a chain of bash + sqlite + jq: the matcher is small (~200-300 LOC) and the multi-signal scoring + stratified output are easier in Python. Single self-contained script: `scripts/spike-google-icloud-gps.py`.

## Conflicts and edge cases addressed

| Edge case | Resolution |
|-----------|------------|
| Google has compressed copy (not original) | `is_original = False`; `hash_db` and `sha256` skipped (recorded as `N/A`) |
| Multiple iCloud candidates for one Google filename | Output multiple rows; user sees disagreement in table |
| Google photo with NO iCloud match | Row with all match-signal columns empty; `confidence = 0`; flagged as Google-only |
| Burst photos sharing near-identical timestamps | Multi-row output; manual review resolves |
| Live Photos (HEIC + MOV pair) | Match on the HEIC; MOV is informational, not a separate row |
| `_edited` variants in iCloud | Match Google to the unedited original; flag if Google's also edited |
| Filename case differences | Lowercased comparison |
| Capture timestamp precision (Google sec vs iCloud float-sec) | ±2 sec window |

## Manual review protocol

The user reviews ~100 sampled rows from the CSV. For each:

- Read the (`google_path`, `icloud_candidate_path`) pair
- Mark verdict: `correct` | `wrong` | `should-be-unmatched` | `unsure`
- Optional: a one-line note

The reviewer's verdicts go into a sidecar `2026-04-26-google-vs-icloud-gps-review.csv`. We then compute per-bucket precision (high / medium / low / unmatched) and use it to refine the confidence formula or, more likely, to confirm that the formula is good enough.

## Estimated total wall-clock

Phase A: ~30 min (extraction is the long pole on this RAID)
Phase B+C: ~1–2 hours (1500 photos × 6 algorithms; mostly fast lookups + a few slow sha256 reads)
Phase D: ~1 hour (user time, parallel to anything else)
Phase E: ~15 min (decision + report writing)

**Total agent time: ~2-3 hours of execution. User time: ~1 hour for review.**

## Why this approach is right-sized

- **Single archive, not all 50.** Cost-bounded. If the answer is "no gap," we spent ~3 hours not ~3 weeks.
- **All algorithms run, results stored** (per user's explicit preference). No early termination, no information loss.
- **Originality is a signal, not a routing decision.** Compressed copies legitimately fail sha256, but that's recorded and visible — no hidden assumption.
- **Confidence formula is provisional** and refined by manual review. The first run produces a table; the second run uses the user's verdicts to tune weights.
- **The decision gate at Phase A could end the spike in 30 min** if Google didn't actually add GPS beyond what was already in EXIF.

## Spec self-review

- [x] **Placeholder scan**: no TBD / TODO / vague requirements remain.
- [x] **Internal consistency**: Phase B+C section matches the algorithm table; output format matches what the algorithms produce; manual review uses the buckets defined by the confidence formula.
- [x] **Scope check**: One archive, one matcher script, one output table, one report. Tightly bounded for a spike.
- [x] **Ambiguity check**: All sequential vs. parallel relationships are explicit. Every algorithm has a "when to skip" clause.

## Open questions for the user before implementation planning

None — all clarifying questions answered in brainstorm.

## Next step

Once you approve this design, the brainstorming skill hands off to
`writing-plans` to produce the step-by-step implementation plan.
