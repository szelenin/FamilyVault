"""Unit tests for the pure model-lifecycle helper `models_to_unload` (task T030).

Pure function, no mocks, no system calls. Determines which currently-loaded
Ollama models should be unloaded so that only the current phase's required
models stay resident.
"""
from caption.base import REQUIRED_MODELS
from resources import models_to_unload


class TestModelsToUnloadBasic:
    def test_returns_loaded_not_in_required(self):
        loaded = ["qwen3-vl:8b", "bge-m3", "llama3:70b"]
        required = ["qwen3-vl:8b", "bge-m3"]
        assert models_to_unload(loaded, required) == ["llama3:70b"]

    def test_empty_loaded_returns_empty(self):
        assert models_to_unload([], ["bge-m3"]) == []

    def test_empty_required_unloads_everything(self):
        assert models_to_unload(["a", "b"], []) == ["a", "b"]

    def test_all_loaded_are_required_returns_empty(self):
        assert models_to_unload(["bge-m3", "qwen3-vl:8b"], ["qwen3-vl:8b", "bge-m3"]) == []

    def test_case_sensitive_exact_match(self):
        # "BGE-M3" != "bge-m3" → not required → unloaded
        assert models_to_unload(["BGE-M3"], ["bge-m3"]) == ["BGE-M3"]

    def test_preserves_loaded_order(self):
        loaded = ["z", "bge-m3", "a"]
        assert models_to_unload(loaded, ["bge-m3"]) == ["z", "a"]


class TestModelsToUnloadWithRequiredModelsManifest:
    def test_photo_phase_keeps_only_photo_models(self):
        # Loaded: photo models + the MLX/video VLM accidentally loaded + an extra.
        required_ollama = REQUIRED_MODELS["photo"]["ollama"]  # qwen3-vl:8b, bge-m3
        loaded = [
            "qwen3-vl:8b",
            "bge-m3",
            "mlx-community/Qwen3-VL-8B-Instruct-4bit",
            "some-extra:latest",
        ]
        result = models_to_unload(loaded, required_ollama)
        assert result == [
            "mlx-community/Qwen3-VL-8B-Instruct-4bit",
            "some-extra:latest",
        ]
        assert "qwen3-vl:8b" not in result
        assert "bge-m3" not in result

    def test_video_phase_unloads_photo_vlm_keeps_embedder(self):
        # In the video phase only bge-m3 is a required *ollama* model;
        # the photo VLM qwen3-vl:8b must be unloaded, bge-m3 kept.
        required_ollama = REQUIRED_MODELS["video"]["ollama"]  # bge-m3
        loaded = ["qwen3-vl:8b", "bge-m3"]
        result = models_to_unload(loaded, required_ollama)
        assert result == ["qwen3-vl:8b"]
        assert "bge-m3" not in result
