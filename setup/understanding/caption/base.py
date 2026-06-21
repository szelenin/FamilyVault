"""caption.base — shared contract types for the VLM captioning layer.

Exports
-------
CaptionResult   structured extraction result (photo or video)
Captioner       typing.Protocol — both Ollama-photo and MLX-video backends must satisfy this
REQUIRED_MODELS per-phase model manifest consumed by the memory governor
"""
from __future__ import annotations

import dataclasses
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# REQUIRED_MODELS
# Memory governor reads this to decide which runtimes to load per phase.
# Invariant: only one VLM runtime is resident at a time.
#   photo phase → Ollama only  (qwen3-vl:8b + bge-m3); MLX empty
#   video phase → MLX VLM    (Qwen3-VL-8B-4bit) + Ollama embedder (bge-m3)
# ---------------------------------------------------------------------------

REQUIRED_MODELS: dict[str, dict[str, list[str]]] = {
    "photo": {
        "ollama": ["qwen3-vl:8b", "bge-m3"],
        "mlx": [],
    },
    "video": {
        "ollama": ["bge-m3"],
        "mlx": ["mlx-community/Qwen3-VL-8B-Instruct-4bit"],
    },
}


def model_present(required: str, installed) -> bool:
    """Whether an Ollama model *required* is satisfied by the *installed* names.

    Ollama reports names with a tag (e.g. ``bge-m3:latest``). A bare required
    name (no ``:tag``) matches any tag of that model; a tagged required name
    must match exactly.
    """
    if required in installed:
        return True
    if ":" in required:
        return False
    return any(m.split(":", 1)[0] == required for m in installed)


# ---------------------------------------------------------------------------
# CaptionResult
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class CaptionResult:
    """Structured output from any Captioner backend.

    Fields
    ------
    caption    English canonical description (non-empty).
    ocr_text   Deduped on-screen text; "" when none detected.
    segments   Video-only: list of per-segment dicts with keys
               {t_start, t_end, caption, ocr_text}.  None for photos.
    model      Provenance string, e.g. "qwen3-vl:8b" or "mlx:Qwen3-VL-8B-4bit".
    """

    caption: str
    model: str
    ocr_text: str = ""
    segments: list | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.caption, str):
            raise TypeError(
                f"caption must be a str, got {type(self.caption).__name__!r}"
            )
        if not self.caption.strip():
            raise ValueError("caption must be a non-empty, non-whitespace string")

    def to_dict(self) -> dict:
        """Return a plain dict with the four canonical keys."""
        return {
            "caption": self.caption,
            "ocr_text": self.ocr_text,
            "segments": self.segments,
            "model": self.model,
        }


# ---------------------------------------------------------------------------
# Captioner protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Captioner(Protocol):
    """Structural interface every captioner backend must satisfy.

    Both the Ollama-photo backend and the MLX-video backend implement this;
    callers depend only on this contract, making them independently testable
    and swappable.
    """

    def caption(
        self,
        paths: list[str],
        *,
        is_video: bool,
        ocr_frames: list[str] | None = None,
    ) -> CaptionResult:
        """Run captioning on one or more image/video frames.

        Parameters
        ----------
        paths       Local file paths to process.
        is_video    True → video path; expect segments in result.
        ocr_frames  Optional subset of frame paths to run OCR over.
        """
        ...
