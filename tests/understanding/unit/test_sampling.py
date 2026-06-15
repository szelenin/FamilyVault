"""Unit tests for fetch.sampling — hybrid video frame sampling logic.

All tests operate on SYNTHETIC scene lists (no scenedetect, no files, no FFmpeg).
Must run in milliseconds with zero third-party dependencies.

Public API under test:
    plan_frames(scenes, duration, *, frame_min, frame_max, frames_per_scene)
        -> SamplingPlan(caption_frames: list[float], ocr_frames: list[float])

Config-backed defaults (env: FRAME_MIN=3, FRAME_MAX=20, FRAMES_PER_SCENE=2).
"""
import os
import pytest
from fetch.sampling import plan_frames, SamplingPlan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scenes(*bounds):
    """Build a scene list from (start, end) pairs."""
    return list(bounds)


# ---------------------------------------------------------------------------
# SamplingPlan shape
# ---------------------------------------------------------------------------

class TestSamplingPlanShape:
    def test_is_dataclass_with_caption_and_ocr_fields(self):
        plan = plan_frames([], duration=10.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert hasattr(plan, "caption_frames")
        assert hasattr(plan, "ocr_frames")

    def test_caption_frames_is_sorted_list_of_floats(self):
        plan = plan_frames([], duration=10.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert isinstance(plan.caption_frames, list)
        assert plan.caption_frames == sorted(plan.caption_frames)
        for t in plan.caption_frames:
            assert isinstance(t, float)

    def test_ocr_frames_is_subset_of_caption_frames(self):
        scenes = _scenes((0.0, 5.0), (5.0, 10.0), (10.0, 20.0))
        plan = plan_frames(scenes, duration=20.0, frame_min=3, frame_max=20, frames_per_scene=2)
        for t in plan.ocr_frames:
            assert t in plan.caption_frames


# ---------------------------------------------------------------------------
# Multi-scene behaviour
# ---------------------------------------------------------------------------

class TestMultiScene:
    def test_caption_frames_includes_first_mid_last_anchors(self):
        scenes = _scenes((0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, 20.0))
        duration = 20.0
        plan = plan_frames(scenes, duration=duration, frame_min=3, frame_max=20, frames_per_scene=2)
        cf = plan.caption_frames
        # first anchor
        assert cf[0] == pytest.approx(0.0, abs=1e-6)
        # last anchor
        assert cf[-1] == pytest.approx(duration, abs=1e-6)
        # mid anchor present somewhere in the middle
        mid = duration / 2.0
        assert any(abs(t - mid) < 1.0 for t in cf), f"No frame near midpoint {mid} in {cf}"

    def test_caption_frames_has_roughly_frames_per_scene_per_scene(self):
        # 4 scenes × 2 fps = 8 scene frames + anchors → well below frame_max=20
        scenes = _scenes((0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, 20.0))
        plan = plan_frames(scenes, duration=20.0, frame_min=3, frame_max=20, frames_per_scene=2)
        # At minimum each scene contributes 1 frame; total should be > 4
        assert len(plan.caption_frames) >= 4

    def test_caption_frames_all_within_duration(self):
        scenes = _scenes((0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, 20.0))
        duration = 20.0
        plan = plan_frames(scenes, duration=duration, frame_min=3, frame_max=20, frames_per_scene=2)
        for t in plan.caption_frames:
            assert -1e-9 <= t <= duration + 1e-9, f"Frame {t} out of [0, {duration}]"

    def test_caption_frames_unique(self):
        scenes = _scenes((0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, 20.0))
        plan = plan_frames(scenes, duration=20.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert len(plan.caption_frames) == len(set(plan.caption_frames))

    def test_caption_frames_sorted(self):
        scenes = _scenes((0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, 20.0))
        plan = plan_frames(scenes, duration=20.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert plan.caption_frames == sorted(plan.caption_frames)


# ---------------------------------------------------------------------------
# frame_max cap
# ---------------------------------------------------------------------------

class TestFrameMaxCap:
    def test_many_scenes_capped_at_frame_max(self):
        # 30 scenes, 2 fps each = 60 raw frames → must be capped to frame_max=20
        scenes = [(i * 2.0, (i + 1) * 2.0) for i in range(30)]
        duration = 60.0
        frame_max = 20
        plan = plan_frames(scenes, duration=duration, frame_min=3, frame_max=frame_max, frames_per_scene=2)
        assert len(plan.caption_frames) <= frame_max

    def test_cap_preserves_sorted_unique(self):
        scenes = [(i * 2.0, (i + 1) * 2.0) for i in range(30)]
        plan = plan_frames(scenes, duration=60.0, frame_min=3, frame_max=20, frames_per_scene=2)
        cf = plan.caption_frames
        assert cf == sorted(set(cf))

    def test_cap_frames_still_within_duration(self):
        scenes = [(i * 2.0, (i + 1) * 2.0) for i in range(30)]
        duration = 60.0
        plan = plan_frames(scenes, duration=duration, frame_min=3, frame_max=20, frames_per_scene=2)
        for t in plan.caption_frames:
            assert 0.0 - 1e-9 <= t <= duration + 1e-9


# ---------------------------------------------------------------------------
# frame_min floor
# ---------------------------------------------------------------------------

class TestFrameMinFloor:
    def test_tiny_clip_single_scene_returns_at_least_frame_min(self):
        scenes = _scenes((0.0, 2.0))
        plan = plan_frames(scenes, duration=2.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert len(plan.caption_frames) >= 3

    def test_zero_duration_still_returns_frame_min(self):
        # Edge case: 0-duration clip should not crash and returns >= frame_min
        plan = plan_frames([], duration=0.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert len(plan.caption_frames) >= 3

    def test_frame_min_5_respected(self):
        scenes = _scenes((0.0, 1.0))
        plan = plan_frames(scenes, duration=1.0, frame_min=5, frame_max=20, frames_per_scene=2)
        assert len(plan.caption_frames) >= 5


# ---------------------------------------------------------------------------
# Uniform fallback (empty or single scene)
# ---------------------------------------------------------------------------

class TestUniformFallback:
    def test_empty_scenes_returns_evenly_spaced(self):
        plan = plan_frames([], duration=10.0, frame_min=3, frame_max=20, frames_per_scene=2)
        cf = plan.caption_frames
        assert len(cf) >= 3
        # evenly spaced → gaps between consecutive frames should be roughly equal
        if len(cf) > 1:
            gaps = [cf[i + 1] - cf[i] for i in range(len(cf) - 1)]
            assert max(gaps) - min(gaps) < 1e-6, f"Gaps not uniform: {gaps}"

    def test_single_scene_treated_as_uniform_fallback(self):
        plan = plan_frames([(0.0, 10.0)], duration=10.0, frame_min=3, frame_max=20, frames_per_scene=2)
        cf = plan.caption_frames
        assert len(cf) >= 3

    def test_uniform_fallback_spans_full_duration(self):
        plan = plan_frames([], duration=30.0, frame_min=3, frame_max=20, frames_per_scene=2)
        cf = plan.caption_frames
        assert cf[0] == pytest.approx(0.0, abs=1e-6)
        assert cf[-1] == pytest.approx(30.0, abs=1e-6)

    def test_uniform_fallback_frames_within_duration(self):
        plan = plan_frames([], duration=10.0, frame_min=3, frame_max=20, frames_per_scene=2)
        for t in plan.caption_frames:
            assert 0.0 - 1e-9 <= t <= 10.0 + 1e-9

    def test_single_scene_ge_frame_min(self):
        plan = plan_frames([(0.0, 5.0)], duration=5.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert len(plan.caption_frames) >= 3


# ---------------------------------------------------------------------------
# OCR frames
# ---------------------------------------------------------------------------

class TestOcrFrames:
    def test_ocr_has_one_representative_per_scene(self):
        # 3 scenes → 3 OCR frames (one midpoint each)
        scenes = _scenes((0.0, 5.0), (5.0, 10.0), (10.0, 15.0))
        plan = plan_frames(scenes, duration=15.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert len(plan.ocr_frames) == 3

    def test_ocr_frames_are_scene_midpoints(self):
        scenes = [(0.0, 4.0), (4.0, 8.0), (8.0, 12.0)]
        plan = plan_frames(scenes, duration=12.0, frame_min=3, frame_max=20, frames_per_scene=2)
        expected_mids = [2.0, 6.0, 10.0]
        for mid in expected_mids:
            assert any(abs(t - mid) < 1e-6 for t in plan.ocr_frames), \
                f"Expected OCR frame near {mid}, got {plan.ocr_frames}"

    def test_ocr_frames_subset_of_caption_frames(self):
        scenes = _scenes((0.0, 5.0), (5.0, 10.0), (10.0, 15.0))
        plan = plan_frames(scenes, duration=15.0, frame_min=3, frame_max=20, frames_per_scene=2)
        for t in plan.ocr_frames:
            assert t in plan.caption_frames

    def test_ocr_frames_for_uniform_fallback_is_small_subset(self):
        # Uniform fallback: OCR should be a small subset (< total caption_frames)
        plan = plan_frames([], duration=30.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert len(plan.ocr_frames) <= len(plan.caption_frames)
        assert len(plan.ocr_frames) >= 1

    def test_ocr_frames_sorted(self):
        scenes = _scenes((0.0, 5.0), (5.0, 10.0), (10.0, 15.0))
        plan = plan_frames(scenes, duration=15.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert plan.ocr_frames == sorted(plan.ocr_frames)

    def test_ocr_capped_when_many_scenes(self):
        # 30 scenes but ocr_frames capped reasonably (≤ frame_max)
        scenes = [(i * 2.0, (i + 1) * 2.0) for i in range(30)]
        plan = plan_frames(scenes, duration=60.0, frame_min=3, frame_max=20, frames_per_scene=2)
        assert len(plan.ocr_frames) <= 20


# ---------------------------------------------------------------------------
# Env override (read at call time)
# ---------------------------------------------------------------------------

class TestEnvOverride:
    def test_frame_max_from_env_when_no_param(self, monkeypatch):
        """When FRAME_MAX env var is set, plan_frames() without explicit param respects it."""
        monkeypatch.setenv("FRAME_MAX", "5")
        scenes = [(i * 2.0, (i + 1) * 2.0) for i in range(20)]
        # Call without keyword overrides so env is used
        plan = plan_frames(scenes, duration=40.0)
        assert len(plan.caption_frames) <= 5

    def test_frame_min_from_env_when_no_param(self, monkeypatch):
        monkeypatch.setenv("FRAME_MIN", "7")
        plan = plan_frames([(0.0, 1.0)], duration=1.0)
        assert len(plan.caption_frames) >= 7

    def test_frames_per_scene_from_env(self, monkeypatch):
        monkeypatch.setenv("FRAMES_PER_SCENE", "4")
        monkeypatch.setenv("FRAME_MAX", "50")
        # 2 scenes × 4 fps = 8 scene frames + anchors
        scenes = [(0.0, 5.0), (5.0, 10.0)]
        plan = plan_frames(scenes, duration=10.0)
        # each scene should contribute ~4 frames
        assert len(plan.caption_frames) >= 8

    def test_explicit_params_override_env(self, monkeypatch):
        monkeypatch.setenv("FRAME_MAX", "100")
        scenes = [(i * 2.0, (i + 1) * 2.0) for i in range(30)]
        plan = plan_frames(scenes, duration=60.0, frame_max=10)
        assert len(plan.caption_frames) <= 10


# ---------------------------------------------------------------------------
# Regression: detect_scenes must use the VideoStream's public .duration, NOT
# the removed-in-0.7 .cap attribute. These drive detect_scenes against a fake
# scenedetect whose video has NO .cap — re-introducing video.cap fails here.
# ---------------------------------------------------------------------------

class _FakeTC:
    def __init__(self, s):
        self._s = s

    @property
    def seconds(self):
        return self._s


class _FakeVideoNoCap:
    """Mimics a 0.7 VideoStream: has .duration, deliberately NO .cap."""
    duration = _FakeTC(12.0)


def _patch_scenedetect(monkeypatch, scene_list):
    import pytest
    scenedetect = pytest.importorskip("scenedetect")
    import scenedetect.detectors as _det

    class _FakeSM:
        def add_detector(self, d):
            pass

        def detect_scenes(self, video, show_progress=False):
            pass

        def get_scene_list(self):
            return scene_list

    monkeypatch.setattr(scenedetect, "open_video", lambda p: _FakeVideoNoCap())
    monkeypatch.setattr(scenedetect, "SceneManager", lambda: _FakeSM())
    monkeypatch.setattr(_det, "AdaptiveDetector", lambda *a, **k: object())


class TestDetectScenesApi:
    def test_no_cuts_uses_duration_not_cap(self, monkeypatch):
        from fetch import sampling
        _patch_scenedetect(monkeypatch, scene_list=[])
        # _FakeVideoNoCap has no .cap → if detect_scenes touches it, AttributeError.
        assert sampling.detect_scenes("/x.mp4") == [(0.0, 12.0)]

    def test_with_cuts_returns_scene_bounds_in_seconds(self, monkeypatch):
        from fetch import sampling
        scenes = [(_FakeTC(0.0), _FakeTC(4.0)), (_FakeTC(4.0), _FakeTC(10.0))]
        _patch_scenedetect(monkeypatch, scene_list=scenes)
        assert sampling.detect_scenes("/x.mp4") == [(0.0, 4.0), (4.0, 10.0)]
