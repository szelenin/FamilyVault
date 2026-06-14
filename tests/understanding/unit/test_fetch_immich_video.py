"""Unit tests for fetch.immich — video path (T023, T026).

Tests for:
  download_video(session, asset_id, dest_path, *, base_url=...) -> str | None
  extract_frames(video_path, timestamps, dest_dir, *, runner=subprocess.run) -> list[str]

Mocking policy: Immich HTTP uses an injectable session (MagicMock); ffmpeg is
invoked through an injectable runner (also MagicMock). No real network or
ffmpeg process is ever started. Filesystem writes use real tmp_path fixtures.
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from fetch.immich import download_video, extract_frames


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_video_response(content: bytes, status_code: int = 200):
    """Build a minimal mock requests.Response for a video download."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    return resp


def _fake_runner_creating_files(cmd, **kwargs):
    """A fake runner that actually creates the output file (last arg of cmd)."""
    output_path = cmd[-1]
    Path(output_path).write_bytes(b"fake-frame-content")
    result = MagicMock()
    result.returncode = 0
    return result


# ---------------------------------------------------------------------------
# download_video — write video bytes to dest_path
# ---------------------------------------------------------------------------


class TestDownloadVideo:
    def test_200_with_bytes_writes_file_and_returns_path(self, tmp_path):
        """A 200 response with content writes bytes to dest_path and returns path."""
        session = MagicMock()
        video_bytes = b"\x00\x00\x00\x18ftyp fake-mp4-content"
        session.get.return_value = _make_video_response(video_bytes, 200)

        dest = tmp_path / "video.mp4"
        result = download_video(
            session, "video-asset-uuid", dest, base_url="http://immich.test:2283"
        )

        assert result == str(dest)
        assert dest.exists()
        assert dest.read_bytes() == video_bytes

    def test_404_returns_none(self, tmp_path):
        """A 404 response returns None."""
        session = MagicMock()
        session.get.return_value = _make_video_response(b"", 404)

        dest = tmp_path / "video.mp4"
        result = download_video(
            session, "video-asset-uuid", dest, base_url="http://immich.test:2283"
        )

        assert result is None

    def test_non_200_status_returns_none(self, tmp_path):
        """Any non-200 status (e.g. 500) returns None."""
        session = MagicMock()
        session.get.return_value = _make_video_response(b"server error", 500)

        dest = tmp_path / "video.mp4"
        result = download_video(
            session, "video-asset-uuid", dest, base_url="http://immich.test:2283"
        )

        assert result is None

    def test_200_but_empty_body_returns_none(self, tmp_path):
        """A 200 with an empty body returns None (no usable video)."""
        session = MagicMock()
        session.get.return_value = _make_video_response(b"", 200)

        dest = tmp_path / "video.mp4"
        result = download_video(
            session, "video-asset-uuid", dest, base_url="http://immich.test:2283"
        )

        assert result is None

    def test_calls_correct_original_url(self, tmp_path):
        """GET must target the /api/assets/{id}/original endpoint."""
        session = MagicMock()
        session.get.return_value = _make_video_response(b"data", 200)

        dest = tmp_path / "video.mp4"
        download_video(
            session, "my-video-id", dest, base_url="http://immich.test:2283"
        )

        call_args = session.get.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url")
        assert "my-video-id" in url
        assert "original" in url

    def test_uses_default_base_url(self, tmp_path):
        """download_video works without an explicit base_url (uses env default)."""
        session = MagicMock()
        session.get.return_value = _make_video_response(b"data", 200)

        dest = tmp_path / "video.mp4"
        # Should not raise; default URL is used.
        result = download_video(session, "asset-id", dest)
        assert result == str(dest)


# ---------------------------------------------------------------------------
# extract_frames — ffmpeg frame extraction with injectable runner
# ---------------------------------------------------------------------------


class TestExtractFrames:
    def test_three_timestamps_calls_runner_three_times(self, tmp_path):
        """extract_frames calls the runner exactly once per timestamp."""
        fake_runner = MagicMock(return_value=MagicMock(returncode=0))
        video_path = str(tmp_path / "clip.mp4")
        timestamps = [0.0, 5.5, 12.0]

        extract_frames(video_path, timestamps, str(tmp_path), runner=fake_runner)

        assert fake_runner.call_count == 3

    def test_returns_three_output_paths(self, tmp_path):
        """extract_frames returns one output path per timestamp."""
        fake_runner = MagicMock(return_value=MagicMock(returncode=0))
        video_path = str(tmp_path / "clip.mp4")
        timestamps = [1.0, 2.0, 3.0]

        paths = extract_frames(video_path, timestamps, str(tmp_path), runner=fake_runner)

        assert len(paths) == 3

    def test_commands_contain_ffmpeg_and_ss_flag(self, tmp_path):
        """Each runner call must include 'ffmpeg' and '-ss' with the right timestamp."""
        fake_runner = MagicMock(return_value=MagicMock(returncode=0))
        video_path = str(tmp_path / "clip.mp4")
        timestamps = [3.0, 7.5, 20.0]

        extract_frames(video_path, timestamps, str(tmp_path), runner=fake_runner)

        for i, (call_obj, ts) in enumerate(zip(fake_runner.call_args_list, timestamps)):
            cmd = call_obj[0][0]  # positional first arg = the command list
            assert "ffmpeg" in cmd[0] or any("ffmpeg" in str(c) for c in cmd), \
                f"Call {i}: 'ffmpeg' not found in command {cmd}"
            assert "-ss" in cmd, f"Call {i}: '-ss' flag missing from {cmd}"
            ss_index = cmd.index("-ss")
            assert str(ts) in cmd[ss_index + 1], \
                f"Call {i}: timestamp {ts} not found after -ss in {cmd}"

    def test_commands_contain_input_flag_and_video_path(self, tmp_path):
        """Each ffmpeg command must include '-i' and the video path."""
        fake_runner = MagicMock(return_value=MagicMock(returncode=0))
        video_path = str(tmp_path / "myvideo.mp4")
        timestamps = [0.0, 5.0]

        extract_frames(video_path, timestamps, str(tmp_path), runner=fake_runner)

        for i, call_obj in enumerate(fake_runner.call_args_list):
            cmd = call_obj[0][0]
            assert "-i" in cmd, f"Call {i}: '-i' flag missing from {cmd}"
            i_index = cmd.index("-i")
            assert cmd[i_index + 1] == video_path, \
                f"Call {i}: video path not after '-i' in {cmd}"

    def test_output_filenames_are_unique_per_timestamp(self, tmp_path):
        """Output paths are unique for each timestamp/index combination."""
        fake_runner = MagicMock(return_value=MagicMock(returncode=0))
        video_path = str(tmp_path / "clip.mp4")
        timestamps = [1.0, 1.0, 2.0]  # two identical timestamps → still unique by index

        paths = extract_frames(video_path, timestamps, str(tmp_path), runner=fake_runner)

        assert len(paths) == len(set(paths)), "Output paths must be unique"

    def test_output_files_land_in_dest_dir(self, tmp_path):
        """All returned paths must be inside dest_dir."""
        fake_runner = MagicMock(return_value=MagicMock(returncode=0))
        video_path = str(tmp_path / "clip.mp4")
        timestamps = [0.5, 3.0]

        dest_dir = tmp_path / "frames"
        dest_dir.mkdir()
        paths = extract_frames(video_path, timestamps, str(dest_dir), runner=fake_runner)

        for p in paths:
            assert str(dest_dir) in p, f"Path {p!r} is not inside {dest_dir}"

    def test_empty_timestamps_returns_empty_list(self, tmp_path):
        """Zero timestamps → zero calls and empty list returned."""
        fake_runner = MagicMock(return_value=MagicMock(returncode=0))
        video_path = str(tmp_path / "clip.mp4")

        paths = extract_frames(video_path, [], str(tmp_path), runner=fake_runner)

        assert paths == []
        fake_runner.assert_not_called()

    def test_fake_runner_creates_real_files(self, tmp_path):
        """When the fake runner actually creates files, the returned paths exist."""
        video_path = str(tmp_path / "clip.mp4")
        timestamps = [0.0, 5.0, 10.0]

        paths = extract_frames(
            video_path, timestamps, str(tmp_path), runner=_fake_runner_creating_files
        )

        assert len(paths) == 3
        for p in paths:
            assert Path(p).exists(), f"Expected file to exist: {p}"
            assert Path(p).read_bytes() == b"fake-frame-content"

    def test_output_filenames_contain_index_and_timestamp(self, tmp_path):
        """Output filenames encode the frame index and timestamp for traceability."""
        fake_runner = MagicMock(return_value=MagicMock(returncode=0))
        video_path = str(tmp_path / "clip.mp4")
        timestamps = [2.5, 8.0]

        paths = extract_frames(video_path, timestamps, str(tmp_path), runner=fake_runner)

        # index 0 → "frame_0_2.5.jpg" (or similar); index 1 → "frame_1_8.0.jpg"
        assert "0" in Path(paths[0]).name
        assert "1" in Path(paths[1]).name


class TestListVideoAssets:
    def _resp(self, items, next_page=None):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.json.return_value = {"assets": {"items": items, "nextPage": next_page}}
        return r

    def test_paginates_and_returns_all_videos(self):
        from unittest.mock import MagicMock
        from fetch.immich import list_video_assets
        s = MagicMock()
        s.post.side_effect = [
            self._resp([{"id": "v1", "type": "VIDEO"}], next_page=2),
            self._resp([{"id": "v2", "type": "VIDEO"}], next_page=None),
        ]
        assets = list_video_assets(s, base_url="http://x:2283")
        assert [a["id"] for a in assets] == ["v1", "v2"]

    def test_post_body_requests_video_type(self):
        from unittest.mock import MagicMock
        from fetch.immich import list_video_assets
        s = MagicMock()
        s.post.return_value = self._resp([], next_page=None)
        list_video_assets(s, base_url="http://x:2283")
        _, kwargs = s.post.call_args
        assert kwargs["json"]["type"] == "VIDEO"
