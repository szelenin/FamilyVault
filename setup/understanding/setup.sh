#!/usr/bin/env bash
# =============================================================================
# FamilyVault Understanding Layer — setup.sh
# =============================================================================
#
# Installs Python dependencies and (optionally) pulls Ollama/MLX models needed
# for the understanding-layer indexer.
#
# Usage:
#   bash setup/understanding/setup.sh [--type photo|video|all]
#
# Operator Workflow:
#   1. bash setup/understanding/setup.sh --type photo|video|all   # install deps
#   2. python3.13 setup/understanding/index_cli.py doctor --type photo   # readiness check
#   3. python3.13 setup/understanding/index_cli.py run --type photo [--limit N]  # index
#   4. python3.13 setup/understanding/index_cli.py status          # counts
#   5. python3.13 setup/understanding/index_cli.py report [--auto-regenerate]   # missing previews
#   6. python3.13 setup/understanding/index_cli.py retry --status no_preview|error  # re-queue
#   7. python3.13 setup/understanding/index_cli.py search "<query>"  # find
# =============================================================================
#
# Idempotent setup for the understanding-layer indexer (IMP-018).
# Pulls the local models and installs Python/system deps. Safe to re-run.
#
# Photo-only runs do NOT need MLX/ffmpeg/scenedetect, so --type photo skips them.
# See setup/local-agent/SETUP-NOTES.md for the python3.13 + Ollama-runner gotchas.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/config.sh"

TYPE="all"
[[ "${1:-}" == "--type" && -n "${2:-}" ]] && TYPE="$2"

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

# --- Ollama models (both photo and video need the embedder) ------------------
say "Ollama models"
if ! command -v ollama >/dev/null 2>&1; then
  echo "FAIL: ollama not found. Install: brew install ollama && ollama serve" >&2
  exit 3
fi
ollama pull "$EMBED_MODEL"                       # bge-m3 (multilingual embeddings)
if [[ "$TYPE" == "photo" || "$TYPE" == "all" ]]; then
  ollama pull "$PHOTO_CAPTION_MODEL"             # qwen3-vl:8b (photo caption+OCR)
fi

# --- Python deps -------------------------------------------------------------
say "Python deps (python3.13)"
"$PYTHON" -m pip install --break-system-packages --upgrade requests psutil

if [[ "$TYPE" == "video" || "$TYPE" == "all" ]]; then
  say "Video deps (MLX-VLM, PySceneDetect, ffmpeg)"
  "$PYTHON" -m pip install --break-system-packages --upgrade mlx-vlm scenedetect
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg not found — installing via brew"; brew install ffmpeg
  fi
  # Warm the MLX model cache so the first real run does not stall on download.
  "$PYTHON" - <<PY || echo "WARN: MLX model warmup skipped (run again to cache)"
from mlx_vlm import load
load("$VIDEO_CAPTION_MODEL")
print("MLX model cached: $VIDEO_CAPTION_MODEL")
PY
fi

# --- Index location ----------------------------------------------------------
say "Index dirs"
mkdir -p "$(dirname "$INDEX_DB")" "$STAGING_DIR" "$INDEX_BACKUP_DIR"

say "Setup complete (type=$TYPE). Next: $PYTHON setup/understanding/index_cli.py status"

echo ""
echo "=== Setup complete. Operator workflow ==="
echo "  1. index_cli.py doctor --type photo|video   # readiness"
echo "  2. index_cli.py run --type photo|video       # index"
echo "  3. index_cli.py status                       # counts"
echo "  4. index_cli.py report [--auto-regenerate]   # missing previews"
echo "  5. index_cli.py retry --status no_preview    # re-queue"
echo "  6. index_cli.py search \"<query>\"             # find"
