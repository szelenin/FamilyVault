# FamilyVault Local Agent (Phase 1)

A locally hosted LLM agent that drives the FamilyVault story workflow with **no cloud dependency**. From a natural-language request it searches your Immich library, creates a v2 project, and writes an ordered timeline to `project.json` — running entirely on the Mac Mini via Ollama.

This is Phase 1 of the local-LLM track (PRD `IMP-015`). Video assembly is deferred; the agent gets you to a reviewed timeline, which you then open in the Selection UI.

- **Design:** `docs/spike/2026-06-06-local-llm-agent-design.md`
- **Options spike:** `docs/spike/2026-04-27-local-llm-agent-options.md`
- **Plan:** `docs/superpowers/plans/2026-06-06-local-llm-agent-phase1.md`
- **Environment gotchas (read first):** `SETUP-NOTES.md`

## Architecture

```
You (terminal)
   ↓ natural language
agent.py  ──HTTP──>  Ollama (qwen3:14b, localhost:11434)
   ↓ tool dispatch (registry.py)
tools/  ──>  v2 story-engine functions (search_photos, manage_project)
   ↓
Immich API + project.json
```

The same `tools/` package is also exposed over MCP by `server.py` (for Goose or any MCP client — see "Goose", parked).

## The 5 tools

| Tool | What it does |
|---|---|
| `search_photos` | Search Immich by query/person/date/location → compact records |
| `list_projects` | List existing projects (id, title, state) |
| `create_project` | Create a project, returns `project_id` |
| `get_project` | Read full project state |
| `set_timeline` | Replace the timeline with an ordered list of asset ids |

## Prerequisites

- **Ollama** running with `qwen3:14b` pulled. See `SETUP-NOTES.md` — on this Mac Mini the working setup is the Homebrew **formula** (launchd-managed) plus the **cask's** `llama-server` runner copied in.
- **Python 3.13** at `/opt/homebrew/bin/python3.13` (the default `python3` on this box is broken — see SETUP-NOTES). Deps: `openai`, `mcp`, `requests`, `pytest`.
- **Immich** reachable and the API key at `/Volumes/HomeRAID/immich/api-key.txt`.

Config defaults live in `config.sh` (`OLLAMA_URL`, `OLLAMA_MODEL`, `IMMICH_URL`, `IMMICH_API_KEY_FILE`, `STORIES_DIR`).

## Run the agent (custom loop)

```bash
cd setup/local-agent
source config.sh
/opt/homebrew/bin/python3.13 agent.py 'Find our Miami beach photos, create a project "Miami", put the first 10 on the timeline'
```

Then review the result in the Selection UI at `macmini:3000/project/<id>`.

## Smoke test (go/no-go)

```bash
/opt/homebrew/bin/python3.13 scripts/smoke_test.py
# Expect: PASS: model emits correct tool call
```

## Tests

```bash
cd setup/local-agent
/opt/homebrew/bin/python3.13 -m pytest -q     # 14 tests, no network/Ollama needed
```

## Goose (parked — PRD R083)

`server.py` is an MCP server exposing the 5 tools, ready to plug into [Goose](https://github.com/block/goose) as an alternate runtime. This path is parked: the custom loop (the long-term direction) already works end-to-end. To revisit, see Task 7 in the plan.
