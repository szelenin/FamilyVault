# Quickstart — IMP-018 Understanding-Layer Indexer

> Runs on the Mac Mini (`macmini.local`). Use `python3.13` (the default `python3` is broken — see `setup/local-agent/SETUP-NOTES.md`). Ollama must be launchd-managed (`brew services start ollama`).

## 1. One-time setup

```bash
cd setup/understanding
./setup.sh           # pulls qwen3-vl:8b + bge-m3 (Ollama); installs mlx-vlm + MLX model,
                     # scenedetect; ensures ffmpeg; documents gotchas
```

## 2. Verify the environment

```bash
/opt/homebrew/bin/python3.13 index_cli.py doctor --type photo
# OK lines, or a FAIL with the exact fix command. Fails fast — no heavy work until green.
```

## 3. Phase A — index photos (baseline)

```bash
source config.sh
/opt/homebrew/bin/python3.13 index_cli.py run --type photo            # incremental, resumable
/opt/homebrew/bin/python3.13 index_cli.py status                      # counts by status
```

Smoke-check the index (build verification, not the tuned ranker):

```bash
/opt/homebrew/bin/python3.13 index_cli.py search "kids playing in the snow"
/opt/homebrew/bin/python3.13 index_cli.py search "играют в снегу"      # cross-language works
```

Handle assets missing a preview:

```bash
/opt/homebrew/bin/python3.13 index_cli.py report                      # IDs + regeneration steps
# (regenerate previews in Immich, then:)
/opt/homebrew/bin/python3.13 index_cli.py retry --status no_preview
/opt/homebrew/bin/python3.13 index_cli.py run --type photo
```

## 4. Phase B — index videos

```bash
/opt/homebrew/bin/python3.13 index_cli.py doctor --type video
/opt/homebrew/bin/python3.13 index_cli.py run --type video            # MLX-VLM; hybrid sampling
```

## 5. Phase C — large unattended batch (automatic memory governance)

```bash
# default (--memory auto): governor frees RAM only when low, restores after
/opt/homebrew/bin/python3.13 index_cli.py run --type all
# overnight, reclaim max RAM up front:
/opt/homebrew/bin/python3.13 index_cli.py run --type all --memory force
```

## 6. Tests

```bash
cd /Users/szelenin/projects/FamilyVault-AI
/opt/homebrew/bin/python3.13 -m pytest tests/understanding/unit -q              # fast, no network
/opt/homebrew/bin/python3.13 -m pytest tests/understanding/integration -q       # live Immich/Ollama/ffmpeg/MLX (opt-in)
/opt/homebrew/bin/python3.13 -m pytest tests/understanding/e2e -q               # fixture → index → search
```

## Acceptance smoke (maps to spec)

- Photo of a child at a piano → `search "playing piano"` returns it (SC-002 smoke).
- Cross-language query returns the English-described asset (SC-003 smoke).
- Re-run with no changes → `status` shows 0 newly processed (SC-005).
- Interrupt mid-run, re-run → completed assets skipped (SC-006).
- `doctor` with a missing component → stops in ~seconds with the fix (SC-010).
