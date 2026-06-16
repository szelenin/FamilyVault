"""Unit tests for the automatic memory governor (tasks T029 + T032).

ALL OS-touching dependencies are injected as fakes. No real psutil, docker,
orbstack, ollama, subprocess, or network calls happen here.

A small stateful fake memory reader simulates "freeing" memory: it returns
successive available_gb values from a list, advancing one step each time the
governor re-measures. This lets us assert the escalation ladder re-measures
after each step and stops as soon as enough memory is available.
"""
import pytest

from caption.base import REQUIRED_MODELS
from resources import (
    MemoryGovernor,
    StoppedState,
    InsufficientMemoryError,
)


def make_mem_reader(values):
    """Return a () -> float that yields successive values, holding the last."""
    seq = list(values)
    state = {"i": 0}

    def reader():
        i = state["i"]
        if i < len(seq):
            state["i"] += 1
            return seq[i]
        return seq[-1]

    return reader


class Recorder:
    """Collects calls so tests can assert what the governor did and in what order."""

    def __init__(self, loaded=None):
        self.loaded = list(loaded or [])
        self.unloaded = []
        self.events = []  # ordered log of side-effect names

    # injectable seams ---------------------------------------------------
    def list_loaded(self):
        return list(self.loaded)

    def unload(self, model):
        self.unloaded.append(model)
        self.events.append(("unload", model))

    def stop_immich(self):
        self.events.append(("stop_immich", None))

    def start_immich(self):
        self.events.append(("start_immich", None))

    def stop_orbstack(self):
        self.events.append(("stop_orbstack", None))

    def start_orbstack(self):
        self.events.append(("start_orbstack", None))

    def names(self):
        return [e[0] for e in self.events]


def make_governor(mem_values, loaded=None):
    rec = Recorder(loaded=loaded)
    gov = MemoryGovernor(
        available_gb_fn=make_mem_reader(mem_values),
        list_loaded_fn=rec.list_loaded,
        unload_fn=rec.unload,
        stop_immich_fn=rec.stop_immich,
        start_immich_fn=rec.start_immich,
        stop_orbstack_fn=rec.stop_orbstack,
        start_orbstack_fn=rec.start_orbstack,
    )
    return gov, rec


PHOTO = REQUIRED_MODELS["photo"]


# ---------------------------------------------------------------------------
# StoppedState shape
# ---------------------------------------------------------------------------

class TestStoppedState:
    def test_default_empty_state(self):
        s = StoppedState(unloaded_models=[], immich_stopped=False, orbstack_stopped=False)
        assert s.unloaded_models == []
        assert s.immich_stopped is False
        assert s.orbstack_stopped is False


# ---------------------------------------------------------------------------
# policy='auto'
# ---------------------------------------------------------------------------

class TestAutoAmpleMemory:
    def test_does_nothing_when_already_enough(self):
        # SC-008: ample memory must not touch Immich or anything.
        gov, rec = make_governor([64.0], loaded=["qwen3-vl:8b", "extra:latest"])
        state = gov.free_for_phase(PHOTO, policy="auto", need_gb=16.0)
        assert state.unloaded_models == []
        assert state.immich_stopped is False
        assert state.orbstack_stopped is False
        assert rec.unloaded == []
        assert rec.events == []


class TestAutoEscalation:
    def test_enough_after_unload_only(self):
        # Start low (8), after unloading non-required models we have 20 >= 16.
        gov, rec = make_governor([8.0, 20.0], loaded=["qwen3-vl:8b", "bge-m3", "extra:latest"])
        state = gov.free_for_phase(PHOTO, policy="auto", need_gb=16.0)
        # only the non-required model unloaded
        assert state.unloaded_models == ["extra:latest"]
        assert state.immich_stopped is False
        assert state.orbstack_stopped is False
        assert rec.unloaded == ["extra:latest"]
        assert "stop_immich" not in rec.names()
        assert "stop_orbstack" not in rec.names()

    def test_stops_immich_when_unload_insufficient(self):
        # low (8) -> after unload still low (9) -> after immich enough (18)
        gov, rec = make_governor([8.0, 9.0, 18.0], loaded=["qwen3-vl:8b", "extra:latest"])
        state = gov.free_for_phase(PHOTO, policy="auto", need_gb=16.0)
        assert state.unloaded_models == ["extra:latest"]
        assert state.immich_stopped is True
        assert state.orbstack_stopped is False
        assert "stop_immich" in rec.names()
        assert "stop_orbstack" not in rec.names()

    def test_stops_orbstack_when_immich_insufficient(self):
        # low through unload + immich, only orbstack pushes us over.
        gov, rec = make_governor([8.0, 9.0, 10.0, 20.0], loaded=["qwen3-vl:8b", "extra:latest"])
        state = gov.free_for_phase(PHOTO, policy="auto", need_gb=16.0)
        assert state.unloaded_models == ["extra:latest"]
        assert state.immich_stopped is True
        assert state.orbstack_stopped is True
        assert rec.names() == ["unload", "stop_immich", "stop_orbstack"]

    def test_remeasures_and_stops_escalating_early(self):
        # After unload we are already over need; Immich must NOT be stopped.
        gov, rec = make_governor([5.0, 100.0, 100.0], loaded=["extra:latest"])
        state = gov.free_for_phase(PHOTO, policy="auto", need_gb=16.0)
        assert state.immich_stopped is False
        assert state.orbstack_stopped is False
        assert rec.names() == ["unload"]

    def test_no_nonrequired_models_escalates_straight_to_immich(self):
        # All loaded models are required → nothing to unload → escalate.
        gov, rec = make_governor([8.0, 8.0, 20.0], loaded=["qwen3-vl:8b", "bge-m3"])
        state = gov.free_for_phase(PHOTO, policy="auto", need_gb=16.0)
        assert state.unloaded_models == []
        assert state.immich_stopped is True
        assert rec.unloaded == []


# ---------------------------------------------------------------------------
# policy='force'
# ---------------------------------------------------------------------------

class TestForcePolicy:
    def test_stops_everything_regardless_of_high_memory(self):
        gov, rec = make_governor([200.0], loaded=["qwen3-vl:8b", "extra:latest"])
        state = gov.free_for_phase(PHOTO, policy="force", need_gb=16.0)
        assert state.unloaded_models == ["extra:latest"]
        assert state.immich_stopped is True
        assert state.orbstack_stopped is True
        assert rec.names() == ["unload", "stop_immich", "stop_orbstack"]


# ---------------------------------------------------------------------------
# policy='never'
# ---------------------------------------------------------------------------

class TestNeverPolicy:
    def test_only_unloads_and_never_touches_services(self):
        gov, rec = make_governor([8.0, 20.0], loaded=["qwen3-vl:8b", "extra:latest"])
        state = gov.free_for_phase(PHOTO, policy="never", need_gb=16.0)
        assert state.unloaded_models == ["extra:latest"]
        assert state.immich_stopped is False
        assert state.orbstack_stopped is False
        assert "stop_immich" not in rec.names()
        assert "stop_orbstack" not in rec.names()

    def test_raises_when_still_low_after_unload(self):
        gov, rec = make_governor([8.0, 9.0], loaded=["qwen3-vl:8b", "extra:latest"])
        with pytest.raises(InsufficientMemoryError):
            gov.free_for_phase(PHOTO, policy="never", need_gb=16.0)
        # services never touched even on failure
        assert "stop_immich" not in rec.names()
        assert "stop_orbstack" not in rec.names()

    def test_does_not_unload_when_already_enough(self):
        gov, rec = make_governor([64.0], loaded=["qwen3-vl:8b", "extra:latest"])
        state = gov.free_for_phase(PHOTO, policy="never", need_gb=16.0)
        assert state.unloaded_models == []
        assert rec.events == []


# ---------------------------------------------------------------------------
# restore()
# ---------------------------------------------------------------------------

class TestRestore:
    def test_empty_state_is_noop(self):
        gov, rec = make_governor([64.0])
        gov.restore(StoppedState(unloaded_models=[], immich_stopped=False, orbstack_stopped=False))
        assert rec.events == []

    def test_restarts_only_immich_when_only_immich_stopped(self):
        gov, rec = make_governor([64.0])
        gov.restore(StoppedState(unloaded_models=["x"], immich_stopped=True, orbstack_stopped=False))
        assert rec.names() == ["start_immich"]

    def test_restarts_only_orbstack_when_only_orbstack_stopped(self):
        gov, rec = make_governor([64.0])
        gov.restore(StoppedState(unloaded_models=[], immich_stopped=False, orbstack_stopped=True))
        assert rec.names() == ["start_orbstack"]

    def test_restarts_orbstack_before_immich_when_both_stopped(self):
        gov, rec = make_governor([64.0])
        gov.restore(StoppedState(unloaded_models=["x"], immich_stopped=True, orbstack_stopped=True))
        assert rec.names() == ["start_orbstack", "start_immich"]

    def test_does_not_restore_unloaded_models(self):
        # Unloaded models lazy-load on next request; restore must not reload them.
        gov, rec = make_governor([64.0])
        gov.restore(StoppedState(unloaded_models=["a", "b"], immich_stopped=False, orbstack_stopped=False))
        assert rec.events == []

    def test_roundtrip_auto_full_escalation(self):
        gov, rec = make_governor([8.0, 9.0, 10.0, 20.0], loaded=["qwen3-vl:8b", "extra:latest"])
        state = gov.free_for_phase(PHOTO, policy="auto", need_gb=16.0)
        gov.restore(state)
        # restore appended exactly the two start calls in dependency order
        assert rec.names()[-2:] == ["start_orbstack", "start_immich"]


# ---------------------------------------------------------------------------
# Regression: real default service commands must be correct for this host and
# must NOT silently swallow failures (the original governor bug).
# ---------------------------------------------------------------------------

class TestDefaultServiceCommands:
    def test_immich_container_filter_default_and_override(self, monkeypatch):
        import resources
        monkeypatch.delenv("IMMICH_CONTAINER_FILTER", raising=False)
        assert resources._immich_filter() == "name=immich"
        monkeypatch.setenv("IMMICH_CONTAINER_FILTER", "name=myimmich")
        assert resources._immich_filter() == "name=myimmich"

    def test_stop_immich_stops_running_containers_by_name(self, monkeypatch):
        import resources, subprocess
        calls = []

        class CP:
            def __init__(self, stdout=""):
                self.stdout = stdout

        def fake_run(cmd, **kw):
            calls.append((cmd, kw))
            return CP(stdout="c1\nc2\n") if cmd[:2] == ["docker", "ps"] else CP()

        monkeypatch.setattr(subprocess, "run", fake_run)
        resources._default_stop_immich()
        assert calls[0][0][:3] == ["docker", "ps", "-q"]      # list running immich
        assert "name=immich" in calls[0][0]
        assert calls[1][0] == ["docker", "stop", "c1", "c2"]  # stop them
        assert calls[1][1].get("check") is True

    def test_start_immich_starts_all_immich_containers(self, monkeypatch):
        import resources, subprocess
        calls = []

        class CP:
            def __init__(self, stdout=""):
                self.stdout = stdout

        def fake_run(cmd, **kw):
            calls.append((cmd, kw))
            return CP(stdout="c1\n") if cmd[:2] == ["docker", "ps"] else CP()

        monkeypatch.setattr(subprocess, "run", fake_run)
        resources._default_start_immich()
        assert calls[0][0][:3] == ["docker", "ps", "-aq"]     # includes stopped
        assert calls[1][0] == ["docker", "start", "c1"]

    def test_stop_orbstack_uses_orb_binary_and_check_true(self, monkeypatch):
        import resources, subprocess
        seen = {}
        monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: seen.update(cmd=cmd, kw=kw))
        resources._default_stop_orbstack()
        assert seen["cmd"] == ["orb", "stop"]
        assert seen["kw"].get("check") is True

    def test_start_orbstack_uses_orb_binary(self, monkeypatch):
        import resources, subprocess
        seen = {}
        monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: seen.update(cmd=cmd, kw=kw))
        resources._default_start_orbstack()
        assert seen["cmd"] == ["orb", "start"]


class TestEscalationFailureRestores:
    def test_auto_restores_immich_when_orbstack_stop_fails(self):
        import pytest
        from resources import MemoryGovernor

        events = []

        def boom():
            raise RuntimeError("orb missing")

        gov = MemoryGovernor(
            available_gb_fn=lambda: 1.0,                 # always low → full escalation
            list_loaded_fn=lambda: [],
            unload_fn=lambda m: None,
            stop_immich_fn=lambda: events.append("stop_immich"),
            start_immich_fn=lambda: events.append("start_immich"),
            stop_orbstack_fn=boom,                       # fails after Immich stopped
            start_orbstack_fn=lambda: events.append("start_orbstack"),
        )
        with pytest.raises(RuntimeError):
            gov.free_for_phase({"ollama": []}, policy="auto", need_gb=10.0)
        # Immich stopped then restored; OrbStack never successfully stopped → not started.
        assert "stop_immich" in events and "start_immich" in events
        assert "start_orbstack" not in events
