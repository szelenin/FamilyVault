"""caption.video_mlx — MLX-VLM multi-frame video captioner.

Public API
----------
VideoMLXCaptioner(backend=None, *, frame_budget=FRAME_BUDGET)
    .caption(paths, *, is_video, ocr_frames=None, frame_times=None) -> CaptionResult

Produces a *video-level* caption plus timestamped ``segments``. Satisfies the
``caption.base.Captioner`` protocol (with an added optional ``frame_times``
keyword), so the orchestrator can swap it for the photo backend.

Dependency injection
--------------------
The ``backend`` constructor argument is an injectable callable:

    backend(frame_paths: list[str], prompt: str) -> str

It returns the raw model-response string (JSON). When ``backend=None`` (the
default) a real MLX-VLM backend is built lazily; ``mlx_vlm`` is imported INSIDE
the backend call, never at module load, so importing this module and running the
unit tests requires no third-party packages.

Timestamp source (explicit, tested)
-----------------------------------
Frames are still passed as ``paths`` (Captioner protocol), but each frame needs
a wall-clock offset into the clip. The source is resolved in this order:

  1. ``frame_times`` keyword — a parallel ``list[float]`` of seconds-into-clip
     (one per frame). This is the contract the extractor/orchestrator uses.
  2. Filename fallback — a trailing ``_<t>`` in ``frame_<i>_<t>.jpg`` (the
     extractor's naming scheme), parsed when ``frame_times`` is omitted and the
     names match.
  3. Even-spacing fallback — ``0, 1, 2, …`` (``DEFAULT_SPACING`` seconds apart)
     when nothing else is available.

The captioner is authoritative for absolute time: it embeds each window's
absolute frame times into the prompt (``FRAME_TIMES: [...]``) and instructs the
model to emit absolute per-segment times, then clamps them into the window's
range. This keeps map-reduce timestamps correct without trusting the model to
track an offset.

Model-reply contract
--------------------
The backend returns a JSON object:

    {
      "caption":  "<english video-level description>",   # required (non-empty)
      "ocr_text": "<verbatim on-screen text>",            # optional
      "segments": [                                        # optional
          {"t_start": float, "t_end": float,
           "caption": str, "ocr_text": str},
          ...
      ]
    }

Graceful degradation:
  - Missing/empty ``caption`` (per window) → CaptionError.
  - Missing ``ocr_text`` → "".
  - Missing/empty ``segments`` → a single window-spanning segment is synthesized
    from the window caption so a video always carries at least one segment.

Map-reduce
----------
When ``len(frames) > frame_budget`` the frames are split into ordered windows of
``<= frame_budget`` (with their absolute times). Each window is captioned (map);
its segments are clamped to the window's time range and concatenated. The
window-level captions are then REDUCED into one video-level caption with a
second backend call; if that reduce call fails or returns nothing usable, a
deterministic newline-join of the window captions is used instead. OCR is deduped
across the whole clip.

Error handling
--------------
CaptionError (typed; raised; never swallowed) wraps backend transport failures,
non-JSON / unparseable responses, and missing-caption fields. The orchestrator
maps it to ``status=error`` without crashing the batch. A valid CaptionResult is
never returned on failure.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable, Optional

from caption.base import CaptionResult

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class CaptionError(Exception):
    """Raised when the video captioner cannot produce a valid result.

    Covers backend/transport failures, non-JSON or unparseable model
    responses, and responses missing the required per-window ``caption`` field.
    """


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "mlx:Qwen3-VL-8B-4bit"
_MLX_MODEL_ID = "mlx-community/Qwen3-VL-8B-Instruct-4bit"

#: Max frames sent in a single MLX call. Above this, map-reduce kicks in.
FRAME_BUDGET = 16

#: Seconds between frames when no times are supplied and names don't encode them.
DEFAULT_SPACING = 1.0

#: frame_<index>_<time>.jpg  ->  capture the trailing time.
_FRAME_TIME_RE = re.compile(r"frame_\d+_(\d+(?:\.\d+)?)\.[A-Za-z0-9]+$")

_FRAME_TIMES_MARKER = "FRAME_TIMES:"

_MAP_PROMPT = (
    "You are a video-understanding assistant. You are given an ordered set of "
    "frames sampled from a video clip. The absolute time (seconds into the clip) "
    "of each frame, in order, is:\n"
    "{marker} {times}\n"
    "Respond with ONLY a JSON object (no markdown, no extra text) in this exact "
    "shape:\n"
    '{{"caption": "<English description of what happens across these frames>", '
    '"ocr_text": "<verbatim on-screen text across the frames, or empty>", '
    '"segments": [{{"t_start": <abs seconds>, "t_end": <abs seconds>, '
    '"caption": "<what happens in this segment>", '
    '"ocr_text": "<on-screen text in this segment, or empty>"}}]}}\n'
    "Use the ABSOLUTE times listed above for t_start/t_end. Emit one segment per "
    "distinct scene/action. The top-level caption must be a complete English "
    "sentence."
)

_REDUCE_PROMPT = (
    "You are summarizing one video. Below are descriptions of consecutive "
    "windows of the same clip, in order. Combine them into ONE coherent English "
    "description of the whole video. Respond with ONLY a JSON object: "
    '{{"caption": "<one English description of the whole video>"}}\n'
    "Window descriptions:\n{windows}"
)


# ---------------------------------------------------------------------------
# OCR dedupe helper (mirrors photo_ollama._dedup_lines)
# ---------------------------------------------------------------------------

def _dedup_lines(text: str) -> str:
    """Remove duplicate lines from *text*, preserving first-occurrence order."""
    if not text:
        return ""
    seen: set[str] = set()
    out: list[str] = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line:
            continue
        if line not in seen:
            seen.add(line)
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Timestamp resolution
# ---------------------------------------------------------------------------

def _resolve_frame_times(
    paths: list[str], frame_times: Optional[list[float]]
) -> list[float]:
    """Resolve one absolute time (seconds) per frame.

    Priority: explicit ``frame_times`` → filename ``frame_<i>_<t>`` → even
    spacing of ``DEFAULT_SPACING`` seconds.
    """
    n = len(paths)
    if frame_times is not None:
        if len(frame_times) != n:
            raise CaptionError(
                f"frame_times length {len(frame_times)} != number of frames {n}"
            )
        return [float(t) for t in frame_times]

    parsed: list[float] = []
    for p in paths:
        m = _FRAME_TIME_RE.search(os.path.basename(p))
        if not m:
            parsed = []
            break
        parsed.append(float(m.group(1)))
    if len(parsed) == n and n > 0:
        return parsed

    return [i * DEFAULT_SPACING for i in range(n)]


# ---------------------------------------------------------------------------
# Real MLX backend (lazy import — only built when not injected)
# ---------------------------------------------------------------------------

class _MLXBackend:
    """Real backend calling MLX-VLM. ``mlx_vlm`` is imported on first call only."""

    def __init__(self, model_id: Optional[str] = None) -> None:
        self.model_id = model_id or os.environ.get("MLX_VLM_MODEL", _MLX_MODEL_ID)
        self._model = None
        self._processor = None
        self._config = None
        self._generate = None
        self._apply_chat_template = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        # Lazy, in-body imports: never at module load. Keeps unit tests dep-free.
        from mlx_vlm import load, generate  # type: ignore
        from mlx_vlm.prompt_utils import apply_chat_template  # type: ignore
        from mlx_vlm.utils import load_config  # type: ignore

        self._model, self._processor = load(self.model_id)
        self._config = load_config(self.model_id)
        self._generate = generate
        self._apply_chat_template = apply_chat_template

    def __call__(self, frame_paths: list[str], prompt: str) -> str:
        self._ensure_loaded()
        formatted = self._apply_chat_template(
            self._processor, self._config, prompt, num_images=len(frame_paths)
        )
        out = self._generate(
            self._model,
            self._processor,
            formatted,
            image=list(frame_paths),
            verbose=False,
        )
        # mlx_vlm.generate returns either a str or an object with .text
        return getattr(out, "text", out)


Backend = Callable[[list[str], str], str]


# ---------------------------------------------------------------------------
# Captioner
# ---------------------------------------------------------------------------

class VideoMLXCaptioner:
    """MLX-VLM multi-frame captioner producing a video caption + segments.

    Parameters
    ----------
    backend:
        Injectable ``(frame_paths, prompt) -> str`` callable. When None, a real
        MLX backend is built lazily (``mlx_vlm`` imported on first use).
    frame_budget:
        Max frames per model call; over this, map-reduce is used.
    """

    def __init__(
        self,
        backend: Optional[Backend] = None,
        *,
        frame_budget: int = FRAME_BUDGET,
    ) -> None:
        self._backend = backend  # None → lazy real backend
        if frame_budget < 1:
            raise ValueError("frame_budget must be >= 1")
        self.frame_budget = frame_budget

    # -- public ----------------------------------------------------------

    def caption(
        self,
        paths: list[str],
        *,
        is_video: bool,
        ocr_frames: list[str] | None = None,
        frame_times: list[float] | None = None,
    ) -> CaptionResult:
        """Caption a video from sampled frames.

        See module docstring for the timestamp source and model contract.

        Raises
        ------
        CaptionError
            On backend failure, unparseable response, or missing caption.
        """
        if not paths:
            raise CaptionError("no frames supplied to video captioner")

        times = _resolve_frame_times(paths, frame_times)

        # Split into ordered windows of <= frame_budget frames.
        windows: list[tuple[list[str], list[float]]] = []
        for start in range(0, len(paths), self.frame_budget):
            end = start + self.frame_budget
            windows.append((paths[start:end], times[start:end]))

        window_captions: list[str] = []
        all_segments: list[dict] = []
        ocr_chunks: list[str] = []

        # --- MAP: caption each window, with absolute timestamps ---
        for w_paths, w_times in windows:
            parsed = self._caption_window(w_paths, w_times)
            window_captions.append(parsed["caption"])
            all_segments.extend(parsed["segments"])
            if parsed["ocr_text"]:
                ocr_chunks.append(parsed["ocr_text"])

        # --- REDUCE: combine into one video-level caption ---
        if len(windows) == 1:
            video_caption = window_captions[0]
        else:
            video_caption = self._reduce_caption(window_captions)

        ocr_text = _dedup_lines("\n".join(ocr_chunks))

        return CaptionResult(
            caption=video_caption,
            ocr_text=ocr_text,
            segments=all_segments,
            model=MODEL,
        )

    # -- internals -------------------------------------------------------

    def _call_backend(self, frame_paths: list[str], prompt: str) -> str:
        backend = self._backend if self._backend is not None else _get_default_backend()
        try:
            raw = backend(frame_paths, prompt)
        except CaptionError:
            raise
        except Exception as exc:  # backend/transport failure
            raise CaptionError(f"MLX backend call failed: {exc}") from exc
        if not isinstance(raw, str) or not raw.strip():
            raise CaptionError(f"MLX backend returned empty/non-str response: {raw!r}")
        return raw

    @staticmethod
    def _parse_json(raw: str) -> dict:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise CaptionError(f"Model returned non-JSON response: {raw!r}") from exc
        if not isinstance(data, dict):
            raise CaptionError(f"Model response is not a JSON object: {raw!r}")
        return data

    def _caption_window(
        self, w_paths: list[str], w_times: list[float]
    ) -> dict:
        """Caption one window; return {caption, ocr_text, segments(abs+clamped)}."""
        prompt = _MAP_PROMPT.format(
            marker=_FRAME_TIMES_MARKER,
            times=json.dumps([round(t, 4) for t in w_times]),
        )
        raw = self._call_backend(w_paths, prompt)
        data = self._parse_json(raw)

        caption = data.get("caption")
        if not caption or not str(caption).strip():
            raise CaptionError(
                f"Model response missing 'caption' field. Response: {data!r}"
            )
        caption = str(caption).strip()

        ocr_text = data.get("ocr_text") or ""
        if not isinstance(ocr_text, str):
            ocr_text = ""
        ocr_text = _dedup_lines(ocr_text)

        w_lo = w_times[0]
        w_hi = w_times[-1]
        segments = self._normalize_segments(
            data.get("segments"), caption, ocr_text, w_lo, w_hi
        )
        return {"caption": caption, "ocr_text": ocr_text, "segments": segments}

    @staticmethod
    def _normalize_segments(
        raw_segments,
        window_caption: str,
        window_ocr: str,
        w_lo: float,
        w_hi: float,
    ) -> list[dict]:
        """Validate/clamp segment times into the window range; synthesize if none."""
        segments: list[dict] = []
        if isinstance(raw_segments, list):
            for seg in raw_segments:
                if not isinstance(seg, dict):
                    continue
                seg_cap = seg.get("caption")
                if not seg_cap or not str(seg_cap).strip():
                    continue
                try:
                    t_start = float(seg.get("t_start"))
                    t_end = float(seg.get("t_end"))
                except (TypeError, ValueError):
                    continue
                # Clamp into the window range; keep t_end >= t_start.
                t_start = min(max(t_start, w_lo), w_hi)
                t_end = min(max(t_end, w_lo), w_hi)
                if t_end < t_start:
                    t_end = t_start
                seg_ocr = seg.get("ocr_text") or ""
                if not isinstance(seg_ocr, str):
                    seg_ocr = ""
                segments.append(
                    {
                        "t_start": t_start,
                        "t_end": t_end,
                        "caption": str(seg_cap).strip(),
                        "ocr_text": _dedup_lines(seg_ocr),
                    }
                )

        if not segments:
            # Guarantee at least one segment spanning the window.
            segments.append(
                {
                    "t_start": w_lo,
                    "t_end": w_hi,
                    "caption": window_caption,
                    "ocr_text": window_ocr,
                }
            )
        return segments

    def _reduce_caption(self, window_captions: list[str]) -> str:
        """Combine window captions into one video-level caption.

        Tries a second backend call; falls back to a deterministic join if that
        fails or yields nothing usable. Never raises (windows already validated).
        """
        windows_text = "\n".join(
            f"- Window {i + 1}: {c}" for i, c in enumerate(window_captions)
        )
        prompt = _REDUCE_PROMPT.format(windows=windows_text)
        try:
            raw = self._call_backend([], prompt)
            data = self._parse_json(raw)
            caption = data.get("caption")
            if caption and str(caption).strip():
                return str(caption).strip()
        except CaptionError:
            pass
        # Deterministic fallback merge.
        return " ".join(window_captions).strip()


# ---------------------------------------------------------------------------
# Lazy default backend singleton
# ---------------------------------------------------------------------------

_real_backend: Optional[_MLXBackend] = None


def _get_default_backend() -> _MLXBackend:
    global _real_backend
    if _real_backend is None:
        _real_backend = _MLXBackend()
    return _real_backend
