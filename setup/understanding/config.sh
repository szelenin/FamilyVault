#!/usr/bin/env bash
# Configuration for the understanding-layer indexer (IMP-018).
# Sourced by setup.sh and read (via env) by index_cli.py. Override any value by
# exporting it before invoking, e.g.  INDEX_DB=/tmp/test.db ./index_cli.py ...

# --- Index storage -----------------------------------------------------------
: "${INDEX_DB:=$HOME/.familyvault/index/familyvault.db}"   # native SSD, WAL
: "${INDEX_BACKUP_DIR:=/Volumes/HomeRAID/familyvault-index-backup}"

# --- Immich source -----------------------------------------------------------
: "${IMMICH_URL:=http://localhost:2283}"
: "${IMMICH_API_KEY_FILE:=/Volumes/HomeRAID/immich/api-key.txt}"   # provisioned by setup/immich

# --- Staging (bounded scratch space on SSD) ----------------------------------
: "${STAGING_DIR:=$HOME/.familyvault/staging}"
: "${STAGING_BUDGET:=10G}"          # hard cap; chunk size derives from this

# --- Memory governor ---------------------------------------------------------
: "${MEMORY_POLICY:=auto}"          # auto | force | never

# --- Model runtimes ----------------------------------------------------------
: "${OLLAMA_URL:=http://localhost:11434}"
: "${PHOTO_CAPTION_MODEL:=qwen3-vl:8b}"
: "${EMBED_MODEL:=bge-m3}"
: "${VIDEO_CAPTION_MODEL:=mlx-community/Qwen3-VL-8B-Instruct-4bit}"
: "${OLLAMA_NUM_CTX:=8192}"         # photo VLM context window (image ~2.8K + reasoning + answer; 4K is too small)

# --- Frame sampling caps (video) ---------------------------------------------
: "${FRAME_MIN:=3}"                 # minimum frames per clip
: "${FRAME_MAX:=20}"                # per-pass frame budget (map-reduce beyond this)
: "${FRAMES_PER_SCENE:=2}"          # scene-detect frames per detected scene

# --- Discovery (incremental) -------------------------------------------------
: "${DISCOVERY_PENDING_FLOOR:=50}"  # skip the Immich scan when >= this many pending (no --limit)

# --- Interpreter -------------------------------------------------------------
: "${PYTHON:=/opt/homebrew/bin/python3.13}"

export INDEX_DB INDEX_BACKUP_DIR IMMICH_URL IMMICH_API_KEY_FILE \
       STAGING_DIR STAGING_BUDGET MEMORY_POLICY OLLAMA_URL \
       PHOTO_CAPTION_MODEL EMBED_MODEL VIDEO_CAPTION_MODEL OLLAMA_NUM_CTX \
       FRAME_MIN FRAME_MAX FRAMES_PER_SCENE DISCOVERY_PENDING_FLOOR PYTHON
