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
