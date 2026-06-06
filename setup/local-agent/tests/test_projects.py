import os
import pytest
import tools.projects as projects


@pytest.fixture(autouse=True)
def _stories_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("STORIES_DIR", str(tmp_path))


def test_create_and_get_project():
    created = projects.create_project(title="Miami Trip", request="miami 2025")
    pid = created["project_id"]
    assert pid
    got = projects.get_project(pid)
    assert got["id"] == pid
    assert got["title"] == "Miami Trip"
    assert got["state"] == "searching"
    assert got["timeline"] == []


def test_set_timeline_builds_positions():
    created = projects.create_project(title="T", request="r")
    pid = created["project_id"]
    result = projects.set_timeline(pid, ["a1", "a2", "a3"])
    tl = result["timeline"]
    assert [i["position"] for i in tl] == [1, 2, 3]
    assert [i["asset_id"] for i in tl] == ["a1", "a2", "a3"]
    # persisted
    assert projects.get_project(pid)["timeline"] == tl


def test_set_timeline_returns_count():
    created = projects.create_project(title="T2", request="r")
    result = projects.set_timeline(created["project_id"], ["a1"])
    assert result["count"] == 1
