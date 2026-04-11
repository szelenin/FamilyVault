"""Project file management for Story Engine v2. Replaces manage_scenario.py."""
import json
import os
import re
import sys
from datetime import datetime
from typing import Optional

VALID_STATES = ["searching", "selecting", "previewing", "approved", "generated"]
VALID_TRANSITIONS = {
    "searching": ["selecting"],
    "selecting": ["previewing"],
    "previewing": ["approved"],
    "approved": ["generated", "previewing"],
    "generated": [],
}
MAX_ITEMS = 60


def _default_stories_dir():
    return os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")


def _make_id(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    date_prefix = datetime.utcnow().strftime("%Y-%m-%d")
    return "{}-{}".format(date_prefix, slug)


def _project_path(project_id, stories_dir):
    return os.path.join(stories_dir, project_id, "project.json")


def _save(project, stories_dir):
    project["updated_at"] = datetime.utcnow().isoformat() + "Z"
    path = _project_path(project["id"], stories_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(project, f, indent=2)


def _load(project_id, stories_dir):
    path = _project_path(project_id, stories_dir)
    if not os.path.exists(path):
        raise FileNotFoundError("Project not found: {}".format(path))
    with open(path) as f:
        return json.load(f)


def create_project(title, request, search_params=None, stories_dir=None):
    # type: (str, str, Optional[dict], Optional[str]) -> dict
    """Create a new project in searching state."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project_id = _make_id(title)
    now = datetime.utcnow().isoformat() + "Z"
    project = {
        "id": project_id,
        "title": title,
        "request": request,
        "state": "searching",
        "search_params": search_params or {},
        "must_haves": [],
        "candidate_pool": [],
        "burst_groups": {},
        "scenes": [],
        "timeline": [],
        "budget": {
            "total": 0,
            "formula": "base 10 + 5 per day",
            "trip_days": 0,
            "per_scene_overrides": {},
        },
        "discovery": {
            "scenes": [],
            "total_candidates": 0,
            "preview": {"album_id": None, "share_key": None},
        },
        "scene_confirmation": None,
        "assembly_config": {
            "orientation": "portrait",
            "resolution": "1080x1920",
            "crf": 18,
            "fps": 30,
            "padding": "black",
        },
        "music": None,
        "preview": {"album_id": None, "share_key": None},
        "created_at": now,
        "updated_at": now,
    }
    _save(project, stories_dir)
    return project


def show_project(project_id, stories_dir=None):
    # type: (str, Optional[str]) -> dict
    """Load and return a project by ID."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    return _load(project_id, stories_dir)


def set_state(project_id, state, stories_dir=None):
    # type: (str, str, Optional[str]) -> dict
    """Advance project state with transition validation."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    if state not in VALID_STATES:
        raise ValueError("Invalid state: '{}'. Valid: {}".format(state, VALID_STATES))
    project = _load(project_id, stories_dir)
    current = project["state"]
    allowed = VALID_TRANSITIONS.get(current, [])
    if state not in allowed:
        raise ValueError(
            "Cannot transition from '{}' to '{}'. Allowed: {}".format(current, state, allowed)
        )
    project["state"] = state
    _save(project, stories_dir)
    return project


def set_candidate_pool(project_id, candidates, stories_dir=None):
    # type: (str, list, Optional[str]) -> dict
    """Set the candidate pool on a project."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project = _load(project_id, stories_dir)
    project["candidate_pool"] = candidates
    _save(project, stories_dir)
    return project


def set_timeline(project_id, timeline, stories_dir=None):
    # type: (str, list, Optional[str]) -> dict
    """Set the timeline on a project."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project = _load(project_id, stories_dir)
    project["timeline"] = timeline
    _save(project, stories_dir)
    return project


def swap_item(project_id, position, new_asset_id, stories_dir=None):
    # type: (str, int, str, Optional[str]) -> dict
    """Swap a timeline item at position with a new asset."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project = _load(project_id, stories_dir)
    items = project["timeline"]
    idx = None
    for i, item in enumerate(items):
        if item.get("position") == position:
            idx = i
            break
    if idx is None:
        raise ValueError("No item at position {}".format(position))
    items[idx]["asset_id"] = new_asset_id
    _save(project, stories_dir)
    return project


def remove_item(project_id, position, stories_dir=None):
    # type: (str, int, Optional[str]) -> dict
    """Remove a timeline item and renumber."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project = _load(project_id, stories_dir)
    items = project["timeline"]
    project["timeline"] = [item for item in items if item.get("position") != position]
    for i, item in enumerate(project["timeline"]):
        item["position"] = i + 1
    _save(project, stories_dir)
    return project


def reorder_items(project_id, new_order, stories_dir=None):
    # type: (str, list, Optional[str]) -> dict
    """Reorder timeline items. new_order is a list of current positions in desired order."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project = _load(project_id, stories_dir)
    items = project["timeline"]
    by_pos = {item["position"]: item for item in items}
    reordered = []
    for new_pos, old_pos in enumerate(new_order, 1):
        item = by_pos[old_pos]
        item["position"] = new_pos
        reordered.append(item)
    project["timeline"] = reordered
    _save(project, stories_dir)
    return project


def trim_video(project_id, position, start, end, stories_dir=None):
    # type: (str, int, float, float, Optional[str]) -> dict
    """Set trim points for a video clip in the timeline."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project = _load(project_id, stories_dir)
    for item in project["timeline"]:
        if item.get("position") == position:
            item["trim_start"] = start
            item["trim_end"] = end
            _save(project, stories_dir)
            return project
    raise ValueError("No item at position {}".format(position))


def set_budget(project_id, total=None, overrides=None, stories_dir=None):
    # type: (str, Optional[int], Optional[dict], Optional[str]) -> dict
    """Set budget total and/or per-scene overrides."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project = _load(project_id, stories_dir)
    if total is not None:
        project["budget"]["total"] = total
    if overrides is not None:
        project["budget"]["per_scene_overrides"] = overrides
    _save(project, stories_dir)
    return project


def set_discovery(project_id, discovery, stories_dir=None):
    # type: (str, dict, Optional[str]) -> dict
    """Set the discovery result (Phase A output) on a project."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project = _load(project_id, stories_dir)
    project["discovery"] = discovery
    _save(project, stories_dir)
    return project


def set_scene_confirmation(project_id, confirmation, stories_dir=None):
    # type: (str, object, Optional[str]) -> dict
    """Set which scenes the user confirmed for Phase B.

    confirmation can be:
      - "all" — include all scenes
      - ["s1", "s3"] — include specific scene IDs
      - {"exclude": ["s2"]} — include all except listed
    """
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project = _load(project_id, stories_dir)
    project["scene_confirmation"] = confirmation
    _save(project, stories_dir)
    return project


def set_assembly_config(project_id, config, stories_dir=None):
    # type: (str, dict, Optional[str]) -> dict
    """Update assembly config fields. Merges with existing config."""
    if stories_dir is None:
        stories_dir = _default_stories_dir()
    project = _load(project_id, stories_dir)
    if "assembly_config" not in project:
        project["assembly_config"] = {}
    project["assembly_config"].update(config)
    _save(project, stories_dir)
    return project
