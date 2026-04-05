#!/usr/bin/env bats

# T016: external library bind mount tests

COMPOSE_FILE="$BATS_TEST_DIRNAME/../../../setup/immich/docker-compose.yml"

check_service_mounts() {
  local service="$1"
  python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
svc = d['services']['$service']
volumes = svc.get('volumes', [])
for v in volumes:
    if isinstance(v, str) and '/Volumes/HomeRAID/icloud-export' in v and ':ro' in v:
        print('found')
        exit(0)
    elif isinstance(v, dict):
        src = v.get('source', '')
        opts = v.get('read_only', False)
        if '/Volumes/HomeRAID/icloud-export' in src and opts:
            print('found')
            exit(0)
print('not found')
exit(1)
"
}

@test "immich-server has icloud-export bind mount as read-only" {
  run check_service_mounts "immich-server"
  [ "$status" -eq 0 ]
  [ "$output" = "found" ]
}

@test "immich-microservices has icloud-export bind mount as read-only" {
  run check_service_mounts "immich-microservices"
  [ "$status" -eq 0 ]
  [ "$output" = "found" ]
}

@test "icloud-export mount target is /usr/src/app/icloud-export" {
  run python3 -c "
import yaml
with open('$COMPOSE_FILE') as f:
    d = yaml.safe_load(f)
for svc_name in ['immich-server', 'immich-microservices']:
    svc = d['services'][svc_name]
    for v in svc.get('volumes', []):
        if isinstance(v, str) and '/Volumes/HomeRAID/icloud-export' in v:
            assert '/usr/src/app/icloud-export' in v, f'Target path wrong in {svc_name}: {v}'
print('ok')
"
  [ "$status" -eq 0 ]
}
