#!/usr/bin/env bats

# T017 + T019: register-library.sh unit tests

SCRIPT="$BATS_TEST_DIRNAME/../../../setup/immich/scripts/register-library.sh"

setup() {
  WORK_DIR="$(mktemp -d)"
  API_KEY_FILE="$WORK_DIR/api-key.txt"
  echo "mock-api-key-secret" > "$API_KEY_FILE"
  chmod 600 "$API_KEY_FILE"

  # Track API calls
  CALLS_FILE="$WORK_DIR/calls.log"

  mkdir -p "$WORK_DIR/bin"
  cat > "$WORK_DIR/bin/curl" <<'MOCK'
#!/usr/bin/env bash
echo "$*" >> "$CALLS_FILE"
ARGS="$*"
if [[ "$ARGS" == *"GET"* && "$ARGS" == *"libraries"* ]]; then
  echo '[]'
  exit 0
elif [[ "$ARGS" == *"POST"* && "$ARGS" == *"libraries"* && "$ARGS" != *"scan"* ]]; then
  echo '{"id":"lib-123","importPaths":["/usr/src/app/icloud-export"]}'
  exit 0
elif [[ "$ARGS" == *"scan"* ]]; then
  echo '{}'
  exit 0
fi
echo '{}'
exit 0
MOCK
  chmod +x "$WORK_DIR/bin/curl"

  export PATH="$WORK_DIR/bin:$PATH"
  export IMMICH_URL="http://localhost:2283"
  export API_KEY_FILE
  export CALLS_FILE
}

teardown() {
  rm -rf "$WORK_DIR"
}

@test "script exists and is executable" {
  [ -f "$SCRIPT" ]
  [ -x "$SCRIPT" ]
}

@test "reads API key from file" {
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  # curl was called with the API key header
  grep -q "mock-api-key-secret" "$CALLS_FILE"
}

@test "POSTs library with type EXTERNAL" {
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  grep -q "EXTERNAL" "$CALLS_FILE"
}

@test "POSTs library with icloud-export importPaths" {
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  grep -q "icloud-export" "$CALLS_FILE"
}

@test "sets cronExpression for daily scan" {
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  grep -q "cron\|0 0 \* \* \*" "$CALLS_FILE"
}

@test "triggers initial scan after registration" {
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  grep -q "scan" "$CALLS_FILE"
}

@test "is idempotent — skips registration if library already exists" {
  # Mock returns existing library
  cat > "$WORK_DIR/bin/curl" <<'MOCK'
#!/usr/bin/env bash
echo "$*" >> "$CALLS_FILE"
ARGS="$*"
if [[ "$ARGS" == *"GET"* && "$ARGS" == *"libraries"* ]]; then
  echo '[{"id":"lib-existing","importPaths":["/usr/src/app/icloud-export"]}]'
  exit 0
fi
echo '{}'
exit 0
MOCK
  chmod +x "$WORK_DIR/bin/curl"

  run "$SCRIPT"
  [ "$status" -eq 0 ]
  # POST should NOT have been called (library already exists)
  ! grep -q "POST" "$CALLS_FILE"
}

@test "exits 0 when icloud-export mount path is empty directory" {
  EMPTY_DIR="$(mktemp -d)"
  LIBRARY_PATH="$EMPTY_DIR" run "$SCRIPT"
  [ "$status" -eq 0 ]
  rm -rf "$EMPTY_DIR"
}
