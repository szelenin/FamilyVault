"""Unit tests for caption.embed — multilingual bge-m3 embedder.

Tests use a fake client (no network/Ollama required).
Wire format: array('f', floats).tobytes() — matches index/db.py deserialization.
"""
import array

import pytest

from caption.embed import embed, embed_query


# ---------------------------------------------------------------------------
# Fake client helpers
# ---------------------------------------------------------------------------

FAKE_VECTOR = [0.1, 0.2, 0.3, 0.4, 0.5]
DEFAULT_MODEL = "bge-m3"


class FakeOllamaClient:
    """Records calls and returns a fixed vector."""

    def __init__(self, model=DEFAULT_MODEL, vector=None):
        self.model = model
        self.vector = vector or FAKE_VECTOR
        self.calls: list[tuple[str, str]] = []

    def __call__(self, model: str, text: str) -> list[float]:
        self.calls.append((model, text))
        return self.vector


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEmbed:
    def test_returns_bytes(self):
        """embed() returns bytes."""
        fake = FakeOllamaClient()
        result = embed("hello", client=fake)
        assert isinstance(result, bytes)

    def test_bytes_deserializes_to_correct_floats(self):
        """Deserialized bytes equal the floats returned by the fake client."""
        fake = FakeOllamaClient()
        result = embed("hello", client=fake)
        arr = array.array("f")
        arr.frombytes(result)
        # Compare element-by-element with float32 tolerance
        assert len(arr) == len(FAKE_VECTOR)
        for got, expected in zip(arr, FAKE_VECTOR):
            assert abs(got - expected) < 1e-5, f"got {got}, expected {expected}"

    def test_wire_format_is_array_f(self):
        """Bytes must be exactly array('f', floats).tobytes() — the db.py contract."""
        fake = FakeOllamaClient()
        result = embed("hello", client=fake)
        expected = array.array("f", FAKE_VECTOR).tobytes()
        assert result == expected

    def test_fake_client_called_with_model_and_text(self):
        """The injected client is called with the configured model and the input text."""
        fake = FakeOllamaClient()
        embed("hello world", client=fake)
        assert len(fake.calls) == 1
        model_arg, text_arg = fake.calls[0]
        assert model_arg == DEFAULT_MODEL
        assert text_arg == "hello world"

    def test_embed_query_same_bytes_as_embed(self):
        """embed_query uses same model + serialization as embed."""
        text = "search query"
        fake1 = FakeOllamaClient()
        fake2 = FakeOllamaClient()
        result_embed = embed(text, client=fake1)
        result_query = embed_query(text, client=fake2)
        assert result_embed == result_query

    def test_embed_query_called_with_model_and_text(self):
        """embed_query calls the client with the correct model and text."""
        fake = FakeOllamaClient()
        embed_query("что случилось", client=fake)
        assert len(fake.calls) == 1
        model_arg, text_arg = fake.calls[0]
        assert model_arg == DEFAULT_MODEL
        assert text_arg == "что случилось"

    def test_non_ascii_cyrillic_passthrough(self):
        """A Cyrillic string is passed through to the client unchanged."""
        cyrillic = "красивый закат над морем"
        fake = FakeOllamaClient()
        result = embed(cyrillic, client=fake)
        # client received the unmodified Cyrillic text
        assert fake.calls[0][1] == cyrillic
        # result is valid serialized vector
        arr = array.array("f")
        arr.frombytes(result)
        assert len(arr) == len(FAKE_VECTOR)

    def test_no_network_when_client_injected(self):
        """When a client is injected, no real Ollama connection is made.

        This test passes with zero network access because the fake client
        never touches the wire. If the implementation ever falls back to a
        real client despite injection, the fake's call list would be empty
        and the return type assertion would fail or an actual network error
        would surface.
        """
        fake = FakeOllamaClient()
        result = embed("network test", client=fake)
        # Only the fake was called — no default client constructed
        assert fake.calls == [("bge-m3", "network test")]
        assert isinstance(result, bytes)
