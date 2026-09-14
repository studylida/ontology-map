"""One durable product call: preflight, reservation, IO, terminal record.

Internal validators and Entity Resolution do not use this boundary. The caller
owns model_task creation, product validation and the final promotion transaction.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from ontology_map.db import model_tasks as tasks


class ConfirmedProviderFailure(Exception):
    """A classified provider outcome; never pass provider exception text."""

    def __init__(
        self, outcome: tasks.Outcome, *, transient: bool = False,
        retry_after: timedelta | None = None,
    ) -> None:
        if outcome == "SUCCESS" or outcome not in tasks.OUTCOMES:
            raise ValueError("INVALID_PROVIDER_FAILURE")
        super().__init__(outcome)
        self.outcome = outcome
        self.transient = transient
        self.retry_after = retry_after


class UncertainProviderFailure(RuntimeError):
    """Leave RESERVED intact; reclaim will close it UNKNOWN, with no fake attempt."""


@dataclass(frozen=True)
class CallResult[T]:
    status: str
    value: T | None = None


def execute_call[T](
    engine: Engine,
    lease: tasks.Lease,
    preflight: Callable[[], Callable[[], T]],
) -> CallResult[T]:
    """preflight returns the fully prepared single-send operation.

    SDK/HTTP automatic retries must be disabled by the adapter. A preflight
    exception propagates after deterministic failure is recorded, with no slot.
    Runtime payload is returned to the caller only and is never persisted here.
    """
    try:
        send = preflight()
    except Exception:
        with Session(engine) as session, session.begin():
            tasks.fail_execution(session, lease, transient=False)
        raise
    with Session(engine) as session, session.begin():
        slot = tasks.reserve_slot(session, lease)
    if slot is None:
        return CallResult("FINAL_FAILED")
    attempted_at = datetime.now(UTC)
    try:
        value = send()
    except ConfirmedProviderFailure as error:
        result = tasks.TerminalResult(
            error.outcome, attempted_at, error.outcome,
            error.transient, error.retry_after,
        )
        with Session(engine) as session, session.begin():
            status = tasks.record_terminal(session, slot, result)
        return CallResult(status)
    except Exception:
        # Unknown exceptions are not automatically invented PROVIDER_ERRORs.
        raise UncertainProviderFailure("UNCONFIRMED_PROVIDER_RESULT") from None
    with Session(engine) as session, session.begin():
        tasks.record_terminal(session, slot, tasks.TerminalResult("SUCCESS", attempted_at))
    return CallResult("RUNNING", value)
