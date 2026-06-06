import json
from types import SimpleNamespace
import agent as agent_mod


class _FakeClient:
    """Returns a tool call on the first turn, a final answer on the second."""
    def __init__(self):
        self.turns = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools):
        self.turns += 1
        if self.turns == 1:
            tc = SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(name="create_project",
                                         arguments=json.dumps({"title": "X", "request": "r"})),
            )
            msg = SimpleNamespace(role="assistant", content=None, tool_calls=[tc])
        else:
            msg = SimpleNamespace(role="assistant", content="Done — project created.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_loop_dispatches_then_finishes(monkeypatch):
    monkeypatch.setattr(agent_mod.registry, "dispatch",
                        lambda name, args: {"project_id": "p1"} if name == "create_project" else None)
    client = _FakeClient()
    answer, transcript = agent_mod.run_loop(client, "make a project", model="m", max_iters=5)
    assert "Done" in answer
    assert client.turns == 2
    # a tool result message was appended
    assert any(m.get("role") == "tool" for m in transcript)


def test_loop_respects_iteration_cap(monkeypatch):
    monkeypatch.setattr(agent_mod.registry, "dispatch", lambda name, args: {"x": 1})

    class _Loop:
        def __init__(self): self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._c))
        def _c(self, model, messages, tools):
            tc = SimpleNamespace(id="c", function=SimpleNamespace(name="get_project",
                                  arguments=json.dumps({"project_id": "p"})))
            msg = SimpleNamespace(role="assistant", content=None, tool_calls=[tc])
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    answer, _ = agent_mod.run_loop(_Loop(), "x", model="m", max_iters=3)
    assert "stopped" in answer.lower() or "max" in answer.lower()
