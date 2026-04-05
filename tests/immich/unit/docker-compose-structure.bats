#!/usr/bin/env bats

# T003: docker-compose.yml structure tests
# Must FAIL before T004 creates docker-compose.yml

COMPOSE_FILE="$BATS_TEST_DIRNAME/../../../setup/immich/docker-compose.yml"

setup() {
  if ! command -v python3 &>/dev/null && ! command -v yq &>/dev/null; then
    skip "python3 or yq required to parse YAML"
  fi
}

parse_services() {
  python3 -c "
import sys, re
content = open('$COMPOSE_FILE').read()
import json, subprocess
result = subprocess.run(['python3', '-c', '''
import yaml, json, sys
with open(sys.argv[1]) as f:
    d = yaml.safe_load(f)
print(json.dumps(list(d.get(\"services\", {}).keys())))
''', '$COMPOSE_FILE'], capture_output=True, text=True)
print(result.stdout.strip())
"
}

@test "docker-compose.yml exists" {
  [ -f "$COMPOSE_FILE" ]
}

@test "docker-compose.yml defines exactly 5 services" {
  run python3 -c "
import yaml, json
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
services = list(d.get('services', {}).keys())
print(json.dumps(services))
assert len(services) == 5, f'Expected 5 services, got {len(services)}: {services}'
"
  [ "$status" -eq 0 ]
}

@test "docker-compose.yml includes immich-server service" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
assert 'immich-server' in d['services'], 'immich-server not found'
"
  [ "$status" -eq 0 ]
}

@test "docker-compose.yml includes immich-microservices service" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
assert 'immich-microservices' in d['services'], 'immich-microservices not found'
"
  [ "$status" -eq 0 ]
}

@test "docker-compose.yml includes immich-machine-learning service" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
assert 'immich-machine-learning' in d['services'], 'immich-machine-learning not found'
"
  [ "$status" -eq 0 ]
}

@test "docker-compose.yml includes redis service" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
assert 'redis' in d['services'], 'redis not found'
"
  [ "$status" -eq 0 ]
}

@test "docker-compose.yml includes postgres service" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
assert 'postgres' in d['services'], 'postgres not found'
"
  [ "$status" -eq 0 ]
}

@test "all services use restart: unless-stopped" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
for name, svc in d['services'].items():
    restart = svc.get('restart', '')
    assert restart == 'unless-stopped', f'{name} has restart={restart!r}, expected unless-stopped'
"
  [ "$status" -eq 0 ]
}

@test "volume paths contain /Volumes/HomeRAID/immich" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
top_volumes = d.get('volumes', {})
found = False
for vol_name in top_volumes:
    vol = top_volumes[vol_name]
    if vol and isinstance(vol, dict):
        driver_opts = vol.get('driver_opts', {})
        device = driver_opts.get('device', '')
        if '/Volumes/HomeRAID/immich' in device:
            found = True
# Also check bind mounts in services
for name, svc in d['services'].items():
    for v in svc.get('volumes', []):
        if isinstance(v, str) and '/Volumes/HomeRAID/immich' in v:
            found = True
        elif isinstance(v, dict) and '/Volumes/HomeRAID/immich' in v.get('source', ''):
            found = True
assert found, 'No volume paths contain /Volumes/HomeRAID/immich'
"
  [ "$status" -eq 0 ]
}

@test "immich-server has MACHINE_LEARNING_URL env var" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
svc = d['services']['immich-server']
env = svc.get('environment', {})
if isinstance(env, list):
    keys = [e.split('=')[0] for e in env]
    assert 'MACHINE_LEARNING_URL' in keys, 'MACHINE_LEARNING_URL not in immich-server environment'
else:
    assert 'MACHINE_LEARNING_URL' in env, 'MACHINE_LEARNING_URL not in immich-server environment'
"
  [ "$status" -eq 0 ]
}
