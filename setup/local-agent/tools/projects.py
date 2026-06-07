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


def set_timeline(project_id: str, asset_ids: list) -> dict:
    """Replace the project's timeline with an ordered list of assets.

    Args:
        project_id: The project id.
        asset_ids: Asset ids in the desired display order.

    Returns:
        {"timeline": [{"position": int, "asset_id": str}, ...], "count": int}
    """
    items = [{"position": i, "asset_id": aid} for i, aid in enumerate(asset_ids, 1)]
    p = _set_timeline(project_id, items)
    return {"timeline": p["timeline"], "count": len(p["timeline"])}


def list_projects() -> list:
    """List existing projects.

    Returns:
        List of {"id": str, "title": str, "state": str}, sorted by id.
    """
    stories_dir = os.environ.get("STORIES_DIR") or default_stories_dir()
    if not os.path.isdir(stories_dir):
        return []
    out = []
    for entry in sorted(os.listdir(stories_dir)):
        path = os.path.join(stories_dir, entry, "project.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            p = json.load(f)
        out.append({"id": p.get("id"), "title": p.get("title"), "state": p.get("state")})
    return out
