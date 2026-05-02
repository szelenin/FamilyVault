#!/usr/bin/env bash
# Wipe the old RAID Immich tree.
# Destructive — prompts for explicit confirmation before deleting anything.
set -euo pipefail

PATHS=(
  "/Volumes/HomeRAID/immich/upload"
  "/Volumes/HomeRAID/immich/model-cache"
  "/Volumes/HomeRAID/immich/postgres"
  "/Volumes/HomeRAID/immich/api-key.txt"
  "/Volumes/HomeRAID/immich/library-id.txt"
)

echo "About to PERMANENTLY DELETE the following paths:"
for p in "${PATHS[@]}"; do
  if [[ -e "$p" ]]; then
    sz=$(du -sh "$p" 2>/dev/null | cut -f1)
    echo "  - $p ($sz)"
  else
    echo "  - $p (not present, skip)"
  fi
done

# Refuse to run if Immich containers are still up — postgres files would be locked
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qi immich; then
  echo "ERROR: Immich containers are running. Stop them first with 'docker compose -f setup/immich/docker-compose.yml down'." >&2
  exit 2
fi

read -r -p "Type 'WIPE' to confirm deletion: " confirm
if [[ "$confirm" != "WIPE" ]]; then
  echo "Aborted." >&2
  exit 1
fi

for p in "${PATHS[@]}"; do
  if [[ -e "$p" ]]; then
    echo "Removing $p ..."
    rm -rf "$p"
  fi
done

# Remove the now-empty parent if it has nothing left
if [[ -d /Volumes/HomeRAID/immich ]] && [[ -z "$(ls -A /Volumes/HomeRAID/immich 2>/dev/null)" ]]; then
  rmdir /Volumes/HomeRAID/immich
  echo "Removed empty /Volumes/HomeRAID/immich"
fi

echo "Done."
