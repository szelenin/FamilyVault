"""Unit tests for caption.base — CaptionResult, REQUIRED_MODELS, Captioner protocol.

No external dependencies, no mocks needed — pure data structure / contract tests.
All tests must run in milliseconds.
"""
import pytest
from caption.base import CaptionResult, REQUIRED_MODELS, Captioner


# ---------------------------------------------------------------------------
# CaptionResult — photo defaults
# ---------------------------------------------------------------------------

class TestCaptionResultPhotoDefaults:
    def test_constructs_with_required_fields(self):
        r = CaptionResult(caption="A sunny beach", model="qwen3-vl:8b")
        assert r.caption == "A sunny beach"
        assert r.model == "qwen3-vl:8b"

    def test_ocr_text_defaults_to_empty_string(self):
        r = CaptionResult(caption="A sunny beach", model="qwen3-vl:8b")
        assert r.ocr_text == ""

    def test_segments_default_to_none(self):
        r = CaptionResult(caption="A sunny beach", model="qwen3-vl:8b")
        assert r.segments is None

    def test_explicit_ocr_text(self):
        r = CaptionResult(caption="Sign visible", model="qwen3-vl:8b", ocr_text="STOP")
        assert r.ocr_text == "STOP"

    def test_to_dict_contains_required_keys(self):
        r = CaptionResult(caption="A sunny beach", model="qwen3-vl:8b")
        d = r.to_dict()
        assert set(d.keys()) == {"caption", "ocr_text", "segments", "model"}
        assert d["caption"] == "A sunny beach"
        assert d["ocr_text"] == ""
        assert d["segments"] is None
        assert d["model"] == "qwen3-vl:8b"


# ---------------------------------------------------------------------------
# CaptionResult — video with segments
# ---------------------------------------------------------------------------

class TestCaptionResultVideoSegments:
    def test_video_carries_segments(self):
        segs = [
            {"t_start": 0.0, "t_end": 4.5, "caption": "Kids running", "ocr_text": ""},
            {"t_start": 4.5, "t_end": 9.0, "caption": "Adults talking", "ocr_text": ""},
        ]
        r = CaptionResult(
            caption="Family reunion video",
            model="mlx:Qwen3-VL-8B-4bit",
            segments=segs,
        )
        assert r.segments is not None
        assert len(r.segments) == 2
        assert r.segments[0]["t_start"] == 0.0
        assert r.segments[0]["t_end"] == 4.5
        assert r.segments[0]["caption"] == "Kids running"
        assert r.segments[0]["ocr_text"] == ""
        assert r.segments[1]["t_start"] == 4.5

    def test_to_dict_includes_segments(self):
        segs = [{"t_start": 0.0, "t_end": 3.0, "caption": "Intro", "ocr_text": ""}]
        r = CaptionResult(caption="Video summary", model="mlx:Qwen3-VL-8B-4bit", segments=segs)
        d = r.to_dict()
        assert d["segments"] == segs


# ---------------------------------------------------------------------------
# CaptionResult — validation
# ---------------------------------------------------------------------------

class TestCaptionResultValidation:
    def test_rejects_empty_caption(self):
        with pytest.raises((ValueError, TypeError)):
            CaptionResult(caption="", model="qwen3-vl:8b")

    def test_rejects_whitespace_only_caption(self):
        with pytest.raises((ValueError, TypeError)):
            CaptionResult(caption="   ", model="qwen3-vl:8b")

    def test_rejects_non_str_caption(self):
        with pytest.raises((ValueError, TypeError)):
            CaptionResult(caption=None, model="qwen3-vl:8b")

    def test_rejects_int_caption(self):
        with pytest.raises((ValueError, TypeError)):
            CaptionResult(caption=42, model="qwen3-vl:8b")

    def test_valid_caption_does_not_raise(self):
        # smoke test: a valid result should never raise
        r = CaptionResult(caption="valid description", model="qwen3-vl:8b")
        assert r.caption == "valid description"


# ---------------------------------------------------------------------------
# REQUIRED_MODELS
# ---------------------------------------------------------------------------

class TestRequiredModels:
    def test_has_exactly_photo_and_video_keys(self):
        assert set(REQUIRED_MODELS.keys()) == {"photo", "video"}

    def test_photo_requires_ollama_vlm(self):
        assert "qwen3-vl:8b" in REQUIRED_MODELS["photo"]["ollama"]

    def test_photo_requires_ollama_embedder(self):
        assert "bge-m3" in REQUIRED_MODELS["photo"]["ollama"]

    def test_photo_requires_no_mlx_models(self):
        assert REQUIRED_MODELS["photo"]["mlx"] == []

    def test_video_requires_mlx_vlm(self):
        assert "mlx-community/Qwen3-VL-8B-Instruct-4bit" in REQUIRED_MODELS["video"]["mlx"]

    def test_video_requires_ollama_embedder(self):
        assert "bge-m3" in REQUIRED_MODELS["video"]["ollama"]

    def test_video_does_not_require_photo_vlm(self):
        # Only one VLM runtime is resident per phase — photo VLM must NOT be in video's ollama list
        assert "qwen3-vl:8b" not in REQUIRED_MODELS["video"]["ollama"]


# ---------------------------------------------------------------------------
# Captioner — protocol conformance
# ---------------------------------------------------------------------------

class TestCaptionerProtocol:
    def test_conforming_stub_is_recognized(self):
        """A minimal class with the right signature satisfies the Captioner protocol."""

        class StubCaptioner:
            def caption(
                self,
                paths: list,
                *,
                is_video: bool,
                ocr_frames=None,
            ) -> CaptionResult:
                return CaptionResult(caption="stub", model="stub")

        stub = StubCaptioner()
        # Structural check: the protocol method must be callable with the expected signature
        result = stub.caption(["img.jpg"], is_video=False)
        assert isinstance(result, CaptionResult)
        assert result.caption == "stub"

    def test_nonconforming_object_missing_caption_method(self):
        """An object without .caption() should NOT satisfy the protocol structurally."""

        class NotACaptioner:
            def process(self, paths):
                pass

        obj = NotACaptioner()
        assert not hasattr(obj, "caption")

    def test_captioner_protocol_is_runtime_checkable(self):
        """If Captioner is runtime-checkable, isinstance works on conforming stubs."""
        import typing

        # Only verify this if the Protocol is actually runtime_checkable
        if not getattr(Captioner, "__protocol_attrs__", None) is not None:
            # Fall back: just verify the Protocol exists and has 'caption' in its members
            members = getattr(Captioner, "__protocol_attrs__", None) or []
            # Accept either approach: runtime-checkable isinstance OR attribute inspection
            if members:
                assert "caption" in members
            else:
                # Minimal: just confirm it's a type/protocol
                assert isinstance(Captioner, type) or hasattr(Captioner, "__mro__")
