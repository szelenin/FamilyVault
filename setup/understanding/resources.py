"""resources — the automatic memory governor for the understanding-layer indexer.

The governor frees enough host RAM for the current indexing phase (photo or
video) by escalating through the least-disruptive remediation first, and undoes
exactly what it did when the phase finishes.

Escalation ladder (policy='auto', re-measuring after EACH step, stopping as soon
as `available_gb >= need_gb`):
    (a) unload Ollama models not required by this phase   (cheap, transparent)
    (b) stop Immich                                       (photo server offline)
    (c) stop OrbStack                                     (all containers offline)

Policies
--------
auto    do nothing if memory already ample (SC-008); otherwise climb the ladder.
force   always perform (a)+(b)+(c) regardless of memory.
never   perform only (a); never stop Immich/OrbStack. If still short of need_gb
        after unloading, raise InsufficientMemoryError.

Design rule: EVERY OS-touching operation is an injected dependency so the whole
module is unit-testable with fakes. The real defaults lazy-import psutil / use
urllib / subprocess INSIDE the function bodies — never at import time.
"""
from __future__ import annotations

import dataclasses
import json
import os


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class StoppedState:
    """Record of exactly what `free_for_phase` did, so `restore` undoes only that.

    Fields
    ------
    unloaded_models   Ollama model names we unloaded (informational; not restored
                      — Ollama lazy-loads them on the next request).
    immich_stopped    True iff this governor stopped Immich.
    orbstack_stopped  True iff this governor stopped OrbStack.
    """

    unloaded_models: list[str]
    immich_stopped: bool
    orbstack_stopped: bool


class InsufficientMemoryError(Exception):
    """Raised only under policy='never' when memory is still below need_gb
    after unloading non-required models (services must not be stopped)."""


# ---------------------------------------------------------------------------
# Pure helper (task T030)
# ---------------------------------------------------------------------------

def models_to_unload(loaded: list[str], required_ollama: list[str]) -> list[str]:
    """Return the currently-loaded Ollama models that are NOT required by the
    current phase, preserving `loaded` order.

    Matching is case-sensitive and exact. This is how the governor keeps only
    the current phase's models resident — anything loaded but not required is a
    candidate to unload.
    """
    required = set(required_ollama)
    return [m for m in loaded if m not in required]


# ---------------------------------------------------------------------------
# Default (real) seams — lazy imports inside the bodies only.
# ---------------------------------------------------------------------------

_OLLAMA_URL = "http://localhost:11434"


def _default_available_gb() -> float:
    import psutil  # lazy: never imported at module load / in tests

    return psutil.virtual_memory().available / 1e9


def _default_list_loaded() -> list[str]:
    import urllib.request  # lazy

    with urllib.request.urlopen(f"{_OLLAMA_URL}/api/ps", timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m["name"] for m in data.get("models", [])]


def _run(cmd: list[str], *, check: bool = True) -> None:
    """Run an external command. Service controls use check=True so a failure
    surfaces (CalledProcessError) instead of being silently swallowed — the
    original governor bug was believing a failed stop had succeeded."""
    import subprocess  # lazy

    subprocess.run(cmd, check=check)


def _immich_compose_file() -> str:
    """Absolute path to Immich's docker-compose.yml.

    Override with IMMICH_COMPOSE_FILE; defaults to the repo's
    setup/immich/docker-compose.yml resolved relative to this file (so it works
    regardless of the current working directory — the old relative default did not).
    """
    env = os.environ.get("IMMICH_COMPOSE_FILE")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))  # setup/understanding
    return os.path.normpath(os.path.join(here, "..", "immich", "docker-compose.yml"))


def _default_unload(model: str) -> None:
    # Best-effort (non-disruptive step); a failed unload isn't critical.
    _run(["ollama", "stop", model], check=False)


def _default_stop_immich() -> None:
    _run(["docker", "compose", "-f", _immich_compose_file(), "stop"])


def _default_start_immich() -> None:
    _run(["docker", "compose", "-f", _immich_compose_file(), "start"])


def _default_stop_orbstack() -> None:
    # OrbStack's CLI binary is `orb`; bare `orb stop` stops the whole service.
    _run(["orb", "stop"])


def _default_start_orbstack() -> None:
    _run(["orb", "start"])


# ---------------------------------------------------------------------------
# MemoryGovernor
# ---------------------------------------------------------------------------

class MemoryGovernor:
    """Frees RAM for the current phase via an escalation ladder, and restores
    exactly what it stopped afterward. All OS interactions are injectable."""

    def __init__(
        self,
        *,
        available_gb_fn=None,
        list_loaded_fn=None,
        unload_fn=None,
        stop_immich_fn=None,
        start_immich_fn=None,
        stop_orbstack_fn=None,
        start_orbstack_fn=None,
    ):
        self._available_gb = available_gb_fn or _default_available_gb
        self._list_loaded = list_loaded_fn or _default_list_loaded
        self._unload = unload_fn or _default_unload
        self._stop_immich = stop_immich_fn or _default_stop_immich
        self._start_immich = start_immich_fn or _default_start_immich
        self._stop_orbstack = stop_orbstack_fn or _default_stop_orbstack
        self._start_orbstack = start_orbstack_fn or _default_start_orbstack

    # -- internal ladder steps ------------------------------------------
    def _unload_non_required(self, required_models: dict) -> list[str]:
        required_ollama = required_models.get("ollama", [])
        loaded = self._list_loaded()
        to_unload = models_to_unload(loaded, required_ollama)
        for model in to_unload:
            self._unload(model)
        return to_unload

    # -- public API ------------------------------------------------------
    def free_for_phase(self, required_models: dict, *, policy: str = "auto", need_gb: float) -> StoppedState:
        if policy == "force":
            return self._free_force(required_models)
        if policy == "never":
            return self._free_never(required_models, need_gb)
        if policy == "auto":
            return self._free_auto(required_models, need_gb)
        raise ValueError(f"unknown policy {policy!r}; expected 'auto', 'force', or 'never'")

    def _free_auto(self, required_models: dict, need_gb: float) -> StoppedState:
        state = StoppedState(unloaded_models=[], immich_stopped=False, orbstack_stopped=False)

        # Step 0: ample memory → do nothing (SC-008). Don't even list models.
        if self._available_gb() >= need_gb:
            return state

        # If any step fails, undo what we already did before propagating, so a
        # failure never leaves Immich/OrbStack stopped.
        try:
            # (a) unload non-required ollama models, then re-measure.
            state.unloaded_models = self._unload_non_required(required_models)
            if self._available_gb() >= need_gb:
                return state

            # (b) stop Immich, then re-measure.
            self._stop_immich()
            state.immich_stopped = True
            if self._available_gb() >= need_gb:
                return state

            # (c) stop OrbStack (last resort).
            self._stop_orbstack()
            state.orbstack_stopped = True
            return state
        except Exception:
            self.restore(state)
            raise

    def _free_force(self, required_models: dict) -> StoppedState:
        state = StoppedState(unloaded_models=[], immich_stopped=False, orbstack_stopped=False)
        try:
            state.unloaded_models = self._unload_non_required(required_models)
            self._stop_immich()
            state.immich_stopped = True
            self._stop_orbstack()
            state.orbstack_stopped = True
            return state
        except Exception:
            self.restore(state)
            raise

    def _free_never(self, required_models: dict, need_gb: float) -> StoppedState:
        state = StoppedState(unloaded_models=[], immich_stopped=False, orbstack_stopped=False)

        # Ample already → do nothing.
        if self._available_gb() >= need_gb:
            return state

        # Only step (a) is permitted under 'never'.
        state.unloaded_models = self._unload_non_required(required_models)
        if self._available_gb() >= need_gb:
            return state

        raise InsufficientMemoryError(
            f"Only {self._available_gb():.1f} GB available after unloading non-required "
            f"models, but {need_gb:.1f} GB is required for this phase. policy='never' "
            f"forbids stopping Immich/OrbStack. Free memory manually, reduce the "
            f"workload, or rerun with policy='auto' (or 'force')."
        )

    def restore(self, state: StoppedState) -> None:
        """Restart exactly what was stopped, in dependency order: OrbStack (the
        runtime) must come up before Immich (which runs inside it). Unloaded
        models need no restore — Ollama lazy-loads them. Safe on an empty state.
        """
        if state.orbstack_stopped:
            self._start_orbstack()
        if state.immich_stopped:
            self._start_immich()
