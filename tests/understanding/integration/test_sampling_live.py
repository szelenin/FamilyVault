"""Integration — exercise the REAL PySceneDetect adapter on a generated clip.

This is what would have caught the `'VideoStreamCv2' object has no attribute 'cap'`
regression: the mocked unit tests can't see real API drift. Opt-in (`integration`
marker); skips automatically if ffmpeg or scenedetect are unavailable.
"""
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.integration


def _make_clip(path, seconds=2):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")
    rc = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"testsrc=duration={seconds}:size=128x96:rate=10",
         "-pix_fmt", "yuv420p", str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode
    if rc != 0:
        pytest.skip("ffmpeg failed to generate the test clip")


def test_detect_scenes_runs_on_a_real_clip(tmp_path):
    pytest.importorskip("scenedetect")
    from fetch.sampling import detect_scenes

    clip = tmp_path / "clip.mp4"
    _make_clip(clip, seconds=2)

    scenes = detect_scenes(str(clip))           # must NOT raise (regression guard)

    assert isinstance(scenes, list) and scenes
    for start, end in scenes:                    # well-formed (start, end) seconds
        assert isinstance(start, float) and isinstance(end, float)
        assert 0.0 <= start <= end <= 2.5        # within the clip duration (+slack)
