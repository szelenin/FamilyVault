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
