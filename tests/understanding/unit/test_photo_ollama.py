"""Unit tests for caption.photo_ollama — Ollama qwen3-vl:8b photo captioner.

All tests use a fake injected client; no network, no Ollama process required.

Model reply contract under test:
    JSON string: {"caption": "<english text>", "ocr_text": "<verbatim on-screen text>"}
    Both fields are optional in the response — graceful degradation tested here.

Fake client signature:
    client(model: str, image_path: str) -> str
    Returns the raw model response string (same as the real Ollama chat response).
"""
import json
import pytest

from caption.base import CaptionResult
from caption.photo_ollama import PhotoOllamaCaptioner, CaptionError


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_fake_client(response: str | Exception):
    """Return a callable fake that either returns a string or raises."""
    calls = []

    def fake_client(model: str, image_path: str) -> str:
        calls.append({"model": model, "image_path": image_path})
        if isinstance(response, Exception):
            raise response
        return response

    fake_client.calls = calls
    return fake_client


def _json_response(caption: str, ocr_text: str) -> str:
    return json.dumps({"caption": caption, "ocr_text": ocr_text})


# ---------------------------------------------------------------------------
# T014 — Normal happy-path
# ---------------------------------------------------------------------------

class TestNormalResponse:
    def test_returns_caption_result_instance(self):
        fake = _make_fake_client(_json_response("A family barbecue in the backyard.", ""))
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/photo.jpg"], is_video=False)
        assert isinstance(result, CaptionResult)

    def test_caption_matches_model_response(self):
        fake = _make_fake_client(_json_response("A family barbecue in the backyard.", ""))
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/photo.jpg"], is_video=False)
        assert result.caption == "A family barbecue in the backyard."

    def test_model_field_is_qwen3_vl(self):
        fake = _make_fake_client(_json_response("Children playing at the park.", ""))
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/photo.jpg"], is_video=False)
        assert result.model == "qwen3-vl:8b"

    def test_segments_is_none_for_photos(self):
        fake = _make_fake_client(_json_response("A birthday celebration.", ""))
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/photo.jpg"], is_video=False)
        assert result.segments is None

    def test_no_ocr_text_returns_empty_string(self):
        fake = _make_fake_client(_json_response("A mountain landscape at sunset.", ""))
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/photo.jpg"], is_video=False)
        assert result.ocr_text == ""


# ---------------------------------------------------------------------------
# T014 — OCR text handling
# ---------------------------------------------------------------------------

class TestOcrText:
    def test_ocr_text_returned_when_present(self):
        fake = _make_fake_client(_json_response("A storefront.", "OPEN\nDaily 9-5"))
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/shop.jpg"], is_video=False)
        assert "OPEN" in result.ocr_text
        assert "Daily 9-5" in result.ocr_text

    def test_duplicate_lines_are_deduped(self):
        # Same line appearing twice in ocr_text → appears once in result
        fake = _make_fake_client(
            _json_response("A store sign.", "OPEN\nOPEN\nDaily 9-5\nDaily 9-5")
        )
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/shop.jpg"], is_video=False)
        lines = result.ocr_text.splitlines()
        assert lines.count("OPEN") == 1
        assert lines.count("Daily 9-5") == 1

    def test_duplicate_entire_ocr_block_deduplicated(self):
        # Exact same text repeated → single occurrence
        fake = _make_fake_client(
            _json_response("Menu board.", "Burger $5\nBurger $5\nFries $3\nFries $3")
        )
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/menu.jpg"], is_video=False)
        lines = result.ocr_text.splitlines()
        assert lines.count("Burger $5") == 1
        assert lines.count("Fries $3") == 1

    def test_no_text_in_response_gives_empty_string(self):
        # Model explicitly returns empty ocr_text
        fake = _make_fake_client(_json_response("A forest path.", ""))
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/forest.jpg"], is_video=False)
        assert result.ocr_text == ""


# ---------------------------------------------------------------------------
# T018 — Client injection and call verification
# ---------------------------------------------------------------------------

class TestClientInjection:
    def test_fake_client_is_called_with_image_path(self):
        fake = _make_fake_client(_json_response("A portrait.", ""))
        cap = PhotoOllamaCaptioner(client=fake)
        cap.caption(["/tmp/portrait.jpg"], is_video=False)
        assert len(fake.calls) == 1
        assert fake.calls[0]["image_path"] == "/tmp/portrait.jpg"

    def test_fake_client_is_called_with_model_name(self):
        fake = _make_fake_client(_json_response("A portrait.", ""))
        cap = PhotoOllamaCaptioner(client=fake)
        cap.caption(["/tmp/portrait.jpg"], is_video=False)
        assert fake.calls[0]["model"] == "qwen3-vl:8b"

    def test_no_network_call_when_client_injected(self):
        # Verifies by side-effect: if the real client were used, it would try
        # to connect and either succeed (bad) or raise ConnectionRefusedError (bad).
        # The fake succeeds instantly — test passes → no network used.
        fake = _make_fake_client(_json_response("A desk photo.", ""))
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/desk.jpg"], is_video=False)
        assert result.caption == "A desk photo."


# ---------------------------------------------------------------------------
# T018 — Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_transport_error_raises_caption_error(self):
        fake = _make_fake_client(ConnectionError("Ollama not running"))
        cap = PhotoOllamaCaptioner(client=fake)
        with pytest.raises(CaptionError):
            cap.caption(["/tmp/photo.jpg"], is_video=False)

    def test_malformed_json_raises_caption_error(self):
        fake = _make_fake_client("this is not json at all")
        cap = PhotoOllamaCaptioner(client=fake)
        with pytest.raises(CaptionError):
            cap.caption(["/tmp/photo.jpg"], is_video=False)

    def test_missing_caption_field_raises_caption_error(self):
        # JSON is valid but lacks a usable "caption" key
        fake = _make_fake_client(json.dumps({"ocr_text": "some text"}))
        cap = PhotoOllamaCaptioner(client=fake)
        with pytest.raises(CaptionError):
            cap.caption(["/tmp/photo.jpg"], is_video=False)

    def test_caption_error_is_not_swallowed(self):
        # Ensure the error propagates — captioner does NOT return a partial result
        fake = _make_fake_client(RuntimeError("GPU OOM"))
        cap = PhotoOllamaCaptioner(client=fake)
        raised = False
        try:
            cap.caption(["/tmp/photo.jpg"], is_video=False)
        except CaptionError:
            raised = True
        except Exception:
            pytest.fail("Expected CaptionError but got a different exception type")
        assert raised, "Expected CaptionError to be raised"

    def test_caption_error_contains_context(self):
        # CaptionError should carry some useful message
        fake = _make_fake_client(ConnectionError("Ollama not running"))
        cap = PhotoOllamaCaptioner(client=fake)
        with pytest.raises(CaptionError) as exc_info:
            cap.caption(["/tmp/photo.jpg"], is_video=False)
        assert str(exc_info.value)  # non-empty message


# ---------------------------------------------------------------------------
# T018 — Graceful degradation (missing optional ocr_text in response)
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    def test_missing_ocr_text_field_defaults_to_empty(self):
        # Valid JSON with caption but no ocr_text field
        fake = _make_fake_client(json.dumps({"caption": "A snowy mountain top."}))
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/snow.jpg"], is_video=False)
        assert result.caption == "A snowy mountain top."
        assert result.ocr_text == ""

    def test_null_ocr_text_treated_as_empty(self):
        # Model returns null for ocr_text → treat as ""
        fake = _make_fake_client(json.dumps({"caption": "Kids at the pool.", "ocr_text": None}))
        cap = PhotoOllamaCaptioner(client=fake)
        result = cap.caption(["/tmp/pool.jpg"], is_video=False)
        assert result.ocr_text == ""
