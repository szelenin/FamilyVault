#!/usr/bin/env bats

# T008: provision-api-key.sh unit tests

SCRIPT="$BATS_TEST_DIRNAME/../../../setup/immich/scripts/provision-api-key.sh"

setup() {
  WORK_DIR="$(mktemp -d)"
  API_KEY_FILE="$WORK_DIR/api-key.txt"

  # Mock curl to avoid real HTTP calls
  mkdir -p "$WORK_DIR/bin"
  cat > "$WORK_DIR/bin/curl" <<'EOF'
#!/usr/bin/env bash
# Mock curl: detect which endpoint is being called and return fixture data
ARGS="$*"
if [[ "$ARGS" == *"admin-sign-up"* ]]; then
  echo '{"id":"admin-id","email":"admin@familyvault.local"}'
  exit 0
elif [[ "$ARGS" == *"auth/login"* ]]; then
  echo '{"accessToken":"mock-access-token"}'
  exit 0
elif [[ "$ARGS" == *"api-keys"* ]]; then
  echo '{"apiKey":{"secret":"mock-api-key-secret-1234567890"}}'
  exit 0
elif [[ "$ARGS" == *"server/config"* ]]; then
  echo '{"isInitialized":true}'
  exit 0
fi
echo '{}'
exit 0
EOF
  chmod +x "$WORK_DIR/bin/curl"

  export PATH="$WORK_DIR/bin:$PATH"
  export IMMICH_URL="http://localhost:2283"
  export API_KEY_FILE
}

teardown() {
  rm -rf "$WORK_DIR"
}

@test "script exists and is executable" {
  [ -f "$SCRIPT" ]
  [ -x "$SCRIPT" ]
}

@test "writes API key to file" {
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -f "$API_KEY_FILE" ]
}

@test "API key file contains non-empty content" {
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -s "$API_KEY_FILE" ]
}

@test "API key file has permissions 600" {
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  run stat -f "%A" "$API_KEY_FILE"
  [ "$output" = "600" ]
}

@test "is idempotent — skips key creation if file already exists" {
  echo "existing-key" > "$API_KEY_FILE"
  chmod 600 "$API_KEY_FILE"
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  # File content should be unchanged (still the pre-existing key)
  run cat "$API_KEY_FILE"
  [ "$output" = "existing-key" ]
}
