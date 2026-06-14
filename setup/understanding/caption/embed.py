"""Multilingual text embedder — bge-m3 via Ollama embeddings endpoint.

Wire format (MUST match index/db.py deserialization):
    array('f', list_of_floats).tobytes()

Public API
----------
embed(text, *, client=None) -> bytes
    Embed a caption at index time.

embed_query(text, *, client=None) -> bytes
    Embed a user query at search time.  Same model + serialization as embed()
    so multilingual queries (RU, UK, EN …) match English captions.

Dependency injection
--------------------
Both functions accept an optional ``client`` keyword argument.  The client
must be callable as:

    client(model: str, text: str) -> list[float]

When ``client=None`` (the default), a real OllamaEmbeddingClient is
constructed lazily using environment variables:

    EMBED_MODEL  — Ollama model name  (default: "bge-m3")
    OLLAMA_URL   — Ollama base URL    (default: "http://localhost:11434")

The lazy default means the unit tests (which always inject a fake client)
never import or construct anything that touches the network.
"""
import array as _array
import os
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Wire-format helper
# ---------------------------------------------------------------------------

def _to_bytes(floats: list[float]) -> bytes:
    """Serialize a float list to array('f') bytes — the db.py contract."""
    return _array.array("f", floats).tobytes()


# ---------------------------------------------------------------------------
# Default (real) client — constructed only when no client is injected
# ---------------------------------------------------------------------------

def _default_model() -> str:
    return os.environ.get("EMBED_MODEL", "bge-m3")


def _default_url() -> str:
    return os.environ.get("OLLAMA_URL", "http://localhost:11434")


class OllamaEmbeddingClient:
    """Thin wrapper around Ollama's REST embeddings endpoint.

    Only imported/instantiated when the caller does not inject a fake client.
    Uses stdlib ``urllib`` so no third-party dependency is needed at import time.
    """

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model or _default_model()
        self.base_url = (base_url or _default_url()).rstrip("/")

    def __call__(self, model: str, text: str) -> list[float]:
        import json
        import urllib.request

        payload = json.dumps({"model": model, "prompt": text}).encode()
        url = f"{self.base_url}/api/embeddings"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        return data["embedding"]


# ---------------------------------------------------------------------------
# Lazily-constructed singleton default client
# ---------------------------------------------------------------------------

_real_client: Optional[OllamaEmbeddingClient] = None


def _get_default_client() -> OllamaEmbeddingClient:
    global _real_client
    if _real_client is None:
        _real_client = OllamaEmbeddingClient()
    return _real_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

Client = Callable[[str, str], list[float]]


def embed(text: str, *, client: Optional[Client] = None) -> bytes:
    """Embed *text* (caption) and return float32 bytes.

    Parameters
    ----------
    text:
        The caption or document text to embed.
    client:
        Injectable embedding callable ``(model, text) -> list[float]``.
        Defaults to a real OllamaEmbeddingClient using env vars.
    """
    c = client if client is not None else _get_default_client()
    model = _default_model()
    floats = c(model, text)
    return _to_bytes(floats)


def embed_query(text: str, *, client: Optional[Client] = None) -> bytes:
    """Embed *text* (user query) and return float32 bytes.

    Identical model + serialization to :func:`embed` so multilingual queries
    match English captions in cosine-similarity search.

    Parameters
    ----------
    text:
        The search query (any language supported by bge-m3).
    client:
        Injectable embedding callable ``(model, text) -> list[float]``.
        Defaults to a real OllamaEmbeddingClient using env vars.
    """
    return embed(text, client=client)
