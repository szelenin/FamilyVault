# Local agent config. Reuses story-engine defaults; override via env.
: "${OLLAMA_URL:=http://localhost:11434/v1}"
: "${OLLAMA_MODEL:=qwen3:14b}"
: "${IMMICH_URL:=http://immich-immich-server-1.orb.local}"
: "${IMMICH_API_KEY_FILE:=/Volumes/HomeRAID/immich/api-key.txt}"
: "${STORIES_DIR:=/Volumes/HomeRAID/stories}"
export OLLAMA_URL OLLAMA_MODEL IMMICH_URL IMMICH_API_KEY_FILE STORIES_DIR
