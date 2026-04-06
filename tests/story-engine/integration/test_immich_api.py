"""
Integration tests against live Immich instance.

Requires:
  IMMICH_URL=http://immich-immich-server-1.orb.local (or macmini:2283)
  IMMICH_API_KEY_FILE=/Volumes/HomeRAID/immich/api-key.txt

Run:
  python3 -m pytest tests/story-engine/integration/test_immich_api.py -v
"""
import os
import pytest
import requests
import sys

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                "setup", "story-engine"))

from scripts.search_photos import (
    make_session,
    person_name_to_id,
    build_smart_search_request,
    parse_asset_response,
)

IMMICH_URL = os.environ.get("IMMICH_URL", "http://immich-immich-server-1.orb.local")
API_KEY_FILE = os.environ.get("IMMICH_API_KEY_FILE", "/Volumes/HomeRAID/immich/api-key.txt")


@pytest.fixture(scope="module")
def session():
    """Authenticated requests session for live Immich."""
    if not os.path.exists(API_KEY_FILE):
        pytest.skip(f"API key file not found: {API_KEY_FILE}")
    return make_session(IMMICH_URL, API_KEY_FILE)


class TestImmichReachable:
    def test_immich_reachable(self, session):
        """Immich server responds to ping."""
        resp = session.get(f"{IMMICH_URL}/api/server/ping")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("res") == "pong"

    def test_immich_authenticated(self, session):
        """API key is valid — /api/users/me returns user info."""
        resp = session.get(f"{IMMICH_URL}/api/users/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "email" in data

    def test_immich_has_assets(self, session):
        """Library has at least 1 asset indexed."""
        resp = session.get(f"{IMMICH_URL}/api/assets/statistics")
        assert resp.status_code == 200
        data = resp.json()
        total = data.get("images", 0) + data.get("videos", 0)
        assert total > 0, "No assets found — is Immich indexed?"


class TestSearchPersonByName:
    def test_people_endpoint_returns_list(self, session):
        """GET /api/people returns a people list."""
        resp = session.get(f"{IMMICH_URL}/api/people", params={"withHidden": "false"})
        assert resp.status_code == 200
        data = resp.json()
        assert "people" in data
        assert isinstance(data["people"], list)

    def test_search_person_by_name_returns_results(self, session):
        """person_name_to_id finds a known person (or gracefully returns None)."""
        # Get any person from the library to use as test subject
        resp = session.get(f"{IMMICH_URL}/api/people", params={"withHidden": "false"})
        people = resp.json().get("people", [])

        if not people:
            pytest.skip("No people with names in Immich — run face recognition first")

        # Pick the first person with a name
        named = [p for p in people if p.get("name")]
        if not named:
            pytest.skip("No named people in Immich")

        test_person = named[0]
        found_id = person_name_to_id(session, test_person["name"], IMMICH_URL)
        assert found_id == test_person["id"], (
            f"Expected {test_person['id']} for '{test_person['name']}', got {found_id}"
        )

    def test_person_name_not_found_returns_none(self, session):
        """person_name_to_id returns None for a name that doesn't exist."""
        result = person_name_to_id(session, "ZZZNOBODYNAMEXYZ", IMMICH_URL)
        assert result is None


class TestSmartSearch:
    def test_smart_search_returns_assets(self, session):
        """POST /api/search/smart returns assets for a broad query."""
        body = build_smart_search_request(query="photo", limit=5)
        resp = session.post(f"{IMMICH_URL}/api/search/smart", json=body)
        assert resp.status_code == 200
        assets = parse_asset_response(resp.json())
        assert len(assets) > 0, "Smart search returned no results for 'photo'"

    def test_smart_search_asset_has_required_fields(self, session):
        """Each asset from smart search has id, type, filename, taken_at."""
        body = build_smart_search_request(query="family", limit=3)
        resp = session.post(f"{IMMICH_URL}/api/search/smart", json=body)
        assert resp.status_code == 200
        assets = parse_asset_response(resp.json())
        if not assets:
            pytest.skip("No results for 'family' query")
        for asset in assets:
            assert asset["id"], "Asset missing id"
            assert asset["type"] in ("IMAGE", "VIDEO"), f"Unknown type: {asset['type']}"
            assert asset["filename"], "Asset missing filename"
            assert asset["taken_at"], "Asset missing taken_at"

    def test_smart_search_respects_limit(self, session):
        """Smart search returns at most limit results."""
        limit = 5
        body = build_smart_search_request(query="outdoor", limit=limit)
        resp = session.post(f"{IMMICH_URL}/api/search/smart", json=body)
        assert resp.status_code == 200
        assets = parse_asset_response(resp.json())
        assert len(assets) <= limit

    def test_smart_search_no_results_exits_cleanly(self, session):
        """Smart search with nonsense query returns empty list (not error)."""
        body = build_smart_search_request(query="xyzzy_no_match_zzz_12345", limit=5)
        resp = session.post(f"{IMMICH_URL}/api/search/smart", json=body)
        assert resp.status_code == 200
        assets = parse_asset_response(resp.json())
        assert isinstance(assets, list)

    def test_metadata_search_with_date_range(self, session):
        """POST /api/search/metadata with date range returns assets."""
        from scripts.search_photos import build_metadata_search_request
        body = build_metadata_search_request(after="2020-01-01", before="2026-12-31", limit=5)
        resp = session.post(f"{IMMICH_URL}/api/search/metadata", json=body)
        assert resp.status_code == 200
        assets = parse_asset_response(resp.json())
        assert len(assets) > 0, "No assets found in 2020-2026 range"
