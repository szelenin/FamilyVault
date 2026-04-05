#!/usr/bin/env bats

# T023: ML service configuration tests

COMPOSE_FILE="$BATS_TEST_DIRNAME/../../../setup/immich/docker-compose.yml"

@test "immich-machine-learning service has correct image tag v2.6.3" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
svc = d['services']['immich-machine-learning']
image = svc.get('image', '')
assert 'v2.6.3' in image, f'Expected v2.6.3 in image, got: {image}'
"
  [ "$status" -eq 0 ]
}

@test "immich-machine-learning has model-cache volume at /Volumes/HomeRAID/immich/model-cache" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
svc = d['services']['immich-machine-learning']
found = False
for v in svc.get('volumes', []):
    if isinstance(v, str) and '/Volumes/HomeRAID/immich/model-cache' in v:
        found = True
assert found, 'model-cache volume not found'
"
  [ "$status" -eq 0 ]
}

@test "immich-server has MACHINE_LEARNING_URL pointing to immich-machine-learning" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
svc = d['services']['immich-server']
env = svc.get('environment', {})
if isinstance(env, list):
    ml_url = next((e.split('=',1)[1] for e in env if e.startswith('MACHINE_LEARNING_URL=')), None)
else:
    ml_url = env.get('MACHINE_LEARNING_URL')
assert ml_url and 'immich-machine-learning' in ml_url, f'MACHINE_LEARNING_URL wrong: {ml_url}'
"
  [ "$status" -eq 0 ]
}

@test "immich-microservices has MACHINE_LEARNING_URL pointing to immich-machine-learning" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
svc = d['services']['immich-microservices']
env = svc.get('environment', {})
if isinstance(env, list):
    ml_url = next((e.split('=',1)[1] for e in env if e.startswith('MACHINE_LEARNING_URL=')), None)
else:
    ml_url = env.get('MACHINE_LEARNING_URL')
assert ml_url and 'immich-machine-learning' in ml_url, f'MACHINE_LEARNING_URL wrong: {ml_url}'
"
  [ "$status" -eq 0 ]
}
