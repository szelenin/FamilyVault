"""Unit tests for assemble-video.py — FFmpeg filter_complex math and helpers."""
import pytest
from unittest.mock import MagicMock, patch


from scripts.assemble_video import (
    xfade_offset,
    total_duration,
    scale_pad_filter,
    audio_fade_filter,
    build_filter_complex,
    detect_heic,
    sips_convert_cmd,
    build_ffmpeg_cmd,
)


# ---------------------------------------------------------------------------
# FFmpeg math tests (T030)
# ---------------------------------------------------------------------------

class TestXfadeOffset:
    def test_xfade_offset_calculation_2_items(self):
        """With 2 items, 1 transition offset = duration[0] - fade."""
        # Item durations [4, 4], fade 1s → offset[0] = 4 - 1 = 3
        offsets = xfade_offset(durations=[4, 4], fade=1.0)
        assert len(offsets) == 1
        assert offsets[0] == pytest.approx(3.0)

    def test_xfade_offset_calculation_5_items(self):
        """With 5 items, 4 transition offsets calculated correctly."""
        durations = [4, 4, 4, 4, 4]
        fade = 1.0
        offsets = xfade_offset(durations=durations, fade=fade)
        assert len(offsets) == 4
        # offset[0] = 4 - 1 = 3
        # offset[1] = (4 + 4) - (2 * 1) = 6
        # offset[2] = (4 + 4 + 4) - (3 * 1) = 9
        # offset[3] = (4 + 4 + 4 + 4) - (4 * 1) = 12
        assert offsets[0] == pytest.approx(3.0)
        assert offsets[1] == pytest.approx(6.0)
        assert offsets[2] == pytest.approx(9.0)
        assert offsets[3] == pytest.approx(12.0)

    def test_xfade_offset_single_item_no_transitions(self):
        """Single item produces no offsets (no transitions needed)."""
        offsets = xfade_offset(durations=[4], fade=1.0)
        assert offsets == []


class TestTotalDuration:
    def test_total_duration_calculation(self):
        """Total duration = sum(durations) - fade * (n-1)."""
        # 5 items × 4s - 1s × 4 transitions = 20 - 4 = 16
        result = total_duration(durations=[4, 4, 4, 4, 4], fade=1.0)
        assert result == pytest.approx(16.0)

    def test_total_duration_single_item(self):
        """Single item: total = duration, no fade deduction."""
        result = total_duration(durations=[4], fade=1.0)
        assert result == pytest.approx(4.0)

    def test_total_duration_varied_durations(self):
        """Mixed durations: sum minus (n-1) fades."""
        result = total_duration(durations=[5, 3, 4], fade=1.0)
        # 5 + 3 + 4 - 2 = 10
        assert result == pytest.approx(10.0)


class TestScalePadFilter:
    def test_scale_pad_filter_string(self):
        """scale_pad_filter returns correct FFmpeg filter for 1920x1080."""
        f = scale_pad_filter(resolution="1920:1080")
        assert "scale" in f
        assert "1920" in f
        assert "1080" in f
        assert "pad" in f

    def test_scale_pad_filter_custom_resolution(self):
        """scale_pad_filter works with custom resolution."""
        f = scale_pad_filter(resolution="1280:720")
        assert "1280" in f
        assert "720" in f


class TestAudioFadeFilter:
    def test_audio_filter_with_fade_out(self):
        """audio_fade_filter includes afade out at correct offset."""
        f = audio_fade_filter(total_dur=16.0, fade_dur=2.0)
        assert "afade" in f
        assert "out" in f
        # fade starts at total_dur - fade_dur = 14.0
        assert "14" in f

    def test_audio_filter_trims_to_total_duration(self):
        """audio_fade_filter trims audio to total video duration."""
        f = audio_fade_filter(total_dur=16.0, fade_dur=2.0)
        assert "atrim" in f or "asetpts" in f or "16" in f


class TestBuildFilterComplex:
    def test_filter_complex_for_images_only(self):
        """filter_complex for 3 image inputs uses xfade transitions."""
        n = 3
        fc = build_filter_complex(
            n_inputs=n,
            durations=[4, 4, 4],
            fade=1.0,
            resolution="1920:1080",
            transition="fade",
            has_audio=False,
        )
        assert "xfade" in fc
        assert "scale" in fc

    def test_filter_complex_for_mixed_inputs(self):
        """filter_complex with audio includes amix or audio handling."""
        fc = build_filter_complex(
            n_inputs=3,
            durations=[4, 4, 4],
            fade=1.0,
            resolution="1920:1080",
            transition="fade",
            has_audio=True,
        )
        assert "xfade" in fc
        # Should have audio filter chain
        assert any(tag in fc for tag in ["amix", "aevalsrc", "afade", "atrim"])


# ---------------------------------------------------------------------------
# HEIC and precondition tests (T032)
# ---------------------------------------------------------------------------

class TestHeicDetection:
    def test_heic_detected_from_mime_type(self):
        """detect_heic returns True for image/heic mime type."""
        assert detect_heic("image/heic") is True

    def test_heic_detected_from_heif_mime_type(self):
        """detect_heic returns True for image/heif mime type."""
        assert detect_heic("image/heif") is True

    def test_jpeg_not_heic(self):
        """detect_heic returns False for image/jpeg."""
        assert detect_heic("image/jpeg") is False

    def test_png_not_heic(self):
        """detect_heic returns False for image/png."""
        assert detect_heic("image/png") is False


class TestSipsConvert:
    def test_sips_command_for_heic(self):
        """sips_convert_cmd returns correct sips command."""
        cmd = sips_convert_cmd(
            src="/tmp/photo.heic",
            dst="/tmp/photo.jpg"
        )
        assert "sips" in cmd
        assert "/tmp/photo.heic" in cmd
        assert "/tmp/photo.jpg" in cmd
        assert "jpeg" in cmd.lower() or "JPEG" in cmd


class TestBuildFFmpegCmd:
    def test_assemble_dry_run_prints_command_no_exec(self, tmp_path):
        """build_ffmpeg_cmd returns a command list without executing."""
        # Create a fake scenario for testing
        scenario = {
            "id": "test-id",
            "items": [
                {"asset_id": "uuid-1", "caption": "Photo 1",
                 "position": 1, "_local_path": str(tmp_path / "photo1.jpg")},
                {"asset_id": "uuid-2", "caption": "Photo 2",
                 "position": 2, "_local_path": str(tmp_path / "photo2.jpg")},
            ],
            "music": None,
            "state": "approved",
        }
        output_path = str(tmp_path / "output.mp4")
        cmd = build_ffmpeg_cmd(
            scenario=scenario,
            output_path=output_path,
            image_duration=4,
            fade_duration=1,
            resolution="1920:1080",
            transition="fade",
            ffmpeg_bin="/opt/homebrew/bin/ffmpeg",
        )
        # Should return a list of strings (the command)
        assert isinstance(cmd, list)
        assert cmd[0].endswith("ffmpeg")
        assert output_path in cmd

    def test_temp_dir_path_format(self, tmp_path):
        """Temp dir for assembly follows expected naming pattern."""
        from scripts.assemble_video import make_temp_dir_path
        path = make_temp_dir_path("2025-03-15-edgar-birthday", base_tmp="/tmp")
        assert "2025-03-15-edgar-birthday" in path
        assert path.startswith("/tmp")


# ---------------------------------------------------------------------------
# T041: Video output quality tests (US4)
# ---------------------------------------------------------------------------

class TestVideoOutputQuality:
    def _make_scenario(self, with_music=False):
        scenario = {
            "items": [
                {"asset_id": "a1", "_local_path": "/tmp/a1.jpg", "mime_type": "image/jpeg"},
                {"asset_id": "a2", "_local_path": "/tmp/a2.jpg", "mime_type": "image/jpeg"},
            ],
            "music": None,
        }
        if with_music:
            scenario["music"] = {"type": "bundled", "path": "/music/track.mp3"}
        return scenario

    def test_ffmpeg_cmd_crf_18(self):
        """Output video should use CRF 18 for high quality."""
        cmd = build_ffmpeg_cmd(self._make_scenario(), "/out/output.mp4",
                               image_duration=4, fade_duration=1.0,
                               resolution="1920:1080", transition="fade",
                               ffmpeg_bin="ffmpeg")
        assert "-crf" in cmd
        crf_idx = cmd.index("-crf")
        assert cmd[crf_idx + 1] == "18"

    def test_ffmpeg_cmd_maxrate_10M(self):
        """Output should cap bitrate at 10M."""
        cmd = build_ffmpeg_cmd(self._make_scenario(), "/out/output.mp4",
                               image_duration=4, fade_duration=1.0,
                               resolution="1920:1080", transition="fade",
                               ffmpeg_bin="ffmpeg")
        assert "-maxrate" in cmd
        mr_idx = cmd.index("-maxrate")
        assert cmd[mr_idx + 1] == "10M"

    def test_ffmpeg_cmd_30fps(self):
        """Output should use 30 fps."""
        filter_str = build_filter_complex(
            n_inputs=2,
            durations=[4.0, 4.0],
            fade=1.0,
            resolution="1920:1080",
            transition="fade",
            has_audio=False,
        )
        assert "fps=30" in filter_str

    def test_sips_quality_100(self):
        """HEIC conversion should use maximum JPEG quality."""
        cmd = sips_convert_cmd("/in/photo.heic", "/out/photo.jpg")
        assert "formatOptions" in cmd
        assert "100" in cmd

    def test_audio_bitrate_192k(self):
        """Audio should be 192k, not 128k."""
        cmd = build_ffmpeg_cmd(self._make_scenario(with_music=True), "/out/output.mp4",
                               image_duration=4, fade_duration=1.0,
                               resolution="1920:1080", transition="fade",
                               ffmpeg_bin="ffmpeg")
        assert "192k" in cmd


# ---------------------------------------------------------------------------
# T050: Video clip inclusion tests (US3)
# ---------------------------------------------------------------------------

class TestVideoClipInclusion:
    def test_build_filter_complex_with_video_clip(self):
        """Video inputs should NOT use loop filter."""
        fc = build_filter_complex(
            n_inputs=3,
            durations=[4.0, 10.0, 4.0],
            fade=1.0,
            resolution="1920:1080",
            transition="fade",
            has_audio=False,
            input_types=["IMAGE", "VIDEO", "IMAGE"],
        )
        # First input (image) should have loop
        assert "loop=loop=-1:size=1:start=0" in fc.split(";")[0]
        # Second input (video) should NOT have loop
        video_part = fc.split(";")[1]
        assert "loop" not in video_part
        assert "trim=duration=10.000" in video_part
        # Third input (image) should have loop
        assert "loop=loop=-1:size=1:start=0" in fc.split(";")[2]

    def test_build_filter_complex_video_trim(self):
        """Video clips trimmed to specified duration."""
        fc = build_filter_complex(
            n_inputs=1,
            durations=[5.5],
            fade=0.0,
            resolution="1920:1080",
            transition="fade",
            has_audio=False,
            input_types=["VIDEO"],
        )
        assert "trim=duration=5.500" in fc
        assert "loop" not in fc

    def test_build_filter_complex_photo_to_video_transition(self):
        """Photo→Video transition uses xfade like photo→photo."""
        fc = build_filter_complex(
            n_inputs=2,
            durations=[4.0, 10.0],
            fade=1.0,
            resolution="1920:1080",
            transition="fade",
            has_audio=False,
            input_types=["IMAGE", "VIDEO"],
        )
        assert "xfade" in fc

    def test_build_filter_complex_video_to_photo_transition(self):
        """Video→Photo transition uses xfade."""
        fc = build_filter_complex(
            n_inputs=2,
            durations=[10.0, 4.0],
            fade=1.0,
            resolution="1920:1080",
            transition="fade",
            has_audio=False,
            input_types=["VIDEO", "IMAGE"],
        )
        assert "xfade" in fc

    def test_build_filter_complex_all_videos(self):
        """All-video input should have no loop filters."""
        fc = build_filter_complex(
            n_inputs=2,
            durations=[8.0, 12.0],
            fade=1.0,
            resolution="1920:1080",
            transition="fade",
            has_audio=False,
            input_types=["VIDEO", "VIDEO"],
        )
        assert "loop" not in fc
        assert "xfade" in fc


# ---------------------------------------------------------------------------
# T002: v2 project assembler tests
# ---------------------------------------------------------------------------

class TestAssemblerV2:
    def _make_v2_project(self):
        return {
            "id": "test-project",
            "timeline": [
                {"asset_id": "a1", "type": "IMAGE", "duration": 4.0,
                 "trim_start": None, "trim_end": None, "transition": "crossfade"},
                {"asset_id": "a2", "type": "IMAGE", "duration": 4.0,
                 "trim_start": None, "trim_end": None, "transition": "crossfade"},
            ],
            "assembly_config": {
                "orientation": "portrait",
                "resolution": "1080x1920",
                "crf": 18,
                "fps": 30,
                "padding": "black",
            },
            "music": None,
        }

    def test_build_ffmpeg_cmd_from_project(self):
        """build_ffmpeg_cmd_v2 reads project dict."""
        from scripts.assemble_video import build_ffmpeg_cmd_v2
        project = self._make_v2_project()
        # Simulate local paths
        local_paths = {"a1": "/tmp/a1.jpg", "a2": "/tmp/a2.jpg"}
        cmd = build_ffmpeg_cmd_v2(project, "/out/output.mp4", local_paths, "ffmpeg")
        assert "ffmpeg" in cmd[0]
        assert "/out/output.mp4" in cmd

    def test_build_ffmpeg_cmd_portrait_resolution(self):
        """Portrait config produces 1080x1920 scale filter."""
        from scripts.assemble_video import build_ffmpeg_cmd_v2
        project = self._make_v2_project()
        local_paths = {"a1": "/tmp/a1.jpg", "a2": "/tmp/a2.jpg"}
        cmd = build_ffmpeg_cmd_v2(project, "/out/output.mp4", local_paths, "ffmpeg")
        cmd_str = " ".join(cmd)
        assert "1080:1920" in cmd_str

    def test_build_ffmpeg_cmd_reads_assembly_config(self):
        """CRF and fps from assembly_config."""
        from scripts.assemble_video import build_ffmpeg_cmd_v2
        project = self._make_v2_project()
        project["assembly_config"]["crf"] = 20
        project["assembly_config"]["fps"] = 24
        local_paths = {"a1": "/tmp/a1.jpg", "a2": "/tmp/a2.jpg"}
        cmd = build_ffmpeg_cmd_v2(project, "/out/output.mp4", local_paths, "ffmpeg")
        assert "-crf" in cmd
        crf_idx = cmd.index("-crf")
        assert cmd[crf_idx + 1] == "20"
        cmd_str = " ".join(cmd)
        assert "fps=24" in cmd_str


# ---------------------------------------------------------------------------
# T008: DNG tests
# ---------------------------------------------------------------------------

class TestDNGSupport:
    def test_sips_convert_dng_to_jpeg(self):
        """DNG conversion uses explicit jpeg format."""
        cmd = sips_convert_cmd("/in/photo.DNG", "/out/photo.jpg")
        assert "format" in cmd.lower()
        assert "jpeg" in cmd.lower() or "JPEG" in cmd
        assert "formatOptions" in cmd
        assert "100" in cmd

    def test_detect_dng_by_extension(self):
        from scripts.assemble_video import detect_format
        assert detect_format("photo.DNG", "image/x-adobe-dng") == "dng"
        assert detect_format("photo.dng", "image/x-adobe-dng") == "dng"

    def test_detect_dng_by_mime(self):
        from scripts.assemble_video import detect_format
        assert detect_format("photo.raw", "image/x-adobe-dng") == "dng"

    def test_detect_heic(self):
        from scripts.assemble_video import detect_format
        assert detect_format("photo.HEIC", "image/heic") == "heic"
        assert detect_format("photo.heif", "image/heif") == "heic"

    def test_detect_jpeg(self):
        from scripts.assemble_video import detect_format
        assert detect_format("photo.jpg", "image/jpeg") == "jpeg"

    def test_detect_video(self):
        from scripts.assemble_video import detect_format
        assert detect_format("clip.MOV", "video/quicktime") == "video"
        assert detect_format("clip.mp4", "video/mp4") == "video"
