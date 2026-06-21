"""Asset processing status model (data-model.md state machine).

States and legal transitions::

    pending ──caption+embed ok──▶ done
    pending ──no usable preview─▶ no_preview
    pending ──caption/model err─▶ error
    no_preview ──remediated + retry──▶ pending
    error      ──retry──────────────▶ pending

`done` is terminal. Re-indexing a `done` asset happens via the *plan* layer
(source_hash change / schema bump), not via a status transition.
"""
from enum import Enum


class Status(str, Enum):
    PENDING = "pending"
    DONE = "done"
    NO_PREVIEW = "no_preview"
    ERROR = "error"


# States a `retry` command may move back to PENDING for re-processing.
RETRYABLE = frozenset({Status.ERROR, Status.NO_PREVIEW})

# Forward transitions out of PENDING during a run.
_PROCESSING_TARGETS = frozenset({Status.DONE, Status.NO_PREVIEW, Status.ERROR})


def can_transition(src: Status, dst: Status) -> bool:
    """Return True if moving an asset from ``src`` to ``dst`` is legal."""
    if src is Status.PENDING:
        return dst in _PROCESSING_TARGETS
    if src in RETRYABLE:
        return dst is Status.PENDING
    # DONE is terminal.
    return False
