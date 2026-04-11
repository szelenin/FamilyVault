# Implementation Plan: Assembler Refactor

**Branch**: `009-assembler-refactor` | **Date**: 2026-04-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/009-assembler-refactor/spec.md`

## Summary

Refactor `assemble_video.py` to read v2 `project.json`, handle DNG/RAW files, include video clips with audio, and support AI-driven orientation/resolution config. Remove v1 `manage_scenario.py` dependency. Add resilience (skip failed items).

## Technical Context

**Language/Version**: Python 3.13 (Mac Mini) + Python 3.9 (local tests)
**Primary Dependencies**: FFmpeg 8+ (HEVC decode, xfade, audio mixing), sips (DNG→JPEG), Immich REST API
**Storage**: Project files on `/Volumes/HomeRAID/stories/`
**Testing**: pytest TDD (this is Python code, not AI reasoning)
**Target Platform**: macOS (Mac Mini)
**Project Type**: Refactor of existing CLI script

## Research

### R1: DNG Conversion via sips

**Tested**: `sips -s format jpeg -s formatOptions 100 input.DNG --out output.jpg` — works. Produces valid JPEG (26MB, 8064×6048). The previous crash was because sips defaulted to TIFF output for DNG — explicit `-s format jpeg` fixes it.

### R2: Video Clip Format

**Tested**: Trip videos are HEVC 1920×1080 MOV files. FFmpeg 8 decodes HEVC natively. The `build_filter_complex()` already supports `input_types=["VIDEO"]` — just needs wiring in the assembler.

### R3: Assembly Config in project.json

**Decision**: Add `assembly_config` field to project.json:
```json
{
  "assembly_config": {
    "orientation": "portrait",
    "resolution": "1080x1920",
    "crf": 18,
    "fps": 30,
    "padding": "blur"
  }
}
```
The AI writes this via `set_assembly_config()`. The assembler reads it. Default: portrait 1080×1920, CRF 18, 30fps, black padding.

### R4: Video Audio Handling

**Decision**: For mixed photo+video timelines:
- Video clips keep their original audio
- Photo segments are silent
- During crossfade transitions between video→photo, audio fades out over the transition duration
- During photo→video transitions, audio fades in
- FFmpeg `amix` or `anull` filters handle this

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First | PASS | TDD for assembler code |
| II. Three-Layer Pyramid | PASS | Unit tests for new functions, integration test with FFmpeg, E2E with live Immich |
| III. AI-Interaction First | PASS | Assembly config driven by AI via project.json |
| IV. Simplicity / YAGNI | PASS | Refactor existing file, no new abstractions |
| V. Privacy / Local-First | PASS | All local processing |

## Project Structure

### Source Code

```text
setup/story-engine/scripts/
├── assemble_video.py      # MAJOR REFACTOR: v2 project.json, DNG, video clips, orientation
├── manage_project.py      # MODIFY: add set_assembly_config()
└── manage_scenario.py     # DEPRECATE: kept for backward compat until cleanup task

tests/story-engine/
├── unit/
│   └── test_assembly.py   # MODIFY: add v2, DNG, video, orientation tests
└── e2e/
    └── test_full_story_flow.py  # MODIFY: update for v2 project flow

.claude/skills/story-engine/
└── SKILL.md               # MODIFY: add assembly config guidance
```

**Structure Decision**: Refactor in place. No new Python files. `manage_scenario.py` kept until cleanup task confirms nothing depends on it.

## Implementation Steps

### Step 1: Assembly config in project.json
- Add `set_assembly_config()` to manage_project.py
- Add `assembly_config` field to create_project() defaults

### Step 2: Assembler reads v2 project.json
- New `assemble()` entry point that reads project.json instead of scenario.json
- Reads timeline items with type, duration, trim_start, trim_end
- Reads assembly_config for resolution, orientation, padding

### Step 3: DNG/RAW conversion
- Update `sips_convert_cmd()` to handle DNG: explicit `-s format jpeg -s formatOptions 100`
- Detect DNG by extension (.dng, .DNG) or mime type
- Fallback: skip and log warning if conversion fails

### Step 4: Video clip support
- Download VIDEO items as-is (no sips conversion)
- Apply trim via `-ss`/`-to` FFmpeg input flags
- Pass `input_types` to `build_filter_complex()`
- Handle audio: video clips keep audio, photos are silent, crossfade transitions fade audio

### Step 5: Orientation & no-crop
- Read resolution from assembly_config
- `scale_pad_filter()` adapts to any resolution (already parameterized)
- AI determines orientation in SKILL.md, writes to project.json

### Step 6: Resilience
- Wrap each item's download+convert in try/except
- Skip failed items, log warning, continue
- Report skipped items count at the end

### Step 7: Cleanup analysis
- Check what still uses manage_scenario.py
- Check which tests reference v1 format
- Document findings, decide what to delete/migrate
