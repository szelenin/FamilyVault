"""Unit tests for caption.video_mlx — MLX-VLM multi-frame video captioner.

All tests inject a FAKE backend callable; no MLX, no network, no third-party
deps. The module must import even though ``mlx_vlm`` is not installed (the real
backend lazy-imports it inside the function body).

Model-reply contract under test (the raw string the backend returns):
    JSON: {
        "caption": "<english video-level description>",
        "ocr_text": "<verbatim on-screen text>",       # optional
        "segments": [                                    # optional
            {"t_start": float, "t_end": float,
             "caption": str, "ocr_text": str},
            ...
        ]
    }

Backend signature (injectable):
    backend(frame_paths: list[str], prompt: str) -> str
The captioner embeds each window's absolute frame times into the prompt; the
fake backend parses them back out so it can emit absolute per-segment times,
exactly as the real model is instructed to.

Timestamp source under test:
    caption(paths, *, is_video, ocr_frames=None, frame_times=None)
``frame_times`` is a parallel list of seconds-into-clip for each frame. When
omitted, evenly-spaced times are derived. A trailing ``_<t>`` in a
``frame_<i>_<t>.jpg`` filename is also accepted as a fallback.
"""
import json
import re

import pytest

from caption.base import CaptionResult
from caption.video_mlx import VideoMLXCaptioner, CaptionError, FRAME_BUDGET


# ---------------------------------------------------------------------------
# Fake backend helpers
# ---------------------------------------------------------------------------

_TIMES_RE = re.compile(r"FRAME_TIMES:\s*(\[[^\]]*\])")


def _times_from_prompt(prompt: str) -> list[float]:
    """Extract the absolute frame-time list the captioner embedded in the prompt."""
    m = _TIMES_RE.search(prompt)
    assert m, f"prompt did not contain FRAME_TIMES marker: {prompt!r}"
    return json.loads(m.group(1))


def _make_scene_backend(n_segments_per_window: int = 2, ocr_per_frame=None):
    """Fake backend that produces one segment per consecutive pair of frames.

    It reads the window's absolute frame times from the prompt and emits
    segments whose t_start/t_end are real absolute times. Records every call.
    """
    calls = []

    def backend(frame_paths, prompt):
        times = _times_from_prompt(prompt)
        calls.append({"frame_paths": list(frame_paths), "times": list(times)})

        segments = []
        # one segment per consecutive pair so multi-frame windows -> multi-segment
        for i in range(len(times) - 1):
            seg_ocr = ""
            if ocr_per_frame is not None and i < len(ocr_per_frame):
                seg_ocr = ocr_per_frame[i]
            segments.append(
                {
                    "t_start": times[i],
                    "t_end": times[i + 1],
                    "caption": f"scene at {times[i]:.1f}s",
                    "ocr_text": seg_ocr,
                }
            )
        # if only a single frame, still make one zero-length segment
        if not segments and times:
            segments.append(
                {
                    "t_start": times[0],
                    "t_end": times[0],
                    "caption": f"scene at {times[0]:.1f}s",
                    "ocr_text": "",
                }
            )

        ocr_all = "\n".join(s["ocr_text"] for s in segments if s["ocr_text"])
        return json.dumps(
            {
                "caption": "A clip showing several moments across the video.",
                "ocr_text": ocr_all,
                "segments": segments,
            }
        )

    backend.calls = calls
    return backend


def _frames(n):
    return [f"/tmp/frame_{i}.jpg" for i in range(n)]


# ---------------------------------------------------------------------------
# No third-party import at module load
# ---------------------------------------------------------------------------

def test_module_imports_without_mlx_installed():
    # Importing the module (already imported at top of this file) and using it
    # must not import mlx_vlm. NB: we deliberately do NOT importlib.reload here,
    # which would rebind CaptionError to a fresh class and break other tests'
    # pytest.raises identity checks.
    import sys

    import caption.video_mlx  # noqa: F401  (ensures it is importable)

    assert "mlx_vlm" not in sys.modules


# ---------------------------------------------------------------------------
# Within-budget single call
# ---------------------------------------------------------------------------

class TestWithinBudget:
    def test_returns_caption_result(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend)
        result = cap.caption(_frames(3), is_video=True, frame_times=[0.0, 1.0, 2.0])
        assert isinstance(result, CaptionResult)

    def test_video_level_caption_non_empty(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend)
        result = cap.caption(_frames(3), is_video=True, frame_times=[0.0, 1.0, 2.0])
        assert result.caption.strip()

    def test_model_field(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend)
        result = cap.caption(_frames(2), is_video=True, frame_times=[0.0, 5.0])
        assert result.model == "mlx:Qwen3-VL-8B-4bit"

    def test_segments_present_with_required_keys(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend)
        result = cap.caption(_frames(3), is_video=True, frame_times=[0.0, 1.0, 2.0])
        assert isinstance(result.segments, list) and result.segments
        for seg in result.segments:
            assert "t_start" in seg
            assert "t_end" in seg
            assert "caption" in seg and seg["caption"]
            assert "ocr_text" in seg

    def test_single_call_within_budget(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend)
        n = FRAME_BUDGET  # exactly at budget -> single call
        cap.caption(_frames(n), is_video=True, frame_times=[float(i) for i in range(n)])
        assert len(backend.calls) == 1


# ---------------------------------------------------------------------------
# Multi-scene -> more than one segment
# ---------------------------------------------------------------------------

class TestMultiScene:
    def test_more_than_one_segment(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend)
        result = cap.caption(
            _frames(4), is_video=True, frame_times=[0.0, 2.0, 4.0, 6.0]
        )
        assert len(result.segments) > 1


# ---------------------------------------------------------------------------
# Timestamp source
# ---------------------------------------------------------------------------

class TestTimestamps:
    def test_explicit_frame_times_used(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend)
        times = [0.0, 3.5, 7.0]
        result = cap.caption(_frames(3), is_video=True, frame_times=times)
        starts = [seg["t_start"] for seg in result.segments]
        assert starts == [0.0, 3.5]
        assert result.segments[-1]["t_end"] == 7.0

    def test_derived_even_spacing_when_omitted(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend)
        # 4 frames, no times -> derived 0,1,2,3 (default 1.0s spacing)
        result = cap.caption(_frames(4), is_video=True)
        starts = [seg["t_start"] for seg in result.segments]
        assert starts == [0.0, 1.0, 2.0]

    def test_times_parsed_from_filename_fallback(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend)
        paths = ["/tmp/frame_0_0.0.jpg", "/tmp/frame_1_4.5.jpg", "/tmp/frame_2_9.0.jpg"]
        result = cap.caption(paths, is_video=True)  # no frame_times -> parse names
        starts = [seg["t_start"] for seg in result.segments]
        assert starts == [0.0, 4.5]
        assert result.segments[-1]["t_end"] == 9.0


# ---------------------------------------------------------------------------
# Map-reduce when over budget
# ---------------------------------------------------------------------------

class TestMapReduce:
    def test_backend_called_more_than_once(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend, frame_budget=4)
        n = 10  # > budget of 4 -> windows of 4,4,2 = 3 map calls (+ maybe reduce)
        cap.caption(
            _frames(n),
            is_video=True,
            frame_times=[float(i) for i in range(n)],
        )
        assert len(backend.calls) > 1

    def test_segments_span_all_windows_absolute_times(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend, frame_budget=4)
        n = 10
        times = [float(i) for i in range(n)]
        result = cap.caption(_frames(n), is_video=True, frame_times=times)
        starts = [seg["t_start"] for seg in result.segments]
        # every consecutive pair across the WHOLE clip should be a segment start
        # (windows are stitched; absolute times preserved end-to-end)
        assert starts[0] == 0.0
        assert max(seg["t_end"] for seg in result.segments) == 9.0
        # a timestamp from a later window must be present (proves absolute, not reset)
        assert any(s >= 8.0 for s in starts)
        # monotonic non-decreasing across windows
        assert starts == sorted(starts)

    def test_one_combined_video_level_caption(self):
        backend = _make_scene_backend()
        cap = VideoMLXCaptioner(backend=backend, frame_budget=4)
        n = 10
        result = cap.caption(
            _frames(n), is_video=True, frame_times=[float(i) for i in range(n)]
        )
        assert isinstance(result.caption, str) and result.caption.strip()


# ---------------------------------------------------------------------------
# OCR dedupe across the whole clip
# ---------------------------------------------------------------------------

class TestOcrDedup:
    def test_duplicate_ocr_across_frames_appears_once(self):
        # Same on-screen text repeated across frames -> once in top-level ocr_text
        ocr = ["WELCOME", "WELCOME", "WELCOME"]
        backend = _make_scene_backend(ocr_per_frame=ocr)
        cap = VideoMLXCaptioner(backend=backend)
        result = cap.caption(_frames(4), is_video=True, frame_times=[0.0, 1.0, 2.0, 3.0])
        assert result.ocr_text.splitlines().count("WELCOME") == 1

    def test_duplicate_ocr_across_windows_deduped(self):
        ocr = ["SALE"] * 12
        backend = _make_scene_backend(ocr_per_frame=ocr)
        cap = VideoMLXCaptioner(backend=backend, frame_budget=4)
        n = 12
        result = cap.caption(
            _frames(n), is_video=True, frame_times=[float(i) for i in range(n)]
        )
        assert result.ocr_text.splitlines().count("SALE") == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrors:
    def test_backend_raises_becomes_caption_error(self):
        def backend(frame_paths, prompt):
            raise RuntimeError("MLX OOM")

        cap = VideoMLXCaptioner(backend=backend)
        with pytest.raises(CaptionError):
            cap.caption(_frames(3), is_video=True, frame_times=[0.0, 1.0, 2.0])

    def test_unparseable_response_raises_caption_error(self):
        def backend(frame_paths, prompt):
            return "not json at all <<<"

        cap = VideoMLXCaptioner(backend=backend)
        with pytest.raises(CaptionError):
            cap.caption(_frames(3), is_video=True, frame_times=[0.0, 1.0, 2.0])

    def test_missing_caption_field_raises_caption_error(self):
        def backend(frame_paths, prompt):
            return json.dumps({"segments": [], "ocr_text": ""})

        cap = VideoMLXCaptioner(backend=backend)
        with pytest.raises(CaptionError):
            cap.caption(_frames(3), is_video=True, frame_times=[0.0, 1.0, 2.0])

    def test_error_not_swallowed_no_bad_result(self):
        def backend(frame_paths, prompt):
            return ""

        cap = VideoMLXCaptioner(backend=backend)
        raised = False
        try:
            cap.caption(_frames(2), is_video=True, frame_times=[0.0, 1.0])
        except CaptionError:
            raised = True
        except Exception:
            pytest.fail("Expected CaptionError, got a different exception")
        assert raised

    def test_error_carries_message(self):
        def backend(frame_paths, prompt):
            raise ConnectionError("backend down")

        cap = VideoMLXCaptioner(backend=backend)
        with pytest.raises(CaptionError) as exc:
            cap.caption(_frames(2), is_video=True, frame_times=[0.0, 1.0])
        assert str(exc.value)
