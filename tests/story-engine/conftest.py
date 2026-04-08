"""Shared pytest fixtures for story-engine tests."""
import json
import os
import sys
import pytest
import tempfile

# Add setup/story-engine to path so tests can import scripts as a package
_SCRIPTS_PARENT = os.path.join(
    os.path.dirname(__file__), "..", "..", "setup", "story-engine"
)
sys.path.insert(0, os.path.abspath(_SCRIPTS_PARENT))
from unittest.mock import MagicMock


@pytest.fixture
def temp_stories_dir(tmp_path):
    """Temporary STORIES_DIR for tests."""
    stories = tmp_path / "stories"
    stories.mkdir()
    return str(stories)


@pytest.fixture(autouse=True)
def set_stories_dir(temp_stories_dir, monkeypatch):
    """Auto-set STORIES_DIR env var to temp dir for all tests."""
    monkeypatch.setenv("STORIES_DIR", temp_stories_dir)


@pytest.fixture
def sample_immich_assets():
    """Mock Immich asset search response."""
    return {
        "assets": {
            "items": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "type": "IMAGE",
                    "originalFileName": "birthday_cake.jpg",
                    "originalMimeType": "image/jpeg",
                    "fileCreatedAt": "2025-03-15T14:30:00.000Z",
                    "localDateTime": "2025-03-15T14:30:00.000Z",
                    "exifInfo": {
                        "city": "Miami",
                        "country": "United States",
                        "description": "Birthday cake with candles"
                    }
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "type": "IMAGE",
                    "originalFileName": "birthday_party.heic",
                    "originalMimeType": "image/heic",
                    "fileCreatedAt": "2025-03-15T15:00:00.000Z",
                    "localDateTime": "2025-03-15T15:00:00.000Z",
                    "exifInfo": {
                        "city": "Miami",
                        "country": "United States",
                        "description": "Everyone at the party"
                    }
                }
            ],
            "total": 2,
            "count": 2,
            "nextPage": None
        }
    }


@pytest.fixture
def sample_scenario_json():
    """Sample scenario JSON for testing."""
    return {
        "id": "2025-03-15-edgar-birthday-miami",
        "title": "Edgar Birthday Miami",
        "request": "birthday march 2025",
        "state": "draft",
        "narrative": "",
        "items": [],
        "music": None,
        "created_at": "2025-03-15T00:00:00Z",
        "updated_at": "2025-03-15T00:00:00Z"
    }


@pytest.fixture
def mock_immich_session():
    """Mock requests.Session for Immich API calls."""
    session = MagicMock()
    session.headers = {}
    return session
