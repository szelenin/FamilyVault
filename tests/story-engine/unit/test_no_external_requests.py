"""FR-009: Test that assemble-video.py only contacts IMMICH_URL, no external hosts."""
import os
import pytest
from unittest.mock import MagicMock, patch, call


class TestNoExternalRequests:
    def test_no_external_requests(self, tmp_path, monkeypatch):
        """assemble-video.py only calls URLs matching IMMICH_URL; no external hosts."""
        immich_url = "http://immich-immich-server-1.orb.local"
        monkeypatch.setenv("IMMICH_URL", immich_url)

        calls_made = []

        def mock_get(url, **kwargs):
            calls_made.append(url)
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.iter_content.return_value = [b"fake image data"]
            return mock_resp

        from scripts import assemble_video

        with patch("requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.get.side_effect = mock_get
            mock_session_cls.return_value = mock_session

            # Verify that if we were to call download_asset, it uses IMMICH_URL
            dest = str(tmp_path / "photo.jpg")
            import requests
            session = requests.Session()
            session.get = mock_get
            assemble_video.download_asset(session, immich_url, "test-uuid", dest)

        # All calls should start with IMMICH_URL
        for url in calls_made:
            assert url.startswith(immich_url), (
                f"Call to external URL detected: {url}. "
                "All asset downloads must go through IMMICH_URL."
            )

    def test_download_asset_uses_immich_url(self, tmp_path):
        """download_asset constructs URL as IMMICH_URL/api/assets/{id}/original."""
        from scripts.assemble_video import download_asset

        immich_url = "http://my-immich.local"
        asset_id = "abc-123-def"
        dest = str(tmp_path / "asset.jpg")

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content.return_value = [b"data"]
        mock_session.get.return_value = mock_resp

        download_asset(mock_session, immich_url, asset_id, dest)

        expected_url = f"{immich_url}/api/assets/{asset_id}/original"
        mock_session.get.assert_called_once_with(expected_url, stream=True)
