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

From the options spike, the path is **Goose first, then a custom loop**:

- **Phase 1 (Goose):** Wrap FamilyVault's existing scripts as tools, expose them via an MCP server, drive them with [Goose](https://github.com/block/goose) + Ollama. Fastest path to a working agent; validates local-model quality with minimal new code.
- **Phase 1b (Custom loop):** Replace Goose with a ~80–150 line custom Python agent loop calling the **same tool functions** directly. Maximum learning and full control.

The reusable investment is the **tool logic** (the code that talks to Immich, FFmpeg, and `project.json`) — written once, called two ways.

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

## Tools (the agent's capabilities)

Minimal set — local models degrade with large tool sets. Covers the full story workflow:

| Tool | What it does | Wraps |
|---|---|---|
| `search_photos` | Search Immich by query, person, date, location | `search_photos.py` |
| `list_projects` | List existing projects | `manage_scenario.py list` |
| `create_project` | Create a project, returns `project_id` | `manage_scenario.py create` |
| `get_project` | Read project state (timeline, narrative, status) | `manage_scenario.py show` |
| `set_timeline` | Replace the full ordered scene list in one call | `manage_scenario.py add/remove/reorder` |
| `set_narrative` | Set the story narrative text | `manage_scenario.py set-narrative` |
| `assemble_video` | Trigger FFmpeg assembly, return output path | `assemble_video.py` |

Design notes:
- `set_timeline` takes the **full ordered list** rather than incremental add/remove/reorder ops — simpler for the model (build the list it wants, set it; no index tracking across calls).
- `search_photos` returns a **compact** record (asset id, date, location, people, thumbnail URL) — keeps the context window lean.
- `assemble_video` is blocking with streamed progress (~30–60s for a 2-min video).

**Intentionally excluded for now:** photo scoring, burst dedup, scene detection. These currently live in Claude's reasoning. Phase 1 simplifies to search → pick → assemble. Scoring can be reintroduced once the basic loop works.

---

## File Layout

All new code under `setup/local-agent/`, isolated from `setup/story-engine/` (which it wraps):

```
setup/local-agent/
├── README.md                 # setup + usage
├── pyproject.toml            # deps: mcp, requests (reuses existing scripts)
├── config.sh                 # OLLAMA_URL, MODEL; reuses story-engine config.sh
├── tools/                    # ← shared core (Phase 1 AND 1b)
│   ├── __init__.py
│   ├── photos.py             # search_photos
│   ├── projects.py           # list/create/get_project, set_timeline, set_narrative
│   └── video.py              # assemble_video
├── server.py                 # Phase 1: MCP server — registers tools/ for Goose
├── agent.py                  # Phase 1b: custom loop — imports tools/ directly
└── tests/
    ├── test_tools.py         # unit tests per tool (mock Immich/subprocess)
    └── test_agent.py         # Phase 1b loop tests
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

| Step | What | Depends on |
|---|---|---|
| 0 | Install Ollama + qwen3:14b + smoke test (go/no-go) | Mac Mini |
| 1 | Build `tools/` (7 functions) + unit tests | Step 0 |
| 2 | `server.py` MCP wrapper + connect Goose | Step 1 |
| 3 | End-to-end: create a real story through Goose | Step 2 |
| 4 | **Phase 1b:** `agent.py` custom loop over same tools | Step 3 |

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

- The novel AI-directed UI (voice, dynamic tool activation, live state) — future spec.
- Cloud productization & agent sandboxing (e.g. patterns from NemoClaw) — Phase 3+ if pursued.
- Photo scoring / burst dedup / scene detection — reintroduce after the basic loop works.
