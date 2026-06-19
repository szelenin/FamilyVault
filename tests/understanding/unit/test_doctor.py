"""Unit tests for the doctor preflight (T035).

All environment probing is injected via a fake DoctorEnv so these tests need
NO live Immich/Ollama/ffmpeg/MLX and perform no real subprocess/network/imports.

Key behaviours under test:
  * scoping — photo runs must NOT include video-only checks; video/all do
  * per-check failures surface an exact remediation command in `fix`
  * doctor_ok is True only when every check passes
"""
from preflight import Check, DoctorEnv, doctor_ok, run_doctor
from caption.base import REQUIRED_MODELS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _good_env(**overrides):
    """A DoctorEnv whose probes all report a healthy environment.

    Override any single probe via kwargs to simulate a specific failure.
    """
    base = dict(
        ollama_models=lambda: ["qwen3-vl:8b", "bge-m3"],
        immich_ok=lambda: True,
        has_binary=lambda name: True,
        can_import=lambda module: True,
        mlx_model_cached=lambda: True,
        sqlite_writable=lambda: True,
        free_gb=lambda: 500.0,
    )
    base.update(overrides)
    return DoctorEnv(**base)


def _by_name(checks):
    return {c.name: c for c in checks}


VIDEO_ONLY = {"ffmpeg", "scenedetect", "mlx_vlm", "mlx_model"}


# ---------------------------------------------------------------------------
# Scoping
# ---------------------------------------------------------------------------

def test_photo_all_good_passes_and_excludes_video_checks():
    checks = run_doctor("photo", env=_good_env())
    assert doctor_ok(checks)
    names = {c.name for c in checks}
    # ALWAYS checks present
    assert {"immich", "sqlite", "disk", "ollama"} <= names
    # No video-only checks for a photo run (the core scoping rule)
    assert names.isdisjoint(VIDEO_ONLY)


def test_video_all_good_passes_and_includes_video_checks():
    checks = run_doctor("video", env=_good_env())
    assert doctor_ok(checks)
    names = {c.name for c in checks}
    assert {"immich", "sqlite", "disk", "ollama"} <= names
    assert VIDEO_ONLY <= names


def test_all_includes_everything():
    checks = run_doctor("all", env=_good_env())
    assert doctor_ok(checks)
    names = {c.name for c in checks}
    assert {"immich", "sqlite", "disk", "ollama"} <= names
    assert VIDEO_ONLY <= names


def test_all_requires_union_of_ollama_models():
    # bge-m3 present but qwen3-vl:8b (photo-only) missing → ollama fails for 'all'.
    env = _good_env(ollama_models=lambda: ["bge-m3"])
    checks = _by_name(run_doctor("all", env=env))
    assert checks["ollama"].ok is False
    assert "ollama pull qwen3-vl:8b" in checks["ollama"].fix


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def test_photo_missing_ollama_model():
    env = _good_env(ollama_models=lambda: ["bge-m3"])  # qwen3-vl:8b absent
    checks = _by_name(run_doctor("photo", env=env))
    assert checks["ollama"].ok is False
    assert "ollama pull qwen3-vl:8b" in checks["ollama"].fix
    assert doctor_ok(run_doctor("photo", env=env)) is False


def test_ollama_down_reports_serve_remediation():
    def _raise():
        raise ConnectionError("connection refused")

    env = _good_env(ollama_models=_raise)
    checks = _by_name(run_doctor("photo", env=env))
    assert checks["ollama"].ok is False
    assert "ollama serve" in checks["ollama"].fix


def test_video_missing_mlx_ollama_model():
    # video needs bge-m3 only on the ollama side; absent → fail.
    env = _good_env(ollama_models=lambda: ["qwen3-vl:8b"])
    checks = _by_name(run_doctor("video", env=env))
    assert checks["ollama"].ok is False
    assert "ollama pull bge-m3" in checks["ollama"].fix


# ---------------------------------------------------------------------------
# Always checks
# ---------------------------------------------------------------------------

def test_immich_down():
    env = _good_env(immich_ok=lambda: False)
    checks = _by_name(run_doctor("photo", env=env))
    assert checks["immich"].ok is False
    assert checks["immich"].fix  # has a remediation message
    assert "api-key" in checks["immich"].fix or "API key" in checks["immich"].fix


def test_sqlite_not_writable():
    env = _good_env(sqlite_writable=lambda: False)
    checks = _by_name(run_doctor("photo", env=env))
    assert checks["sqlite"].ok is False
    assert checks["sqlite"].fix


def test_disk_below_minimum():
    env = _good_env(free_gb=lambda: 3.0)
    checks = _by_name(run_doctor("photo", env=env, min_free_gb=10.0))
    assert checks["disk"].ok is False
    assert "10" in checks["disk"].fix


def test_disk_at_minimum_passes():
    env = _good_env(free_gb=lambda: 10.0)
    checks = _by_name(run_doctor("photo", env=env, min_free_gb=10.0))
    assert checks["disk"].ok is True


# ---------------------------------------------------------------------------
# Video-only check failures
# ---------------------------------------------------------------------------

def test_video_ffmpeg_missing():
    env = _good_env(has_binary=lambda name: name != "ffmpeg")
    checks = _by_name(run_doctor("video", env=env))
    assert checks["ffmpeg"].ok is False
    assert checks["ffmpeg"].fix == "brew install ffmpeg"
    assert doctor_ok(run_doctor("video", env=env)) is False


def test_video_scenedetect_missing():
    env = _good_env(can_import=lambda module: module != "scenedetect")
    checks = _by_name(run_doctor("video", env=env))
    assert checks["scenedetect"].ok is False
    assert "scenedetect" in checks["scenedetect"].fix


def test_video_mlx_vlm_missing():
    env = _good_env(can_import=lambda module: module != "mlx_vlm")
    checks = _by_name(run_doctor("video", env=env))
    assert checks["mlx_vlm"].ok is False
    assert "mlx-vlm" in checks["mlx_vlm"].fix


def test_video_mlx_model_not_cached():
    env = _good_env(mlx_model_cached=lambda: False)
    checks = _by_name(run_doctor("video", env=env))
    assert checks["mlx_model"].ok is False
    assert REQUIRED_MODELS["video"]["mlx"][0] in checks["mlx_model"].fix


# ---------------------------------------------------------------------------
# doctor_ok aggregation
# ---------------------------------------------------------------------------

def test_doctor_ok_true_only_when_all_pass():
    assert doctor_ok([Check("a", True), Check("b", True)]) is True
    assert doctor_ok([Check("a", True), Check("b", False)]) is False
    assert doctor_ok([]) is True


def test_default_env_constructs_callables():
    # Smoke: default_env() must build without touching real services.
    from preflight import default_env

    env = default_env()
    assert callable(env.ollama_models)
    assert callable(env.immich_ok)
    assert callable(env.has_binary)
    assert callable(env.can_import)
    assert callable(env.mlx_model_cached)
    assert callable(env.sqlite_writable)
    assert callable(env.free_gb)
