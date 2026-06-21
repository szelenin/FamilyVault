"""caption.photo_ollama — Ollama qwen3-vl:8b photo captioner.

Public API
----------
PhotoOllamaCaptioner(client=None)
    .caption(paths, *, is_video, ocr_frames=None) -> CaptionResult

Dependency injection
--------------------
The ``client`` constructor argument is injectable for unit testing.
Its call signature:

    client(model: str, image_path: str) -> str

It must return the raw model-response string (JSON).
When ``client=None`` (default), an OllamaVisionClient is constructed lazily
from environment variables so the unit tests (which always inject a fake)
never touch the network or import ``urllib`` at module load time.

Model-reply contract
--------------------
The captioner sends a structured prompt asking for JSON:

    {"caption": "<english description>", "ocr_text": "<verbatim on-screen text>"}

Both fields are optional in the response — graceful degradation:
  - Missing "caption" → raises CaptionError (no usable result)
  - Missing / null "ocr_text" → treated as "" (no on-screen text)

OCR deduplication
-----------------
Duplicate lines in ocr_text are removed while preserving order.

Error handling
--------------
CaptionError (typed; raised; never swallowed) wraps transport errors,
JSON parse failures, and missing-caption fields.  The run orchestrator
maps this exception to status=error in the index.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Callable, Optional

from caption.base import CaptionResult

# ---------------------------------------------------------------------------
# Public exception type
# ---------------------------------------------------------------------------

class CaptionError(Exception):
    """Raised when the Ollama photo captioner cannot produce a valid result.

    Covers:
    - Transport / connection failures
    - Malformed / non-JSON model responses
    - JSON responses missing the required "caption" field
    """


# ---------------------------------------------------------------------------
# Model constants
# ---------------------------------------------------------------------------

_MODEL = "qwen3-vl:8b"

_PROMPT = (
    "You are a photo-description assistant. Look at the image carefully and respond "
    "with ONLY a JSON object (no markdown, no extra text) in this exact format:\n"
    '{"caption": "<English description of what is happening, activity, context, '
    'relationships, setting>", "ocr_text": "<verbatim on-screen text visible in '
    'the image, or empty string if none>"}\n'
    "The caption must be a complete English sentence. "
    "The ocr_text must be verbatim text extracted from signs, labels, screens, etc."
)


# ---------------------------------------------------------------------------
# Deduplication helper
# ---------------------------------------------------------------------------

def _dedup_lines(text: str) -> str:
    """Remove duplicate lines from *text* while preserving first-occurrence order."""
    if not text:
        return ""
    seen: set[str] = set()
    result: list[str] = []
    for line in text.splitlines():
        if line not in seen:
            seen.add(line)
            result.append(line)
    return "\n".join(result)


# ---------------------------------------------------------------------------
# Default (real) Ollama client — constructed lazily, only when not injected
# ---------------------------------------------------------------------------

def _default_url() -> str:
    return os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")


class OllamaVisionClient:
    """Real client that calls Ollama's OpenAI-compatible chat endpoint.

    Only instantiated when no fake client is injected.  Uses stdlib ``urllib``
    and ``base64`` — no third-party imports needed at module load time.
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or _default_url()).rstrip("/")
        self.model = model or _MODEL
        # Context window. Default 4K is too small once an image (~2.8K tokens) is
        # in the prompt — text-heavy photos exhausted it and returned empty
        # content. 8K leaves room for the image + reasoning + the JSON answer.
        self.num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))

    def _build_payload(self, model: str, image_b64: str) -> dict:
        """Build an Ollama native /api/chat request with an adequate num_ctx.

        Native /api/chat (not the OpenAI-compatible endpoint) is required because
        only it accepts ``options.num_ctx``. Images go in the message's ``images``
        array as raw base64.
        """
        return {
            "model": model,
            "messages": [
                {"role": "user", "content": _PROMPT, "images": [image_b64]},
            ],
            "stream": False,
            "options": {"num_ctx": self.num_ctx},
        }

    def __call__(self, model: str, image_path: str) -> str:
        import urllib.request

        # Read + base64-encode the image
        with open(image_path, "rb") as fh:
            image_b64 = base64.b64encode(fh.read()).decode("ascii")

        payload = json.dumps(self._build_payload(model, image_b64)).encode()

        url = f"{self.base_url}/api/chat"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        # Native /api/chat returns the assistant text under message.content
        return data["message"]["content"]


# ---------------------------------------------------------------------------
# Lazy singleton default client
# ---------------------------------------------------------------------------

_real_client: Optional[OllamaVisionClient] = None


def _get_default_client() -> OllamaVisionClient:
    global _real_client
    if _real_client is None:
        _real_client = OllamaVisionClient()
    return _real_client


# ---------------------------------------------------------------------------
# Captioner class
# ---------------------------------------------------------------------------

Client = Callable[[str, str], str]


class PhotoOllamaCaptioner:
    """Ollama qwen3-vl:8b backend for single-image captioning.

    Parameters
    ----------
    client:
        Injectable callable ``(model: str, image_path: str) -> str``.
        When None, a real OllamaVisionClient is constructed lazily.

    Usage
    -----
    ::

        captioner = PhotoOllamaCaptioner()  # real Ollama
        result = captioner.caption(["/path/to/preview.jpg"], is_video=False)

    Or for testing::

        captioner = PhotoOllamaCaptioner(client=fake_client)
        result = captioner.caption(["/path/to/preview.jpg"], is_video=False)
    """

    def __init__(self, client: Optional[Client] = None) -> None:
        self._client = client  # None → lazy real client on first call

    def caption(
        self,
        paths: list[str],
        *,
        is_video: bool,
        ocr_frames: list[str] | None = None,
    ) -> CaptionResult:
        """Caption a single photo using qwen3-vl:8b via Ollama.

        Parameters
        ----------
        paths:
            List of file paths; only the first element is used for photos.
        is_video:
            Must be False for photos (video backend is separate).
        ocr_frames:
            Ignored for photos (OCR is embedded in the single-image call).

        Returns
        -------
        CaptionResult with caption, ocr_text (deduped), segments=None, model="qwen3-vl:8b".

        Raises
        ------
        CaptionError
            On any transport error, unparseable response, or missing caption field.
        """
        image_path = paths[0]
        client = self._client if self._client is not None else _get_default_client()

        # --- Call the model ---
        try:
            raw_response = client(_MODEL, image_path)
        except CaptionError:
            raise  # already typed — pass through
        except Exception as exc:
            raise CaptionError(
                f"Ollama call failed for {image_path!r}: {exc}"
            ) from exc

        # --- Parse JSON response ---
        try:
            data = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError) as exc:
            raise CaptionError(
                f"Model returned non-JSON response for {image_path!r}: {raw_response!r}"
            ) from exc

        # --- Extract caption (required) ---
        caption_text = data.get("caption")
        if not caption_text or not str(caption_text).strip():
            raise CaptionError(
                f"Model response missing 'caption' field for {image_path!r}. "
                f"Response: {data!r}"
            )

        # --- Extract ocr_text (optional — degrade gracefully) ---
        raw_ocr = data.get("ocr_text") or ""
        if not isinstance(raw_ocr, str):
            raw_ocr = ""
        ocr_text = _dedup_lines(raw_ocr)

        return CaptionResult(
            caption=str(caption_text).strip(),
            ocr_text=ocr_text,
            segments=None,
            model=_MODEL,
        )
