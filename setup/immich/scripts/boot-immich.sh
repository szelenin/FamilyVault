#!/usr/bin/env bash
# Boot-time script: check RAID mount, start Docker Compose, start TCP proxy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/check-raid-mount.sh"

DOCKER=$(command -v docker || echo /usr/local/bin/docker)
cd "$SCRIPT_DIR/.."
"$DOCKER" compose up -d

# Wait for container to get its OrbStack IP, then start TCP proxy
sleep 10
nohup python3 "$SCRIPT_DIR/tcp-proxy.py" >> /tmp/immich-proxy.log 2>&1 &
