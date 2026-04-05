#!/usr/bin/env bats

# T007: check-raid-mount.sh unit tests

SCRIPT="$BATS_TEST_DIRNAME/../../../setup/immich/scripts/check-raid-mount.sh"

setup() {
  FAKE_MOUNT="$(mktemp -d)"
  MISSING_MOUNT="/tmp/nonexistent-raid-$$"
}

teardown() {
  rm -rf "$FAKE_MOUNT"
}

@test "script exists and is executable" {
  [ -f "$SCRIPT" ]
  [ -x "$SCRIPT" ]
}

@test "returns 0 when mount path exists" {
  RAID_PATH="$FAKE_MOUNT" RAID_TIMEOUT=5 run "$SCRIPT"
  [ "$status" -eq 0 ]
}

@test "returns 1 when mount path does not exist after timeout" {
  RAID_PATH="$MISSING_MOUNT" RAID_TIMEOUT=3 RAID_POLL_INTERVAL=1 run "$SCRIPT"
  [ "$status" -eq 1 ]
}

@test "logs error message on timeout" {
  RAID_PATH="$MISSING_MOUNT" RAID_TIMEOUT=3 RAID_POLL_INTERVAL=1 run "$SCRIPT"
  [[ "$output" == *"ERROR"* ]] || [[ "$output" == *"not mounted"* ]] || [[ "$output" == *"timed out"* ]]
}

@test "logs progress message while waiting" {
  RAID_PATH="$MISSING_MOUNT" RAID_TIMEOUT=3 RAID_POLL_INTERVAL=1 run "$SCRIPT"
  [[ "$output" == *"Waiting"* ]] || [[ "$output" == *"waiting"* ]] || [[ "$output" == *"mount"* ]]
}
