"""Hybrid video frame sampling — decide which timestamps to extract from a clip.

Public API
----------
detect_scenes(video_path) -> list[tuple[float, float]]
    Thin wrapper around PySceneDetect (lazy-imported inside the function body).
    Returns (start_sec, end_sec) pairs, one per detected scene.
    NOT exercised by unit tests; requires scenedetect to be installed at call time.

plan_frames(scenes, duration, *, frame_min, frame_max, frames_per_scene) -> SamplingPlan
    PURE function. Accepts a list of already-detected (start, end) scene tuples plus
    the clip duration (seconds). Returns the timestamps to extract for captioning and
    for OCR. Config-backed defaults are read from env vars at call time.

SamplingPlan
    caption_frames : list[float]  — sorted, unique timestamps for VLM captioning
    ocr_frames     : list[float]  — sorted subset chosen for on-screen-text reading

Config env vars (read at call time; explicit keyword args override them):
    FRAME_MIN         default 3   — minimum caption frames returned
    FRAME_MAX         default 20  — maximum caption frames returned
    FRAMES_PER_SCENE  default 2   — frames sampled inside each scene
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

@dataclass
class SamplingPlan:
    """Result of plan_frames()."""
    caption_frames: list[float] = field(default_factory=list)
    ocr_frames: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

_SENTINEL = object()  # distinguishes "not supplied" from None/0


def _cfg_int(env_name: str, default: int, override) -> int:
    """Return override if supplied, else env var if set, else default."""
    if override is not _SENTINEL:
        return int(override)
    raw = os.environ.get(env_name)
    if raw is not None:
        return int(raw)
    return default


# ---------------------------------------------------------------------------
# Core pure logic
# ---------------------------------------------------------------------------

def plan_frames(
    scenes: Sequence[tuple[float, float]],
    duration: float,
    *,
    frame_min=_SENTINEL,
    frame_max=_SENTINEL,
    frames_per_scene=_SENTINEL,
) -> SamplingPlan:
    """Return a SamplingPlan for the given scene list and clip duration.

    Parameters
    ----------
    scenes:
        List of (start_sec, end_sec) tuples from scene detection. Pass [] or a
        single-element list to trigger the uniform-fallback path.
    duration:
        Total clip length in seconds.
    frame_min, frame_max, frames_per_scene:
        Optional overrides; if omitted the env vars FRAME_MIN / FRAME_MAX /
        FRAMES_PER_SCENE are consulted, falling back to 3 / 20 / 2.
    """
    fmin = _cfg_int("FRAME_MIN", 3, frame_min)
    fmax = _cfg_int("FRAME_MAX", 20, frame_max)
    fps = _cfg_int("FRAMES_PER_SCENE", 2, frames_per_scene)

    # Guard: clamp to sensible relationship
    fmax = max(fmax, fmin)

    # ------------------------------------------------------------------
    # Uniform fallback: 0 or 1 scene
    # ------------------------------------------------------------------
    if len(scenes) <= 1:
        return _uniform_plan(duration, fmin, fmax)

    # ------------------------------------------------------------------
    # Multi-scene path
    # ------------------------------------------------------------------

    # 1. Global anchors: first, middle, last
    anchors: list[float] = [0.0, duration / 2.0, duration]

    # 2. Per-scene frames (fps evenly-spaced timestamps inside each scene)
    #    The scene midpoint is always included as the first/only frame so it
    #    is guaranteed to appear in caption_frames (and thus in ocr_frames).
    scene_frames: list[float] = []
    ocr_candidates: list[float] = []  # scene midpoints for OCR

    for start, end in scenes:
        length = end - start
        if length <= 0:
            continue

        # Midpoint → OCR representative; always added to scene_frames so it
        # survives into caption_frames after dedup/cap.
        mid = start + length / 2.0
        ocr_candidates.append(mid)
        scene_frames.append(mid)

        # Additional frames to fill up to fps total per scene
        if fps > 1:
            # Place (fps-1) extra points around the midpoint
            extras = fps - 1
            step = length / (extras + 1)
            for k in range(1, extras + 1):
                t = start + k * step
                if abs(t - mid) > 1e-9:  # skip if it would duplicate mid
                    scene_frames.append(t)

    # 3. Combine & deduplicate
    raw = _dedup_sorted(anchors + scene_frames)

    # 4. Cap to frame_max (evenly downsample if needed)
    caption = _cap(raw, fmax)

    # 5. Enforce frame_min floor (add evenly-spaced frames if short)
    if len(caption) < fmin:
        extra = _uniform_timestamps(duration, fmin)
        caption = _dedup_sorted(caption + extra)

    # ------------------------------------------------------------------
    # OCR frames: scene midpoints, all present in caption_frames (by
    # construction above), capped at fmax.
    # ------------------------------------------------------------------
    ocr = _build_ocr(ocr_candidates, caption, fmax)

    return SamplingPlan(caption_frames=caption, ocr_frames=ocr)


# ---------------------------------------------------------------------------
# Uniform fallback helpers
# ---------------------------------------------------------------------------

def _uniform_plan(duration: float, fmin: int, fmax: int) -> SamplingPlan:
    """Uniform-fallback: evenly spaced frames across duration."""
    n = max(fmin, 3)  # always at least frame_min, at least 3
    n = min(n, fmax)
    caption = _uniform_timestamps(duration, n)
    # OCR: small subset of caption frames (up to ~3)
    ocr_n = max(1, min(3, len(caption)))
    if ocr_n >= len(caption):
        ocr = list(caption)
    else:
        indices = _evenly_spaced_indices(len(caption), ocr_n)
        ocr = [caption[i] for i in indices]
    return SamplingPlan(caption_frames=caption, ocr_frames=ocr)


def _uniform_timestamps(duration: float, n: int) -> list[float]:
    """Return n evenly-spaced timestamps in [0, duration]."""
    if n <= 0:
        return []
    if n == 1:
        return [0.0]
    if duration <= 0.0:
        # Zero-duration edge: return n copies of 0.0 deduplicated → just [0.0]
        # But we must return at least frame_min; fill with 0.0
        return [0.0] * n  # will be deduped by caller if needed
    step = duration / (n - 1)
    return [round(i * step, 10) for i in range(n)]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _dedup_sorted(frames: list[float]) -> list[float]:
    """Return sorted, deduplicated list. Uses exact float equality."""
    return sorted(set(frames))


def _cap(frames: list[float], limit: int) -> list[float]:
    """Evenly downsample `frames` to at most `limit` entries."""
    if len(frames) <= limit:
        return list(frames)
    indices = _evenly_spaced_indices(len(frames), limit)
    return [frames[i] for i in indices]


def _evenly_spaced_indices(total: int, count: int) -> list[int]:
    """Pick `count` evenly-spaced indices from range(total)."""
    if count >= total:
        return list(range(total))
    if count == 1:
        return [total // 2]
    step = (total - 1) / (count - 1)
    return [round(i * step) for i in range(count)]


def _build_ocr(
    ocr_candidates: list[float],
    caption_frames: list[float],
    fmax: int,
) -> list[float]:
    """Select OCR frames: scene midpoints that appear in caption_frames, capped."""
    caption_set = set(caption_frames)

    # Keep candidates that are in caption_frames
    matched = [t for t in ocr_candidates if t in caption_set]

    # If none matched (due to capping), take the nearest caption frame for each candidate
    if not matched:
        seen: set[float] = set()
        for cand in ocr_candidates:
            nearest = min(caption_frames, key=lambda t: abs(t - cand))
            if nearest not in seen:
                matched.append(nearest)
                seen.add(nearest)

    # Cap to fmax
    if len(matched) > fmax:
        indices = _evenly_spaced_indices(len(matched), fmax)
        matched = [matched[i] for i in indices]

    return sorted(matched)


# ---------------------------------------------------------------------------
# Thin PySceneDetect wrapper (lazy import — NOT used by unit tests)
# ---------------------------------------------------------------------------

def _tc_seconds(timecode) -> float:
    """Seconds from a PySceneDetect FrameTimecode, across versions.

    0.7 exposes a `.seconds` property (and deprecates `.get_seconds()`).
    """
    val = getattr(timecode, "seconds", None)
    return float(val) if val is not None else float(timecode.get_seconds())


def detect_scenes(video_path: str) -> list[tuple[float, float]]:
    """Detect scenes in a video file using PySceneDetect.

    Lazy-imports scenedetect at call time so importing this module never
    requires PySceneDetect to be installed (unit tests import safely).

    Returns a list of (start_sec, end_sec) tuples, one per scene.
    Raises ImportError if scenedetect is not installed.
    """
    # Lazy imports — intentionally inside the function body.
    from scenedetect import open_video, SceneManager  # type: ignore[import]
    from scenedetect.detectors import AdaptiveDetector  # type: ignore[import]

    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(AdaptiveDetector())
    scene_manager.detect_scenes(video, show_progress=False)

    scene_list = scene_manager.get_scene_list()
    if not scene_list:
        # No cuts detected → single scene spanning the whole clip. Use the
        # VideoStream's public duration (PySceneDetect 0.7 removed `.cap`).
        duration = _tc_seconds(video.duration) if getattr(video, "duration", None) else 0.0
        return [(0.0, duration)]

    return [(_tc_seconds(scene[0]), _tc_seconds(scene[1])) for scene in scene_list]
