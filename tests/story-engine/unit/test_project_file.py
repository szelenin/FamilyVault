"""Unit tests for manage_project.py — project file CRUD and state machine."""
import json
import os
import pytest

from scripts.manage_project import (
    create_project,
    show_project,
    set_state,
    set_candidate_pool,
    set_timeline,
    swap_item,
    remove_item,
    reorder_items,
    trim_video,
    set_budget,
    VALID_STATES,
    VALID_TRANSITIONS,
)


# ---------------------------------------------------------------------------
# T008: Project file CRUD and state machine
# ---------------------------------------------------------------------------

class TestCreateProject:
    def test_create_project_returns_dict(self, temp_stories_dir):
        project = create_project("Test Trip", "test request", stories_dir=temp_stories_dir)
        assert isinstance(project, dict)
        assert project["title"] == "Test Trip"
        assert project["request"] == "test request"
        assert project["state"] == "searching"

    def test_create_project_generates_id(self, temp_stories_dir):
        project = create_project("Miami Trip March 2026", "miami", stories_dir=temp_stories_dir)
        assert "miami" in project["id"].lower()
        assert project["id"]  # non-empty

    def test_create_project_persists_to_disk(self, temp_stories_dir):
        project = create_project("Disk Test", "test", stories_dir=temp_stories_dir)
        path = os.path.join(temp_stories_dir, project["id"], "project.json")
        assert os.path.exists(path)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["title"] == "Disk Test"

    def test_create_project_with_search_params(self, temp_stories_dir):
        params = {"queries": ["miami"], "date_range": {"after": "2026-03-01"}}
        project = create_project("SP Test", "test", search_params=params, stories_dir=temp_stories_dir)
        assert project["search_params"] == params

    def test_create_project_initializes_empty_collections(self, temp_stories_dir):
        project = create_project("Empty Test", "test", stories_dir=temp_stories_dir)
        assert project["candidate_pool"] == []
        assert project["burst_groups"] == {}
        assert project["scenes"] == []
        assert project["timeline"] == []
        assert project["must_haves"] == []
        assert project["music"] is None
        assert project["preview"] == {"album_id": None, "share_key": None}


class TestShowProject:
    def test_show_project_loads_from_disk(self, temp_stories_dir):
        project = create_project("Show Test", "test", stories_dir=temp_stories_dir)
        loaded = show_project(project["id"], stories_dir=temp_stories_dir)
        assert loaded["title"] == "Show Test"
        assert loaded["id"] == project["id"]

    def test_show_project_not_found_raises(self, temp_stories_dir):
        with pytest.raises((FileNotFoundError, SystemExit)):
            show_project("nonexistent-project", stories_dir=temp_stories_dir)


class TestSetState:
    def test_set_state_forward_searching_to_selecting(self, temp_stories_dir):
        project = create_project("State Test", "test", stories_dir=temp_stories_dir)
        updated = set_state(project["id"], "selecting", stories_dir=temp_stories_dir)
        assert updated["state"] == "selecting"

    def test_set_state_full_forward_chain(self, temp_stories_dir):
        project = create_project("Chain Test", "test", stories_dir=temp_stories_dir)
        for state in ["selecting", "previewing", "approved", "generated"]:
            updated = set_state(project["id"], state, stories_dir=temp_stories_dir)
            assert updated["state"] == state

    def test_set_state_back_to_previewing_from_approved(self, temp_stories_dir):
        project = create_project("Back Test", "test", stories_dir=temp_stories_dir)
        set_state(project["id"], "selecting", stories_dir=temp_stories_dir)
        set_state(project["id"], "previewing", stories_dir=temp_stories_dir)
        set_state(project["id"], "approved", stories_dir=temp_stories_dir)
        updated = set_state(project["id"], "previewing", stories_dir=temp_stories_dir)
        assert updated["state"] == "previewing"

    def test_set_state_invalid_transition_raises(self, temp_stories_dir):
        project = create_project("Invalid Test", "test", stories_dir=temp_stories_dir)
        with pytest.raises((ValueError, SystemExit)):
            set_state(project["id"], "approved", stories_dir=temp_stories_dir)

    def test_set_state_invalid_state_name_raises(self, temp_stories_dir):
        project = create_project("Bad State", "test", stories_dir=temp_stories_dir)
        with pytest.raises((ValueError, SystemExit)):
            set_state(project["id"], "nonexistent", stories_dir=temp_stories_dir)


class TestCandidatePool:
    def test_set_candidate_pool(self, temp_stories_dir):
        project = create_project("Pool Test", "test", stories_dir=temp_stories_dir)
        candidates = [
            {"asset_id": "uuid-1", "type": "IMAGE", "score": {"total": 0.9}},
            {"asset_id": "uuid-2", "type": "VIDEO", "score": {"total": 0.7}},
        ]
        updated = set_candidate_pool(project["id"], candidates, stories_dir=temp_stories_dir)
        assert len(updated["candidate_pool"]) == 2
        assert updated["candidate_pool"][0]["asset_id"] == "uuid-1"


class TestTimeline:
    def test_set_timeline(self, temp_stories_dir):
        project = create_project("TL Test", "test", stories_dir=temp_stories_dir)
        timeline = [
            {"position": 1, "asset_id": "uuid-1", "type": "IMAGE", "duration": 4.0},
            {"position": 2, "asset_id": "uuid-2", "type": "VIDEO", "duration": 10.0},
        ]
        updated = set_timeline(project["id"], timeline, stories_dir=temp_stories_dir)
        assert len(updated["timeline"]) == 2
        assert updated["timeline"][0]["position"] == 1


# ---------------------------------------------------------------------------
# T009: Timeline operations
# ---------------------------------------------------------------------------

class TestSwapItem:
    def test_swap_item_replaces_asset(self, temp_stories_dir):
        project = create_project("Swap Test", "test", stories_dir=temp_stories_dir)
        set_timeline(project["id"], [
            {"position": 1, "asset_id": "uuid-1", "type": "IMAGE", "duration": 4.0},
            {"position": 2, "asset_id": "uuid-2", "type": "IMAGE", "duration": 4.0},
        ], stories_dir=temp_stories_dir)
        updated = swap_item(project["id"], 1, "uuid-new", stories_dir=temp_stories_dir)
        assert updated["timeline"][0]["asset_id"] == "uuid-new"
        assert updated["timeline"][1]["asset_id"] == "uuid-2"  # unchanged

    def test_swap_item_invalid_position_raises(self, temp_stories_dir):
        project = create_project("Swap Fail", "test", stories_dir=temp_stories_dir)
        set_timeline(project["id"], [
            {"position": 1, "asset_id": "uuid-1", "type": "IMAGE", "duration": 4.0},
        ], stories_dir=temp_stories_dir)
        with pytest.raises((IndexError, ValueError, SystemExit)):
            swap_item(project["id"], 5, "uuid-new", stories_dir=temp_stories_dir)


class TestRemoveItem:
    def test_remove_item_renumbers(self, temp_stories_dir):
        project = create_project("Remove Test", "test", stories_dir=temp_stories_dir)
        set_timeline(project["id"], [
            {"position": 1, "asset_id": "uuid-1", "type": "IMAGE", "duration": 4.0},
            {"position": 2, "asset_id": "uuid-2", "type": "IMAGE", "duration": 4.0},
            {"position": 3, "asset_id": "uuid-3", "type": "IMAGE", "duration": 4.0},
        ], stories_dir=temp_stories_dir)
        updated = remove_item(project["id"], 2, stories_dir=temp_stories_dir)
        assert len(updated["timeline"]) == 2
        assert updated["timeline"][0]["asset_id"] == "uuid-1"
        assert updated["timeline"][0]["position"] == 1
        assert updated["timeline"][1]["asset_id"] == "uuid-3"
        assert updated["timeline"][1]["position"] == 2


class TestReorderItems:
    def test_reorder_items(self, temp_stories_dir):
        project = create_project("Reorder Test", "test", stories_dir=temp_stories_dir)
        set_timeline(project["id"], [
            {"position": 1, "asset_id": "uuid-1", "type": "IMAGE", "duration": 4.0},
            {"position": 2, "asset_id": "uuid-2", "type": "IMAGE", "duration": 4.0},
            {"position": 3, "asset_id": "uuid-3", "type": "IMAGE", "duration": 4.0},
        ], stories_dir=temp_stories_dir)
        updated = reorder_items(project["id"], [3, 1, 2], stories_dir=temp_stories_dir)
        assert updated["timeline"][0]["asset_id"] == "uuid-3"
        assert updated["timeline"][0]["position"] == 1
        assert updated["timeline"][1]["asset_id"] == "uuid-1"
        assert updated["timeline"][2]["asset_id"] == "uuid-2"


class TestTrimVideo:
    def test_trim_video_sets_points(self, temp_stories_dir):
        project = create_project("Trim Test", "test", stories_dir=temp_stories_dir)
        set_timeline(project["id"], [
            {"position": 1, "asset_id": "uuid-v1", "type": "VIDEO", "duration": 30.0,
             "trim_start": None, "trim_end": None},
        ], stories_dir=temp_stories_dir)
        updated = trim_video(project["id"], 1, 5.0, 15.0, stories_dir=temp_stories_dir)
        assert updated["timeline"][0]["trim_start"] == 5.0
        assert updated["timeline"][0]["trim_end"] == 15.0


class TestSetBudget:
    def test_set_budget_total(self, temp_stories_dir):
        project = create_project("Budget Test", "test", stories_dir=temp_stories_dir)
        updated = set_budget(project["id"], total=30, stories_dir=temp_stories_dir)
        assert updated["budget"]["total"] == 30

    def test_set_budget_with_overrides(self, temp_stories_dir):
        project = create_project("Budget Override", "test", stories_dir=temp_stories_dir)
        updated = set_budget(
            project["id"], total=25,
            overrides={"scene-001": 10, "scene-002": 5},
            stories_dir=temp_stories_dir,
        )
        assert updated["budget"]["per_scene_overrides"]["scene-001"] == 10
        assert updated["budget"]["per_scene_overrides"]["scene-002"] == 5
