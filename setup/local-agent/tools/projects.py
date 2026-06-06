"""Project management tools (v2 manage_project)."""
import json
import os

from tools._engine import (
    create_project as _create_project,
    show_project as _show_project,
    set_timeline as _set_timeline,
    default_stories_dir,
)


def create_project(title: str, request: str) -> dict:
    """Create a new story project.

    Args:
        title: Human-readable title (used to derive the project id).
        request: The original natural-language request.

    Returns:
        {"project_id": str, "title": str, "state": str}
    """
    p = _create_project(title=title, request=request)
    return {"project_id": p["id"], "title": p["title"], "state": p["state"]}


def get_project(project_id: str) -> dict:
    """Return the full project state (timeline, scenes, status, etc.).

    Args:
        project_id: The project id returned by create_project.
    """
    return _show_project(project_id)
