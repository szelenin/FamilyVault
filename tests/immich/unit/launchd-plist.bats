#!/usr/bin/env bats

# T009: launchd plist unit tests

PLIST="$BATS_TEST_DIRNAME/../../../setup/immich/launchd/com.familyvault.immich.plist"

@test "launchd plist exists" {
  [ -f "$PLIST" ]
}

@test "plist has RunAtLoad true" {
  run python3 -c "
import plistlib
with open('$PLIST', 'rb') as f:
    d = plistlib.load(f)
assert d.get('RunAtLoad') is True, f'RunAtLoad is {d.get(\"RunAtLoad\")!r}, expected True'
"
  [ "$status" -eq 0 ]
}

@test "plist Label is com.familyvault.immich" {
  run python3 -c "
import plistlib
with open('$PLIST', 'rb') as f:
    d = plistlib.load(f)
assert d.get('Label') == 'com.familyvault.immich', f'Label is {d.get(\"Label\")!r}'
"
  [ "$status" -eq 0 ]
}

@test "plist ProgramArguments references check-raid-mount.sh or setup.sh" {
  run python3 -c "
import plistlib
with open('$PLIST', 'rb') as f:
    d = plistlib.load(f)
args = d.get('ProgramArguments', [])
args_str = ' '.join(args)
assert 'check-raid-mount' in args_str or 'setup.sh' in args_str or 'immich' in args_str, \
    f'ProgramArguments does not reference setup script: {args}'
"
  [ "$status" -eq 0 ]
}

@test "plist ProgramArguments references docker compose or setup.sh" {
  run python3 -c "
import plistlib
with open('$PLIST', 'rb') as f:
    d = plistlib.load(f)
args = d.get('ProgramArguments', [])
args_str = ' '.join(args)
assert 'docker' in args_str or 'setup.sh' in args_str, \
    f'ProgramArguments does not reference docker or setup.sh: {args}'
"
  [ "$status" -eq 0 ]
}
