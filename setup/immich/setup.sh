#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMMICH_URL="${IMMICH_URL:-http://localhost:2283}"
export IMMICH_URL
export API_KEY_FILE="${API_KEY_FILE:-/Volumes/HomeRAID/immich/api-key.txt}"

log() { echo "[setup] $*"; }
err() { echo "[setup] ERROR: $*" >&2; exit 1; }

# --- Pre-flight checks ---
log "Running pre-flight checks..."

# Check Docker is available
if ! command -v docker &>/dev/null; then
  err "Docker not found. Install OrbStack (brew install orbstack) or Homebrew Docker, then re-run setup."
fi

# Check port 2283 is free
if lsof -i :2283 &>/dev/null 2>&1; then
  err "Port 2283 is already in use. Check what's running: lsof -i :2283"
fi

# --- RAID mount check ---
log "Checking RAID mount..."
"$SCRIPT_DIR/scripts/check-raid-mount.sh"

# --- Start Docker Compose ---
log "Starting Immich stack..."
cd "$SCRIPT_DIR"
docker compose up -d

# --- Wait for Immich to be healthy ---
log "Waiting for Immich to be healthy..."
HEALTH_TIMEOUT=120
elapsed=0
while [ "$elapsed" -lt "$HEALTH_TIMEOUT" ]; do
  if curl -sf --max-time 2 "$IMMICH_URL/api/server/ping" | grep -q pong; then
    log "Immich is healthy"
    break
  fi
  sleep 5
  elapsed=$(( elapsed + 5 ))
  log "  ...waiting for health ($elapsed/${HEALTH_TIMEOUT}s)"
done

if [ "$elapsed" -ge "$HEALTH_TIMEOUT" ]; then
  err "Immich did not become healthy within ${HEALTH_TIMEOUT}s. Check: docker compose logs"
fi

# --- Provision admin account and API key ---
log "Provisioning API key..."
"$SCRIPT_DIR/scripts/provision-api-key.sh"

# --- Register external library ---
log "Registering icloud-export as external library..."
"$SCRIPT_DIR/scripts/register-library.sh"

# --- Verify ML configuration ---
log "Verifying machine learning configuration..."
"$SCRIPT_DIR/scripts/configure-ml.sh"

# --- Install launchd agent ---
PLIST_SRC="$SCRIPT_DIR/launchd/com.familyvault.immich.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.familyvault.immich.plist"

log "Installing launchd boot agent..."
cp "$PLIST_SRC" "$PLIST_DEST"

# Unload first if already loaded (idempotent)
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

log ""
log "✓ Immich setup complete!"
log ""
log "  Web UI:  http://macmini.local:2283"
log "  API:     http://macmini.local:2283/api"
log "  API key: $API_KEY_FILE"
log ""
log "Next: open http://macmini.local:2283 in your browser to verify."
