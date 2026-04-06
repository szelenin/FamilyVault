"""
End-to-end test for the full story engine pipeline.

Requires:
  - Live Immich at IMMICH_URL (default: http://immich-immich-server-1.orb.local)
  - FFmpeg available at FFMPEG_BIN (default: ffmpeg)
  - IMMICH_API_KEY_FILE pointing to a valid key

Run:
  IMMICH_URL=http://macmini:2283 python3 -m pytest tests/story-engine/e2e/test_full_story_flow.py -v

Exit codes verified:
  ffprobe -v error -select_streams v:0 -show_entries stream=codec_name returns h264
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import pytest

# Add setup/story-engine to path
_SCRIPTS_PARENT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "setup", "story-engine")
sys.path.insert(0, os.path.abspath(_SCRIPTS_PARENT))

from scripts.search_photos import make_session, search_photos
from scripts.manage_scenario import (
    create_scenario,
    show_scenario,
    add_item,
    set_narrative,
    set_state,
)

IMMICH_URL = os.environ.get("IMMICH_URL", "http://immich-immich-server-1.orb.local")
API_KEY_FILE = os.environ.get("IMMICH_API_KEY_FILE", "/Volumes/HomeRAID/immich/api-key.txt")
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")


@pytest.fixture(scope="module")
def stories_dir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("e2e_stories"))


@pytest.fixture(scope="module")
def immich_session():
    if not os.path.exists(API_KEY_FILE):
        pytest.skip(f"API key file not found: {API_KEY_FILE}")
    return make_session(IMMICH_URL, API_KEY_FILE)


@pytest.fixture(scope="module")
def ffmpeg_available():
    try:
        subprocess.run([FFMPEG_BIN, "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip(f"FFmpeg not found at '{FFMPEG_BIN}'")


@pytest.fixture(scope="module")
def sample_assets(immich_session):
    """Fetch 3 real assets from Immich for the e2e test."""
    assets = search_photos(
        immich_url=IMMICH_URL,
        session=immich_session,
        limit=3,
    )
    if len(assets) < 3:
        pytest.skip(f"Need at least 3 assets in Immich, found {len(assets)}")
    return assets[:3]


class TestFullStoryFlow:
    def test_full_story_flow(self, stories_dir, immich_session, ffmpeg_available, sample_assets, monkeypatch):
        """
        Full pipeline: search → create scenario → add 3 items → set narrative
        → set state approved → assemble → verify output is valid h264 MP4.
        """
        monkeypatch.setenv("STORIES_DIR", stories_dir)
        monkeypatch.setenv("IMMICH_URL", IMMICH_URL)
        monkeypatch.setenv("IMMICH_API_KEY_FILE", API_KEY_FILE)
        monkeypatch.setenv("FFMPEG_BIN", FFMPEG_BIN)

        # Step 1: Create scenario
        scenario = create_scenario(
            title="E2E Test Story",
            request="e2e test",
            stories_dir=stories_dir,
        )
        scenario_id = scenario["id"]
        assert scenario_id, "create_scenario returned empty ID"

        scenario = show_scenario(scenario_id, stories_dir=stories_dir)
        assert scenario["state"] == "draft"

        # Step 2: Add 3 items
        for i, asset in enumerate(sample_assets):
            add_item(
                scenario_id,
                asset_id=asset["id"],
                caption=f"Photo {i + 1}",
                stories_dir=stories_dir,
            )

        scenario = show_scenario(scenario_id, stories_dir=stories_dir)
        assert len(scenario["items"]) == 3

        # Step 3: Set narrative
        set_narrative(
            scenario_id,
            narrative="A short test story with three photos.",
            stories_dir=stories_dir,
        )

        # Step 4: Advance state to approved
        set_state(scenario_id, "reviewed", stories_dir=stories_dir)
        set_state(scenario_id, "approved", stories_dir=stories_dir)

        scenario = show_scenario(scenario_id, stories_dir=stories_dir)
        assert scenario["state"] == "approved"

        # Step 5: Assemble video
        from scripts.assemble_video import assemble

        assemble(
            scenario_id=scenario_id,
            stories_dir=stories_dir,
            immich_url=IMMICH_URL,
            api_key_file=API_KEY_FILE,
            ffmpeg_bin=FFMPEG_BIN,
            image_duration=3,
            fade_duration=0.5,
            resolution="1280:720",
            transition="fade",
        )

        # Step 6: Verify output
        output_path = os.path.join(stories_dir, scenario_id, "output.mp4")
        assert os.path.exists(output_path), f"output.mp4 not found at {output_path}"
        assert os.path.getsize(output_path) > 10_000, "output.mp4 is suspiciously small"

        # Verify codec is h264 via ffprobe
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                output_path,
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"ffprobe failed: {result.stderr}"
        codec = result.stdout.strip()
        assert codec == "h264", f"Expected h264, got '{codec}'"

        # Verify state advanced to generated
        scenario = show_scenario(scenario_id, stories_dir=stories_dir)
        assert scenario["state"] == "generated"
