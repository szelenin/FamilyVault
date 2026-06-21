# Understanding-Layer Indexer — Operator Guide

## What this is

The understanding-layer indexer (IMP-018) walks every asset in your Immich library, generates a VLM caption and OCR text, and stores a multilingual embedding in a local SQLite hybrid index keyed to Immich asset IDs. Photos are captioned via Ollama (`qwen3-vl:8b`) and embedded via `bge-m3`. Videos are captioned with MLX-VLM (`Qwen3-VL-8B-Instruct-4bit`) and embedded with the same `bge-m3` model. Identity stays in Immich — the VLM describes "a boy at a piano"; Immich knows the name.

---

## Prerequisites / one-time setup

Run on the Mac Mini (`macmini.local`). The default `python3` is broken on this machine — always use `/opt/homebrew/bin/python3.13`. See `setup/local-agent/SETUP-NOTES.md` for the full story.

Ollama must be launchd-managed so it survives between sessions and across memory-governor restarts:

```bash
brew services start ollama
```

Then run the setup script once (safe to re-run). Pass `--type photo`, `--type video`, or `--type all` to limit which models and deps are installed:

```bash
cd setup/understanding
./setup.sh --type all       # pulls qwen3-vl:8b + bge-m3 (Ollama), installs mlx-vlm,
                            # scenedetect, ffmpeg (if absent), warms MLX model cache
```

---

## Verify the environment

Run `doctor` before indexing to catch missing models, missing tools, and bad API keys. It exits immediately with a plain-English fix command on any failure.

```bash
/opt/homebrew/bin/python3.13 index_cli.py doctor --type photo   # photo checks only
/opt/homebrew/bin/python3.13 index_cli.py doctor --type video   # video checks only
/opt/homebrew/bin/python3.13 index_cli.py doctor --type all     # all checks (default)
```

Each line prints `[OK  ]` or `[FAIL] <check>  -> <fix command>`. Fix every `FAIL` before proceeding.

---

## Phased runs

### Phase A — photos (baseline)

```bash
source config.sh
/opt/homebrew/bin/python3.13 index_cli.py run --type photo      # incremental, resumable
/opt/homebrew/bin/python3.13 index_cli.py status                # counts by status
```

### Phase B — videos

```bash
/opt/homebrew/bin/python3.13 index_cli.py doctor --type video
/opt/homebrew/bin/python3.13 index_cli.py run --type video      # MLX-VLM; hybrid frame sampling
```

### Unattended large batch

Run photos and videos in sequence. The memory governor (see below) manages RAM automatically:

```bash
# Default — free RAM only when the system is actually low:
source config.sh
/opt/homebrew/bin/python3.13 index_cli.py run --type photo
/opt/homebrew/bin/python3.13 index_cli.py run --type video

# Overnight — reclaim max RAM up front before captioning each chunk:
/opt/homebrew/bin/python3.13 index_cli.py run --type photo --memory force
/opt/homebrew/bin/python3.13 index_cli.py run --type video --memory force
```

`--memory` accepts `auto` (default), `force`, or `never`. With `never` the governor logs a warning and aborts if RAM is insufficient rather than stopping services.

All runs are incremental and resumable — already-indexed assets are skipped. Use `--full-scan` to force a complete re-list of Immich assets (ignores the discovery watermark).

---

## Inspecting results

### Index counts

```bash
/opt/homebrew/bin/python3.13 index_cli.py status
```

Prints `pending`, `done`, `no_preview`, and `error` counts.

### Search

```bash
/opt/homebrew/bin/python3.13 index_cli.py search "kids playing in the snow"
/opt/homebrew/bin/python3.13 index_cli.py search "играют в снегу"    # cross-language works
```

`bge-m3` is a multilingual model — queries in any language find captions written in English. Add `-k N` to return more than the default 5 results.

### Assets missing a preview

```bash
/opt/homebrew/bin/python3.13 index_cli.py report                    # list IDs + remediation steps
```

After regenerating thumbnails in Immich (Administration → Jobs → Generate Thumbnails → Missing):

```bash
/opt/homebrew/bin/python3.13 index_cli.py retry --status no_preview
/opt/homebrew/bin/python3.13 index_cli.py run --type photo          # or --type video
```

`--auto-regenerate` on `report` will trigger Immich thumbnail regeneration via the API automatically.

`retry` also accepts `--status error` to re-queue failed assets. Both flags are repeatable and default to both statuses when omitted.

---

## Memory governor

The governor monitors available system RAM before each captioning chunk. With ample memory it does nothing. When RAM is low it escalates in order: unload non-required Ollama models → stop Immich → stop OrbStack. After captioning finishes it restores exactly what it stopped, in reverse order, so the system returns to its previous state. Control it with `--memory auto|force|never`: `auto` (default) acts only when needed; `force` always offloads before captioning; `never` skips all offloading and aborts with a clear message if RAM is insufficient.

---

## Running tests

Run from the repository root:

```bash
cd /Users/szelenin/projects/FamilyVault-AI

# Fast unit tests — no network, no models required:
/opt/homebrew/bin/python3.13 -m pytest tests/understanding/unit -q

# Integration tests — requires live Immich, Ollama, ffmpeg, MLX (opt-in):
/opt/homebrew/bin/python3.13 -m pytest tests/understanding/integration -q

# End-to-end: fixture → index → search:
/opt/homebrew/bin/python3.13 -m pytest tests/understanding/e2e -q
```

---

## Key configuration (`config.sh`)

Source `config.sh` before running the CLI to set defaults. Override any variable by exporting it before invoking.

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_NUM_CTX` | `8192` | Photo VLM context window. Must be at least 8192 — an image token-encodes to ~2.8K tokens plus reasoning chain; 4K is too small and produces empty captions. |
| `FAMILYVAULT_DB` | `~/.familyvault/index/familyvault.db` | Path the CLI reads for the SQLite index. Set this env var to override (not `INDEX_DB`, which is the shell-level config.sh variable). |
| `IMMICH_API_KEY_FILE` | `/Volumes/HomeRAID/immich/api-key.txt` | Path to the Immich API key (provisioned by `setup/immich`). Set `IMMICH_API_KEY` env var to bypass the file entirely. |
| `STAGING_BUDGET` | `10G` | Hard cap on the staging scratch directory. Chunk size is derived from this. |

> **`FAMILYVAULT_DB` vs `INDEX_DB`:** `config.sh` sets `INDEX_DB` for shell scripts; `index_cli.py` reads `FAMILYVAULT_DB`. They are separate. To override the DB path for the CLI, export `FAMILYVAULT_DB`.
