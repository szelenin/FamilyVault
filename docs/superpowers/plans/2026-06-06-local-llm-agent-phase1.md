# Local LLM Agent (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-LLM agent that, from a natural-language request, searches the Immich library, creates a v2 project, and writes an ordered timeline to `project.json` — first driven by Goose+MCP (Phase 1), then by a custom Python loop (Phase 1b). Video assembly is deferred.

**Architecture:** A new `setup/local-agent/` package whose `tools/` modules are thin wrappers over the existing v2 story-engine functions (`search_photos.search_photos`, `manage_project.create_project/show_project/set_timeline`) plus one new `list_projects` helper. `server.py` exposes those functions over MCP (FastMCP) for Goose. `agent.py` (Phase 1b) imports the same functions and runs its own tool-calling loop against Ollama's OpenAI-compatible endpoint. The `tools/` package is the shared core; both runtimes are thin adapters.

**Tech Stack:** Python 3.13, Ollama (`qwen3:14b`), `mcp` (FastMCP) for Phase 1, `openai` SDK pointed at Ollama for Phase 1b, `pytest` for tests, Goose CLI.

**Baseline:** v2 `manage_project.py` / `project.json` / `timeline` field. v1 (`manage_scenario.py`) is deprecated and not used. Spec: `docs/spike/2026-06-06-local-llm-agent-design.md`.

---

## Task 0: Ollama install + tool-calling smoke test (go/no-go gate)

This runs on the Mac Mini (Apple M4, 24GB). It de-risks the single biggest unknown — can a local model do reliable tool calling fast enough — **before** any tool code is written. If the smoke test fails, stop and reconsider the model choice; do not proceed to Task 1.

**Files:**
- Create: `setup/local-agent/scripts/smoke_test.py`

- [ ] **Step 1: Install Ollama and pull the model (on the Mac Mini)**

Run:
```bash
ssh macmini "/opt/homebrew/bin/brew install ollama && brew services start ollama && sleep 3 && ollama pull qwen3:14b && ollama list"
```
Expected: `ollama list` shows `qwen3:14b`.

- [ ] **Step 2: Write the smoke test script**

```python
# setup/local-agent/scripts/smoke_test.py
"""Go/no-go: verify the local model emits a correct tool call and measure speed."""
import json
import time
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
}]


def main():
    start = time.time()
    resp = client.chat.completions.create(
        model="qwen3:14b",
        messages=[{"role": "user", "content": "What's the weather in Miami? Use the tool."}],
        tools=TOOLS,
    )
    elapsed = time.time() - start
    msg = resp.choices[0].message
    calls = msg.tool_calls or []
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Tool calls: {len(calls)}")
    assert calls, "FAIL: model did not emit a tool call"
    call = calls[0]
    assert call.function.name == "get_weather", f"FAIL: wrong tool {call.function.name}"
    args = json.loads(call.function.arguments)
    assert args.get("city", "").lower() == "miami", f"FAIL: wrong args {args}"
    print("PASS: model emits correct tool call")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the smoke test on the Mac Mini**

Run:
```bash
ssh macmini "cd /path/to/FamilyVault-AI && pip3 install openai && python3 setup/local-agent/scripts/smoke_test.py"
```
Expected: `PASS: model emits correct tool call`, with elapsed time printed. **Go/no-go:** if it prints PASS and elapsed is acceptable (a few seconds), proceed. If it FAILs or is unusably slow, try `qwen2.5:14b`, then re-run; if still failing, stop and revisit the model decision before continuing.

- [ ] **Step 4: Commit**

```bash
git add setup/local-agent/scripts/smoke_test.py
git commit -m "feat(local-agent): Ollama tool-calling smoke test (go/no-go gate)"
```

---

## Task 1: Package scaffolding + engine bridge

Creates the `setup/local-agent/` package and the single place that puts the story-engine `scripts` package on the import path. Mirrors the existing convention in `tests/story-engine/conftest.py`.

**Files:**
- Create: `setup/local-agent/__init__.py` (empty)
- Create: `setup/local-agent/tools/__init__.py` (empty)
- Create: `setup/local-agent/tools/_engine.py`
- Create: `setup/local-agent/pyproject.toml`
- Create: `setup/local-agent/config.sh`
- Create: `setup/local-agent/tests/__init__.py` (empty)
- Create: `setup/local-agent/tests/conftest.py`
- Test: `setup/local-agent/tests/test_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# setup/local-agent/tests/test_engine.py
"""The engine bridge must expose the v2 story-engine functions."""

def test_engine_exposes_v2_functions():
    from tools import _engine
    assert callable(_engine.search_photos)
    assert callable(_engine.make_session)
    assert callable(_engine.create_project)
    assert callable(_engine.show_project)
    assert callable(_engine.set_timeline)
    assert callable(_engine.default_stories_dir)
```

- [ ] **Step 2: Write conftest (adds local-agent to sys.path)**

```python
# setup/local-agent/tests/conftest.py
"""Put the local-agent package root on sys.path so `import tools...` works."""
import os
import sys

_PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _PKG_ROOT)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd setup/local-agent && python3 -m pytest tests/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools._engine'`

- [ ] **Step 4: Write the engine bridge**

```python
# setup/local-agent/tools/_engine.py
"""Single import bridge to the v2 story-engine scripts.

Mirrors tests/story-engine/conftest.py: add setup/story-engine to sys.path,
then import the `scripts` package. v1 (manage_scenario) is intentionally NOT
imported — v2 manage_project is the baseline.
"""
import os
import sys

_ENGINE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "story-engine")
)
if _ENGINE_ROOT not in sys.path:
    sys.path.insert(0, _ENGINE_ROOT)

from scripts.search_photos import search_photos, make_session, get_api_key  # noqa: E402
from scripts.manage_project import (  # noqa: E402
    create_project,
    show_project,
    set_timeline,
    _default_stories_dir as default_stories_dir,
)

__all__ = [
    "search_photos",
    "make_session",
    "get_api_key",
    "create_project",
    "show_project",
    "set_timeline",
    "default_stories_dir",
]
```

- [ ] **Step 5: Write pyproject.toml and config.sh**

```toml
# setup/local-agent/pyproject.toml
[project]
name = "familyvault-local-agent"
version = "0.1.0"
description = "Local-LLM agent for FamilyVault (Phase 1)"
requires-python = ">=3.13"
dependencies = ["openai>=1.0", "mcp>=1.0", "requests>=2.0"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

```bash
# setup/local-agent/config.sh
# Local agent config. Reuses story-engine defaults; override via env.
: "${OLLAMA_URL:=http://localhost:11434/v1}"
: "${OLLAMA_MODEL:=qwen3:14b}"
: "${IMMICH_URL:=http://immich-immich-server-1.orb.local}"
: "${IMMICH_API_KEY_FILE:=/Volumes/HomeRAID/immich/api-key.txt}"
: "${STORIES_DIR:=/Volumes/HomeRAID/stories}"
export OLLAMA_URL OLLAMA_MODEL IMMICH_URL IMMICH_API_KEY_FILE STORIES_DIR
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd setup/local-agent && python3 -m pytest tests/test_engine.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add setup/local-agent/__init__.py setup/local-agent/tools/ setup/local-agent/pyproject.toml setup/local-agent/config.sh setup/local-agent/tests/
git commit -m "feat(local-agent): package scaffolding + v2 engine import bridge"
```

---

## Task 2: `search_photos` tool

Wraps `search_photos.search_photos()`. Builds the Immich session from config, returns compact records, and **traps the `sys.exit(3)`** the underlying function raises on request errors (otherwise it would kill the agent process).

**Files:**
- Create: `setup/local-agent/tools/photos.py`
- Test: `setup/local-agent/tests/test_photos.py`

- [ ] **Step 1: Write the failing test**

```python
# setup/local-agent/tests/test_photos.py
from unittest.mock import patch
import tools.photos as photos


def test_search_returns_compact_records():
    fake_assets = [
        {"id": "a1", "asset_id": "a1", "type": "IMAGE", "filename": "x.jpg",
         "mime_type": "image/jpeg", "taken_at": "2025-03-15T14:30:00Z",
         "city": "Miami", "country": "US", "description": "cake"},
    ]
    with patch.object(photos, "_search_photos", return_value=fake_assets), \
         patch.object(photos, "_make_session", return_value=object()):
        out = photos.search_photos(query="birthday", limit=5)
    assert isinstance(out, list)
    rec = out[0]
    assert rec["asset_id"] == "a1"
    assert rec["taken_at"] == "2025-03-15T14:30:00Z"
    assert rec["city"] == "Miami"
    assert rec["thumbnail_url"].endswith("/api/assets/a1/thumbnail")
    # compact: no raw mime/filename noise
    assert set(rec.keys()) == {
        "asset_id", "type", "taken_at", "city", "country", "description", "thumbnail_url"
    }


def test_search_traps_systemexit():
    def boom(*a, **k):
        raise SystemExit(3)
    with patch.object(photos, "_search_photos", side_effect=boom), \
         patch.object(photos, "_make_session", return_value=object()):
        try:
            photos.search_photos(query="x")
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "search failed" in str(e).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd setup/local-agent && python3 -m pytest tests/test_photos.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.photos'`

- [ ] **Step 3: Write the implementation**

```python
# setup/local-agent/tools/photos.py
"""search_photos tool — compact Immich search for the agent."""
import os

from tools._engine import (
    search_photos as _search_photos,
    make_session as _make_session,
)

_IMMICH_URL = os.environ.get("IMMICH_URL", "http://immich-immich-server-1.orb.local")
_API_KEY_FILE = os.environ.get(
    "IMMICH_API_KEY_FILE", "/Volumes/HomeRAID/immich/api-key.txt"
)


def _compact(asset: dict) -> dict:
    aid = asset.get("asset_id") or asset.get("id")
    return {
        "asset_id": aid,
        "type": asset.get("type"),
        "taken_at": asset.get("taken_at"),
        "city": asset.get("city"),
        "country": asset.get("country"),
        "description": asset.get("description"),
        "thumbnail_url": f"{_IMMICH_URL}/api/assets/{aid}/thumbnail",
    }


def search_photos(
    query: str = "",
    person: str = "",
    after: str = "",
    before: str = "",
    city: str = "",
    country: str = "",
    media_type: str = "IMAGE",
    limit: int = 30,
) -> list:
    """Search the photo/video library.

    Args:
        query: Free-text semantic query (e.g. "birthday cake").
        person: Person name to filter by.
        after: Start date YYYY-MM-DD.
        before: End date YYYY-MM-DD.
        city: City filter.
        country: Country filter.
        media_type: IMAGE or VIDEO.
        limit: Max results.

    Returns:
        List of compact asset records: asset_id, type, taken_at, city,
        country, description, thumbnail_url.
    """
    session = _make_session(_IMMICH_URL, _API_KEY_FILE)
    try:
        assets = _search_photos(
            immich_url=_IMMICH_URL,
            session=session,
            query=query or None,
            person_name=person or None,
            after=after or None,
            before=before or None,
            city=city or None,
            country=country or None,
            media_type=media_type,
            limit=limit,
        )
    except SystemExit as e:  # underlying script calls sys.exit(3) on errors
        raise RuntimeError(f"search failed (exit {e.code})")
    return [_compact(a) for a in assets]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd setup/local-agent && python3 -m pytest tests/test_photos.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add setup/local-agent/tools/photos.py setup/local-agent/tests/test_photos.py
git commit -m "feat(local-agent): search_photos tool with compact records + SystemExit trap"
```

---

## Task 3: `create_project` + `get_project` tools

Thin wrappers over the v2 functions, using a temp `STORIES_DIR` in tests (real filesystem, no network).

**Files:**
- Create: `setup/local-agent/tools/projects.py`
- Test: `setup/local-agent/tests/test_projects.py`

- [ ] **Step 1: Write the failing test**

```python
# setup/local-agent/tests/test_projects.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd setup/local-agent && python3 -m pytest tests/test_projects.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.projects'`

- [ ] **Step 3: Write the implementation**

```python
# setup/local-agent/tools/projects.py
"""Project management tools (v2 manage_project)."""
from tools._engine import (
    create_project as _create_project,
    show_project as _show_project,
    set_timeline as _set_timeline,
)


def create_project(title: str, request: str) -> dict:
    """Create a new story project.

    Args:
        title: Human-readable title (used to derive the project id).
        request: The original natural-language request.

    Returns:
        {"project_id": str, "title": str, "state": str}
    """
    p = _create_project(title=title, request=request)
    return {"project_id": p["id"], "title": p["title"], "state": p["state"]}


def get_project(project_id: str) -> dict:
    """Return the full project state (timeline, scenes, status, etc.).

    Args:
        project_id: The project id returned by create_project.
    """
    return _show_project(project_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd setup/local-agent && python3 -m pytest tests/test_projects.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add setup/local-agent/tools/projects.py setup/local-agent/tests/test_projects.py
git commit -m "feat(local-agent): create_project + get_project tools"
```

---

## Task 4: `set_timeline` tool

Accepts an ordered list of asset ids, builds canonical timeline items (`{position, asset_id}`), and persists via the v2 function.

**Files:**
- Modify: `setup/local-agent/tools/projects.py`
- Test: `setup/local-agent/tests/test_projects.py`

- [ ] **Step 1: Write the failing test (append to test_projects.py)**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd setup/local-agent && python3 -m pytest tests/test_projects.py::test_set_timeline_builds_positions -v`
Expected: FAIL with `AttributeError: module 'tools.projects' has no attribute 'set_timeline'`

- [ ] **Step 3: Add the implementation to projects.py**

```python
def set_timeline(project_id: str, asset_ids: list) -> dict:
    """Replace the project's timeline with an ordered list of assets.

    Args:
        project_id: The project id.
        asset_ids: Asset ids in the desired display order.

    Returns:
        {"timeline": [{"position": int, "asset_id": str}, ...], "count": int}
    """
    items = [{"position": i, "asset_id": aid} for i, aid in enumerate(asset_ids, 1)]
    p = _set_timeline(project_id, items)
    return {"timeline": p["timeline"], "count": len(p["timeline"])}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd setup/local-agent && python3 -m pytest tests/test_projects.py -v`
Expected: PASS (all project tests)

- [ ] **Step 5: Commit**

```bash
git add setup/local-agent/tools/projects.py setup/local-agent/tests/test_projects.py
git commit -m "feat(local-agent): set_timeline tool (asset ids -> positioned items)"
```

---

## Task 5: `list_projects` tool (new helper)

No v2 list function exists. Implement by scanning `STORIES_DIR` for `*/project.json` and returning `{id, title, state}` per project.

**Files:**
- Modify: `setup/local-agent/tools/projects.py`
- Test: `setup/local-agent/tests/test_projects.py`

- [ ] **Step 1: Write the failing test (append to test_projects.py)**

```python
def test_list_projects_empty():
    assert projects.list_projects() == []


def test_list_projects_returns_summaries():
    a = projects.create_project(title="Alpha", request="r1")
    b = projects.create_project(title="Beta", request="r2")
    listed = projects.list_projects()
    ids = {p["id"] for p in listed}
    assert {a["project_id"], b["project_id"]} <= ids
    for p in listed:
        assert set(p.keys()) == {"id", "title", "state"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd setup/local-agent && python3 -m pytest tests/test_projects.py::test_list_projects_empty -v`
Expected: FAIL with `AttributeError: module 'tools.projects' has no attribute 'list_projects'`

- [ ] **Step 3: Add the implementation to projects.py**

Add this import near the top of `projects.py`:
```python
import json
import os

from tools._engine import default_stories_dir
```

Add the function:
```python
def list_projects() -> list:
    """List existing projects.

    Returns:
        List of {"id": str, "title": str, "state": str}, sorted by id.
    """
    stories_dir = os.environ.get("STORIES_DIR") or default_stories_dir()
    if not os.path.isdir(stories_dir):
        return []
    out = []
    for entry in sorted(os.listdir(stories_dir)):
        path = os.path.join(stories_dir, entry, "project.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            p = json.load(f)
        out.append({"id": p.get("id"), "title": p.get("title"), "state": p.get("state")})
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd setup/local-agent && python3 -m pytest tests/test_projects.py -v`
Expected: PASS (all project tests)

- [ ] **Step 5: Commit**

```bash
git add setup/local-agent/tools/projects.py setup/local-agent/tests/test_projects.py
git commit -m "feat(local-agent): list_projects helper (scan STORIES_DIR)"
```

---

## Task 6: MCP server (`server.py`) for Goose

Exposes the 5 tools over MCP using FastMCP, which derives schemas from type hints + docstrings. Test asserts all 5 tools are registered.

**Files:**
- Create: `setup/local-agent/server.py`
- Test: `setup/local-agent/tests/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# setup/local-agent/tests/test_server.py
import asyncio


def test_server_registers_five_tools():
    import server
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "search_photos", "list_projects", "create_project",
        "get_project", "set_timeline",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd setup/local-agent && python3 -m pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Write the implementation**

```python
# setup/local-agent/server.py
"""FamilyVault MCP server — exposes the 5 Phase-1 tools for Goose."""
from mcp.server.fastmcp import FastMCP

from tools.photos import search_photos as _search_photos
from tools.projects import (
    list_projects as _list_projects,
    create_project as _create_project,
    get_project as _get_project,
    set_timeline as _set_timeline,
)

mcp = FastMCP("familyvault")

mcp.tool()(_search_photos)
mcp.tool()(_list_projects)
mcp.tool()(_create_project)
mcp.tool()(_get_project)
mcp.tool()(_set_timeline)


if __name__ == "__main__":
    mcp.run()  # stdio transport
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd setup/local-agent && python3 -m pytest tests/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `cd setup/local-agent && python3 -m pytest -v`
Expected: PASS (all tests across engine, photos, projects, server)

- [ ] **Step 6: Commit**

```bash
git add setup/local-agent/server.py setup/local-agent/tests/test_server.py
git commit -m "feat(local-agent): FastMCP server exposing the 5 Phase-1 tools"
```

---

## Task 7: Goose configuration + end-to-end validation (Phase 1 complete)

Manual integration on the Mac Mini: point Goose at Ollama + the MCP server, then drive a real request and verify a timeline lands in `project.json`. No automated test — this is the human checkpoint.

**Files:**
- Create: `setup/local-agent/README.md` (Goose setup section; expanded in Task 11)

- [ ] **Step 1: Install Goose on the Mac Mini**

Run:
```bash
ssh macmini "curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | bash"
```
Expected: `goose` binary installed.

- [ ] **Step 2: Configure Goose to use Ollama**

Run: `ssh macmini -t "goose configure"` and select Provider = Ollama, Model = `qwen3:14b`.
Expected: `~/.config/goose/config.yaml` written with the Ollama provider.

- [ ] **Step 3: Register the MCP server as a Goose extension**

Add to `~/.config/goose/config.yaml` (stdio extension):
```yaml
extensions:
  familyvault:
    type: stdio
    cmd: python3
    args: ["/ABSOLUTE/PATH/FamilyVault-AI/setup/local-agent/server.py"]
    enabled: true
    envs:
      STORIES_DIR: /Volumes/HomeRAID/stories
      IMMICH_URL: http://immich-immich-server-1.orb.local
      IMMICH_API_KEY_FILE: /Volumes/HomeRAID/immich/api-key.txt
```

- [ ] **Step 4: Run an end-to-end session**

Run: `ssh macmini -t "goose session"` then type:
> Find photos from our Miami trip in March 2025, create a project called "Miami March", and put the 10 best on the timeline.

Expected: Goose calls `search_photos`, `create_project`, then `set_timeline`.

- [ ] **Step 5: Verify the result on disk**

Run:
```bash
ssh macmini "ls /Volumes/HomeRAID/stories/ && cat /Volumes/HomeRAID/stories/*miami-march*/project.json | python3 -m json.tool | head -40"
```
Expected: a `project.json` exists with a non-empty `timeline` of `{position, asset_id}` items. **Phase 1 is functionally complete when this passes.**

- [ ] **Step 6: Commit**

```bash
git add setup/local-agent/README.md
git commit -m "docs(local-agent): Goose + Ollama setup; Phase 1 e2e validated"
```

---

## Task 8: OpenAI tool-schema generator (`registry.py`) — Phase 1b

The custom loop needs OpenAI-format tool schemas. Generate them by introspecting the tool functions (signature + docstring). One registry lists the 5 tools.

**Files:**
- Create: `setup/local-agent/registry.py`
- Test: `setup/local-agent/tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# setup/local-agent/tests/test_registry.py
import registry


def test_registry_has_five_tools():
    assert set(registry.TOOLS.keys()) == {
        "search_photos", "list_projects", "create_project",
        "get_project", "set_timeline",
    }


def test_openai_schema_shape():
    schemas = registry.openai_schemas()
    by_name = {s["function"]["name"]: s for s in schemas}
    sp = by_name["search_photos"]
    assert sp["type"] == "function"
    params = sp["function"]["parameters"]
    assert params["type"] == "object"
    # required params have no default; optional ones do
    assert "query" in params["properties"]
    assert params["properties"]["query"]["type"] == "string"
    # create_project: title and request are required (no defaults)
    cp = by_name["create_project"]["function"]["parameters"]
    assert set(cp["required"]) == {"title", "request"}


def test_dispatch_calls_function(monkeypatch):
    called = {}
    monkeypatch.setitem(registry.TOOLS, "create_project",
                        lambda title, request: called.update(title=title, request=request) or {"ok": 1})
    out = registry.dispatch("create_project", {"title": "X", "request": "r"})
    assert out == {"ok": 1}
    assert called == {"title": "X", "request": "r"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd setup/local-agent && python3 -m pytest tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'registry'`

- [ ] **Step 3: Write the implementation**

```python
# setup/local-agent/registry.py
"""Tool registry + OpenAI schema generation for the custom loop (Phase 1b)."""
import inspect
import typing

from tools.photos import search_photos
from tools.projects import (
    list_projects, create_project, get_project, set_timeline,
)

TOOLS = {
    "search_photos": search_photos,
    "list_projects": list_projects,
    "create_project": create_project,
    "get_project": get_project,
    "set_timeline": set_timeline,
}

_PY_TO_JSON = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array"}


def _json_type(annotation):
    return _PY_TO_JSON.get(annotation, "string")


def _schema_for(name, fn):
    sig = inspect.signature(fn)
    props = {}
    required = []
    for pname, param in sig.parameters.items():
        ann = param.annotation if param.annotation is not inspect.Parameter.empty else str
        props[pname] = {"type": _json_type(ann)}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": (inspect.getdoc(fn) or "").split("\n\n")[0],
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


def openai_schemas():
    """Return OpenAI-format tool schemas for all registered tools."""
    return [_schema_for(name, fn) for name, fn in TOOLS.items()]


def dispatch(name, arguments: dict):
    """Call a registered tool by name with a dict of arguments."""
    if name not in TOOLS:
        raise KeyError(f"unknown tool: {name}")
    return TOOLS[name](**arguments)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd setup/local-agent && python3 -m pytest tests/test_registry.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add setup/local-agent/registry.py setup/local-agent/tests/test_registry.py
git commit -m "feat(local-agent): tool registry + OpenAI schema generator (Phase 1b)"
```

---

## Task 9: Custom agent loop (`agent.py`) — dispatch logic

The loop: send messages + schemas to the LLM, execute any tool calls, append results, repeat until a plain-text answer or the iteration cap. Test the loop with a fake client (no Ollama needed).

**Files:**
- Create: `setup/local-agent/agent.py`
- Test: `setup/local-agent/tests/test_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# setup/local-agent/tests/test_agent.py
import json
from types import SimpleNamespace
import agent as agent_mod


class _FakeClient:
    """Returns a tool call on the first turn, a final answer on the second."""
    def __init__(self):
        self.turns = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools):
        self.turns += 1
        if self.turns == 1:
            tc = SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(name="create_project",
                                         arguments=json.dumps({"title": "X", "request": "r"})),
            )
            msg = SimpleNamespace(role="assistant", content=None, tool_calls=[tc])
        else:
            msg = SimpleNamespace(role="assistant", content="Done — project created.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_loop_dispatches_then_finishes(monkeypatch):
    monkeypatch.setattr(agent_mod.registry, "dispatch",
                        lambda name, args: {"project_id": "p1"} if name == "create_project" else None)
    client = _FakeClient()
    answer, transcript = agent_mod.run_loop(client, "make a project", model="m", max_iters=5)
    assert "Done" in answer
    assert client.turns == 2
    # a tool result message was appended
    assert any(m.get("role") == "tool" for m in transcript)


def test_loop_respects_iteration_cap(monkeypatch):
    monkeypatch.setattr(agent_mod.registry, "dispatch", lambda name, args: {"x": 1})

    class _Loop:
        def __init__(self): self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._c))
        def _c(self, model, messages, tools):
            tc = SimpleNamespace(id="c", function=SimpleNamespace(name="get_project",
                                  arguments=json.dumps({"project_id": "p"})))
            msg = SimpleNamespace(role="assistant", content=None, tool_calls=[tc])
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    answer, _ = agent_mod.run_loop(_Loop(), "x", model="m", max_iters=3)
    assert "stopped" in answer.lower() or "max" in answer.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd setup/local-agent && python3 -m pytest tests/test_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent'`

- [ ] **Step 3: Write the implementation**

```python
# setup/local-agent/agent.py
"""Custom tool-calling loop over Ollama's OpenAI-compatible endpoint (Phase 1b)."""
import json
import os

import registry

SYSTEM_PROMPT = (
    "You are FamilyVault's assistant. Use the tools to search the photo library, "
    "create projects, and build timelines. Build the full ordered list of asset_ids "
    "and call set_timeline once. When the task is done, reply with a short summary."
)


def run_loop(client, user_message: str, model: str, max_iters: int = 10):
    """Run the agent loop. Returns (final_text, transcript)."""
    schemas = registry.openai_schemas()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    for _ in range(max_iters):
        resp = client.chat.completions.create(model=model, messages=messages, tools=schemas)
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            return (msg.content or "", messages)
        messages.append({"role": "assistant", "content": msg.content,
                         "tool_calls": [
                             {"id": tc.id, "type": "function",
                              "function": {"name": tc.function.name,
                                           "arguments": tc.function.arguments}}
                             for tc in tool_calls]})
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                result = registry.dispatch(tc.function.name, args)
            except Exception as e:  # surface tool errors back to the model
                result = {"error": str(e)}
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, default=str)})
    return ("Stopped: reached the maximum number of steps.", messages)


def main():
    import sys
    from openai import OpenAI

    model = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/v1")
    client = OpenAI(base_url=base_url, api_key="ollama")
    user_message = " ".join(sys.argv[1:]) or input("Request: ")
    answer, _ = run_loop(client, user_message, model=model)
    print(answer)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd setup/local-agent && python3 -m pytest tests/test_agent.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full suite**

Run: `cd setup/local-agent && python3 -m pytest -v`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add setup/local-agent/agent.py setup/local-agent/tests/test_agent.py
git commit -m "feat(local-agent): custom tool-calling loop with dispatch + iteration cap"
```

---

## Task 10: Custom loop end-to-end on Ollama (Phase 1b complete)

Manual checkpoint: run `agent.py` against real Ollama + Immich and confirm it produces the same kind of `project.json` Goose did.

- [ ] **Step 1: Run the loop on the Mac Mini**

Run:
```bash
ssh macmini "cd /path/to/FamilyVault-AI/setup/local-agent && source config.sh && python3 agent.py 'Find Miami March 2025 photos, create project \"Miami Loop\", put 8 on the timeline'"
```
Expected: prints a short summary; no crash.

- [ ] **Step 2: Verify the result on disk**

Run:
```bash
ssh macmini "cat /Volumes/HomeRAID/stories/*miami-loop*/project.json | python3 -m json.tool | head -40"
```
Expected: `project.json` with a non-empty positioned `timeline`. **Phase 1b is complete when this passes.**

---

## Task 11: Documentation — local-agent README + story-engine v2 correction

Two doc updates: finish the local-agent README, and correct the story-engine README, which still presents the deprecated v1 `manage_scenario.py` CLI as current.

**Files:**
- Modify: `setup/local-agent/README.md`
- Modify: `setup/story-engine/README.md`

- [ ] **Step 1: Write the local-agent README**

Content must cover: purpose (Phase 1 local agent), the 5 tools, prerequisites (Ollama + `qwen3:14b`, Goose), how to run via Goose (Task 7 config), how to run the custom loop (`python3 agent.py "..."`), how to run tests (`python3 -m pytest`), and a pointer to the design doc `docs/spike/2026-06-06-local-llm-agent-design.md`.

- [ ] **Step 2: Correct the story-engine README for v2**

In `setup/story-engine/README.md`: add a note at the top of the scenario-management section stating that `manage_scenario.py` is **deprecated (v1)** and the current model is v2 `manage_project.py` using `project.json` with a `timeline` field. Note that v2 project management is currently driven programmatically (importable functions) and by the Selection UI, and that video assembly via v2 is not yet wired (`assemble_video.py` still targets v1). Do not delete the v1 examples; mark the section "Legacy (v1)".

- [ ] **Step 3: Verify no test references broke**

Run: `cd /path/to/FamilyVault-AI && python3 -m pytest tests/story-engine/ -q`
Expected: PASS (docs-only change; existing tests unaffected).

- [ ] **Step 4: Commit**

```bash
git add setup/local-agent/README.md setup/story-engine/README.md
git commit -m "docs: local-agent README + mark story-engine v1 scenario CLI as legacy"
```

---

## Done criteria

- Task 0 smoke test passed (go/no-go).
- `python3 -m pytest` green in `setup/local-agent/`.
- Goose (Phase 1) and `agent.py` (Phase 1b) each produce a `project.json` with a populated timeline from a natural-language request.
- READMEs reflect the v2 baseline.
