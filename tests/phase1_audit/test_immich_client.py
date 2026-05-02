"""Tests for the Immich REST client."""
from __future__ import annotations
from unittest.mock import MagicMock, patch

import pytest

from scripts.phase1_audit.immich_client import ImmichClient


def _mock_response(status=200, json_body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_body if json_body is not None else {}
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return r


def test_client_get_statistics_calls_correct_endpoint() -> None:
    with patch("requests.get", return_value=_mock_response(json_body={"photos": 100, "videos": 20})) as g:
        c = ImmichClient(server="http://x", api_key="k")
        out = c.get_statistics()
    assert out == {"photos": 100, "videos": 20}
    args, kwargs = g.call_args
    assert args[0] == "http://x/api/server/statistics"
    assert kwargs["headers"] == {"x-api-key": "k"}


def test_client_list_albums_returns_list() -> None:
    body = [{"id": "a", "albumName": "Trip A"}, {"id": "b", "albumName": "Trip B"}]
    with patch("requests.get", return_value=_mock_response(json_body=body)):
        c = ImmichClient(server="http://x", api_key="k")
        out = c.list_albums()
    assert out == body


def test_client_search_metadata_posts_payload() -> None:
    # 1 item back is less than the page size (1000) so pagination short-circuits after 1 page
    body = {"assets": {"items": [{"originalFileName": "a.heic"}], "total": 1}}
    with patch("requests.post", return_value=_mock_response(json_body=body)) as p:
        c = ImmichClient(server="http://x", api_key="k")
        items = c.search_metadata({"originalFileName": ".heic"})
    assert items == body["assets"]["items"]
    args, kwargs = p.call_args
    assert args[0] == "http://x/api/search/metadata"
    # search_metadata adds size + page for pagination control
    assert kwargs["json"] == {"originalFileName": ".heic", "size": 1000, "page": 1}


def test_client_search_metadata_paginates_when_page_full() -> None:
    """When a page returns exactly size items, fetch the next page until partial."""
    page1 = {"assets": {"items": [{"id": str(i)} for i in range(1000)], "total": 1500}}
    page2 = {"assets": {"items": [{"id": str(i)} for i in range(500)], "total": 1500}}
    with patch("requests.post", side_effect=[_mock_response(json_body=page1),
                                             _mock_response(json_body=page2)]) as p:
        c = ImmichClient(server="http://x", api_key="k")
        items = c.search_metadata({"originalFileName": ".heic"})
    assert len(items) == 1500
    assert p.call_count == 2
    # Second call should be page 2
    second_call_kwargs = p.call_args_list[1].kwargs
    assert second_call_kwargs["json"]["page"] == 2


def test_client_search_metadata_count_paginates_and_sums() -> None:
    """search_metadata_count walks pages (Immich's 'total' is per-page, not overall)."""
    page1 = {"assets": {"items": [{"id": str(i)} for i in range(1000)]}}  # full page
    page2 = {"assets": {"items": [{"id": str(i)} for i in range(347)]}}   # partial → last page
    with patch("requests.post", side_effect=[_mock_response(json_body=page1),
                                             _mock_response(json_body=page2)]) as p:
        c = ImmichClient(server="http://x", api_key="k")
        count = c.search_metadata_count({"originalFileName": ".heic"})
    assert count == 1347
    assert p.call_count == 2
