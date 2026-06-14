"""T005 — failing unit tests for the asset-status model (data-model.md state machine)."""
import pytest

from index.status import Status, can_transition, RETRYABLE


def test_enum_has_exactly_the_four_states():
    assert {s.value for s in Status} == {"pending", "done", "no_preview", "error"}


def test_status_values_are_strings():
    # Stored as TEXT in SQLite; the enum value must be the literal column value.
    assert Status.PENDING.value == "pending"
    assert Status.DONE.value == "done"
    assert Status.NO_PREVIEW.value == "no_preview"
    assert Status.ERROR.value == "error"


@pytest.mark.parametrize("target", [Status.DONE, Status.NO_PREVIEW, Status.ERROR])
def test_pending_may_transition_to_terminal_states(target):
    assert can_transition(Status.PENDING, target)


@pytest.mark.parametrize("src", [Status.ERROR, Status.NO_PREVIEW])
def test_retryable_states_may_return_to_pending(src):
    assert can_transition(src, Status.PENDING)
    assert src in RETRYABLE


def test_done_is_terminal_and_not_retryable():
    assert Status.DONE not in RETRYABLE
    assert not can_transition(Status.DONE, Status.PENDING)


def test_done_does_not_transition_onward():
    for target in (Status.NO_PREVIEW, Status.ERROR):
        assert not can_transition(Status.DONE, target)


def test_pending_cannot_self_loop_or_be_a_retry_target_from_pending():
    # Re-running an already-pending asset is a no-op transition, not a state change.
    assert not can_transition(Status.PENDING, Status.PENDING)
