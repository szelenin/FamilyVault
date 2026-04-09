"""Scoring, deduplication, scene detection, and timeline selection for Story Engine v2."""
import sys
import os
from datetime import datetime
from typing import Optional

# Photo scoring weights
PHOTO_WEIGHTS = {"faces": 0.4, "relevance": 0.3, "diversity": 0.2, "resolution": 0.1}
# Video scoring weights
VIDEO_WEIGHTS = {"relevance": 0.4, "duration": 0.25, "diversity": 0.2, "faces": 0.15}
# Duration sweet spot (seconds)
DURATION_SWEET_MIN = 5.0
DURATION_SWEET_MAX = 30.0
# Budget cap
MAX_BUDGET = 60
# Default photo duration in timeline (seconds)
DEFAULT_PHOTO_DURATION = 4.0


def _aid(candidate):
    """Get asset_id from candidate, supporting both 'asset_id' and 'id' fields."""
    return candidate.get("asset_id") or candidate.get("id", "")


def _parse_time(ts):
    """Parse ISO 8601 timestamp string to datetime."""
    ts = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, AttributeError):
        # Python 3.9 fallback
        ts = ts.replace("+00:00", "")
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")


def _face_score(face_count):
    """Normalize face count to 0-1 score. 1-3 faces is ideal."""
    if face_count == 0:
        return 0.0
    if face_count <= 3:
        return 1.0
    return max(0.5, 1.0 - (face_count - 3) * 0.1)


def _resolution_score(width, height):
    """Normalize resolution to 0-1 score. 4K+ gets 1.0."""
    pixels = (width or 0) * (height or 0)
    if pixels >= 12_000_000:  # 4K
        return 1.0
    if pixels >= 8_000_000:  # ~3K
        return 0.8
    if pixels >= 2_000_000:  # ~1080p
        return 0.6
    if pixels >= 1_000_000:
        return 0.3
    return 0.1


def _duration_score(duration):
    """Score video duration. Sweet spot is 5-30s."""
    if duration is None or duration <= 0:
        return 0.0
    if duration < 2.0:
        return duration / 2.0 * 0.2  # 0 to 0.2 for < 2s
    if DURATION_SWEET_MIN <= duration <= DURATION_SWEET_MAX:
        return 1.0
    if duration < DURATION_SWEET_MIN:
        return 0.5 + 0.5 * (duration - 2.0) / (DURATION_SWEET_MIN - 2.0)
    # > 30s, decay
    return max(0.3, 1.0 - (duration - DURATION_SWEET_MAX) / 120.0)


def generate_caption(candidate):
    """Generate a caption from Immich metadata. Never hallucinate."""
    parts = []
    desc = candidate.get("description", "")
    if desc:
        parts.append(desc)
    names = candidate.get("people_names", [])
    if names:
        parts.append(", ".join(names))
    city = candidate.get("city", "")
    if city and not parts:
        parts.append(city)
    if not parts:
        fname = candidate.get("filename", "")
        if fname:
            parts.append(fname.rsplit(".", 1)[0])
    return " — ".join(parts) if parts else ""


def extract_must_have_keywords(prompt):
    """Extract must-have keywords from a user prompt.

    Looks for patterns like:
    - "X, Y, Z must have"
    - "must include X, Y"
    - Comma-separated items after location/trip description
    """
    import re
    prompt_lower = prompt.lower()

    # Pattern: "X, Y, Z must have" or "must have X, Y, Z"
    match = re.search(r'(.+?)\s+must\s+have', prompt_lower)
    if match:
        # Extract the part before "must have" and split by comma
        before = match.group(1)
        # Take only the comma-separated tail
        parts = [p.strip() for p in before.split(",")]
        # Filter out parts that look like the main query (> 5 words)
        keywords = [p for p in parts if p and len(p.split()) <= 4]
        if keywords:
            return keywords

    match = re.search(r'must\s+(?:have|include)\s+(.+)', prompt_lower)
    if match:
        after = match.group(1)
        keywords = [p.strip().rstrip(".") for p in after.split(",")]
        return [k for k in keywords if k]

    return []


def generate_search_variations(keyword):
    """Generate search variations for a keyword to handle typos and metadata mismatches.

    Returns a list of search strings to try.
    """
    variations = [keyword]
    # Add singular/plural
    if keyword.endswith("s"):
        variations.append(keyword[:-1])
    else:
        variations.append(keyword + "s")
    # Add with/without common suffixes
    for suffix in [" garden", " gardens", " park", " beach", " tour"]:
        if keyword.endswith(suffix):
            variations.append(keyword.replace(suffix, ""))
        elif not any(keyword.endswith(s) for s in [" garden", " gardens", " park", " beach", " tour"]):
            variations.append(keyword + suffix)
    # Deduplicate
    seen = set()
    unique = []
    for v in variations:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique[:5]  # Cap at 5 variations


def score_candidates(candidates, must_have_keywords=None):
    # type: (list, Optional[list]) -> list
    """Score each candidate using fixed-weight formulas. Must-haves bypass scoring."""
    for c in candidates:
        is_video = c.get("type") == "VIDEO"
        face_s = _face_score(c.get("face_count", 0))
        rel_s = c.get("relevance_score", 0.5)
        res_s = _resolution_score(c.get("width", 0), c.get("height", 0))
        div_s = 0.5  # default diversity; adjusted later by select_timeline

        if is_video:
            dur_s = _duration_score(c.get("duration"))
            total = (
                VIDEO_WEIGHTS["relevance"] * rel_s
                + VIDEO_WEIGHTS["duration"] * dur_s
                + VIDEO_WEIGHTS["diversity"] * div_s
                + VIDEO_WEIGHTS["faces"] * face_s
            )
            c["score"] = {
                "faces": face_s,
                "relevance": rel_s,
                "duration": dur_s,
                "diversity": div_s,
                "resolution": res_s,
                "total": round(total, 4),
            }
        else:
            total = (
                PHOTO_WEIGHTS["faces"] * face_s
                + PHOTO_WEIGHTS["relevance"] * rel_s
                + PHOTO_WEIGHTS["diversity"] * div_s
                + PHOTO_WEIGHTS["resolution"] * res_s
            )
            c["score"] = {
                "faces": face_s,
                "relevance": rel_s,
                "diversity": div_s,
                "resolution": res_s,
                "total": round(total, 4),
            }

    return candidates


def detect_bursts(candidates, time_threshold_sec=5):
    # type: (list, int) -> dict
    """Group candidates by timestamp proximity into burst groups."""
    if not candidates:
        return {}

    sorted_c = sorted(candidates, key=lambda c: c.get("taken_at", ""))
    groups = {}
    current_group = [sorted_c[0]]
    group_counter = 0

    for c in sorted_c[1:]:
        prev_time = _parse_time(current_group[-1].get("taken_at", "2000-01-01T00:00:00Z"))
        curr_time = _parse_time(c.get("taken_at", "2000-01-01T00:00:00Z"))
        diff = abs((curr_time - prev_time).total_seconds())

        if diff <= time_threshold_sec:
            current_group.append(c)
        else:
            if len(current_group) > 1:
                groups = _finalize_burst_group(groups, current_group, group_counter)
                group_counter += 1
            current_group = [c]

    # Final group
    if len(current_group) > 1:
        groups = _finalize_burst_group(groups, current_group, group_counter)

    return groups


def _finalize_burst_group(groups, members, counter):
    """Pick primary from burst group members, store alternates."""
    gid = "bg-{:03d}".format(counter)

    # Prefer videos over photos
    videos = [m for m in members if m.get("type") == "VIDEO"]
    photos = [m for m in members if m.get("type") != "VIDEO"]

    if videos:
        # Sort videos by score, pick best as primary
        videos.sort(key=lambda m: m.get("score", {}).get("total", 0), reverse=True)
        primary = videos[0]
        rest = videos[1:] + photos
    else:
        # All photos — sort by score
        members_sorted = sorted(members, key=lambda m: m.get("score", {}).get("total", 0), reverse=True)
        primary = members_sorted[0]
        rest = members_sorted[1:]

    alternates = [m.get("asset_id") or m.get("id") for m in rest[:3]]
    timestamps = [m.get("taken_at", "") for m in members]

    groups[gid] = {
        "primary_asset_id": primary.get("asset_id") or primary.get("id"),
        "alternate_asset_ids": alternates,
        "timestamp_range": [min(timestamps), max(timestamps)],
    }

    # Tag members with burst group
    for m in members:
        m["burst_group_id"] = gid

    return groups


def detect_scenes(candidates, gap_minutes=30):
    # type: (list, int) -> list
    """Split candidates into scenes by time gaps."""
    if not candidates:
        return []

    sorted_c = sorted(candidates, key=lambda c: c.get("taken_at", ""))
    scenes = []
    current_scene = [sorted_c[0]]
    scene_counter = 0

    for c in sorted_c[1:]:
        prev_time = _parse_time(current_scene[-1].get("taken_at", "2000-01-01T00:00:00Z"))
        curr_time = _parse_time(c.get("taken_at", "2000-01-01T00:00:00Z"))
        diff_minutes = abs((curr_time - prev_time).total_seconds()) / 60.0

        if diff_minutes > gap_minutes:
            scenes.append(_make_scene(current_scene, scene_counter))
            scene_counter += 1
            current_scene = [c]
        else:
            current_scene.append(c)

    scenes.append(_make_scene(current_scene, scene_counter))
    return scenes


def _make_scene(members, counter):
    timestamps = [m.get("taken_at", "") for m in members]
    return {
        "id": "scene-{:03d}".format(counter),
        "label": "Scene {}".format(counter + 1),
        "time_range": [min(timestamps), max(timestamps)],
        "candidate_count": len(members),
        "asset_ids": [_aid(m) for m in members],
    }


def allocate_budget(scenes, total_budget, overrides=None):
    # type: (list, int, Optional[dict]) -> dict
    """Distribute total budget across scenes proportionally."""
    effective_budget = min(total_budget, MAX_BUDGET)
    overrides = overrides or {}

    # Apply overrides first
    alloc = {}
    remaining_budget = effective_budget
    remaining_scenes = []

    for scene in scenes:
        sid = scene["id"]
        if sid in overrides:
            alloc[sid] = overrides[sid]
            remaining_budget -= overrides[sid]
        else:
            remaining_scenes.append(scene)

    if not remaining_scenes:
        return alloc

    # Distribute remaining proportionally
    total_candidates = sum(s["candidate_count"] for s in remaining_scenes)
    if total_candidates == 0:
        for s in remaining_scenes:
            alloc[s["id"]] = 1
        return alloc

    # If more scenes than remaining budget, only top scenes get items
    if len(remaining_scenes) > remaining_budget:
        # Sort by candidate count descending, only top N scenes get 1 each
        remaining_scenes.sort(key=lambda s: s["candidate_count"], reverse=True)
        for i, s in enumerate(remaining_scenes):
            alloc[s["id"]] = 1 if i < remaining_budget else 0
        return {k: v for k, v in alloc.items() if v > 0}

    for s in remaining_scenes:
        proportion = s["candidate_count"] / total_candidates
        alloc[s["id"]] = max(1, round(proportion * remaining_budget))

    # Adjust if over/under budget
    allocated = sum(alloc.values())
    if allocated > effective_budget:
        # Trim from largest non-override scenes
        diff = allocated - effective_budget
        for s in sorted(remaining_scenes, key=lambda s: alloc[s["id"]], reverse=True):
            if diff <= 0:
                break
            reduce = min(diff, alloc[s["id"]] - 1)
            alloc[s["id"]] -= reduce
            diff -= reduce
    elif allocated < effective_budget:
        # Add to largest non-override scenes
        diff = effective_budget - allocated
        for s in sorted(remaining_scenes, key=lambda s: alloc[s["id"]], reverse=True):
            if diff <= 0:
                break
            alloc[s["id"]] += 1
            diff -= 1

    return alloc


def select_timeline(candidates, burst_groups, scenes, budget_allocation, must_haves=None):
    # type: (list, dict, list, dict, Optional[list]) -> list
    """Pick final timeline items respecting budget, diversity, and must-haves."""
    must_haves = must_haves or []
    must_have_ids = {_aid(m) for m in must_haves}

    # Build burst primary set
    burst_primaries = set()
    burst_non_primaries = set()
    for gid, g in burst_groups.items():
        burst_primaries.add(g["primary_asset_id"])
        for alt in g["alternate_asset_ids"]:
            burst_non_primaries.add(alt)

    # Build scene membership map
    scene_map = {}
    for scene in scenes:
        for aid in scene.get("asset_ids", []):
            scene_map[aid] = scene["id"]

    # Start with must-haves
    selected_ids = set()
    timeline = []

    for mh in must_haves:
        aid = _aid(mh)
        if aid not in selected_ids:
            selected_ids.add(aid)
            timeline.append(mh)

    # For each scene, pick top-scored candidates up to budget
    for scene in scenes:
        sid = scene["id"]
        budget = budget_allocation.get(sid, 0)

        # Candidates in this scene, not already selected, not burst alternates
        scene_candidates = [
            c for c in candidates
            if _aid(c) in scene.get("asset_ids", [])
            and _aid(c) not in selected_ids
            and _aid(c) not in burst_non_primaries
        ]

        # Sort by score descending
        scene_candidates.sort(key=lambda c: c.get("score", {}).get("total", 0), reverse=True)

        # Already selected from this scene (must-haves)
        already_in_scene = sum(1 for aid in selected_ids if scene_map.get(aid) == sid)
        remaining = max(0, budget - already_in_scene)

        for c in scene_candidates[:remaining]:
            selected_ids.add(_aid(c))
            timeline.append(c)

    # Enforce diversity: no more than 30% from any single scene
    total_budget_sum = sum(budget_allocation.values())
    if total_budget_sum > 0:
        max_per_scene = max(1, int(total_budget_sum * 0.3) + 1)
        scene_counts = {}
        filtered = []
        for item in timeline:
            sid = scene_map.get(_aid(item), "")
            scene_counts[sid] = scene_counts.get(sid, 0) + 1
            if scene_counts[sid] <= max_per_scene or _aid(item) in must_have_ids:
                filtered.append(item)
        timeline = filtered

    # Sort chronologically
    timeline.sort(key=lambda c: c.get("taken_at", ""))

    # Assign positions and durations
    result = []
    for i, item in enumerate(timeline):
        is_video = item.get("type") == "VIDEO"
        duration = item.get("duration", DEFAULT_PHOTO_DURATION) if is_video else DEFAULT_PHOTO_DURATION

        result.append({
            "position": i + 1,
            "asset_id": _aid(item),
            "type": item.get("type", "IMAGE"),
            "caption": item.get("description", ""),
            "taken_at": item.get("taken_at", ""),
            "duration": duration,
            "trim_start": None if not is_video else 0.0,
            "trim_end": None if not is_video else duration,
            "transition": "crossfade",
            "scene_id": scene_map.get(_aid(item), ""),
        })

    return result
