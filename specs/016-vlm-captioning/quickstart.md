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

### Acceptance results (2026-06-20, Mac Mini, live Immich + Ollama)

Ran end-to-end on the real Mac Mini (24 GB) against live services. Index already held ~195K discovered assets.

- **doctor --type photo** → all green (immich/sqlite/disk/ollama). Confirms the Ollama tag-normalization fix (`bge-m3:latest` ↔ `bge-m3`).
- **run --type photo --limit 5** → 5 photos captioned (done 10→15), 0 errors, 0 no_preview, ~67s/photo. Captions are rich and each row carries a 4096-byte bge-m3 embedding.
- **SC-002 (EN search)** `"family selfie on a balcony"` → correct asset ranks #1 (0.832) with FTS highlighting. PASS.
- **SC-003 (cross-language)** `"семья на балконе у моря"` (Russian, no shared tokens) → the English-described family-on-balcony photos rank top (0.758) via bge-m3 multilingual embedding. PASS.
- **SC-005 (idempotent)** `plan()` over the index returns 0 overlap with already-`done` assets — done assets are never re-selected. PASS.
- **SC-010 (fail-fast)** `doctor` with Ollama unreachable → fails in **3.09s** (< 5s) with the exact `ollama serve` remediation. PASS.
- **SC-007/008 (governor)** On this 24 GB box the photo phase's need exceeded free RAM with Immich running, so the governor escalated (stopped Immich + OrbStack) during the chunk caption-pass and **restored both on normal completion** (doctor green afterward). PASS for normal/SIGINT/SIGTERM/exception exits (restore is in a `finally`).
  - **SIGTERM recovery verified live:** `run --type photo --memory force` (deterministically stops Immich + OrbStack) → `kill -TERM` mid-run → handler converts SIGTERM to a clean unwind → `finally` restored OrbStack + Immich, printed `Interrupted — services restored; re-run to resume.`, exit 130; docker daemon + Immich ping 200 + `doctor` green afterward. PASS.
  - **Remaining caveat:** only `kill -9` (SIGKILL) is unrecoverable (cannot be trapped); the stack is restored by the next run between chunks. Manual recovery if ever needed: `orb start && docker start $(docker ps -aq --filter name=immich)`.
