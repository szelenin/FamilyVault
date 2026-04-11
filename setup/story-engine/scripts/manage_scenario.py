#!/usr/bin/env python3
"""
DEPRECATED: Use manage_project.py instead. This file is kept only for
backward compatibility with the old assemble() function in assemble_video.py.
Will be removed once assemble_v2() fully replaces assemble().

manage-scenario.py — Create and manage story scenarios.

Commands:
  create   --title TITLE --request REQUEST
  show     SCENARIO_ID
  list
  add-item SCENARIO_ID --asset-id ID --caption TEXT [--position N]
  remove-item SCENARIO_ID --position N
  reorder  SCENARIO_ID --order 3,1,2
  set-narrative SCENARIO_ID --text TEXT
  set-music SCENARIO_ID --type bundled --mood upbeat --track track1
  set-music SCENARIO_ID --type user --file /path/to/song.mp3
  set-music SCENARIO_ID --type none
  list-music
  set-state SCENARIO_ID --state reviewed|approved|generated

Exit codes:
  0 — success
  2 — not found
  3 — precondition error (invalid state transition, missing file, etc.)
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

VALID_STATES = ["draft", "reviewed", "approved", "generated"]
VALID_TRANSITIONS: Dict[str, List[str]] = {
    "draft": ["reviewed"],
    "reviewed": ["approved"],
    "approved": ["generated"],
    "generated": [],
}

# Bundled music catalog structure: mood -> list of track names
BUNDLED_MUSIC_DIR = os.path.join(
    os.path.dirname(__file__), "..", "music"
)
BUNDLED_TRACKS: Dict[str, List[str]] = {
    "upbeat": ["track1", "track2", "track3", "track4"],
    "calm": ["track1", "track2", "track3", "track4"],
    "sentimental": ["track1", "track2", "track3", "track4"],
}

MAX_ITEMS = 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scenario_path(scenario_id: str, stories_dir: str) -> str:
    return os.path.join(stories_dir, scenario_id, "scenario.json")


def _load(scenario_id: str, stories_dir: str) -> dict:
    path = _scenario_path(scenario_id, stories_dir)
    if not os.path.exists(path):
        print(f"ERROR: Scenario not found: {scenario_id}", file=sys.stderr)
        sys.exit(2)
    with open(path) as f:
        return json.load(f)


def _save(scenario: dict, stories_dir: str) -> None:
    path = _scenario_path(scenario["id"], stories_dir)
    scenario["updated_at"] = datetime.utcnow().isoformat() + "Z"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(scenario, f, indent=2)


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _make_id(title: str) -> str:
    today = date.today().isoformat()
    slug = _slugify(title)
    return f"{today}-{slug}"


# ---------------------------------------------------------------------------
# US1: create / show / list
# ---------------------------------------------------------------------------

def create_scenario(
    title: str,
    request: str,
    stories_dir: Optional[str] = None,
) -> dict:
    """Create a new scenario in draft state."""
    if stories_dir is None:
        stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")
    scenario_id = _make_id(title)
    now = datetime.utcnow().isoformat() + "Z"
    scenario = {
        "id": scenario_id,
        "title": title,
        "request": request,
        "state": "draft",
        "narrative": "",
        "items": [],
        "music": None,
        "created_at": now,
        "updated_at": now,
    }
    _save(scenario, stories_dir)
    return scenario


def show_scenario(
    scenario_id: str,
    stories_dir: Optional[str] = None,
) -> dict:
    """Load and return a scenario by ID."""
    if stories_dir is None:
        stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")
    return _load(scenario_id, stories_dir)


def list_scenarios(stories_dir: Optional[str] = None) -> List[dict]:
    """Return all scenarios in STORIES_DIR."""
    if stories_dir is None:
        stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")
    scenarios = []
    if not os.path.isdir(stories_dir):
        return scenarios
    for entry in sorted(os.listdir(stories_dir)):
        path = os.path.join(stories_dir, entry, "scenario.json")
        if os.path.isfile(path):
            with open(path) as f:
                scenarios.append(json.load(f))
    return scenarios


# ---------------------------------------------------------------------------
# US2: add-item / remove-item / reorder / set-narrative
# ---------------------------------------------------------------------------

def add_item(
    scenario_id: str,
    asset_id: str,
    caption: str,
    position: Optional[int] = None,
    stories_dir: Optional[str] = None,
) -> dict:
    """Append or insert a media item into the scenario."""
    if stories_dir is None:
        stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")
    scenario = _load(scenario_id, stories_dir)
    items = scenario["items"]

    if len(items) >= MAX_ITEMS:
        print(f"ERROR: Scenario already has {MAX_ITEMS} items (maximum).", file=sys.stderr)
        sys.exit(3)

    new_item = {
        "asset_id": asset_id,
        "caption": caption,
        "position": None,  # set after insert
    }

    if position is not None:
        # 1-based insert; position 1 = insert before current first item
        idx = position - 1
        idx = max(0, min(idx, len(items)))
        items.insert(idx, new_item)
    else:
        items.append(new_item)

    # Renumber
    for i, item in enumerate(items):
        item["position"] = i + 1

    scenario["items"] = items
    _save(scenario, stories_dir)
    return scenario


def remove_item(
    scenario_id: str,
    position: int,
    stories_dir: Optional[str] = None,
) -> dict:
    """Remove item at given 1-based position and renumber."""
    if stories_dir is None:
        stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")
    scenario = _load(scenario_id, stories_dir)
    items = scenario["items"]
    idx = position - 1
    if idx < 0 or idx >= len(items):
        print(f"ERROR: No item at position {position}.", file=sys.stderr)
        sys.exit(3)
    items.pop(idx)
    for i, item in enumerate(items):
        item["position"] = i + 1
    scenario["items"] = items
    _save(scenario, stories_dir)
    return scenario


def reorder_items(
    scenario_id: str,
    new_order: List[int],
    stories_dir: Optional[str] = None,
) -> dict:
    """Reorder items. new_order is list of current positions in desired order."""
    if stories_dir is None:
        stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")
    scenario = _load(scenario_id, stories_dir)
    items = scenario["items"]
    n = len(items)

    if len(new_order) != n:
        print(
            f"ERROR: new_order has {len(new_order)} positions but scenario has {n} items.",
            file=sys.stderr,
        )
        sys.exit(3)

    if len(set(new_order)) != len(new_order):
        print("ERROR: new_order contains duplicate positions.", file=sys.stderr)
        sys.exit(3)

    expected = set(range(1, n + 1))
    provided = set(new_order)
    if provided != expected:
        print(
            f"ERROR: new_order must contain all positions 1-{n}. Got: {sorted(provided)}",
            file=sys.stderr,
        )
        sys.exit(3)

    reordered = [items[pos - 1] for pos in new_order]
    for i, item in enumerate(reordered):
        item["position"] = i + 1
    scenario["items"] = reordered
    _save(scenario, stories_dir)
    return scenario


def set_narrative(
    scenario_id: str,
    narrative: str,
    stories_dir: Optional[str] = None,
) -> dict:
    """Update the narrative field of a scenario."""
    if stories_dir is None:
        stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")
    scenario = _load(scenario_id, stories_dir)
    scenario["narrative"] = narrative
    _save(scenario, stories_dir)
    return scenario


# ---------------------------------------------------------------------------
# US3: set-music / list-music
# ---------------------------------------------------------------------------

def set_music(
    scenario_id: str,
    music_type: str,
    mood: Optional[str] = None,
    track: Optional[str] = None,
    file_path: Optional[str] = None,
    stories_dir: Optional[str] = None,
) -> dict:
    """Set music selection on a scenario."""
    if stories_dir is None:
        stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")
    scenario = _load(scenario_id, stories_dir)

    if music_type == "bundled":
        if mood not in BUNDLED_TRACKS:
            print(f"ERROR: Unknown mood '{mood}'. Valid: {list(BUNDLED_TRACKS)}", file=sys.stderr)
            sys.exit(3)
        if track not in BUNDLED_TRACKS[mood]:
            print(f"ERROR: Unknown track '{track}' for mood '{mood}'.", file=sys.stderr)
            sys.exit(3)
        track_path = os.path.join(BUNDLED_MUSIC_DIR, mood, f"{track}.mp3")
        scenario["music"] = {
            "type": "bundled",
            "mood": mood,
            "track": track,
            "path": track_path,
        }
    elif music_type == "user":
        if not file_path:
            print("ERROR: --file required for user music type.", file=sys.stderr)
            sys.exit(3)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Music file not found: {file_path}")
        scenario["music"] = {
            "type": "user",
            "path": file_path,
        }
    elif music_type == "none":
        scenario["music"] = {"type": "none"}
    else:
        print(f"ERROR: Unknown music type '{music_type}'. Valid: bundled, user, none", file=sys.stderr)
        sys.exit(3)

    _save(scenario, stories_dir)
    return scenario


def list_bundled_tracks() -> Dict[str, List[str]]:
    """Return dict of mood -> list of track names."""
    return {mood: list(tracks) for mood, tracks in BUNDLED_TRACKS.items()}


# ---------------------------------------------------------------------------
# US4: set-state
# ---------------------------------------------------------------------------

def set_state(
    scenario_id: str,
    new_state: str,
    stories_dir: Optional[str] = None,
) -> dict:
    """Advance scenario state (forward-only)."""
    if stories_dir is None:
        stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")

    if new_state not in VALID_STATES:
        print(f"ERROR: Unknown state '{new_state}'. Valid: {VALID_STATES}", file=sys.stderr)
        sys.exit(3)

    scenario = _load(scenario_id, stories_dir)
    current = scenario["state"]
    allowed = VALID_TRANSITIONS.get(current, [])

    if new_state not in allowed:
        print(
            f"ERROR: Cannot transition from '{current}' to '{new_state}'. "
            f"Allowed: {allowed}",
            file=sys.stderr,
        )
        sys.exit(3)

    scenario["state"] = new_state
    _save(scenario, stories_dir)
    return scenario


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Manage story scenarios")
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create")
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--request", required=True)

    # show
    p_show = sub.add_parser("show")
    p_show.add_argument("scenario_id")

    # list
    sub.add_parser("list")

    # add-item
    p_add = sub.add_parser("add-item")
    p_add.add_argument("scenario_id")
    p_add.add_argument("--asset-id", required=True, dest="asset_id")
    p_add.add_argument("--caption", required=True)
    p_add.add_argument("--position", type=int, default=None)

    # remove-item
    p_remove = sub.add_parser("remove-item")
    p_remove.add_argument("scenario_id")
    p_remove.add_argument("--position", type=int, required=True)

    # reorder
    p_reorder = sub.add_parser("reorder")
    p_reorder.add_argument("scenario_id")
    p_reorder.add_argument("--order", required=True,
                           help="Comma-separated new order, e.g. 3,1,2")

    # set-narrative
    p_narrative = sub.add_parser("set-narrative")
    p_narrative.add_argument("scenario_id")
    p_narrative.add_argument("--text", required=True)

    # set-music
    p_music = sub.add_parser("set-music")
    p_music.add_argument("scenario_id")
    p_music.add_argument("--type", choices=["bundled", "user", "none"], required=True,
                         dest="music_type")
    p_music.add_argument("--mood")
    p_music.add_argument("--track")
    p_music.add_argument("--file", dest="file_path")

    # list-music
    sub.add_parser("list-music")

    # set-state
    p_state = sub.add_parser("set-state")
    p_state.add_argument("scenario_id")
    p_state.add_argument("--state", required=True, dest="new_state")

    args = parser.parse_args()
    stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")

    if args.command == "create":
        s = create_scenario(args.title, args.request, stories_dir=stories_dir)
        print(json.dumps(s, indent=2))
    elif args.command == "show":
        s = show_scenario(args.scenario_id, stories_dir=stories_dir)
        print(json.dumps(s, indent=2))
    elif args.command == "list":
        scenarios = list_scenarios(stories_dir=stories_dir)
        if not scenarios:
            print("No scenarios found.")
            return
        # Table
        header = f"{'ID':<45} {'Title':<30} {'State':<12} {'Items':>5} {'Created'}"
        print(header)
        print("-" * len(header))
        for s in scenarios:
            print(
                f"{s['id']:<45} {s['title']:<30} {s['state']:<12} "
                f"{len(s['items']):>5}  {s['created_at'][:10]}"
            )
    elif args.command == "add-item":
        s = add_item(args.scenario_id, args.asset_id, args.caption,
                     position=args.position, stories_dir=stories_dir)
        print(json.dumps(s, indent=2))
    elif args.command == "remove-item":
        s = remove_item(args.scenario_id, args.position, stories_dir=stories_dir)
        print(json.dumps(s, indent=2))
    elif args.command == "reorder":
        new_order = [int(x) for x in args.order.split(",")]
        s = reorder_items(args.scenario_id, new_order, stories_dir=stories_dir)
        print(json.dumps(s, indent=2))
    elif args.command == "set-narrative":
        s = set_narrative(args.scenario_id, args.text, stories_dir=stories_dir)
        print(json.dumps(s, indent=2))
    elif args.command == "set-music":
        s = set_music(args.scenario_id, music_type=args.music_type,
                      mood=args.mood, track=args.track,
                      file_path=args.file_path, stories_dir=stories_dir)
        print(json.dumps(s, indent=2))
    elif args.command == "list-music":
        tracks = list_bundled_tracks()
        for mood, names in tracks.items():
            print(f"\n{mood.upper()}")
            for name in names:
                print(f"  {name}")
    elif args.command == "set-state":
        s = set_state(args.scenario_id, args.new_state, stories_dir=stories_dir)
        print(json.dumps(s, indent=2))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
