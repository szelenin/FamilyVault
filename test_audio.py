import sys, json, os, subprocess, requests
sys.path.insert(0, "setup/story-engine")
from scripts.assemble_video import build_ffmpeg_cmd_v2, detect_format, sips_convert_cmd, make_temp_dir_path

IMMICH_URL = "http://localhost:2283"
STORIES_DIR = "/Volumes/HomeRAID/stories"
FFMPEG_BIN = "/opt/homebrew/bin/ffmpeg"
project_id = "2026-04-11-miami-trip-last-visit"

project = json.load(open("{}/{}/project.json".format(STORIES_DIR, project_id)))
timeline = project["timeline"]
key = open("/Volumes/HomeRAID/immich/api-key.txt").read().strip()
headers = {"x-api-key": key}

tmp_dir = make_temp_dir_path(project_id)
os.makedirs(tmp_dir, exist_ok=True)

local_paths = {}
skipped = 0
for i, item in enumerate(timeline):
    aid = item["asset_id"]
    try:
        resp = requests.get("{}/api/assets/{}".format(IMMICH_URL, aid), headers=headers, timeout=10)
        asset = resp.json()
        fname = asset.get("originalFileName", "unknown")
        mime = asset.get("originalMimeType", "")
        fmt = detect_format(fname, mime)
        
        resp = requests.get("{}/api/assets/{}/original".format(IMMICH_URL, aid), headers=headers, timeout=30)
        raw_path = os.path.join(tmp_dir, "{}.{}".format(aid, fname.rsplit(".", 1)[-1]))
        with open(raw_path, "wb") as f:
            f.write(resp.content)
        
        if fmt == "video":
            local_paths[aid] = raw_path
        elif fmt in ("heic", "dng"):
            jpg_path = os.path.join(tmp_dir, "{}.jpg".format(aid))
            cmd = sips_convert_cmd(raw_path, jpg_path)
            result = subprocess.run(cmd, shell=True, capture_output=True)
            if result.returncode == 0 and os.path.getsize(jpg_path) > 100:
                local_paths[aid] = jpg_path
            else:
                skipped += 1
        else:
            local_paths[aid] = raw_path
    except Exception as e:
        skipped += 1

print("Ready: {}, Skipped: {}".format(len(local_paths), skipped))

valid_timeline = [item for item in timeline if item["asset_id"] in local_paths]
project_copy = dict(project)
project_copy["timeline"] = valid_timeline

output_path = "{}/{}/output_v3_audio.mp4".format(STORIES_DIR, project_id)
cmd = build_ffmpeg_cmd_v2(project_copy, output_path, local_paths, FFMPEG_BIN)

# Check if audio is in the command
has_aout = "[aout]" in " ".join(cmd)
print("Audio enabled: {}".format(has_aout))

result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
if result.returncode == 0:
    size = os.path.getsize(output_path)
    print("SUCCESS: {:.1f} MB".format(size/1024/1024))
else:
    print("FAILED")
    print(result.stderr[-300:] if result.stderr else "")
