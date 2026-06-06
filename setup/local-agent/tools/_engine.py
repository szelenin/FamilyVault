"""Single import bridge to the v2 story-engine scripts.

Mirrors tests/story-engine/conftest.py: add setup/story-engine to sys.path,
then import the `scripts` package. v1 (manage_scenario) is intentionally NOT
imported — v2 manage_project is the baseline.
"""
import os
import sys

_ENGINE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "story-engine")
)
if _ENGINE_ROOT not in sys.path:
    sys.path.insert(0, _ENGINE_ROOT)

from scripts.search_photos import search_photos, make_session, get_api_key  # noqa: E402
from scripts.manage_project import (  # noqa: E402
    create_project,
    show_project,
    set_timeline,
    _default_stories_dir as default_stories_dir,
)

__all__ = [
    "search_photos",
    "make_session",
    "get_api_key",
    "create_project",
    "show_project",
    "set_timeline",
    "default_stories_dir",
]
