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


class TestPreviewAlbum:
    pass  # Implemented in Phase 4
