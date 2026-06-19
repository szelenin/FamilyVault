"""preflight — `doctor` environment readiness check for the indexer.

`doctor` is a fail-fast preflight run before any heavy work. It is scoped per
`--type`: a `photo` run must NOT require the video-only stack (MLX, ffmpeg,
scenedetect), so those checks are simply absent from a photo result. Each
failing check carries an *exact* remediation command in `Check.fix`.

Design — all environment probing is injected via :class:`DoctorEnv`, a bundle
of callables. The real probes built by :func:`default_env` lazy-import / use
urllib / subprocess / shutil INSIDE each callable body, never at import time,
so importing this module and running ``run_doctor`` against a fake env needs no
live services. The whole thing is intended to complete in seconds.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, List, Optional

from caption.base import REQUIRED_MODELS


# ---------------------------------------------------------------------------
# Result + injectable probe types
# ---------------------------------------------------------------------------

@dataclass
class Check:
    """One readiness check result.

    name : stable identifier (e.g. "immich", "ollama", "ffmpeg").
    ok   : whether the check passed.
    fix  : exact remediation command, shown to the user when ``not ok``.
    """

    name: str
    ok: bool
    fix: str = ""


@dataclass
class DoctorEnv:
    """Injectable environment probes. Real defaults are built by ``default_env``.

    Every field is a callable so tests can supply controlled values without any
    network / subprocess / import side effects.
    """

    ollama_models: Callable[[], List[str]]   # installed Ollama model names; raises if Ollama is down
    immich_ok: Callable[[], bool]            # Immich reachable + API key valid
    has_binary: Callable[[str], bool]        # shutil.which(name) is not None
    can_import: Callable[[str], bool]        # importlib can find the module
    mlx_model_cached: Callable[[], bool]     # MLX VLM weights available locally
    sqlite_writable: Callable[[], bool]      # index DB dir exists + writable
    free_gb: Callable[[], float]             # free space (GB) on the index/staging volume


# ---------------------------------------------------------------------------
# Check assembly
# ---------------------------------------------------------------------------

def _ollama_check(asset_type: str, env: DoctorEnv) -> Check:
    """Ollama up AND all required models for ``asset_type`` present.

    For 'all', require the union of photo + video Ollama models.
    """
    if asset_type == "all":
        required = list(
            dict.fromkeys(
                REQUIRED_MODELS["photo"]["ollama"] + REQUIRED_MODELS["video"]["ollama"]
            )
        )
    else:
        required = REQUIRED_MODELS[asset_type]["ollama"]

    try:
        installed = env.ollama_models()
    except Exception:
        return Check("ollama", ok=False, fix="Start Ollama: `ollama serve`")

    installed_set = set(installed)
    missing = [m for m in required if m not in installed_set]
    if missing:
        fixes = "; ".join(f"ollama pull {m}" for m in missing)
        return Check("ollama", ok=False, fix=fixes)
    return Check("ollama", ok=True)


def _always_checks(asset_type: str, env: DoctorEnv, min_free_gb: float) -> List[Check]:
    immich = Check(
        "immich",
        ok=bool(env.immich_ok()),
        fix=(
            "Start Immich and set the API key (see setup/immich); verify: "
            "curl -H 'x-api-key: <key>' http://localhost:2283/api/users/me"
        ),
    )
    sqlite = Check(
        "sqlite",
        ok=bool(env.sqlite_writable()),
        fix="Ensure the index dir exists and is writable (FAMILYVAULT_DB / config.sh INDEX_DB)",
    )
    disk = Check(
        "disk",
        ok=env.free_gb() >= min_free_gb,
        fix=f"Free up disk; need >= {min_free_gb} GB on the index/staging volume",
    )
    return [immich, sqlite, disk, _ollama_check(asset_type, env)]


def _video_checks(env: DoctorEnv) -> List[Check]:
    mlx_model = REQUIRED_MODELS["video"]["mlx"][0]
    return [
        Check("ffmpeg", ok=bool(env.has_binary("ffmpeg")), fix="brew install ffmpeg"),
        Check(
            "scenedetect",
            ok=bool(env.can_import("scenedetect")),
            fix="/opt/homebrew/bin/python3.13 -m pip install --break-system-packages scenedetect",
        ),
        Check(
            "mlx_vlm",
            ok=bool(env.can_import("mlx_vlm")),
            fix="/opt/homebrew/bin/python3.13 -m pip install --break-system-packages mlx-vlm",
        ),
        Check(
            "mlx_model",
            ok=bool(env.mlx_model_cached()),
            fix=(
                "Cache the MLX model: python3.13 -c "
                f"\"from mlx_vlm import load; load('{mlx_model}')\""
            ),
        ),
    ]


def run_doctor(
    asset_type: str,
    *,
    env: Optional[DoctorEnv] = None,
    min_free_gb: float = 10.0,
) -> List[Check]:
    """Return the scoped list of checks for ``asset_type``.

    asset_type in {'photo', 'video', 'all'}. Photo runs exclude the video-only
    checks (ffmpeg/scenedetect/mlx_vlm/mlx_model); video and all include them.
    """
    if asset_type not in ("photo", "video", "all"):
        raise ValueError(
            f"asset_type must be one of 'photo', 'video', 'all'; got {asset_type!r}"
        )
    if env is None:
        env = default_env()

    checks = _always_checks(asset_type, env, min_free_gb)
    if asset_type in ("video", "all"):
        checks.extend(_video_checks(env))
    return checks


def doctor_ok(checks: List[Check]) -> bool:
    """True iff every check passed (vacuously true for an empty list)."""
    return all(c.ok for c in checks)


# ---------------------------------------------------------------------------
# Real probes (lazy: nothing here runs until the callable is invoked)
# ---------------------------------------------------------------------------

def _real_ollama_models() -> List[str]:
    """GET {OLLAMA_URL}/api/tags and return installed model names.

    Raises on any connectivity/parse error so the caller treats it as "down".
    """
    import json
    from urllib.request import urlopen

    base = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    with urlopen(f"{base}/api/tags", timeout=3) as resp:  # noqa: S310 (trusted local URL)
        data = json.loads(resp.read().decode("utf-8"))
    return [m["name"] for m in data.get("models", [])]


def _real_immich_ok() -> bool:
    """True iff Immich /api/users/me returns 200 with the resolved API key."""
    from urllib.request import Request, urlopen

    try:
        import index_cli

        api_key = index_cli._resolve_api_key()
        base = os.environ.get("IMMICH_URL", "http://localhost:2283").rstrip("/")
        req = Request(f"{base}/api/users/me", headers={"x-api-key": api_key})
        with urlopen(req, timeout=3) as resp:  # noqa: S310 (trusted local URL)
            return resp.status == 200
    except Exception:
        return False


def _real_has_binary(name: str) -> bool:
    import shutil

    return shutil.which(name) is not None


def _real_can_import(module: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _real_mlx_model_cached() -> bool:
    """Best-effort: the MLX VLM weights are usable locally.

    Treat "mlx_vlm importable AND the model dir is present in the HF cache" as
    cached; fall back to import-only when the cache layout can't be inspected.
    """
    import importlib.util

    if importlib.util.find_spec("mlx_vlm") is None:
        return False

    model = REQUIRED_MODELS["video"]["mlx"][0]
    # HF caches as models--<org>--<name> under HF_HOME or ~/.cache/huggingface/hub.
    hf_home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    cache_dir = os.path.join(hf_home, "hub")
    slug = "models--" + model.replace("/", "--")
    if os.path.isdir(cache_dir):
        return os.path.isdir(os.path.join(cache_dir, slug))
    # Cache dir absent: be lenient — import works, let the run surface a miss.
    return True


def _real_sqlite_writable() -> bool:
    """True iff the index DB's parent dir exists (creatable) and is writable."""
    db_path = os.environ.get(
        "FAMILYVAULT_DB", os.path.expanduser("~/.familyvault/index/familyvault.db")
    )
    db_dir = os.path.dirname(db_path) or "."
    try:
        os.makedirs(db_dir, exist_ok=True)
    except OSError:
        return False
    return os.access(db_dir, os.W_OK)


def _real_free_gb() -> float:
    """Free space (GB) on the index/staging volume."""
    import shutil

    db_path = os.environ.get(
        "FAMILYVAULT_DB", os.path.expanduser("~/.familyvault/index/familyvault.db")
    )
    db_dir = os.path.dirname(db_path) or "."
    # Walk up to the nearest existing ancestor so disk_usage doesn't error.
    probe = db_dir
    while probe and not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    if not probe or not os.path.isdir(probe):
        probe = os.path.expanduser("~")
    return shutil.disk_usage(probe).free / (1024 ** 3)


def default_env() -> DoctorEnv:
    """Build a DoctorEnv wired to the real probes (each lazy-imports internally)."""
    return DoctorEnv(
        ollama_models=_real_ollama_models,
        immich_ok=_real_immich_ok,
        has_binary=_real_has_binary,
        can_import=_real_can_import,
        mlx_model_cached=_real_mlx_model_cached,
        sqlite_writable=_real_sqlite_writable,
        free_gb=_real_free_gb,
    )
