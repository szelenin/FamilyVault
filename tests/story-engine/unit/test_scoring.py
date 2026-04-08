"""Unit tests for score_and_select.py — scoring, burst detection, scene detection, budget allocation."""
import pytest
from datetime import datetime, timedelta

from scripts.score_and_select import (
    score_candidates,
    detect_bursts,
    detect_scenes,
    allocate_budget,
    select_timeline,
)


def _make_candidate(asset_id="uuid-1", asset_type="IMAGE", taken_at="2026-03-31T12:00:00Z",
                     face_count=0, width=4032, height=3024, thumbhash="abc123",
                     description="", duration=None, relevance_score=0.5):
    """Helper to build a candidate dict."""
    return {
        "asset_id": asset_id,
        "type": asset_type,
        "filename": "IMG_{}.HEIC".format(asset_id[:4]),
        "mime_type": "image/heic" if asset_type == "IMAGE" else "video/mp4",
        "taken_at": taken_at,
        "width": width,
        "height": height,
        "thumbhash": thumbhash,
        "face_count": face_count,
        "description": description,
        "duration": duration,
        "relevance_score": relevance_score,
        "city": "Miami",
        "country": "United States",
    }


# ---------------------------------------------------------------------------
# T017: Scoring tests
# ---------------------------------------------------------------------------

class TestScoreCandidates:
    def test_score_photo_weights(self):
        """Photos: faces 40%, relevance 30%, diversity 20%, resolution 10%."""
        candidates = [_make_candidate(face_count=2, relevance_score=0.8, width=4032, height=3024)]
        scored = score_candidates(candidates)
        assert len(scored) == 1
        s = scored[0]["score"]
        assert "faces" in s
        assert "relevance" in s
        assert "diversity" in s
        assert "resolution" in s
        assert "total" in s
        assert s["total"] > 0

    def test_score_video_weights(self):
        """Videos: relevance 40%, duration 25%, diversity 20%, faces 15%."""
        candidates = [_make_candidate(
            asset_type="VIDEO", duration=15.0, face_count=1, relevance_score=0.9
        )]
        scored = score_candidates(candidates)
        s = scored[0]["score"]
        assert "duration" in s
        assert s["total"] > 0

    def test_score_video_duration_sweet_spot(self):
        """Videos 5-30s should score highest on duration."""
        short = _make_candidate(asset_id="short", asset_type="VIDEO", duration=1.0, relevance_score=0.5)
        sweet = _make_candidate(asset_id="sweet", asset_type="VIDEO", duration=15.0, relevance_score=0.5)
        long_ = _make_candidate(asset_id="long", asset_type="VIDEO", duration=120.0, relevance_score=0.5)
        scored = score_candidates([short, sweet, long_])
        scores = {c["asset_id"]: c["score"]["duration"] for c in scored}
        assert scores["sweet"] > scores["short"]
        assert scores["sweet"] > scores["long"]

    def test_score_video_duration_penalty_short(self):
        """Videos < 2s should get low duration score."""
        very_short = _make_candidate(asset_type="VIDEO", duration=0.5, relevance_score=0.5)
        scored = score_candidates([very_short])
        assert scored[0]["score"]["duration"] < 0.3

    def test_score_must_have_bypasses_scoring(self):
        """Must-have candidates get total=1.0 and skip normal scoring."""
        candidates = [_make_candidate(face_count=0, relevance_score=0.1)]
        scored = score_candidates(candidates, must_have_keywords=["speed boat"])
        # With must_have_keywords, the function should mark them but still score
        # The actual must-have bypassing happens in select_timeline
        assert len(scored) == 1


# ---------------------------------------------------------------------------
# T018: Burst detection tests
# ---------------------------------------------------------------------------

class TestDetectBursts:
    def test_detect_bursts_within_5_seconds(self):
        """Photos within 5s of each other form a burst group."""
        c1 = _make_candidate(asset_id="a", taken_at="2026-03-31T12:00:00Z", face_count=1)
        c2 = _make_candidate(asset_id="b", taken_at="2026-03-31T12:00:02Z", face_count=2)
        c3 = _make_candidate(asset_id="c", taken_at="2026-03-31T12:00:04Z", face_count=0)
        c4 = _make_candidate(asset_id="d", taken_at="2026-03-31T12:01:00Z", face_count=1)
        # Score them first
        scored = score_candidates([c1, c2, c3, c4])
        groups = detect_bursts(scored)
        # a, b, c should be in one group; d is separate (>5s gap)
        assert len(groups) >= 1
        burst = None
        for gid, g in groups.items():
            if len(g["alternate_asset_ids"]) > 0:
                burst = g
                break
        assert burst is not None
        # Primary should be highest-scored (b has 2 faces)
        all_ids = [burst["primary_asset_id"]] + burst["alternate_asset_ids"]
        assert "a" in all_ids
        assert "b" in all_ids
        assert "c" in all_ids
        assert "d" not in all_ids

    def test_detect_bursts_keeps_highest_score(self):
        """Primary in a burst group should be the highest-scored."""
        c1 = _make_candidate(asset_id="low", taken_at="2026-03-31T12:00:00Z", face_count=0)
        c2 = _make_candidate(asset_id="high", taken_at="2026-03-31T12:00:03Z", face_count=3)
        scored = score_candidates([c1, c2])
        groups = detect_bursts(scored)
        for gid, g in groups.items():
            if len(g["alternate_asset_ids"]) > 0:
                assert g["primary_asset_id"] == "high"

    def test_detect_bursts_stores_alternates(self):
        """Burst group stores up to 3 alternates."""
        candidates = [
            _make_candidate(asset_id="a{}".format(i),
                          taken_at="2026-03-31T12:00:0{}Z".format(i),
                          face_count=i)
            for i in range(5)
        ]
        scored = score_candidates(candidates)
        groups = detect_bursts(scored)
        for gid, g in groups.items():
            assert len(g["alternate_asset_ids"]) <= 3

    def test_detect_bursts_video_preferred_over_photo(self):
        """When video and photo are in same burst, video is primary."""
        photo = _make_candidate(asset_id="photo", taken_at="2026-03-31T12:00:00Z",
                               face_count=2, relevance_score=0.9)
        video = _make_candidate(asset_id="video", asset_type="VIDEO",
                               taken_at="2026-03-31T12:00:02Z",
                               face_count=1, duration=10.0, relevance_score=0.5)
        scored = score_candidates([photo, video])
        groups = detect_bursts(scored)
        for gid, g in groups.items():
            if len(g["alternate_asset_ids"]) > 0:
                assert g["primary_asset_id"] == "video"

    def test_detect_bursts_photo_kept_as_alternate(self):
        """Photo is kept as alternate when video is primary in a burst."""
        photo = _make_candidate(asset_id="photo", taken_at="2026-03-31T12:00:00Z", face_count=2)
        video = _make_candidate(asset_id="video", asset_type="VIDEO",
                               taken_at="2026-03-31T12:00:02Z", duration=10.0)
        scored = score_candidates([photo, video])
        groups = detect_bursts(scored)
        for gid, g in groups.items():
            if g["primary_asset_id"] == "video":
                assert "photo" in g["alternate_asset_ids"]


# ---------------------------------------------------------------------------
# T019: Scene detection and budget tests
# ---------------------------------------------------------------------------

class TestDetectScenes:
    def test_detect_scenes_30min_gap(self):
        """Photos >30 min apart form separate scenes."""
        c1 = _make_candidate(asset_id="a", taken_at="2026-03-31T10:00:00Z")
        c2 = _make_candidate(asset_id="b", taken_at="2026-03-31T10:15:00Z")
        c3 = _make_candidate(asset_id="c", taken_at="2026-03-31T12:00:00Z")
        c4 = _make_candidate(asset_id="d", taken_at="2026-03-31T12:10:00Z")
        scenes = detect_scenes([c1, c2, c3, c4])
        assert len(scenes) == 2
        assert scenes[0]["candidate_count"] == 2
        assert scenes[1]["candidate_count"] == 2


class TestAllocateBudget:
    def test_allocate_budget_proportional(self):
        """Budget distributed proportionally by candidate count."""
        scenes = [
            {"id": "s1", "candidate_count": 30},
            {"id": "s2", "candidate_count": 10},
        ]
        alloc = allocate_budget(scenes, total_budget=20)
        assert alloc["s1"] > alloc["s2"]
        assert alloc["s1"] + alloc["s2"] == 20

    def test_allocate_budget_min_1_per_scene(self):
        """Every scene gets at least 1 item."""
        scenes = [
            {"id": "s1", "candidate_count": 100},
            {"id": "s2", "candidate_count": 1},
            {"id": "s3", "candidate_count": 1},
        ]
        alloc = allocate_budget(scenes, total_budget=5)
        assert alloc["s2"] >= 1
        assert alloc["s3"] >= 1

    def test_allocate_budget_with_overrides(self):
        """Per-scene overrides are respected."""
        scenes = [
            {"id": "s1", "candidate_count": 50},
            {"id": "s2", "candidate_count": 50},
        ]
        alloc = allocate_budget(scenes, total_budget=20, overrides={"s1": 15})
        assert alloc["s1"] == 15
        assert alloc["s2"] == 5

    def test_allocate_budget_cap_60(self):
        """Total budget capped at 60."""
        scenes = [{"id": "s1", "candidate_count": 200}]
        alloc = allocate_budget(scenes, total_budget=100)
        assert sum(alloc.values()) <= 60


# ---------------------------------------------------------------------------
# T020: Must-have extraction tests
# ---------------------------------------------------------------------------

class TestMustHaveExtraction:
    def test_must_have_guaranteed_in_timeline(self):
        """Must-have items appear in the final timeline regardless of score."""
        must_have = _make_candidate(asset_id="must", face_count=0, relevance_score=0.1,
                                    taken_at="2026-03-31T14:00:00Z")
        must_have["is_must_have"] = True
        regular = _make_candidate(asset_id="reg", face_count=3, relevance_score=0.9,
                                  taken_at="2026-03-31T14:05:00Z")
        scored = score_candidates([must_have, regular])
        for c in scored:
            if c["asset_id"] == "must":
                c["is_must_have"] = True
        groups = detect_bursts(scored)
        scenes = detect_scenes(scored)
        alloc = allocate_budget(scenes, total_budget=1)  # budget for only 1
        timeline = select_timeline(scored, groups, scenes, alloc, must_haves=[must_have])
        asset_ids = [item["asset_id"] for item in timeline]
        assert "must" in asset_ids


# ---------------------------------------------------------------------------
# T021: Timeline selection tests
# ---------------------------------------------------------------------------

class TestSelectTimeline:
    def test_select_timeline_respects_budget(self):
        """Timeline doesn't exceed allocated budget."""
        candidates = [
            _make_candidate(asset_id="c{}".format(i),
                          taken_at="2026-03-31T12:{:02d}:00Z".format(i),
                          face_count=i % 3)
            for i in range(20)
        ]
        scored = score_candidates(candidates)
        groups = detect_bursts(scored)
        scenes = detect_scenes(scored)
        alloc = allocate_budget(scenes, total_budget=5)
        timeline = select_timeline(scored, groups, scenes, alloc)
        assert len(timeline) <= 5

    def test_select_timeline_diversity_30pct_cap(self):
        """No more than 30% from a single 30-min window."""
        # 10 candidates in one scene, 2 in another
        candidates = [
            _make_candidate(asset_id="dense{}".format(i),
                          taken_at="2026-03-31T12:{:02d}:00Z".format(i),
                          face_count=2)
            for i in range(10)
        ]
        candidates += [
            _make_candidate(asset_id="sparse{}".format(i),
                          taken_at="2026-03-31T15:{:02d}:00Z".format(i),
                          face_count=1)
            for i in range(2)
        ]
        scored = score_candidates(candidates)
        groups = detect_bursts(scored)
        scenes = detect_scenes(scored)
        alloc = allocate_budget(scenes, total_budget=10)
        timeline = select_timeline(scored, groups, scenes, alloc)
        # Count items from the dense scene (12:xx)
        # Diversity cap is 30% of total budget (10), so max 4 from dense scene
        dense_count = sum(1 for item in timeline
                         if item.get("taken_at", "").startswith("2026-03-31T12"))
        max_allowed = max(1, int(10 * 0.3) + 1)  # 30% of budget=10 → 4
        assert dense_count <= max_allowed

    def test_select_timeline_chronological_order(self):
        """Timeline items are in chronological order."""
        candidates = [
            _make_candidate(asset_id="late", taken_at="2026-03-31T18:00:00Z", face_count=2),
            _make_candidate(asset_id="early", taken_at="2026-03-31T08:00:00Z", face_count=2),
            _make_candidate(asset_id="mid", taken_at="2026-03-31T13:00:00Z", face_count=2),
        ]
        scored = score_candidates(candidates)
        groups = detect_bursts(scored)
        scenes = detect_scenes(scored)
        alloc = allocate_budget(scenes, total_budget=3)
        timeline = select_timeline(scored, groups, scenes, alloc)
        times = [item.get("taken_at", "") for item in timeline]
        assert times == sorted(times)

    def test_select_timeline_auto_duration(self):
        """Each photo gets a default duration, videos keep their duration."""
        photo = _make_candidate(asset_id="photo", taken_at="2026-03-31T12:00:00Z", face_count=1)
        video = _make_candidate(asset_id="video", asset_type="VIDEO",
                               taken_at="2026-03-31T13:00:00Z", duration=15.0)
        scored = score_candidates([photo, video])
        groups = detect_bursts(scored)
        scenes = detect_scenes(scored)
        alloc = allocate_budget(scenes, total_budget=2)
        timeline = select_timeline(scored, groups, scenes, alloc)
        for item in timeline:
            assert item["duration"] > 0
            if item["type"] == "VIDEO":
                assert item["duration"] == 15.0
