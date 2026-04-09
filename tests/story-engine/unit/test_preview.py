"""Unit tests for preview.py — Immich album creation and cleanup."""
import pytest
from unittest.mock import MagicMock, patch, call

from scripts.preview import (
    create_preview_album,
    delete_preview_album,
)


class TestCreatePreviewAlbum:
    def test_create_preview_album_returns_album_info(self):
        """create_preview_album returns dict with album_id, share_key, share_url."""
        session = MagicMock()
        # Mock POST /api/albums → returns album
        album_resp = MagicMock()
        album_resp.json.return_value = {"id": "album-123", "albumName": "Preview"}
        album_resp.raise_for_status = MagicMock()
        # Mock PUT /api/albums/{id}/assets → success
        add_resp = MagicMock()
        add_resp.json.return_value = [{"id": "asset-1", "success": True}]
        add_resp.raise_for_status = MagicMock()
        # Mock POST /api/shared-links → returns share link
        share_resp = MagicMock()
        share_resp.json.return_value = {"id": "link-1", "key": "abc123"}
        share_resp.raise_for_status = MagicMock()

        session.post.side_effect = [album_resp, share_resp]
        session.put.return_value = add_resp

        result = create_preview_album(
            session, "http://immich:2283",
            asset_ids=["asset-1", "asset-2"],
            title="Preview: Miami Trip",
        )
        assert result["album_id"] == "album-123"
        assert result["share_key"] == "abc123"
        assert "share" in result["share_url"]


class TestDeletePreviewAlbum:
    def test_delete_preview_album_calls_api(self):
        """delete_preview_album calls DELETE /api/albums/{id}."""
        session = MagicMock()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        session.delete.return_value = resp

        delete_preview_album(session, "http://immich:2283", "album-123")
        session.delete.assert_called_once_with("http://immich:2283/api/albums/album-123")


class TestPreviewCleanup:
    def test_create_album_cleans_old_preview(self):
        """If project has existing preview, it's deleted before creating new one."""
        session = MagicMock()
        # Mock responses
        delete_resp = MagicMock()
        delete_resp.raise_for_status = MagicMock()
        session.delete.return_value = delete_resp

        album_resp = MagicMock()
        album_resp.json.return_value = {"id": "album-new", "albumName": "Preview"}
        album_resp.raise_for_status = MagicMock()

        add_resp = MagicMock()
        add_resp.json.return_value = []
        add_resp.raise_for_status = MagicMock()

        share_resp = MagicMock()
        share_resp.json.return_value = {"id": "link-1", "key": "newkey"}
        share_resp.raise_for_status = MagicMock()

        session.post.side_effect = [album_resp, share_resp]
        session.put.return_value = add_resp

        # Call with old_album_id to trigger cleanup
        result = create_preview_album(
            session, "http://immich:2283",
            asset_ids=["asset-1"],
            title="Preview",
            old_album_id="album-old",
        )
        # Should have deleted the old album
        session.delete.assert_called_once_with("http://immich:2283/api/albums/album-old")
        assert result["album_id"] == "album-new"
