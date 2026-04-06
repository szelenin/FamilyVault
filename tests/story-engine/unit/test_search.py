"""Unit tests for search-photos.py — Immich API client helpers."""
import json
import pytest
from unittest.mock import MagicMock, patch


# These imports will fail until search-photos.py is implemented (T007 confirms this)
from scripts.search_photos import (
    build_smart_search_request,
    person_name_to_id,
    parse_asset_response,
    search_photos,
)


class TestBuildSmartSearchRequest:
    def test_build_smart_search_request_basic_query(self):
        """Smart search request has correct JSON body with query."""
        body = build_smart_search_request(query="birthday party")
        assert body["query"] == "birthday party"
        assert body["type"] == "IMAGE"

    def test_build_smart_search_request_with_person_id(self):
        """Smart search includes personIds when person_id provided."""
        body = build_smart_search_request(query="beach", person_id="abc-123")
        assert "personIds" in body
        assert body["personIds"] == ["abc-123"]

    def test_build_smart_search_request_without_person(self):
        """Smart search has no personIds when person not specified."""
        body = build_smart_search_request(query="vacation")
        assert "personIds" not in body or body.get("personIds") is None

    def test_build_smart_search_request_with_date_range(self):
        """Smart search includes date range when after/before provided."""
        body = build_smart_search_request(
            query="birthday",
            after="2025-03-01",
            before="2025-03-31"
        )
        assert body.get("takenAfter") == "2025-03-01T00:00:00.000Z"
        assert body.get("takenBefore") == "2025-03-31T23:59:59.999Z"

    def test_build_smart_search_request_with_limit(self):
        """Smart search respects limit parameter."""
        body = build_smart_search_request(query="trip", limit=20)
        assert body.get("size") == 20

    def test_build_smart_search_request_default_limit(self):
        """Smart search defaults to 30 items."""
        body = build_smart_search_request(query="trip")
        assert body.get("size") == 30


class TestPersonNameToId:
    def test_person_name_to_id_found(self):
        """Returns person ID when name matches."""
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {
            "people": [
                {"id": "person-uuid-1", "name": "Edgar"},
                {"id": "person-uuid-2", "name": "Maria"}
            ]
        }
        mock_session.get.return_value.raise_for_status = MagicMock()

        result = person_name_to_id(mock_session, "Edgar", "http://immich.local")
        assert result == "person-uuid-1"

    def test_person_name_to_id_not_found(self):
        """Returns None when name not in people list."""
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {
            "people": [
                {"id": "person-uuid-2", "name": "Maria"}
            ]
        }
        mock_session.get.return_value.raise_for_status = MagicMock()

        result = person_name_to_id(mock_session, "Edgar", "http://immich.local")
        assert result is None

    def test_person_name_to_id_case_insensitive(self):
        """Name lookup is case-insensitive."""
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {
            "people": [{"id": "person-uuid-1", "name": "Edgar"}]
        }
        mock_session.get.return_value.raise_for_status = MagicMock()

        result = person_name_to_id(mock_session, "edgar", "http://immich.local")
        assert result == "person-uuid-1"


class TestParseAssetResponse:
    def test_parse_asset_response_fields(self, sample_immich_assets):
        """Parses required fields from Immich asset response."""
        items = parse_asset_response(sample_immich_assets)
        assert len(items) == 2
        first = items[0]
        assert first["id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert first["type"] == "IMAGE"
        assert first["filename"] == "birthday_cake.jpg"
        assert first["mime_type"] == "image/jpeg"
        assert "taken_at" in first
        assert "city" in first
        assert first["city"] == "Miami"

    def test_parse_asset_response_heic_mime_type(self, sample_immich_assets):
        """Parses HEIC mime type correctly."""
        items = parse_asset_response(sample_immich_assets)
        heic_item = items[1]
        assert heic_item["mime_type"] == "image/heic"

    def test_search_returns_empty_list_on_zero_results(self):
        """Returns empty list when Immich returns zero hits."""
        empty_response = {
            "assets": {
                "items": [],
                "total": 0,
                "count": 0,
                "nextPage": None
            }
        }
        items = parse_asset_response(empty_response)
        assert items == []
