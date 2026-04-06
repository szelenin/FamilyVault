#!/usr/bin/env python3
"""
assemble-video.py — Download assets and assemble MP4 via FFmpeg.

Usage:
  python3 assemble-video.py SCENARIO_ID [--dry-run] [--progress]

Exit codes:
  0 — video generated successfully
  2 — scenario not found
  3 — precondition error (wrong state, missing files, FFmpeg unavailable)
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from typing import List, Optional

import requests


# ---------------------------------------------------------------------------
# Math helpers (testable, no I/O)
# ---------------------------------------------------------------------------

def xfade_offset(durations: List[float], fade: float) -> List[float]:
    """
    Compute xfade offset for each transition between N items.
    Returns N-1 offsets.

    offset[i] = sum(durations[0..i]) - fade * (i+1)
    """
    offsets = []
    cumulative = 0.0
    for i, dur in enumerate(durations[:-1]):
        cumulative += dur
        offsets.append(cumulative - fade * (i + 1))
    return offsets


def total_duration(durations: List[float], fade: float) -> float:
    """Total video duration = sum(durations) - fade * (n-1)."""
    n = len(durations)
    if n == 0:
        return 0.0
    return sum(durations) - fade * (n - 1)


def scale_pad_filter(resolution: str) -> str:
    """
    Return FFmpeg filter string to scale and pad to target resolution.
    E.g. '1920:1080' → 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2'
    """
    w, h = resolution.split(":")
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )


def audio_fade_filter(total_dur: float, fade_dur: float) -> str:
    """
    Return FFmpeg audio filter that trims to total_dur and fades out in the last fade_dur seconds.
    """
    fade_start = total_dur - fade_dur
    return f"atrim=0:{total_dur},asetpts=PTS-STARTPTS,afade=t=out:st={fade_start:.3f}:d={fade_dur:.3f}"


def build_filter_complex(
    n_inputs: int,
    durations: List[float],
    fade: float,
    resolution: str,
    transition: str,
    has_audio: bool,
) -> str:
    """Build FFmpeg filter_complex string for image slideshow with optional audio."""
    parts = []

    # Loop each still image to its required duration, then scale/pad
    for i in range(n_inputs):
        dur = durations[i]
        parts.append(
            f"[{i}:v]loop=loop=-1:size=1:start=0,"
            f"trim=duration={dur:.3f},setpts=PTS-STARTPTS,"
            f"{scale_pad_filter(resolution)},fps=25[v{i}]"
        )

    if n_inputs == 1:
        parts.append(f"[v0]null[vout]")
    else:
        offsets = xfade_offset(durations, fade)
        # Chain xfade transitions
        prev = "v0"
        for i in range(n_inputs - 1):
            out = "vout" if i == n_inputs - 2 else f"xf{i}"
            offset = offsets[i]
            parts.append(
                f"[{prev}][v{i+1}]xfade=transition={transition}:"
                f"duration={fade:.3f}:offset={offset:.3f}[{out}]"
            )
            prev = out

    if has_audio:
        total = total_duration(durations, fade)
        audio_f = audio_fade_filter(total, fade)
        parts.append(f"[{n_inputs}:a]{audio_f}[aout]")

    return ";".join(parts)


# ---------------------------------------------------------------------------
# HEIC detection and conversion
# ---------------------------------------------------------------------------

def detect_heic(mime_type: str) -> bool:
    """Return True if the mime type is HEIC/HEIF."""
    return mime_type.lower() in ("image/heic", "image/heif")


def sips_convert_cmd(src: str, dst: str) -> str:
    """Return sips shell command to convert HEIC to JPEG."""
    return f"sips -s format JPEG '{src}' --out '{dst}'"


def make_temp_dir_path(scenario_id: str, base_tmp: str = "/tmp") -> str:
    """Return path for temp directory during assembly."""
    return os.path.join(base_tmp, f"story-engine-{scenario_id}")


# ---------------------------------------------------------------------------
# FFmpeg command builder
# ---------------------------------------------------------------------------

def build_ffmpeg_cmd(
    scenario: dict,
    output_path: str,
    image_duration: int,
    fade_duration: float,
    resolution: str,
    transition: str,
    ffmpeg_bin: str,
) -> List[str]:
    """Build FFmpeg command list for the given scenario."""
    items = scenario["items"]
    n = len(items)
    durations = [float(image_duration)] * n
    music = scenario.get("music")
    has_audio = music is not None and music.get("type") != "none"

    cmd = [ffmpeg_bin, "-y"]

    # Input images — plain -i, duration handled in filter_complex via loop filter
    for item in items:
        local_path = item.get("_local_path", item.get("asset_id"))
        cmd += ["-i", local_path]

    # Audio input
    if has_audio:
        cmd += ["-i", music["path"]]

    # Filter complex
    fc = build_filter_complex(
        n_inputs=n,
        durations=durations,
        fade=fade_duration,
        resolution=resolution,
        transition=transition,
        has_audio=has_audio,
    )
    cmd += ["-filter_complex", fc]

    # Map outputs
    cmd += ["-map", "[vout]"]
    if has_audio:
        cmd += ["-map", "[aout]"]

    # Codec settings
    cmd += [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-t", str(total_duration(durations, fade_duration)),
    ]
    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "128k"]

    cmd.append(output_path)
    return cmd


# ---------------------------------------------------------------------------
# Asset download
# ---------------------------------------------------------------------------

def download_asset(
    session: requests.Session,
    immich_url: str,
    asset_id: str,
    dest_path: str,
) -> None:
    """Download original asset from Immich to dest_path."""
    url = f"{immich_url}/api/assets/{asset_id}/original"
    resp = session.get(url, stream=True)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)


# ---------------------------------------------------------------------------
# Main assembly pipeline
# ---------------------------------------------------------------------------

def assemble(
    scenario_id: str,
    stories_dir: str,
    immich_url: str,
    api_key_file: str,
    ffmpeg_bin: str,
    image_duration: int,
    fade_duration: float,
    resolution: str,
    transition: str,
    dry_run: bool = False,
    show_progress: bool = False,
) -> None:
    """Full assembly pipeline: prechecks → download → convert → ffmpeg → cleanup."""
    import importlib.util, pathlib
    _scripts_dir = str(pathlib.Path(__file__).parent)
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    from manage_scenario import show_scenario, set_state, _scenario_path

    # Load scenario
    scenario = show_scenario(scenario_id, stories_dir=stories_dir)

    # Precondition: state must be approved
    if scenario["state"] != "approved":
        print(
            f"ERROR: Scenario state must be 'approved', got '{scenario['state']}'. "
            "Advance state with set-state before assembling.",
            file=sys.stderr,
        )
        sys.exit(3)

    # Precondition: FFmpeg available
    try:
        subprocess.run([ffmpeg_bin, "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"ERROR: FFmpeg not found at '{ffmpeg_bin}'.", file=sys.stderr)
        sys.exit(3)

    items = scenario["items"]
    if not items:
        print("ERROR: Scenario has no items.", file=sys.stderr)
        sys.exit(3)

    scenario_dir = os.path.join(stories_dir, scenario_id)
    output_path = os.path.join(scenario_dir, "output.mp4")
    log_path = os.path.join(scenario_dir, "ffmpeg.log")
    tmp_dir = make_temp_dir_path(scenario_id)

    if dry_run:
        # Build command and print, no execution
        for item in items:
            item["_local_path"] = f"{tmp_dir}/{item['asset_id']}.jpg"
        cmd = build_ffmpeg_cmd(
            scenario=scenario,
            output_path=output_path,
            image_duration=image_duration,
            fade_duration=fade_duration,
            resolution=resolution,
            transition=transition,
            ffmpeg_bin=ffmpeg_bin,
        )
        print("DRY RUN — FFmpeg command:")
        print(" ".join(cmd))
        return

    # Download and convert assets
    from search_photos import get_api_key, make_session as _make_session

    api_key = get_api_key(api_key_file)
    session = requests.Session()
    session.headers.update({"x-api-key": api_key})

    os.makedirs(tmp_dir, exist_ok=True)
    try:
        for item in items:
            asset_id = item["asset_id"]
            # Determine extension from original filename or default to jpg
            ext = "jpg"
            raw_path = os.path.join(tmp_dir, f"{asset_id}.orig")
            download_asset(session, immich_url, asset_id, raw_path)

            # Detect HEIC and convert
            mime = item.get("mime_type", "image/jpeg")
            if detect_heic(mime):
                jpg_path = os.path.join(tmp_dir, f"{asset_id}.jpg")
                cmd_str = sips_convert_cmd(raw_path, jpg_path)
                subprocess.run(cmd_str, shell=True, check=True)
                item["_local_path"] = jpg_path
            else:
                final_path = os.path.join(tmp_dir, f"{asset_id}.{ext}")
                os.rename(raw_path, final_path)
                item["_local_path"] = final_path

        # Build and run FFmpeg
        cmd = build_ffmpeg_cmd(
            scenario=scenario,
            output_path=output_path,
            image_duration=image_duration,
            fade_duration=fade_duration,
            resolution=resolution,
            transition=transition,
            ffmpeg_bin=ffmpeg_bin,
        )
        if show_progress:
            print(f"Running: {' '.join(cmd)}")

        with open(log_path, "w") as log_f:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            log_f.write(result.stdout)

        if result.returncode != 0:
            print(f"ERROR: FFmpeg failed. See log: {log_path}", file=sys.stderr)
            sys.exit(3)

        # Advance state to generated
        set_state(scenario_id, "generated", stories_dir=stories_dir)

        # Report
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Video generated: {output_path}")
        print(f"Size: {size_mb:.1f} MB")

    finally:
        # Cleanup temp dir
        import shutil
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Assemble video from scenario")
    parser.add_argument("scenario_id")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print FFmpeg command without executing")
    parser.add_argument("--progress", action="store_true",
                        help="Show progress during assembly")
    args = parser.parse_args()

    stories_dir = os.environ.get("STORIES_DIR", "/Volumes/HomeRAID/stories")
    immich_url = os.environ.get("IMMICH_URL", "http://immich-immich-server-1.orb.local")
    api_key_file = os.environ.get("IMMICH_API_KEY_FILE", "/Volumes/HomeRAID/immich/api-key.txt")
    ffmpeg_bin = os.environ.get("FFMPEG_BIN", "ffmpeg")
    image_duration = int(os.environ.get("IMAGE_DURATION", "4"))
    fade_duration = float(os.environ.get("FADE_DURATION", "1"))
    resolution = os.environ.get("OUTPUT_RESOLUTION", "1920:1080")
    transition = os.environ.get("TRANSITION", "fade")

    assemble(
        scenario_id=args.scenario_id,
        stories_dir=stories_dir,
        immich_url=immich_url,
        api_key_file=api_key_file,
        ffmpeg_bin=ffmpeg_bin,
        image_duration=image_duration,
        fade_duration=fade_duration,
        resolution=resolution,
        transition=transition,
        dry_run=args.dry_run,
        show_progress=args.progress,
    )


if __name__ == "__main__":
    main()
