# Local LLM Agent — Design

**Date:** 2026-06-06
**Branch:** `015-local-llm-spike`
**Status:** Design (approved in brainstorming, pending written review)
**Builds on:** [2026-04-27-local-llm-agent-options.md](./2026-04-27-local-llm-agent-options.md)

---

## Goal

Replace Claude Code + Claude API as FamilyVault's AI orchestrator with a **locally hosted LLM** running on the Mac Mini. Primary motivation is **learning by doing** — understanding how to build agents from scratch — with a possible (not committed) future path to productizing as a cloud service.

This design covers **Phase 1** only. The novel AI-directed UI (voice, dynamic tool activation, live state sync) is a separate spec for a future session.

## Chosen Approach: D → A

The options spike proposed **Goose first, then a custom loop** (D→A):

- **Goose:** Wrap the existing scripts as tools, expose via an MCP server, drive with [Goose](https://github.com/block/goose) + Ollama. Fastest validation with minimal new code.
- **Custom loop:** A ~50-line custom Python agent loop calling the **same tool functions** directly. Maximum learning and full control — the long-term direction.

### What we actually built (2026-06-06)

> **We went straight to the custom loop and skipped Goose.** During execution it became clear the custom loop (the end goal, "A") is our own code talking HTTP to Ollama — which we'd already proven works via the smoke test — and was lower-risk than installing Goose (the Ollama cask binary had shown exec-environment friction on this machine). The custom loop now works end-to-end. **Goose is parked as its own follow-up feature, PRD IMP-017.**

The reusable investment is the **tool logic** (the code that talks to Immich and `project.json`) — written once. It's exposed two ways: as plain functions the custom loop calls directly (`agent.py` → `registry.py` → `tools/`), and over MCP (`server.py`) for when Goose is picked up later.

---

## Target Hardware (verified 2026-06-06)

| Spec | Value | Implication |
|---|---|---|
| Chip | Apple M4 | Fast inference; supports Ollama MLX backend |
| RAM | 24 GB | Comfortable for `qwen3:14b` (~9GB) alongside Immich |
| Ollama | Not yet installed | Clean Step 0 install |

24GB on M4 is comfortable. Primary model `qwen3:14b`; stretch option `qwen2.5:32b` (~20GB, tight if Immich is indexing). The Step 0 smoke test benchmarks and picks.

---

## Architecture

**Phase 1 — Goose + MCP:**

```
User (terminal)
    ↓ natural language
Goose CLI  ←→  Ollama (qwen3:14b, localhost:11434)
    ↓ tool_calls (MCP protocol)
FamilyVault MCP Server (server.py, new)
    ↓ direct calls
tools/ package  →  existing scripts / Immich API / FFmpeg / project.json
```

**Phase 1b — Custom loop (no MCP, no Goose):**

```
User (terminal)
    ↓ natural language
agent.py (custom loop, OpenAI SDK → Ollama)
    ↓ direct function calls
tools/ package  →  same scripts / Immich / FFmpeg / project.json
```

MCP is required for Goose (it's Goose's only extension mechanism). The custom loop calls the `tools/` functions directly — no network protocol, no extra process. **The `tools/` package is the shared core across both phases.**

Everything else — Immich, the `setup/story-engine/` scripts, `project.json`, FFmpeg — stays unchanged. The agent wraps them; it does not replace them.

---

## Baseline: v2 project model

**The v2 `manage_project.py` module is the baseline.** v1 (`manage_scenario.py`, `scenario.json`, `items` field, `draft→approved` states) is deprecated and out of scope. v2 uses `project.json` with a `timeline` field and importable Python functions — no subprocess needed for project management.

Reality check found in the code: v2 `manage_project.py` exists and works for project management, but the **video assembler (`assemble_video.py`) is still wired to v1** and its v2 path (`build_ffmpeg_cmd_v2`) was started but never connected. Rather than finish that migration now, **Phase 1 defers video assembly entirely** (see Scope below).

## Tools (the agent's capabilities)

Minimal set — local models degrade with large tool sets. Phase 1 covers search → create project → build timeline. The user reviews the result in the existing Selection UI. All tools call importable functions from the existing scripts directly.

| Tool | What it does | Backed by |
|---|---|---|
| `search_photos` | Search Immich by query, person, date, location | `search_photos.py::search_photos()` |
| `list_projects` | List existing projects (id, title, state) | new helper (no v2 list fn exists) |
| `create_project` | Create a project, returns `project_id` | `manage_project.py::create_project()` |
| `get_project` | Read project state (timeline, scenes, status) | `manage_project.py::show_project()` |
| `set_timeline` | Replace the full ordered timeline in one call | `manage_project.py::set_timeline()` |

Design notes:
- `set_timeline` takes the **full ordered list** rather than incremental add/remove/reorder ops — simpler for the model (build the list it wants, set it; no index tracking across calls). Timeline item shape: `{"position": int, "asset_id": str}` (videos may add trim `start`/`end`).
- `search_photos` returns a **compact** record (asset id, date, location, people, thumbnail URL) — keeps the context window lean.

**Intentionally excluded from Phase 1:** video assembly (deferred), narrative/per-scene stories (v2 has no top-level narrative field), photo scoring, burst dedup, scene detection. Phase 1 proves the agent loop + tool calling against the real library; capabilities layer on after.

---

## File Layout

All new code under `setup/local-agent/`, isolated from `setup/story-engine/` (which it wraps):

```
setup/local-agent/            # (as built)
├── README.md                 # quickstart + usage
├── SETUP-NOTES.md            # machine gotchas (python3.13, Ollama runner fix)
├── pyproject.toml            # deps: openai, mcp, requests
├── config.sh                 # OLLAMA_URL/MODEL, IMMICH_*, STORIES_DIR
├── tools/                    # ← shared core (used by both runtimes)
│   ├── __init__.py
│   ├── _engine.py            # import bridge to v2 story-engine scripts
│   ├── photos.py             # search_photos
│   └── projects.py           # list/create/get_project, set_timeline
├── registry.py               # tool registry + OpenAI schema gen (custom loop)
├── agent.py                  # custom loop — imports tools/ directly  ← what we run
├── server.py                 # MCP server (for Goose later — IMP-017)
├── scripts/
│   └── smoke_test.py         # go/no-go tool-calling test
└── tests/                    # test_engine, test_photos, test_projects,
                              # test_server, test_registry, test_agent (14 tests)
```

**The shared-core pattern:** each `tools/` function is a plain Python function with type hints and a docstring:

```python
def search_photos(query: str, person: str = None, after: str = None,
                  before: str = None, limit: int = 50) -> list[dict]:
    """Search the photo library. Returns compact asset records."""
    ...
```

- `server.py` introspects these → generates **MCP** tool schemas → exposes over MCP for Goose.
- `agent.py` imports the same functions → generates **OpenAI-format** tool schemas → calls them directly.

The docstring becomes the tool description the LLM sees; the type hints become the parameter schema. Both adapters are thin shells over `tools/`.

Goose config lives in `~/.config/goose/config.yaml` (Goose's own location, outside the repo) pointing at `server.py` as a stdio MCP extension and Ollama as the provider — documented in the README.

---

## Build Sequence

**Step 0 de-risks the biggest unknown first:** can a local model on this hardware do reliable tool calling fast enough?

```bash
# On the Mac Mini
brew install ollama
ollama serve
ollama pull qwen3:14b
```

Then a **go/no-go smoke test** (standalone script, ~5 min): send a prompt with one fake tool, confirm a correct `tool_calls` response, measure tokens/sec on real hardware. If reliable and usable → proceed. If not → adjust model (`qwen2.5:14b`, smaller quant) before building anything on top.

**As built** (Goose step skipped — see "What we actually built" above):

| Step | What | Status |
|---|---|---|
| 0 | Install Ollama + qwen3:14b + smoke test (go/no-go) | ✅ passed |
| 1 | Build `tools/` (5 functions) + unit tests | ✅ |
| 2 | `server.py` MCP wrapper (for future Goose) | ✅ built, not connected |
| 3 | `registry.py` + `agent.py` custom loop + tests | ✅ |
| 4 | End-to-end via the custom loop: search → create project → build timeline; verified `project.json` on disk | ✅ |
| — | Connect Goose to `server.py` | parked → IMP-017 |

---

## Testing Strategy

- **Unit (`test_tools.py`):** each tool function with mocked Immich responses and mocked subprocess calls. No network. Fast.
- **Integration:** tools against a live Immich (reuses existing story-engine test patterns).
- **End-to-end (Step 3):** drive Goose to create a complete story from a natural-language request; assert a video file is produced.
- **Phase 1b (`test_agent.py`):** the loop's tool dispatch, context handling, and stop conditions, with a mocked LLM.

---

## Phase 1b — Custom Loop Notes

The loop (~80–150 lines) handles:
- **Tool dispatch:** parse `tool_calls` from the model, match to `tools/` functions, execute, append results.
- **Context management:** running message history; truncate or summarize old turns when approaching the context window. Search results are already compact to help here.
- **Stop conditions:** plain-text answer (done) or iteration cap (safety).
- **Error handling:** tool exceptions returned to the model as tool results so it can recover, not crash the loop.

Built on the OpenAI Python SDK pointed at Ollama's OpenAI-compatible endpoint (`http://localhost:11434/v1`).

---

## Out of Scope (Phase 1)

- **Video assembly** — deferred. The v2 assembler migration (`build_ffmpeg_cmd_v2`) is unfinished; a later phase wires it up, drops the `approved` gate (generate anytime), and adds a draft/full quality switch.
- The novel AI-directed UI (voice, dynamic tool activation, live state) — future spec.
- Cloud productization & agent sandboxing (e.g. patterns from NemoClaw) — Phase 3+ if pursued.
- Narrative / per-scene stories, photo scoring, burst dedup, scene detection — reintroduce after the basic loop works.
- v1 (`manage_scenario.py`) — deprecated; not used by the agent.

## Related doc updates

- `setup/story-engine/README.md` still documents the v1 `manage_scenario.py` CLI as current. It should be updated to reflect the v2 `manage_project.py` model. Tracked as a task in the implementation plan.
