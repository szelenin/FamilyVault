# Incremental Asset Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Immich discovery cost proportional to new/changed work (not library size) and skippable when enough work is already queued.

**Architecture:** Our SQLite stays authoritative for processing `status`. Add (1) a fast-path that skips the Immich scan when `pending ≥ batch`, and (2) a lower-bound watermark delta scan via `search/metadata`'s `updatedAfter`, advancing a per-type watermark to `max(updatedAt)` only after a complete pass. A shared `_discover()` helper replaces the duplicated list→reconcile→plan blocks in `run_photos`/`run_videos`.

**Tech Stack:** Python 3.13, stdlib `sqlite3`, Immich REST `POST /api/search/metadata`, pytest. Interpreter: `/opt/homebrew/bin/python3.13`.

Design: `docs/superpowers/specs/2026-06-16-imp-018-incremental-discovery-design.md` (PRD R101b).

---

## File Structure

- **`setup/understanding/index/db.py`** — add a `scan_state` table + accessors: `get_watermark`, `set_watermark`, `reset_watermark`, `pending_count`.
- **`setup/understanding/fetch/immich.py`** — add an optional `updated_after` param to `list_photo_assets` and `list_video_assets` (threaded into the `search/metadata` body).
- **`setup/understanding/index_cli.py`** — add a shared `_discover()` helper (fast-path + delta + watermark advance); call it from `run_photos`/`run_videos`; add `full_scan` param + `--full-scan` CLI flag.
- **`setup/understanding/config.sh`** — add `DISCOVERY_PENDING_FLOOR`.
- **Tests** — `tests/understanding/unit/test_db.py`, `test_fetch_immich_photo.py`, `test_fetch_immich_video.py`, new `test_cli_discovery.py`.

Note on schema-bump: reprocessing assets after a `schema_ver` bump is handled by the existing `plan()` over rows already in our DB (it selects `schema_ver < current`) — it does **not** require Immich rediscovery, so no watermark reset is needed for that case. `--full-scan` is the explicit reset/recover hatch. (Refines the design doc's edge-case note.)

---

## Task 1: `scan_state` table + watermark / pending-count accessors

**Files:**
- Modify: `setup/understanding/index/db.py` (add to `_DDL_STATEMENTS`; add 4 functions)
- Test: `tests/understanding/unit/test_db.py` (append)

- [ ] **Step 1: Write the failing tests** (append to `tests/understanding/unit/test_db.py`)

```python
class TestScanStateAndPending:
    def test_watermark_roundtrip(self, tmp_path):
        from index.db import open_db, get_watermark, set_watermark
        conn = open_db(str(tmp_path / "i.db"))
        assert get_watermark(conn, "IMAGE") is None          # unset → None
        set_watermark(conn, "IMAGE", "2026-06-16T00:00:00.000Z")
        assert get_watermark(conn, "IMAGE") == "2026-06-16T00:00:00.000Z"
        set_watermark(conn, "IMAGE", "2026-06-16T01:00:00.000Z")  # upsert
        assert get_watermark(conn, "IMAGE") == "2026-06-16T01:00:00.000Z"
        assert get_watermark(conn, "VIDEO") is None          # per-type isolation

    def test_reset_watermark(self, tmp_path):
        from index.db import open_db, get_watermark, set_watermark, reset_watermark
        conn = open_db(str(tmp_path / "i.db"))
        set_watermark(conn, "VIDEO", "2026-06-16T00:00:00.000Z")
        reset_watermark(conn, "VIDEO")
        assert get_watermark(conn, "VIDEO") is None

    def test_pending_count_by_type(self, tmp_path):
        from index.db import open_db, upsert_asset, pending_count
        conn = open_db(str(tmp_path / "i.db"))
        upsert_asset(conn, {"asset_id": "p1", "type": "IMAGE", "status": "pending", "schema_ver": 1})
        upsert_asset(conn, {"asset_id": "p2", "type": "IMAGE", "status": "pending", "schema_ver": 1})
        upsert_asset(conn, {"asset_id": "d1", "type": "IMAGE", "status": "done", "schema_ver": 1})
        upsert_asset(conn, {"asset_id": "v1", "type": "VIDEO", "status": "pending", "schema_ver": 1})
        assert pending_count(conn, "IMAGE") == 2     # only pending IMAGE
        assert pending_count(conn, "VIDEO") == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /Users/szelenin/projects/FamilyVault-AI && /opt/homebrew/bin/python3.13 -m pytest tests/understanding/unit/test_db.py::TestScanStateAndPending -q`
Expected: FAIL — `ImportError: cannot import name 'get_watermark'` (functions don't exist yet).

- [ ] **Step 3: Add the `scan_state` table to `_DDL_STATEMENTS`**

In `setup/understanding/index/db.py`, add this string as a new element of the `_DDL_STATEMENTS` list (e.g. right after the `runs` table block):

```python
    """
    CREATE TABLE IF NOT EXISTS scan_state (
        asset_type TEXT PRIMARY KEY,   -- 'IMAGE' | 'VIDEO'
        watermark  TEXT                -- max updatedAt discovered (ISO 8601), or NULL
    )
    """,
```

- [ ] **Step 4: Add the four accessor functions**

Append to `setup/understanding/index/db.py` (after `index_state`):

```python
def get_watermark(conn: sqlite3.Connection, asset_type: str):
    """Return the stored discovery watermark (max updatedAt) for a type, or None."""
    row = conn.execute(
        "SELECT watermark FROM scan_state WHERE asset_type=?", (asset_type,)
    ).fetchone()
    return row["watermark"] if row else None


def set_watermark(conn: sqlite3.Connection, asset_type: str, watermark: str) -> None:
    """Upsert the discovery watermark for a type."""
    conn.execute(
        "INSERT INTO scan_state(asset_type, watermark) VALUES (?, ?) "
        "ON CONFLICT(asset_type) DO UPDATE SET watermark=excluded.watermark",
        (asset_type, watermark),
    )
    conn.commit()


def reset_watermark(conn: sqlite3.Connection, asset_type: str) -> None:
    """Clear the watermark for a type (forces a full scan next discovery)."""
    conn.execute("DELETE FROM scan_state WHERE asset_type=?", (asset_type,))
    conn.commit()


def pending_count(conn: sqlite3.Connection, asset_type: str) -> int:
    """Number of assets of *asset_type* currently in status 'pending'."""
    row = conn.execute(
        "SELECT COUNT(*) FROM assets WHERE status='pending' AND type=?", (asset_type,)
    ).fetchone()
    return row[0]
```

- [ ] **Step 5: Run to verify pass**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/understanding/unit/test_db.py -q`
Expected: PASS (all db tests, incl. the 3 new).

- [ ] **Step 6: Commit**

```bash
git add setup/understanding/index/db.py tests/understanding/unit/test_db.py
git commit -m "feat(016): scan_state table + watermark/pending_count accessors (R101b)"
```

---

## Task 2: `updated_after` param on the Immich list functions

**Files:**
- Modify: `setup/understanding/fetch/immich.py` (`list_photo_assets`, `list_video_assets`)
- Test: `tests/understanding/unit/test_fetch_immich_photo.py`, `tests/understanding/unit/test_fetch_immich_video.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/understanding/unit/test_fetch_immich_photo.py`:

```python
class TestListPhotoAssetsUpdatedAfter:
    def _resp(self, items, next_page=None):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.json.return_value = {"assets": {"items": items, "nextPage": next_page}}
        return r

    def test_includes_updated_after_when_set(self):
        from unittest.mock import MagicMock
        from fetch.immich import list_photo_assets
        s = MagicMock()
        s.post.return_value = self._resp([], next_page=None)
        list_photo_assets(s, base_url="http://x:2283", updated_after="2026-06-16T00:00:00.000Z")
        _, kwargs = s.post.call_args
        assert kwargs["json"]["updatedAfter"] == "2026-06-16T00:00:00.000Z"

    def test_omits_updated_after_when_none(self):
        from unittest.mock import MagicMock
        from fetch.immich import list_photo_assets
        s = MagicMock()
        s.post.return_value = self._resp([], next_page=None)
        list_photo_assets(s, base_url="http://x:2283")
        _, kwargs = s.post.call_args
        assert "updatedAfter" not in kwargs["json"]
```

Append the VIDEO equivalent to `tests/understanding/unit/test_fetch_immich_video.py`:

```python
class TestListVideoAssetsUpdatedAfter:
    def _resp(self, items, next_page=None):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.json.return_value = {"assets": {"items": items, "nextPage": next_page}}
        return r

    def test_includes_updated_after_when_set(self):
        from unittest.mock import MagicMock
        from fetch.immich import list_video_assets
        s = MagicMock()
        s.post.return_value = self._resp([], next_page=None)
        list_video_assets(s, base_url="http://x:2283", updated_after="2026-06-16T00:00:00.000Z")
        _, kwargs = s.post.call_args
        assert kwargs["json"]["updatedAfter"] == "2026-06-16T00:00:00.000Z"

    def test_omits_updated_after_when_none(self):
        from unittest.mock import MagicMock
        from fetch.immich import list_video_assets
        s = MagicMock()
        s.post.return_value = self._resp([], next_page=None)
        list_video_assets(s, base_url="http://x:2283")
        _, kwargs = s.post.call_args
        assert "updatedAfter" not in kwargs["json"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/understanding/unit/test_fetch_immich_photo.py::TestListPhotoAssetsUpdatedAfter tests/understanding/unit/test_fetch_immich_video.py::TestListVideoAssetsUpdatedAfter -q`
Expected: FAIL — `TypeError: list_photo_assets() got an unexpected keyword argument 'updated_after'`.

- [ ] **Step 3: Add the param to `list_photo_assets`**

In `setup/understanding/fetch/immich.py`, change the `list_photo_assets` signature and body:

```python
def list_photo_assets(
    session,
    *,
    base_url: str = _DEFAULT_BASE_URL,
    page_size: int = _DEFAULT_PAGE_SIZE,
    updated_after=None,
) -> list:
    """Return IMAGE assets from Immich, paginating until exhausted.

    If *updated_after* (ISO 8601) is given, only assets modified after that
    instant are returned (delta scan).
    """
    url = f"{base_url}/api/search/metadata"
    assets: list = []
    page = 1
    while True:
        body = {"type": "IMAGE", "page": page, "size": page_size}
        if updated_after is not None:
            body["updatedAfter"] = updated_after
        response = session.post(url, json=body)
        data = response.json()
        assets.extend(data["assets"]["items"])
        next_page = data["assets"].get("nextPage")
        if not next_page:
            break
        page = next_page
    return assets
```

- [ ] **Step 4: Add the param to `list_video_assets`**

Same change for `list_video_assets` (note `type="VIDEO"`):

```python
def list_video_assets(
    session,
    *,
    base_url: str = _DEFAULT_BASE_URL,
    page_size: int = _DEFAULT_PAGE_SIZE,
    updated_after=None,
) -> list:
    """Return VIDEO assets from Immich, paginating until exhausted. Delta via updated_after."""
    url = f"{base_url}/api/search/metadata"
    assets: list = []
    page = 1
    while True:
        body = {"type": "VIDEO", "page": page, "size": page_size}
        if updated_after is not None:
            body["updatedAfter"] = updated_after
        response = session.post(url, json=body)
        data = response.json()
        assets.extend(data["assets"]["items"])
        next_page = data["assets"].get("nextPage")
        if not next_page:
            break
        page = next_page
    return assets
```

- [ ] **Step 5: Run to verify pass (incl. existing fetch tests)**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/understanding/unit/test_fetch_immich_photo.py tests/understanding/unit/test_fetch_immich_video.py -q`
Expected: PASS (new + all existing list/pagination tests).

- [ ] **Step 6: Commit**

```bash
git add setup/understanding/fetch/immich.py tests/understanding/unit/test_fetch_immich_photo.py tests/understanding/unit/test_fetch_immich_video.py
git commit -m "feat(016): list_*_assets accept updated_after for delta discovery (R101b)"
```

---

## Task 3: shared `_discover()` helper + integrate into run_photos/run_videos + `--full-scan`

**Files:**
- Modify: `setup/understanding/index_cli.py` (imports; add `_discover`; edit `run_photos`/`run_videos`; add `--full-scan`)
- Modify: `setup/understanding/config.sh` (add `DISCOVERY_PENDING_FLOOR`)
- Test: `tests/understanding/unit/test_cli_discovery.py` (new)

- [ ] **Step 1: Write failing tests** (new file `tests/understanding/unit/test_cli_discovery.py`)

```python
"""R101b — discovery fast-path + delta watermark in the run orchestration."""
from index.db import open_db, upsert_asset, set_watermark, get_watermark
import index_cli


def _seed_pending(conn, asset_type, n):
    for i in range(n):
        upsert_asset(conn, {"asset_id": f"{asset_type}-{i}", "type": asset_type,
                            "status": "pending", "schema_ver": 1, "source_hash": "h"})


class Recorder:
    """Stand-in for list_photo_assets/list_video_assets that records calls."""
    def __init__(self, returns=None):
        self.calls = []
        self._returns = returns or []

    def __call__(self, session, *, updated_after=None, **kw):
        self.calls.append(updated_after)
        return self._returns


def test_fast_path_skips_immich_when_pending_enough(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    _seed_pending(conn, "IMAGE", 5)
    rec = Recorder()
    todo = index_cli._discover(conn, asset_type="IMAGE", list_fn=rec, session=object(),
                               schema_ver=1, limit=3, full_scan=False)
    assert rec.calls == []                 # Immich NOT queried
    assert len(todo) == 3                  # limited from existing pending


def test_delta_passes_watermark_and_advances_after_pass(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))   # 0 pending → must scan
    set_watermark(conn, "IMAGE", "2026-06-16T00:00:00.000Z")
    rec = Recorder(returns=[
        {"id": "a", "type": "IMAGE", "checksum": "h", "updatedAt": "2026-06-16T05:00:00.000Z",
         "localDateTime": "2026-01-01T00:00:00.000Z", "isFavorite": False, "exifInfo": {}, "people": []},
        {"id": "b", "type": "IMAGE", "checksum": "h", "updatedAt": "2026-06-16T03:00:00.000Z",
         "localDateTime": "2026-01-01T00:00:00.000Z", "isFavorite": False, "exifInfo": {}, "people": []},
    ])
    index_cli._discover(conn, asset_type="IMAGE", list_fn=rec, session=object(),
                        schema_ver=1, limit=None, full_scan=False)
    assert rec.calls == ["2026-06-16T00:00:00.000Z"]            # queried with stored watermark
    assert get_watermark(conn, "IMAGE") == "2026-06-16T05:00:00.000Z"  # advanced to max updatedAt


def test_full_scan_ignores_and_resets_watermark(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    _seed_pending(conn, "IMAGE", 50)         # would normally trigger fast-path
    set_watermark(conn, "IMAGE", "2026-06-16T00:00:00.000Z")
    rec = Recorder(returns=[])
    index_cli._discover(conn, asset_type="IMAGE", list_fn=rec, session=object(),
                        schema_ver=1, limit=1, full_scan=True)
    assert rec.calls == [None]               # full list (no updated_after), despite pending+watermark


def test_interrupted_scan_keeps_old_watermark(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    set_watermark(conn, "IMAGE", "2026-06-16T00:00:00.000Z")

    def boom(session, *, updated_after=None, **kw):
        raise RuntimeError("immich down")

    import pytest
    with pytest.raises(RuntimeError):
        index_cli._discover(conn, asset_type="IMAGE", list_fn=boom, session=object(),
                            schema_ver=1, limit=None, full_scan=False)
    assert get_watermark(conn, "IMAGE") == "2026-06-16T00:00:00.000Z"  # unchanged
```

- [ ] **Step 2: Run to verify they fail**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/understanding/unit/test_cli_discovery.py -q`
Expected: FAIL — `AttributeError: module 'index_cli' has no attribute '_discover'`.

- [ ] **Step 3: Add imports + `DISCOVERY_PENDING_FLOOR` in `index_cli.py`**

Add the new names to the existing `from index.db import (...)` block:

```python
    get_watermark,
    set_watermark,
    reset_watermark,
    pending_count,
```

Add a constant near `_DEFAULT_CHUNK_SIZE`:

```python
DISCOVERY_PENDING_FLOOR = int(os.environ.get("DISCOVERY_PENDING_FLOOR", str(_DEFAULT_CHUNK_SIZE)))
```

- [ ] **Step 4: Add the `_discover` helper** (place right after `_reconcile` in `index_cli.py`)

```python
def _discover(conn, *, asset_type, list_fn, session, schema_ver, limit, full_scan):
    """Discover new/changed assets into the index, then return the todo list.

    Fast-path: if enough 'pending' work is already queued, skip the Immich scan.
    Otherwise delta-scan via the updatedAfter watermark (full list when full_scan
    or no watermark yet), reconcile each, and advance the watermark to the max
    updatedAt seen — but only AFTER a complete pass, so an interrupted scan is
    resumable (idempotent reconcile makes the re-query free).
    """
    need = limit if limit is not None else DISCOVERY_PENDING_FLOOR

    if not full_scan and pending_count(conn, asset_type) >= need:
        pass  # fast-path: enough queued; skip Immich discovery entirely
    else:
        if full_scan:
            reset_watermark(conn, asset_type)
            watermark = None
        else:
            watermark = get_watermark(conn, asset_type)

        raw = list_fn(session, updated_after=watermark)

        current_state = index_state(conn)
        max_seen = watermark
        for raw_asset in raw:
            fields = asset_filter_fields(raw_asset)
            _reconcile(conn, fields, current_state.get(fields["asset_id"]), schema_ver)
            ts = raw_asset.get("updatedAt")
            if ts is not None and (max_seen is None or ts > max_seen):
                max_seen = ts

        if max_seen is not None:
            set_watermark(conn, asset_type, max_seen)

    todo = plan(conn, type=asset_type, schema_ver=schema_ver)
    if limit is not None:
        todo = todo[:limit]
    return todo
```

- [ ] **Step 5: Replace the discovery block in `run_photos`**

Add `full_scan: bool = False` to the `run_photos` signature (alongside the other keyword params). Then replace the existing list/reconcile/plan/limit block:

```python
    # Step 1: List Immich assets
    raw_assets = list_photo_assets(session)

    # Step 2: Reconcile each asset against the index
    current_state = index_state(conn)
    for raw_asset in raw_assets:
        fields = asset_filter_fields(raw_asset)
        asset_id = fields["asset_id"]
        stored = current_state.get(asset_id)
        _reconcile(conn, fields, stored, schema_ver)

    # Step 3: Get todo list, apply limit
    todo = plan(conn, type="IMAGE", schema_ver=schema_ver)
    if limit is not None:
        todo = todo[:limit]
```

with:

```python
    todo = _discover(
        conn, asset_type="IMAGE", list_fn=list_photo_assets, session=session,
        schema_ver=schema_ver, limit=limit, full_scan=full_scan,
    )
```

- [ ] **Step 6: Replace the discovery block in `run_videos`**

Add `full_scan: bool = False` to the `run_videos` signature. Replace:

```python
    # Discover + reconcile (change detection) — same as photos.
    current_state = index_state(conn)
    for raw_asset in list_video_assets(session):
        fields = asset_filter_fields(raw_asset)
        _reconcile(conn, fields, current_state.get(fields["asset_id"]), schema_ver)

    todo = plan(conn, type="VIDEO", schema_ver=schema_ver)
    if limit is not None:
        todo = todo[:limit]
```

with:

```python
    todo = _discover(
        conn, asset_type="VIDEO", list_fn=list_video_assets, session=session,
        schema_ver=schema_ver, limit=limit, full_scan=full_scan,
    )
```

- [ ] **Step 7: Wire `--full-scan` into `main()`**

Add the flag to the `run` subparser (next to `--clean-staging`):

```python
    run_p.add_argument(
        "--full-scan",
        action="store_true",
        help="Ignore the discovery watermark + fast-path; re-list all Immich assets.",
    )
```

And pass it in the `run` branch call to `run_fn(...)`:

```python
                full_scan=args.full_scan,
```

- [ ] **Step 8: Add `DISCOVERY_PENDING_FLOOR` to `config.sh`**

In `setup/understanding/config.sh`, after the frame-sampling caps block, add:

```bash
# --- Discovery (incremental) -------------------------------------------------
: "${DISCOVERY_PENDING_FLOOR:=50}"  # skip the Immich scan when >= this many pending (no --limit)
```

and append `DISCOVERY_PENDING_FLOOR` to the `export` line.

- [ ] **Step 9: Run the discovery tests + full suite**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/understanding/unit/test_cli_discovery.py -q && /opt/homebrew/bin/python3.13 -m pytest tests/understanding/ -q`
Expected: PASS — new discovery tests green; full suite green (existing run_photos/run_videos tests still pass because `_discover` reproduces list→reconcile→plan→limit when scanning).

- [ ] **Step 10: Commit**

```bash
git add setup/understanding/index_cli.py setup/understanding/config.sh tests/understanding/unit/test_cli_discovery.py
git commit -m "feat(016): incremental discovery — fast-path + updatedAfter delta in run_* (R101b)"
```

---

## Task 4 (optional): opt-in integration test against live Immich

**Files:**
- Test: `tests/understanding/integration/test_discovery_live.py` (new)

- [ ] **Step 1: Write the opt-in integration test**

```python
"""Integration — updatedAfter returns a bounded delta against live Immich."""
import pytest
from index.db import open_db
import index_cli
from fetch.immich import list_photo_assets

pytestmark = pytest.mark.integration


def _session_or_skip():
    import requests
    key = index_cli._resolve_api_key()
    if not key:
        pytest.skip("no Immich API key")
    s = requests.Session(); s.headers["x-api-key"] = key
    try:
        r = s.get("http://localhost:2283/api/users/me", timeout=5)
        if r.status_code != 200:
            pytest.skip("Immich not reachable")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Immich not reachable: {exc}")
    return s


def test_updated_after_far_future_returns_empty(tmp_path):
    s = _session_or_skip()
    # Nothing is updated after the far future → empty delta (bounded, not full library).
    assets = list_photo_assets(s, updated_after="2099-01-01T00:00:00.000Z")
    assert assets == []
```

- [ ] **Step 2: Run it (opt-in)**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/understanding/integration/test_discovery_live.py -m integration -q`
Expected: PASS (or SKIP if Immich is down).

- [ ] **Step 3: Commit**

```bash
git add tests/understanding/integration/test_discovery_live.py
git commit -m "test(016): opt-in live integration for updatedAfter delta (R101b)"
```

---

## Self-Review

- **Spec coverage:** fast-path (Task 3) ✓; lower-bound watermark delta via `updatedAfter` (Tasks 2+3) ✓; advance-only-after-pass + interrupted-keeps-watermark (Task 3 tests) ✓; `--full-scan` reset hatch (Task 3) ✓; per-type watermark (Task 1 `scan_state` PK + tests) ✓; consistency tolerance via idempotent reconcile (reuses existing `_reconcile`, no change) ✓; deletions out of scope (no task — matches design) ✓. Schema-bump handled by existing `plan()` (documented above) ✓.
- **Placeholders:** none — every code step is complete.
- **Type/name consistency:** `get_watermark`/`set_watermark`/`reset_watermark`/`pending_count`, `_discover(conn, *, asset_type, list_fn, session, schema_ver, limit, full_scan)`, and the `updated_after` kwarg are used identically across Tasks 1–3 and the tests.
- **Boundary overlap note:** the design mentions re-querying from `watermark − 1s`. The plan advances to exact `max(updatedAt)` and relies on idempotent reconcile to absorb a same-second boundary asset on the next run; if a same-second skip is ever observed, subtract 1s in `set_watermark`'s caller. Kept simple (YAGNI) since reconcile is idempotent.
