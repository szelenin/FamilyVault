#!/usr/bin/env bash
set -euo pipefail

IMMICH_URL="${IMMICH_URL:-http://localhost:2283}"
API_KEY_FILE="${API_KEY_FILE:-/Volumes/HomeRAID/immich/api-key.txt}"

API_KEY=$(cat "$API_KEY_FILE")

echo "Verifying machine learning configuration..."

CONFIG=$(curl -sf -H "x-api-key: $API_KEY" "$IMMICH_URL/api/server/config")

ML_ENABLED=$(echo "$CONFIG" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('machineLearning',{}).get('enabled', False))" 2>/dev/null || echo "false")
CLIP_ENABLED=$(echo "$CONFIG" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('machineLearning',{}).get('clip',{}).get('enabled', False))" 2>/dev/null || echo "false")
FACE_ENABLED=$(echo "$CONFIG" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('machineLearning',{}).get('facialRecognition',{}).get('enabled', False))" 2>/dev/null || echo "false")

if [ "$ML_ENABLED" != "True" ] && [ "$ML_ENABLED" != "true" ]; then
  echo "WARNING: Machine learning is disabled in Immich config. Face recognition and semantic search will not work." >&2
fi

if [ "$CLIP_ENABLED" != "True" ] && [ "$CLIP_ENABLED" != "true" ]; then
  echo "WARNING: CLIP semantic search is disabled." >&2
fi

if [ "$FACE_ENABLED" != "True" ] && [ "$FACE_ENABLED" != "true" ]; then
  echo "WARNING: Facial recognition is disabled." >&2
fi

if [ "$ML_ENABLED" = "True" ] || [ "$ML_ENABLED" = "true" ]; then
  echo "Machine learning: enabled"
  echo "CLIP search:      ${CLIP_ENABLED}"
  echo "Face recognition: ${FACE_ENABLED}"
fi
