#!/usr/bin/env bash
# Create the new directories for the split-storage Immich layout.
set -euo pipefail

DIRS=(
  "/Users/szelenin/immich-data/upload"
  "/Users/szelenin/immich-data/postgres"
  "/Users/szelenin/immich-data/model-cache"
  "/Volumes/HomeRAID/immich-library"
)

# Fail fast if RAID is not mounted — without this, mkdir -p would silently
# create /Volumes/HomeRAID/immich-library on the boot disk, breaking the
# split-storage layout downstream.
if [[ ! -d /Volumes/HomeRAID ]]; then
  echo "ERROR: /Volumes/HomeRAID is not mounted. Mount the RAID before running this script." >&2
  exit 2
fi

for d in "${DIRS[@]}"; do
  if [[ -d "$d" ]]; then
    echo "Already exists: $d"
  else
    mkdir -p "$d"
    echo "Created: $d"
  fi
done

# Postgres expects a specific directory permission scheme
chmod 700 /Users/szelenin/immich-data/postgres

echo "All directories ready."
ls -ld "${DIRS[@]}"
