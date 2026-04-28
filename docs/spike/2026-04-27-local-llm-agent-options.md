# Local LLM Agent Options — Spike

**Date:** 2026-04-27  
**Branch:** `015-local-llm-spike`  
**Context:** FamilyVault currently uses Claude Code + Claude API as the AI orchestrator. This spike evaluates 4 approaches for replacing or augmenting that with a locally hosted LLM — motivated by learning-by-doing, with a potential future product path.

**Target hardware:** Mac Mini (Apple Silicon M-series, 16GB RAM assumed)  
**Existing stack:** Python 3.13, TypeScript/SvelteKit, FFmpeg, Immich REST API, `project.json` shared state

---

## Recommended Local Models (all options)

| Model | RAM needed | Tool calling | Notes |
|---|---|---|---|
| `qwen3:14b` | ~9 GB | Reliable | Best overall for M-series 16GB. Use `think=false`. |
| `qwen2.5:14b` | ~9 GB | Reliable | Solid alternative |
| `qwen2.5:32b` | ~20 GB | Very reliable | Needs 32GB Mac |
| `llama3.1:8b` | ~5.5 GB | Unreliable | Dev/prototyping only |
| `llama3.3:70b` | ~40 GB | Excellent | Needs 64GB+ Mac |

Ollama gained MLX backend support (Apple Silicon) in late 2025 — up to 93% faster decode. Use `ollama pull qwen3:14b` to get started.

---

## Option A — Build from Scratch

### What it is

A custom Python agent loop: `while True` → send messages to LLM API → check response for `tool_calls` → execute tool locally → append result to history → repeat until plain text answer or iteration cap.

Ollama exposes an OpenAI-compatible endpoint at `http://localhost:11434/v1`. Switching from Anthropic SDK to `openai` SDK pointed at Ollama is a one-line change (`base_url`, `api_key="ollama"`). Every FamilyVault script becomes a tool with a thin JSON-returning wrapper.

The minimal loop is ~60–80 lines of Python before tool definitions. This is how Aider, Goose, and Claude Code are built internally.

### Pros
- Zero framework lock-in
- Full control over context window, retry logic, context budget
- Direct Ollama compatibility — one-line swap from Claude API
- Existing scripts become tools without architectural change
- Minimal dependencies — works in existing Python 3.13 env
- Most consistent with FamilyVault's "AI as orchestrator" design philosophy

### Cons
- You own everything: context overflow, retry logic, token budgeting, parallel tool calls, streaming
- No built-in state persistence — crashes lose progress unless you add checkpointing
- Local model quality gap is real for complex multi-step reasoning (Qwen 3 14B ≈ 70–80% of Claude on well-defined tasks, more like 50–60% on complex creative/reasoning tasks)

### Development Effort

**Low–Medium | 2–3 weeks solo**

| Week | Work |
|---|---|
| 1 | Core loop, tool registration, Ollama integration, port 3 existing scripts as tools |
| 2 | Context management, error handling, streaming output, conversation history persistence |
| 3 | Testing with local models, tuning prompts for non-Claude behavior |

### Key reusable tools
- `openai` Python SDK (OpenAI-compatible endpoint for Ollama) — already available
- `ollama` Python SDK (v0.4+) — simpler for non-compat usage
- Aider's tool loop (`aider/coders/base_coder.py`, MIT) — reference implementation
- Anthropic's [tool-use agent tutorial](https://platform.claude.com/docs/en/agents-and-tools/tool-use/build-a-tool-using-agent)

---

## Option B — Agent Framework (LangGraph / LlamaIndex / CrewAI)

### What it is

Frameworks provide structured agent loop, tools, memory, and multi-agent orchestration.

- **LangGraph** (v1.0.6): Models agent as a directed graph. State flows between typed nodes. Built-in SQLite/Postgres checkpointers. Best framework for multi-step sequential pipelines.
- **LlamaIndex Workflows** (v0.12+): Event-driven, async-first. Lower overhead (~6ms vs LangGraph's ~14ms). Better for RAG-heavy pipelines.
- **CrewAI** (v0.80+): Role-based multi-agent. Uses LiteLLM under the hood (`ollama/model-name` prefix). 1.3M+ PyPI installs/month.

**Best fit for FamilyVault:** LangGraph — graph nodes map naturally to story pipeline stages (search → score → assemble → review → render), and state persistence means a crashed export resumes.

### Pros
- LangGraph graph nodes map naturally to FamilyVault's pipeline stages
- Built-in checkpointing — interrupted exports resume automatically
- LangGraph's `ToolNode` handles multi-tool-call responses automatically
- Large community, extensive Ollama tutorials

### Cons
- Abstraction tax: learn LangChain's object model (Runnables, MessageState, ToolNode, ChatOllama) before any domain work
- Version churn historically — LangGraph v1 (late 2025) is stable but the ecosystem is large
- Over-engineered for current scope: FamilyVault is single-user, single-agent
- CrewAI has documented tool-calling failures with local Ollama models (community forum threads, late 2025) — tuned for GPT-4-class models

### Development Effort

**Medium | 3–5 weeks solo**

| Week | Work |
|---|---|
| 1 | Learn LangGraph graph model, set up Ollama integration |
| 2 | Port FamilyVault tools as LangGraph tools, wire up graph |
| 3–5 | Tuning prompt behavior for local models, testing full pipeline |

### Key reusable tools
- `langchain-ollama` — official LangChain Ollama integration
- `langgraph` v1.0.6 — SQLite checkpointer included
- `llama-index-llms-ollama` — LlamaIndex Ollama adapter
- [LangGraph + MCP + Ollama integration](https://dasroot.net/posts/2026/01/integrating-langgraph-mcp-ollama-agentic-ai/) (dasroot.net, Jan 2026)

---

## Option C — Open WebUI + Ollama

### What it is

Open WebUI is a self-hosted chat interface (like a local ChatGPT) deployed as a Docker container, connected to Ollama. Three extensibility tiers:

1. **Tools (in-process Python)**: Pure Python functions with docstrings as tool schemas. Can call subprocess → existing FamilyVault scripts.
2. **Pipelines (external worker)**: Separate Docker container for heavy pre/post-processing.
3. **MCP servers (HTTP)**: Native MCP support added mid-2025. `mcpo` proxy translates stdio MCP servers to OpenAPI.

User chats; model calls tools; tools run Python; results display in chat. No separate CLI.

### Pros
- Zero UI work — chat, file attachments, image display, conversation history all pre-built
- Model switching (Claude API ↔ local Ollama) is a settings-page toggle — useful for testing the quality gap
- MCP-compatible: existing scripts can be wrapped as MCP server and connected via `mcpo`
- 75k+ GitHub stars, weekly releases, backed by Open WebUI Inc.
- [15+ community tools](https://github.com/Haervwe/open-webui-tools) as reference implementations

### Cons
- Chat-first UX doesn't fit FamilyVault's visual workflow — Selection UI and Timeline Review are still needed alongside it
- In-process tools have dependency conflicts — the robust path (external MCP server) adds infrastructure anyway
- Native Agentic Mode has documented event emitter gaps — streaming status during long FFmpeg renders doesn't work correctly (as of early 2026)
- You don't own the conversation loop — working around framework limits instead of writing clean code
- Memory pressure: Ollama + Open WebUI + Immich (PostgreSQL + Redis + microservices) on 16GB RAM is tight

### Development Effort

**Low initial → Medium customization | 1 week setup + 2–3 weeks tools**

| Time | Work |
|---|---|
| Days 1–2 | Install Open WebUI + Ollama, connect to Immich |
| Week 1 | Write Python tools for key FamilyVault operations |
| Weeks 2–3 | Build MCP server, connect via `mcpo`, test full workflow |
| Ongoing | Working around Open WebUI limits |

### Key reusable tools
- [`open-webui/open-webui`](https://github.com/open-webui/open-webui) (Docker)
- [`open-webui/mcpo`](https://github.com/open-webui/mcpo) — MCP-to-OpenAPI proxy
- `mcp` Python package — wrap FamilyVault scripts as MCP server
- [`Haervwe/open-webui-tools`](https://github.com/Haervwe/open-webui-tools) — community tools as reference

---

## Option D — Extend Existing CLI Agent (Goose)

### What it is

Production-grade CLI agents that handle the full agent loop internally. You configure them to use Ollama and point them at the FamilyVault project. **Goose** (Block → Linux Foundation AIDF) is the clear winner for FamilyVault among the candidates — the others are IDE tools:

- **Aider**: Git-centric pair programmer. No bash execution loop. Wrong fit for runtime orchestration.
- **Continue.dev**: VS Code/JetBrains extension. Not suited for headless server automation.
- **Codex CLI**: Coding assistant. Similar to Aider, not a media-pipeline orchestrator.

**Goose** has native MCP support (70+ documented extensions), first-class Ollama integration, reusable "recipes" (saved agent behaviors), and a built-in scheduler.

### Pros
- Production-grade loop already built (retry, context management, tool execution, streaming)
- MCP is the extension mechanism — write a Python MCP server, Goose connects to it
- MCP server work is reusable across Options B, C, and D
- Ollama integration is documented and tested
- Built-in scheduler: FamilyVault daily sync story creation as a scheduled recipe
- Apache 2.0, Linux Foundation governance — long-term stability signal

### Cons
- Local model quality gap is most visible here: complex story reasoning degrades noticeably with 14B models vs Claude
- Constrained by Goose's conversation model — custom multi-turn UI flow (show thumbnails, user picks, agent resumes) fights the framework
- Goose is a separate process, not a Python library — can't be embedded in FamilyVault's code or called programmatically
- Four services on 16GB: Goose + Ollama + MCP server + Immich
- Community is medium-sized and younger than LangChain ecosystem

### Development Effort

**Low–Medium | 1–2 weeks setup + 2–3 weeks MCP server**

| Time | Work |
|---|---|
| Days 1–3 | Install Goose, configure Ollama provider, verify tool calling |
| Week 1–2 | Write MCP server: searchImmich, scorePhotos, assembleTimeline, runFFmpeg, readProjectJson, writeProjectJson |
| Week 3 | Test full story creation, tune prompts for local model behavior |

### Key reusable tools
- [`block/goose`](https://github.com/block/goose) (Apache 2.0)
- `mcp` Python package
- [Goose + Ollama integration docs](https://docs.ollama.com/integrations/goose)
- [MCP server + Ollama + Goose tutorial](https://www.youtube.com/watch?v=Q0X_Kx8a2nY)

---

## Summary Comparison

| Dimension | A: Scratch | B: LangGraph | C: Open WebUI | D: Goose |
|---|---|---|---|---|
| **Development effort** | 2–3 wk | 3–5 wk | 1 wk + 2–3 wk | 1–2 wk + 2–3 wk |
| **Agent loop control** | Full | Full | None | None |
| **Ollama tool calling** | Full | Full | Full (with limits) | Full |
| **Best local model** | qwen3:14b | qwen3:14b | qwen3:14b | qwen3:14b |
| **RAM overhead (extra)** | Minimal | Minimal | +1–2 GB | +200 MB |
| **Custom FamilyVault UI** | Build yourself | Build yourself | Not compatible | Build yourself |
| **MCP reuse** | Optional | Optional | Required | Required |
| **Framework lock-in** | None | LangChain | Open WebUI | Goose |
| **Community** | N/A | Very large | Very large | Medium, growing |
| **Learning value** | Highest | High | Low | Medium |

---

## Recommendation

Given the **learning-by-doing** motivation with a **potential product path**:

1. **Option D (Goose) for fastest prototype** — get the MCP server written (this work is required regardless of which option you eventually choose), connect to Goose + Ollama, validate local model quality in 1–2 weeks. The MCP server investment is fully portable.

2. **Option A (Scratch) as the long-term foundation** — once you understand the quality and latency characteristics of local models, replace the Goose loop with a custom Python loop. This is consistent with FamilyVault's "AI as orchestrator" philosophy and gives you full control as the product vision grows toward the novel AI-directed UI.

3. **Option B (LangGraph)** is worth considering if the pipeline becomes multi-agent (separate search/scoring/assembly agents) — but that complexity doesn't exist yet.

4. **Option C (Open WebUI)** is best as a side tool for testing prompts and exploring models, not as the agent itself.

**Suggested path:** D → A → custom UI  
Write the MCP server once. Use Goose to validate the concept. Graduate to a custom loop when you need the control.
