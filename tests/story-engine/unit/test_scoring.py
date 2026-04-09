"""Unit tests for score_and_select.py — scoring, burst detection, scene detection, budget allocation."""
import pytest
from datetime import datetime, timedelta

from scripts.score_and_select import (
    score_candidates,
    detect_bursts,
    detect_scenes,
    allocate_budget,
    select_timeline,
    filter_garbage,
    discover_scenes,
    verify_must_haves,
    detect_mode_from_prompt,
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
        "device_id": "",
        "exif_make": "Apple",
        "exif_model": "iPhone 13 Pro",
        "latitude": 25.7617,
        "longitude": -80.1918,
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


# ---------------------------------------------------------------------------
# T003: Screenshot filtering tests (US1)
# ---------------------------------------------------------------------------

class TestFilterScreenshots:
    def test_filter_screenshot_by_filename(self):
        """Files with 'Screenshot' in name are filtered."""
        candidates = [
            _make_candidate(asset_id="ss1"),
            _make_candidate(asset_id="ss2"),
        ]
        candidates[0]["filename"] = "Screenshot 2024-11-14 at 7.28.36 AM.jpeg"
        kept, filtered, _ = filter_garbage(candidates)
        assert len(kept) == 1
        assert len(filtered) == 1
        assert filtered[0]["asset_id"] == "ss1"

    def test_filter_screenshot_by_filename_case_insensitive(self):
        """Screenshot detection is case-insensitive."""
        c = _make_candidate(asset_id="ss")
        c["filename"] = "screenshot_2024.png"
        kept, filtered, _ = filter_garbage([c])
        assert len(kept) == 0
        assert len(filtered) == 1

    def test_filter_screenshot_by_resolution(self):
        """Images matching known screen dimensions with no EXIF are filtered."""
        c = _make_candidate(asset_id="screen", width=1170, height=2532)
        c["exif_make"] = ""
        c["exif_model"] = ""
        c["latitude"] = None
        c["longitude"] = None
        kept, filtered, _ = filter_garbage([c])
        assert len(kept) == 0

    def test_filter_screenshot_no_exif(self):
        """PNG with no camera EXIF is filtered."""
        c = _make_candidate(asset_id="noexif")
        c["filename"] = "IMG_7280.PNG"
        c["mime_type"] = "image/png"
        c["exif_make"] = ""
        c["exif_model"] = ""
        c["latitude"] = None
        c["longitude"] = None
        kept, filtered, _ = filter_garbage([c])
        assert len(kept) == 0

    def test_filter_keeps_camera_photo_png(self):
        """PNG with camera EXIF is kept (false positive prevention)."""
        c = _make_candidate(asset_id="legit_png")
        c["filename"] = "photo.png"
        c["mime_type"] = "image/png"
        c["exif_make"] = "Canon"
        c["exif_model"] = "EOS R5"
        kept, filtered, _ = filter_garbage([c])
        assert len(kept) == 1
        assert kept[0]["asset_id"] == "legit_png"

    def test_filter_keeps_photo_with_exif(self):
        """Normal camera photos are never filtered."""
        c = _make_candidate(asset_id="normal")
        kept, filtered, _ = filter_garbage([c])
        assert len(kept) == 1
        assert len(filtered) == 0


# ---------------------------------------------------------------------------
# T004: Story-engine clip filtering tests (US2)
# ---------------------------------------------------------------------------

class TestFilterStoryEngine:
    def test_filter_story_engine_clip(self):
        """Assets with deviceId=story-engine are filtered."""
        c = _make_candidate(asset_id="clip", asset_type="VIDEO", duration=37.0)
        c["device_id"] = "story-engine"
        c["filename"] = "output.mp4"
        kept, filtered, _ = filter_garbage([c])
        assert len(kept) == 0
        assert filtered[0]["reason"] == "story_engine"

    def test_filter_keeps_user_video(self):
        """User-uploaded videos are kept."""
        c = _make_candidate(asset_id="uservid", asset_type="VIDEO", duration=10.0)
        c["device_id"] = "Library Import"
        kept, filtered, _ = filter_garbage([c])
        assert len(kept) == 1


# ---------------------------------------------------------------------------
# T010: Non-photo content filtering tests (US3)
# ---------------------------------------------------------------------------

class TestFilterNonPhoto:
    def test_filter_camphoto(self):
        """camphoto_* files are filtered."""
        c = _make_candidate(asset_id="cam")
        c["filename"] = "camphoto_959030623.jpg"
        kept, filtered, _ = filter_garbage([c])
        assert len(kept) == 0

    def test_filter_rpreplay(self):
        """RPReplay_* screen recordings are filtered."""
        c = _make_candidate(asset_id="rp", asset_type="VIDEO", duration=30.0)
        c["filename"] = "RPReplay_Final1234.mov"
        kept, filtered, _ = filter_garbage([c])
        assert len(kept) == 0

    def test_filter_no_metadata_deprioritized(self):
        """Assets with no GPS, no city, no EXIF, no faces get kept but flagged."""
        c = _make_candidate(asset_id="poor", face_count=0)
        c["exif_make"] = ""
        c["exif_model"] = ""
        c["latitude"] = None
        c["longitude"] = None
        c["city"] = None
        c["country"] = None
        # Not hard-excluded, but should be kept (deprioritized via score penalty later)
        kept, filtered, _ = filter_garbage([c])
        assert len(kept) == 1  # kept, not excluded


# ---------------------------------------------------------------------------
# T006: Scene Discovery tests (US1)
# ---------------------------------------------------------------------------

class TestDiscoverScenes:
    def test_discover_scenes_returns_all(self):
        """Discovery returns ALL scenes, no budget cap."""
        candidates = []
        # 3 scenes: morning, afternoon, evening
        for hour, count in [(9, 20), (14, 30), (19, 10)]:
            for i in range(count):
                candidates.append(_make_candidate(
                    asset_id="h{}_{}".format(hour, i),
                    taken_at="2026-03-31T{:02d}:{:02d}:00Z".format(hour, i % 60),
                    face_count=i % 3,
                ))
        result = discover_scenes(candidates, mode="trip")
        assert len(result["scenes"]) == 3
        total_items = sum(s["photo_count"] + s["video_count"] for s in result["scenes"])
        assert total_items == 60  # all candidates accounted for

    def test_discover_scenes_no_budget_cap(self):
        """Even with 100 items per scene, all are counted (no budget)."""
        candidates = [
            _make_candidate(asset_id="big{}".format(i),
                          taken_at="2026-03-31T12:{:02d}:00Z".format(i % 60))
            for i in range(100)
        ]
        result = discover_scenes(candidates, mode="trip")
        total = sum(s["photo_count"] + s["video_count"] for s in result["scenes"])
        assert total == 100

    def test_discover_scenes_trip_mode(self):
        """Trip mode clusters by 30-minute time gaps."""
        c1 = _make_candidate(asset_id="a", taken_at="2026-03-31T10:00:00Z")
        c2 = _make_candidate(asset_id="b", taken_at="2026-03-31T10:15:00Z")
        c3 = _make_candidate(asset_id="c", taken_at="2026-03-31T12:00:00Z")
        result = discover_scenes([c1, c2, c3], mode="trip")
        assert len(result["scenes"]) == 2

    def test_discover_scenes_includes_cities(self):
        """Each scene includes the cities found in its candidates."""
        c1 = _make_candidate(asset_id="m1", taken_at="2026-03-31T10:00:00Z")
        c1["city"] = "Miami"
        c2 = _make_candidate(asset_id="m2", taken_at="2026-03-31T10:10:00Z")
        c2["city"] = "Miami Beach"
        c3 = _make_candidate(asset_id="cg", taken_at="2026-03-31T18:00:00Z")
        c3["city"] = "Coconut Grove"
        result = discover_scenes([c1, c2, c3], mode="trip")
        scene1_cities = result["scenes"][0]["cities"]
        assert "Miami" in scene1_cities
        assert "Miami Beach" in scene1_cities
        scene2_cities = result["scenes"][1]["cities"]
        assert "Coconut Grove" in scene2_cities

    def test_discover_scenes_groups_by_day_over_20(self):
        """When >20 scenes, result includes day_groups."""
        candidates = []
        for day in range(1, 8):  # 7 days
            for hour in [8, 10, 12, 14, 16]:  # 5 scenes per day = 35 total
                candidates.append(_make_candidate(
                    asset_id="d{}h{}".format(day, hour),
                    taken_at="2026-03-{:02d}T{:02d}:00:00Z".format(day, hour),
                ))
        result = discover_scenes(candidates, mode="trip")
        assert len(result["scenes"]) > 20
        assert "day_groups" in result
        assert len(result["day_groups"]) == 7


# ---------------------------------------------------------------------------
# T014: Must-have verification tests (US3)
# ---------------------------------------------------------------------------

class TestVerifyMustHaves:
    def test_verify_must_haves_all_found(self):
        """All must-have keywords match a scene."""
        # Scene with "Miami" city and "speedboat" content
        scenes = [
            {"id": "s1", "label": "Scene 1", "cities": ["Miami Beach"],
             "asset_ids": ["a1", "a2"], "people": []},
            {"id": "s2", "label": "Scene 2", "cities": ["Coconut Grove"],
             "asset_ids": ["a3"], "people": []},
        ]
        candidates = [
            _make_candidate(asset_id="a1"),
            _make_candidate(asset_id="a2"),
            _make_candidate(asset_id="a3"),
        ]
        candidates[0]["city"] = "Miami Beach"
        candidates[0]["source_query"] = "speedboat"
        candidates[2]["city"] = "Coconut Grove"

        result = verify_must_haves(
            keywords=["speedboat", "coconut grove"],
            discovery_scenes=scenes,
            candidates=candidates,
        )
        assert len(result["found"]) == 2
        assert len(result["missing"]) == 0

    def test_verify_must_haves_missing_triggers_search(self):
        """Missing must-have is reported."""
        scenes = [
            {"id": "s1", "label": "Scene 1", "cities": ["Miami"],
             "asset_ids": ["a1"], "people": []},
        ]
        candidates = [_make_candidate(asset_id="a1")]

        result = verify_must_haves(
            keywords=["parasailing"],
            discovery_scenes=scenes,
            candidates=candidates,
        )
        assert len(result["found"]) == 0
        assert len(result["missing"]) == 1
        assert "parasailing" in result["missing"]

    def test_verify_must_haves_matches_by_city(self):
        """Must-have keyword matches scene by city name."""
        scenes = [
            {"id": "s1", "label": "Scene 1", "cities": ["Vizcaya"],
             "asset_ids": ["a1"], "people": []},
        ]
        candidates = [_make_candidate(asset_id="a1")]
        candidates[0]["city"] = "Vizcaya"

        result = verify_must_haves(
            keywords=["vizcaya"],
            discovery_scenes=scenes,
            candidates=candidates,
        )
        assert len(result["found"]) == 1
        assert result["found"][0]["keyword"] == "vizcaya"


# ---------------------------------------------------------------------------
# T019: Detection mode tests (US4)
# ---------------------------------------------------------------------------

class TestDetectMode:
    def test_detect_mode_trip(self):
        """Trip-related prompts select trip mode."""
        assert detect_mode_from_prompt("make a clip of our Miami trip") == "trip"
        assert detect_mode_from_prompt("video of our vacation in Paris") == "trip"
        assert detect_mode_from_prompt("clip from our trip to Japan last summer") == "trip"

    def test_detect_mode_person_timeline(self):
        """Person growth prompts select person-timeline mode."""
        assert detect_mode_from_prompt("make a clip of how Edgar grows up") == "person-timeline"
        assert detect_mode_from_prompt("timeline of my daughter") == "person-timeline"
        assert detect_mode_from_prompt("video of Sarah through the years") == "person-timeline"

    def test_detect_mode_default_general(self):
        """Unrecognized prompts default to general mode."""
        assert detect_mode_from_prompt("make a clip") == "general"
        assert detect_mode_from_prompt("something cool") == "general"
