#!/usr/bin/env bash
# Story Engine configuration defaults.
# Source this file or set env vars to override.

: "${IMMICH_URL:=http://immich-immich-server-1.orb.local}"
: "${IMMICH_API_KEY_FILE:=/Volumes/HomeRAID/immich/api-key.txt}"
: "${STORIES_DIR:=/Volumes/HomeRAID/stories}"
: "${FFMPEG_BIN:=ffmpeg}"
: "${IMAGE_DURATION:=4}"
: "${FADE_DURATION:=1}"
: "${OUTPUT_RESOLUTION:=1920:1080}"
: "${TRANSITION:=fade}"

export IMMICH_URL IMMICH_API_KEY_FILE STORIES_DIR FFMPEG_BIN IMAGE_DURATION FADE_DURATION OUTPUT_RESOLUTION TRANSITION
