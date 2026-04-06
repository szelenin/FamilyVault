"""Unit tests for manage-scenario.py — scenario CRUD operations."""
import json
import os
import pytest
from unittest.mock import patch, MagicMock


from scripts.manage_scenario import (
    create_scenario,
    show_scenario,
    list_scenarios,
    add_item,
    remove_item,
    reorder_items,
    set_narrative,
    set_music,
    list_bundled_tracks,
    set_state,
    VALID_TRANSITIONS,
)


# ---------------------------------------------------------------------------
# US1: create / show / list
# ---------------------------------------------------------------------------

class TestCreateScenario:
    def test_create_scenario_writes_json(self, temp_stories_dir):
        """create_scenario writes scenario.json to STORIES_DIR/{id}/."""
        scenario = create_scenario(
            title="Edgar Birthday Miami",
            request="birthday march 2025",
            stories_dir=temp_stories_dir,
        )
        scenario_path = os.path.join(temp_stories_dir, scenario["id"], "scenario.json")
        assert os.path.exists(scenario_path)
        with open(scenario_path) as f:
            data = json.load(f)
        assert data["title"] == "Edgar Birthday Miami"

    def test_create_scenario_initial_state_is_draft(self, temp_stories_dir):
        """New scenario starts in draft state."""
        scenario = create_scenario(
            title="Test Story",
            request="test",
            stories_dir=temp_stories_dir,
        )
        assert scenario["state"] == "draft"

    def test_create_scenario_generates_id_from_date_and_title(self, temp_stories_dir):
        """Scenario ID is formatted as YYYY-MM-DD-<slug>."""
        scenario = create_scenario(
            title="Edgar Birthday Miami",
            request="birthday march 2025",
            stories_dir=temp_stories_dir,
        )
        # ID should be date-slug format
        parts = scenario["id"].split("-")
        assert len(parts) >= 4  # YYYY-MM-DD-<slug>
        assert parts[0].isdigit() and len(parts[0]) == 4  # year
        assert parts[1].isdigit() and len(parts[1]) == 2  # month
        assert parts[2].isdigit() and len(parts[2]) == 2  # day

    def test_create_scenario_initial_items_is_empty(self, temp_stories_dir):
        """New scenario has empty items list."""
        scenario = create_scenario(
            title="Test", request="test", stories_dir=temp_stories_dir
        )
        assert scenario["items"] == []

    def test_scenario_id_format(self, temp_stories_dir):
        """Scenario ID slug uses hyphens and lowercase."""
        scenario = create_scenario(
            title="My Summer Vacation",
            request="summer",
            stories_dir=temp_stories_dir,
        )
        slug_part = "-".join(scenario["id"].split("-")[3:])
        assert slug_part == slug_part.lower()
        assert " " not in slug_part


class TestShowScenario:
    def test_show_scenario_reads_json(self, temp_stories_dir):
        """show_scenario returns parsed scenario dict."""
        created = create_scenario(
            title="Test Show", request="test", stories_dir=temp_stories_dir
        )
        loaded = show_scenario(created["id"], stories_dir=temp_stories_dir)
        assert loaded["id"] == created["id"]
        assert loaded["title"] == "Test Show"

    def test_show_scenario_missing_raises(self, temp_stories_dir):
        """show_scenario raises FileNotFoundError for unknown ID."""
        with pytest.raises((FileNotFoundError, SystemExit)):
            show_scenario("nonexistent-id", stories_dir=temp_stories_dir)


class TestListScenarios:
    def test_list_scenarios_returns_all(self, temp_stories_dir):
        """list_scenarios returns all scenarios in STORIES_DIR."""
        create_scenario(title="Story A", request="a", stories_dir=temp_stories_dir)
        create_scenario(title="Story B", request="b", stories_dir=temp_stories_dir)
        scenarios = list_scenarios(stories_dir=temp_stories_dir)
        assert len(scenarios) == 2

    def test_list_scenarios_empty_dir(self, temp_stories_dir):
        """list_scenarios returns empty list when no scenarios exist."""
        scenarios = list_scenarios(stories_dir=temp_stories_dir)
        assert scenarios == []


# ---------------------------------------------------------------------------
# US2: add-item / remove-item / reorder / set-narrative
# ---------------------------------------------------------------------------

class TestAddItem:
    def test_add_item_appends_to_end(self, temp_stories_dir):
        """add_item appends media item to end of items list."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-1", caption="First photo",
                 stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-2", caption="Second photo",
                 stories_dir=temp_stories_dir)
        loaded = show_scenario(s["id"], stories_dir=temp_stories_dir)
        assert len(loaded["items"]) == 2
        assert loaded["items"][0]["asset_id"] == "uuid-1"
        assert loaded["items"][1]["asset_id"] == "uuid-2"

    def test_add_item_at_position_inserts(self, temp_stories_dir):
        """add_item with position inserts at that position."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-1", caption="A", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-2", caption="B", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-X", caption="X", position=1,
                 stories_dir=temp_stories_dir)
        loaded = show_scenario(s["id"], stories_dir=temp_stories_dir)
        assert loaded["items"][0]["asset_id"] == "uuid-X"
        assert loaded["items"][1]["asset_id"] == "uuid-1"

    def test_add_item_enforces_60_item_limit(self, temp_stories_dir):
        """add_item raises when items would exceed 60."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        for i in range(60):
            add_item(s["id"], asset_id=f"uuid-{i}", caption=f"Item {i}",
                     stories_dir=temp_stories_dir)
        with pytest.raises((ValueError, SystemExit)):
            add_item(s["id"], asset_id="uuid-61", caption="Over limit",
                     stories_dir=temp_stories_dir)

    def test_add_item_sets_position_field(self, temp_stories_dir):
        """Items have a 1-based position field."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-1", caption="A", stories_dir=temp_stories_dir)
        loaded = show_scenario(s["id"], stories_dir=temp_stories_dir)
        assert loaded["items"][0]["position"] == 1


class TestRemoveItem:
    def test_remove_item_renumbers_positions(self, temp_stories_dir):
        """After remove, remaining items are renumbered starting from 1."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-1", caption="A", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-2", caption="B", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-3", caption="C", stories_dir=temp_stories_dir)
        remove_item(s["id"], position=1, stories_dir=temp_stories_dir)
        loaded = show_scenario(s["id"], stories_dir=temp_stories_dir)
        assert len(loaded["items"]) == 2
        assert loaded["items"][0]["position"] == 1
        assert loaded["items"][0]["asset_id"] == "uuid-2"
        assert loaded["items"][1]["position"] == 2


class TestReorder:
    def test_reorder_validates_all_positions_present(self, temp_stories_dir):
        """reorder raises if not all positions provided."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-1", caption="A", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-2", caption="B", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-3", caption="C", stories_dir=temp_stories_dir)
        with pytest.raises((ValueError, SystemExit)):
            reorder_items(s["id"], new_order=[1, 3], stories_dir=temp_stories_dir)

    def test_reorder_rejects_duplicates(self, temp_stories_dir):
        """reorder raises if duplicate positions provided."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-1", caption="A", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-2", caption="B", stories_dir=temp_stories_dir)
        with pytest.raises((ValueError, SystemExit)):
            reorder_items(s["id"], new_order=[1, 1], stories_dir=temp_stories_dir)

    def test_reorder_applies_new_order(self, temp_stories_dir):
        """reorder rearranges items and renumbers positions."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-1", caption="A", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-2", caption="B", stories_dir=temp_stories_dir)
        add_item(s["id"], asset_id="uuid-3", caption="C", stories_dir=temp_stories_dir)
        reorder_items(s["id"], new_order=[3, 1, 2], stories_dir=temp_stories_dir)
        loaded = show_scenario(s["id"], stories_dir=temp_stories_dir)
        assert loaded["items"][0]["asset_id"] == "uuid-3"
        assert loaded["items"][1]["asset_id"] == "uuid-1"
        assert loaded["items"][0]["position"] == 1


class TestSetNarrative:
    def test_set_narrative_updates_field(self, temp_stories_dir):
        """set_narrative updates the narrative field."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        set_narrative(s["id"], narrative="A fun family birthday story.",
                      stories_dir=temp_stories_dir)
        loaded = show_scenario(s["id"], stories_dir=temp_stories_dir)
        assert loaded["narrative"] == "A fun family birthday story."


# ---------------------------------------------------------------------------
# US3: set-music / list-music
# ---------------------------------------------------------------------------

class TestSetMusic:
    def test_set_music_bundled_sets_path(self, temp_stories_dir):
        """set_music with bundled type stores mood and track path."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        set_music(s["id"], music_type="bundled", mood="upbeat", track="track1",
                  stories_dir=temp_stories_dir)
        loaded = show_scenario(s["id"], stories_dir=temp_stories_dir)
        assert loaded["music"]["type"] == "bundled"
        assert loaded["music"]["mood"] == "upbeat"
        assert "track1" in loaded["music"]["path"]

    def test_set_music_user_validates_file_exists(self, temp_stories_dir, tmp_path):
        """set_music with user type accepts existing file."""
        audio_file = tmp_path / "song.mp3"
        audio_file.write_bytes(b"fake mp3")
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        set_music(s["id"], music_type="user", file_path=str(audio_file),
                  stories_dir=temp_stories_dir)
        loaded = show_scenario(s["id"], stories_dir=temp_stories_dir)
        assert loaded["music"]["type"] == "user"
        assert loaded["music"]["path"] == str(audio_file)

    def test_set_music_user_rejects_missing_file(self, temp_stories_dir):
        """set_music with user type raises if file doesn't exist."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        with pytest.raises((FileNotFoundError, ValueError, SystemExit)):
            set_music(s["id"], music_type="user",
                      file_path="/nonexistent/song.mp3",
                      stories_dir=temp_stories_dir)

    def test_set_music_none_sets_type_none(self, temp_stories_dir):
        """set_music with none type marks music as explicitly skipped."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        set_music(s["id"], music_type="none", stories_dir=temp_stories_dir)
        loaded = show_scenario(s["id"], stories_dir=temp_stories_dir)
        assert loaded["music"]["type"] == "none"


class TestListBundledTracks:
    def test_list_bundled_tracks_by_mood(self):
        """list_bundled_tracks returns tracks organized by mood."""
        tracks = list_bundled_tracks()
        assert "upbeat" in tracks
        assert "calm" in tracks
        assert "sentimental" in tracks
        # Each mood should have at least 1 track listed
        assert len(tracks["upbeat"]) >= 1
        assert len(tracks["calm"]) >= 1
        assert len(tracks["sentimental"]) >= 1


# ---------------------------------------------------------------------------
# US4: set-state
# ---------------------------------------------------------------------------

class TestSetState:
    def test_set_state_forward_only_transition(self, temp_stories_dir):
        """set_state to a previous state raises with exit 3."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        set_state(s["id"], new_state="reviewed", stories_dir=temp_stories_dir)
        with pytest.raises(SystemExit) as exc_info:
            set_state(s["id"], new_state="draft", stories_dir=temp_stories_dir)
        assert exc_info.value.code == 3

    def test_set_state_valid_forward_transition(self, temp_stories_dir):
        """set_state advances state forward."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        set_state(s["id"], new_state="reviewed", stories_dir=temp_stories_dir)
        loaded = show_scenario(s["id"], stories_dir=temp_stories_dir)
        assert loaded["state"] == "reviewed"

    def test_set_state_invalid_state_raises(self, temp_stories_dir):
        """set_state with unknown state raises."""
        s = create_scenario(title="Test", request="test", stories_dir=temp_stories_dir)
        with pytest.raises((ValueError, SystemExit)):
            set_state(s["id"], new_state="bogus", stories_dir=temp_stories_dir)
