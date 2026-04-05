#!/usr/bin/env bash
# Boot-time script: check RAID mount, start Docker Compose, start TCP proxy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/check-raid-mount.sh"

DOCKER=$(command -v docker || echo /usr/local/bin/docker)

# Launch OrbStack if not already running
if ! "$DOCKER" info >/dev/null 2>&1; then
    echo "Starting OrbStack..."
    open -a OrbStack
fi

# Wait for OrbStack Docker daemon to be ready
DOCKER_TIMEOUT=${DOCKER_TIMEOUT:-120}
echo "Waiting for Docker daemon (timeout: ${DOCKER_TIMEOUT}s)..."
elapsed=0
until "$DOCKER" info >/dev/null 2>&1; do
    if [ "$elapsed" -ge "$DOCKER_TIMEOUT" ]; then
        echo "ERROR: Docker daemon not ready after ${DOCKER_TIMEOUT}s" >&2
        exit 1
    fi
    echo "  ...waiting (${elapsed}/${DOCKER_TIMEOUT}s)"
    sleep 5
    elapsed=$((elapsed + 5))
done
echo "Docker daemon ready"
cd "$SCRIPT_DIR/.."
"$DOCKER" compose up -d

# Wait for container to get its OrbStack IP, then run TCP proxy in foreground.
# Running in foreground keeps launchd from killing it when this script exits.
sleep 10
PYTHON3=$(command -v python3 || echo /usr/bin/python3)
exec "$PYTHON3" "$SCRIPT_DIR/tcp-proxy.py"
