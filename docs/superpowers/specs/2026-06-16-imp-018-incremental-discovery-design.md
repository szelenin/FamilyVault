# IMP-018 — Incremental Asset Discovery (delta scan + fast-path)

**Date**: 2026-06-16
**Feature**: extends `016-vlm-captioning` (batch discovery efficiency)
**Status**: approved (brainstorm) → pending implementation plan

## Problem

Every indexing run re-discovers the **entire** Immich library before doing any
work. `fetch.immich.list_photo_assets` / `list_video_assets` send only
`{type, page, size}` (no date filter) and page through all assets; `_reconcile`
then diffs every one against the index; only afterward does `plan()` + `--limit`
slice to the batch. No scan watermark is stored.

Consequences on a 163K-photo / 31K-video library:
- **O(library) discovery on every run**, even for `run --limit 1`.
- **Rescans even when thousands of `pending` assets are already queued** — work is
  waiting, yet we still pay the full Immich listing + reconcile.

Discovery cost should be proportional to *new/changed* work, not library size, and
should be skippable entirely when the queue already has enough to process.

## Research: can Immich be the source of truth for "what needs work"?

Investigated whether processing state could live in Immich (so a single Immich
query yields "assets lacking a description"):

| Mechanism | Writable? | **Filterable/searchable via API?** |
|---|---|---|
| Tags (`bulkTagAssets`) | yes (bulk) | **No** — no endpoint returns assets by tag; `search/metadata` can't filter by tag |
| `asset_metadata` key-value (`getAssetMetadataByKey`) | enum-controlled keys | **No** — per-asset GET only; not searchable |
| Asset `description` field | yes | No clean machine filter |

**Conclusion: Immich cannot be the source of truth.** It can store markers but
exposes no way to *query "assets without my marker,"* which is exactly what
discovery needs. And our captions/embeddings/segments/FTS must live in our store
regardless. So **our SQLite stays authoritative** for processing `status`.

**But** Immich *does* expose `updatedAt` and an **`updatedAfter` filter** on
`POST /api/search/metadata` (alongside `order`, `page`, `size`, `type`) — the lever
for a cheap delta scan. (Immich also has a full "Sync v2" checkpoint API; rejected as
overkill — it targets the mobile sync service and couples us to its protocol.)

## Approach

Keep our DB authoritative; make discovery cheap and skippable. Two complementary
mechanisms:

### 1. Fast-path skip
Before discovering, count `pending` (work already queued) for the run's `--type`.
If `pending >= limit` (or `>= a configured floor` when no limit), **skip Immich
discovery entirely** and `plan()` straight from queued rows. New/changed assets are
picked up on a later run once the queue drains, or via `--full-scan`.

### 2. Lower-bound watermark delta scan
When discovery *does* run, fetch only what changed since last time:

- Persist **one watermark per type**: the max `updatedAt` of all assets discovered
  so far. (New table or a row in a small `meta`/`scan_state` table keyed by type.)
- Query `search/metadata` with **`updatedAfter = watermark`** (open-ended at the
  top — everything newer), paginate the whole (small) delta, `_reconcile` each.
- Track `max(updatedAt)` across returned assets. **Only after the pass completes
  successfully, set `watermark = max(updatedAt seen)`.** If interrupted, don't
  advance → next run re-queries the same window (idempotent reconcile makes redo free).
- **Order-independent:** we do not rely on Immich's `order` (which sorts by capture
  date, not `updatedAt`); advancing only post-pass to max-seen is correct regardless.
- **Boundary overlap:** `updatedAfter` is exclusive, so re-query from `watermark − 1s`
  (or inclusive) to avoid skipping same-second updates; idempotency absorbs the overlap.

### Consistency
A paginated query over a live library is **not** snapshot-consistent (assets can be
added/edited mid-scan, shifting pages). The design tolerates this:
- **Duplicates across pages** → harmless (idempotent reconcile).
- **Misses** (updated during the scan) → keep a high `updatedAt` ≥ recorded watermark
  → caught next run. Eventual consistency across runs, not per-query.

## Edge cases

- **First run / empty watermark** → `updatedAfter` unset (or epoch) → full scan once,
  establishing the watermark.
- **Schema bump** (`schema_ver` increased) → reset watermark so everything is
  rediscovered and re-captioned (the existing `plan()` already re-selects on
  `schema_ver`; we also reset the watermark so discovery doesn't hide them).
- **`--full-scan` flag** → ignore watermark and fast-path; re-list everything (manual
  reconcile / recovery).
- **Deletions** — `updatedAfter` never returns removed assets, so deleted-in-Immich
  assets leave stale index rows. **Out of scope here** (matches today's behavior);
  noted as a separate future cleanup (a periodic full reconcile could prune).

## CLI / config surface

- `run [...] [--full-scan]` — force full discovery, ignore watermark + fast-path.
- Config: `DISCOVERY_PENDING_FLOOR` (fast-path threshold when no `--limit`), default
  e.g. the chunk size.
- No change to `status`/`search`/`report`/`retry`.

## Components & boundaries

- **`fetch/immich.py`** — `list_*_assets` gain an optional `updated_after` param,
  threaded into the `search/metadata` body. Pure addition; existing callers/tests
  unaffected (default `None` = full list).
- **`index/db.py`** — small `scan_state` accessor: `get_watermark(type)` /
  `set_watermark(type, ts)`; `pending_count(type)` for the fast-path. Real temp-dir
  SQLite in tests.
- **`index_cli.py` `run_*`** — orchestrate: fast-path check → (delta) discover →
  advance watermark post-pass → plan/limit → process (unchanged downstream).

## Testing (TDD)

- **Unit:** watermark get/set + reset on schema bump; `pending_count`; fast-path skips
  discovery when pending ≥ limit (assert Immich `list_*` not called); delta path passes
  `updated_after=watermark` and advances to max(updatedAt) only after a complete pass;
  interrupted pass leaves watermark unchanged; boundary overlap re-query.
- **Integration (opt-in):** against live Immich, `updatedAfter` returns a bounded set;
  two consecutive runs with no changes → second discovers ~0.
- **e2e:** seed index with pending ≥ limit → run → Immich not queried, batch processed
  from queue (fast-path); separately, a changed asset (bumped `updatedAt`) is
  rediscovered via delta.

## Scope & sequencing

A discovery-efficiency enhancement to `016-vlm-captioning`; recorded as a new
requirement under IMP-018 in the PRD. Independent of US4 / the remediation ladder.
Backward compatible: watermark/fast-path default to safe behavior; `--full-scan`
reproduces today's full reconcile.
