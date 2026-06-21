"""Unit tests for fetch.immich — photo path (T013, T017).

Mocking policy: mock ONLY external Immich HTTP calls via an injectable session.
Filesystem operations (download_preview) use a real tmp_path fixture.
No real Immich server is ever contacted.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from fetch.immich import (
    asset_filter_fields,
    download_preview,
    list_photo_assets,
)


# ---------------------------------------------------------------------------
# Helpers / fixture data
# ---------------------------------------------------------------------------

_ASSET_PAGE1 = {
    "id": "asset-uuid-1",
    "type": "IMAGE",
    "originalFileName": "IMG_001.jpg",
    "fileCreatedAt": "2025-03-15T14:30:00.000Z",
    "localDateTime": "2025-03-15T14:30:00.000Z",
    "isFavorite": False,
    "checksum": "abc123base64==",
    "duration": "0:00:00.00000",
    "exifInfo": {
        "city": "Miami",
        "country": "United States",
        "latitude": 25.7,
        "longitude": -80.1,
    },
    "people": [
        {"id": "person-uuid-alice", "name": "Alice"},
        {"id": "person-uuid-bob", "name": "Bob"},
    ],
}

_ASSET_PAGE2 = {
    "id": "asset-uuid-2",
    "type": "IMAGE",
    "originalFileName": "IMG_002.jpg",
    "fileCreatedAt": "2025-04-01T09:00:00.000Z",
    "localDateTime": "2025-04-01T09:00:00.000Z",
    "isFavorite": True,
    "checksum": "def456base64==",
    "duration": "0:00:00.00000",
    "exifInfo": {},
    "people": [],
}


def _make_response(json_data, status_code=200):
    """Build a minimal mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.content = b""
    return resp


def _make_preview_response(content: bytes, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    return resp


# ---------------------------------------------------------------------------
# list_photo_assets — pagination
# ---------------------------------------------------------------------------


class TestListPhotoAssets:
    def test_paginates_two_pages_and_returns_all_items(self):
        """list_photo_assets must follow nextPage until null and return all items."""
        session = MagicMock()

        page1_resp = _make_response(
            {"assets": {"items": [_ASSET_PAGE1], "nextPage": 2}}
        )
        page2_resp = _make_response(
            {"assets": {"items": [_ASSET_PAGE2], "nextPage": None}}
        )
        session.post.side_effect = [page1_resp, page2_resp]

        result = list_photo_assets(session, base_url="http://immich.test:2283")

        assert len(result) == 2
        assert result[0]["id"] == "asset-uuid-1"
        assert result[1]["id"] == "asset-uuid-2"

    def test_post_body_requests_image_type(self):
        """The POST body must include type=IMAGE."""
        session = MagicMock()
        page1_resp = _make_response(
            {"assets": {"items": [_ASSET_PAGE1], "nextPage": None}}
        )
        session.post.return_value = page1_resp

        list_photo_assets(session, base_url="http://immich.test:2283")

        call_kwargs = session.post.call_args
        # Body may be passed as json= kwarg or as data= with serialized JSON.
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body is not None, "Expected json= keyword in POST call"
        assert body.get("type") == "IMAGE"

    def test_single_page_no_next(self):
        """A single-page response (nextPage=null) must still return items."""
        session = MagicMock()
        session.post.return_value = _make_response(
            {"assets": {"items": [_ASSET_PAGE1], "nextPage": None}}
        )

        result = list_photo_assets(session, base_url="http://immich.test:2283")

        assert len(result) == 1
        session.post.assert_called_once()

    def test_empty_library_returns_empty_list(self):
        """An empty library (no items) returns an empty list without error."""
        session = MagicMock()
        session.post.return_value = _make_response(
            {"assets": {"items": [], "nextPage": None}}
        )

        result = list_photo_assets(session, base_url="http://immich.test:2283")

        assert result == []

    def test_uses_default_base_url(self):
        """list_photo_assets works without explicit base_url (uses env default)."""
        session = MagicMock()
        session.post.return_value = _make_response(
            {"assets": {"items": [], "nextPage": None}}
        )

        # Should not raise; default URL is used.
        result = list_photo_assets(session)
        assert result == []


# ---------------------------------------------------------------------------
# download_preview
# ---------------------------------------------------------------------------


class TestDownloadPreview:
    def test_200_with_bytes_writes_file_and_returns_path(self, tmp_path):
        """A 200 response with content writes bytes to dest_path and returns path."""
        session = MagicMock()
        image_bytes = b"\xff\xd8\xff\xe0fake-jpeg-content"
        session.get.return_value = _make_preview_response(image_bytes, 200)

        dest = tmp_path / "preview.jpg"
        result = download_preview(
            session, "asset-uuid-1", dest, base_url="http://immich.test:2283"
        )

        assert result == str(dest)
        assert dest.exists()
        assert dest.read_bytes() == image_bytes

    def test_404_returns_none(self, tmp_path):
        """A 404 response returns None (no preview available)."""
        session = MagicMock()
        session.get.return_value = _make_preview_response(b"", 404)

        dest = tmp_path / "preview.jpg"
        result = download_preview(
            session, "asset-uuid-1", dest, base_url="http://immich.test:2283"
        )

        assert result is None

    def test_non_200_status_returns_none(self, tmp_path):
        """Any non-200 status code (e.g. 500) returns None."""
        session = MagicMock()
        session.get.return_value = _make_preview_response(b"server error", 500)

        dest = tmp_path / "preview.jpg"
        result = download_preview(
            session, "asset-uuid-1", dest, base_url="http://immich.test:2283"
        )

        assert result is None

    def test_200_but_empty_body_returns_none(self, tmp_path):
        """A 200 with empty body means no usable preview — return None."""
        session = MagicMock()
        session.get.return_value = _make_preview_response(b"", 200)

        dest = tmp_path / "preview.jpg"
        result = download_preview(
            session, "asset-uuid-1", dest, base_url="http://immich.test:2283"
        )

        assert result is None

    def test_calls_correct_url(self, tmp_path):
        """GET is called on the correct thumbnail endpoint URL."""
        session = MagicMock()
        session.get.return_value = _make_preview_response(b"data", 200)

        dest = tmp_path / "preview.jpg"
        download_preview(
            session, "my-asset-id", dest, base_url="http://immich.test:2283"
        )

        call_args = session.get.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url")
        assert "my-asset-id" in url
        assert "thumbnail" in url


# ---------------------------------------------------------------------------
# asset_filter_fields — column mapping
# ---------------------------------------------------------------------------


class TestAssetFilterFields:
    def test_maps_asset_id(self):
        result = asset_filter_fields(_ASSET_PAGE1)
        assert result["asset_id"] == "asset-uuid-1"

    def test_maps_type(self):
        result = asset_filter_fields(_ASSET_PAGE1)
        assert result["type"] == "IMAGE"

    def test_taken_at_prefers_local_date_time(self):
        """taken_at should prefer localDateTime over fileCreatedAt."""
        asset = {**_ASSET_PAGE1, "localDateTime": "2025-03-15T14:30:00.000Z"}
        result = asset_filter_fields(asset)
        assert result["taken_at"] == "2025-03-15T14:30:00.000Z"

    def test_taken_at_falls_back_to_file_created_at(self):
        """taken_at falls back to fileCreatedAt when localDateTime is absent."""
        asset = {k: v for k, v in _ASSET_PAGE1.items() if k != "localDateTime"}
        result = asset_filter_fields(asset)
        assert result["taken_at"] == "2025-03-15T14:30:00.000Z"

    def test_maps_lat_lon(self):
        result = asset_filter_fields(_ASSET_PAGE1)
        assert result["lat"] == 25.7
        assert result["lon"] == -80.1

    def test_maps_city_and_country(self):
        result = asset_filter_fields(_ASSET_PAGE1)
        assert result["city"] == "Miami"
        assert result["country"] == "United States"

    def test_missing_exif_yields_none_for_geo(self):
        result = asset_filter_fields(_ASSET_PAGE2)
        assert result["lat"] is None
        assert result["lon"] is None
        assert result["city"] is None
        assert result["country"] is None

    def test_source_hash_equals_checksum(self):
        result = asset_filter_fields(_ASSET_PAGE1)
        assert result["source_hash"] == "abc123base64=="

    def test_is_favorite_false_maps_to_0(self):
        result = asset_filter_fields(_ASSET_PAGE1)
        assert result["is_favorite"] == 0

    def test_is_favorite_true_maps_to_1(self):
        result = asset_filter_fields(_ASSET_PAGE2)
        assert result["is_favorite"] == 1

    def test_duration_for_photo_is_none_or_zero(self):
        """Photos have duration 0:00:00.00000 — should parse to 0.0 or None."""
        result = asset_filter_fields(_ASSET_PAGE1)
        # Both None and 0.0 are acceptable for photo zero-duration.
        assert result["duration"] is None or result["duration"] == 0.0

    def test_person_ids_contains_only_ids_not_names(self):
        """FR-007: person_ids must be a JSON list of IDs only — names must be absent."""
        result = asset_filter_fields(_ASSET_PAGE1)
        person_ids = json.loads(result["person_ids"])
        assert isinstance(person_ids, list)
        assert "person-uuid-alice" in person_ids
        assert "person-uuid-bob" in person_ids
        # Names must NOT appear anywhere in the encoded value.
        assert "Alice" not in result["person_ids"]
        assert "Bob" not in result["person_ids"]

    def test_person_ids_privacy_no_names_in_output(self):
        """Extra privacy check: the raw person_ids string contains zero name strings."""
        result = asset_filter_fields(_ASSET_PAGE1)
        raw = result["person_ids"]
        for person in _ASSET_PAGE1["people"]:
            assert person["name"] not in raw

    def test_empty_people_list_encodes_as_empty_json_array(self):
        result = asset_filter_fields(_ASSET_PAGE2)
        assert result["person_ids"] == "[]"

    def test_all_required_columns_present(self):
        """Every cached index column must be present in the returned dict."""
        required = {
            "asset_id", "type", "taken_at", "lat", "lon",
            "city", "country", "person_ids", "is_favorite",
            "duration", "source_hash",
        }
        result = asset_filter_fields(_ASSET_PAGE1)
        assert required.issubset(result.keys())


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
