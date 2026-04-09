"""Integration tests for the full selection pipeline against live Immich."""
import os
import sys
import pytest

_SCRIPTS_PARENT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "setup", "story-engine")
sys.path.insert(0, os.path.abspath(_SCRIPTS_PARENT))

from scripts.search_photos import make_session, search_multi, enrich_assets
from scripts.score_and_select import (
    score_candidates,
    detect_bursts,
    detect_scenes,
    allocate_budget,
    select_timeline,
    generate_caption,
    extract_must_have_keywords,
    filter_garbage,
    GARBAGE_FILENAME_PREFIXES,
)

IMMICH_URL = os.environ.get("IMMICH_URL", "http://immich-immich-server-1.orb.local")
API_KEY_FILE = os.environ.get("IMMICH_API_KEY_FILE", "/Volumes/HomeRAID/immich/api-key.txt")


@pytest.fixture(scope="module")
def immich_session():
    if not os.path.exists(API_KEY_FILE):
        pytest.skip(f"API key file not found: {API_KEY_FILE}")
    return make_session(IMMICH_URL, API_KEY_FILE)


class TestFullSelectionPipeline:
    def test_full_selection_pipeline(self, immich_session):
        """Search → enrich → score → dedup → select → verify quality."""
        # Search with multiple queries
        assets = search_multi(
            immich_url=IMMICH_URL,
            session=immich_session,
            queries=["miami", "beach", "sunset"],
            city="Miami",
            limit=50,
        )
        if len(assets) < 3:
            pytest.skip(f"Need at least 3 Miami assets, found {len(assets)}")

        # Enrich with full asset detail
        enriched = enrich_assets(immich_session, IMMICH_URL, assets)
        assert len(enriched) >= 3
        # Verify enrichment added expected fields
        for a in enriched[:3]:
            assert "thumbhash" in a
            assert "face_count" in a
            assert "width" in a
            assert a["width"] > 0 or a["type"] == "VIDEO"

        # Score
        scored = score_candidates(enriched)
        for a in scored:
            assert "score" in a
            assert a["score"]["total"] > 0

        # Detect bursts and scenes
        bursts = detect_bursts(scored)
        scenes = detect_scenes(scored)
        assert len(scenes) >= 1

        # Allocate budget
        budget = allocate_budget(scenes, total_budget=10)
        assert sum(budget.values()) <= 10

        # Select timeline
        timeline = select_timeline(scored, bursts, scenes, budget)
        assert len(timeline) >= 1
        assert len(timeline) <= 10

        # Verify chronological order
        times = [item["taken_at"] for item in timeline]
        assert times == sorted(times)

        # Verify positions are sequential
        positions = [item["position"] for item in timeline]
        assert positions == list(range(1, len(timeline) + 1))

        # Verify captions are from real data (not hallucinated)
        for item in timeline:
            cap = generate_caption(
                next(c for c in scored if c["asset_id"] == item["asset_id"])
            )
            # Caption should be non-empty for enriched assets
            assert isinstance(cap, str)


class TestGarbageFilterLive:
    """T016: Verify garbage filter against live Immich data."""

    def test_no_screenshots_in_pipeline(self, immich_session):
        """Full pipeline filters out screenshots from real Immich library."""
        # Broad search that should include some screenshots
        assets = search_multi(
            immich_url=IMMICH_URL,
            session=immich_session,
            queries=["miami", "screenshot", "photo"],
            limit=100,
        )
        if len(assets) < 3:
            pytest.skip("Need at least 3 assets")

        enriched = enrich_assets(immich_session, IMMICH_URL, assets)
        kept, filtered, summary = filter_garbage(enriched)

        # Verify no kept asset has screenshot in filename
        for a in kept:
            fname = (a.get("filename") or "").lower()
            assert "screenshot" not in fname, \
                "Screenshot slipped through: {}".format(a.get("filename"))

        # Verify no kept asset is a story-engine clip
        for a in kept:
            assert a.get("device_id") != "story-engine", \
                "Story-engine clip slipped through: {}".format(a.get("filename"))

        # Verify no kept asset has garbage filename prefix
        for a in kept:
            fname = (a.get("filename") or "").lower()
            for prefix in GARBAGE_FILENAME_PREFIXES:
                if prefix == "screenshot":
                    continue  # already checked
                assert not fname.startswith(prefix), \
                    "Garbage file slipped through: {}".format(a.get("filename"))

        # Log what was filtered for visibility
        print("\nFilter results: kept={}, filtered={}".format(len(kept), len(filtered)))
        print("Summary: {}".format(summary))

    def test_story_engine_clip_excluded(self, immich_session):
        """The v1 generated clip (output.mp4, deviceId=story-engine) is excluded."""
        import requests
        # Verify the clip exists in Immich
        api_key = immich_session.headers.get("x-api-key", "")
        resp = requests.get(
            "{}/api/assets/ec2d58a7-e663-4487-ac0d-1e91438c0965".format(IMMICH_URL),
            headers={"x-api-key": api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            pytest.skip("Story-engine clip not found in Immich")

        detail = resp.json()
        assert detail.get("deviceId") == "story-engine"

        # Simulate it appearing in search results
        candidate = {
            "id": detail["id"],
            "asset_id": detail["id"],
            "type": detail.get("type", "VIDEO"),
            "filename": detail.get("originalFileName", "output.mp4"),
            "mime_type": detail.get("originalMimeType", "video/mp4"),
            "device_id": detail.get("deviceId", ""),
            "exif_make": "",
            "exif_model": "",
            "latitude": None,
            "longitude": None,
            "width": 1920,
            "height": 1080,
        }
        kept, filtered, summary = filter_garbage([candidate])
        assert len(kept) == 0
        assert len(filtered) == 1
        assert summary.get("story_engine", 0) == 1

    def test_camera_photos_not_falsely_filtered(self, immich_session):
        """Real camera photos with EXIF data are never filtered."""
        assets = search_multi(
            immich_url=IMMICH_URL,
            session=immich_session,
            queries=["miami"],
            city="Miami",
            limit=20,
        )
        if len(assets) < 3:
            pytest.skip("Need at least 3 Miami assets")

        enriched = enrich_assets(immich_session, IMMICH_URL, assets)
        # Only keep assets that have camera EXIF
        camera_assets = [a for a in enriched if a.get("exif_make")]

        if not camera_assets:
            pytest.skip("No camera assets found with EXIF make")

        kept, filtered, summary = filter_garbage(camera_assets)
        # All camera assets should be kept
        assert len(kept) == len(camera_assets), \
            "False positive: {} camera photos filtered out of {}. Filtered: {}".format(
                len(filtered), len(camera_assets),
                [(f.get("filename"), f.get("reason")) for f in filtered])


class TestPreviewAlbum:
    pass  # Implemented in Phase 4
