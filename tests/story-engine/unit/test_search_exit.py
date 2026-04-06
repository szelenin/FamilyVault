"""Test search-photos.py exit code 2 on no results."""
import subprocess
import sys
import pytest
from unittest.mock import patch, MagicMock

from scripts.search_photos import parse_asset_response, search_photos


class TestNoResultsExitCode:
    def test_parse_returns_empty_on_zero_results(self):
        """parse_asset_response returns [] for empty Immich response."""
        empty = {"assets": {"items": [], "total": 0, "count": 0, "nextPage": None}}
        assert parse_asset_response(empty) == []

    def test_search_returns_empty_list_when_no_results(self):
        """search_photos returns empty list when Immich has no matching assets."""
        mock_session = MagicMock()
        empty_response = MagicMock()
        empty_response.json.return_value = {
            "assets": {"items": [], "total": 0, "count": 0, "nextPage": None}
        }
        empty_response.raise_for_status = MagicMock()
        mock_session.post.return_value = empty_response

        result = search_photos(
            immich_url="http://immich.local",
            session=mock_session,
            query="nonexistent thing xyz",
        )
        assert result == []

    def test_main_exits_2_on_no_results(self, monkeypatch, tmp_path):
        """main() exits with code 2 and prints [] when no results found."""
        import scripts.search_photos as sp

        # Write a fake API key file
        key_file = tmp_path / "api-key.txt"
        key_file.write_text("test-key")

        monkeypatch.setenv("IMMICH_URL", "http://immich.local")
        monkeypatch.setenv("IMMICH_API_KEY_FILE", str(key_file))

        mock_session = MagicMock()
        empty_response = MagicMock()
        empty_response.json.return_value = {
            "assets": {"items": [], "total": 0, "count": 0, "nextPage": None}
        }
        empty_response.raise_for_status = MagicMock()
        mock_session.post.return_value = empty_response

        with patch("scripts.search_photos.requests.Session", return_value=mock_session):
            with pytest.raises(SystemExit) as exc_info:
                monkeypatch.setattr(
                    sys, "argv",
                    ["search-photos.py", "--query", "nonexistent xyz"]
                )
                sp.main()
        assert exc_info.value.code == 2
