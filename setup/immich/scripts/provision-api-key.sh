#!/usr/bin/env bash
set -euo pipefail

IMMICH_URL="${IMMICH_URL:-http://localhost:2283}"
API_KEY_FILE="${API_KEY_FILE:-/Volumes/HomeRAID/immich/api-key.txt}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@familyvault.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(openssl rand -base64 16)}"

# Idempotent: skip if API key file already exists
if [ -f "$API_KEY_FILE" ]; then
  echo "API key file already exists at $API_KEY_FILE — skipping provisioning"
  exit 0
fi

echo "Provisioning Immich admin account and API key..."

# Check if admin already initialized
INITIALIZED=$(curl -sf "$IMMICH_URL/api/server/config" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('isInitialized','false'))" 2>/dev/null || echo "false")

if [ "$INITIALIZED" != "True" ] && [ "$INITIALIZED" != "true" ]; then
  echo "Creating admin account ($ADMIN_EMAIL)..."
  curl -sf -X POST "$IMMICH_URL/api/auth/admin-sign-up" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"Admin\",\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
    > /dev/null
fi

echo "Logging in..."
ACCESS_TOKEN=$(curl -sf -X POST "$IMMICH_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

echo "Creating API key..."
SECRET=$(curl -sf -X POST "$IMMICH_URL/api/api-keys" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"familyvault-setup"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['apiKey']['secret'])")

mkdir -p "$(dirname "$API_KEY_FILE")"
echo -n "$SECRET" > "$API_KEY_FILE"
chmod 600 "$API_KEY_FILE"

echo "API key written to $API_KEY_FILE"
