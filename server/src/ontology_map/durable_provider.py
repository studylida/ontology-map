"""One durable product call: preflight, reservation, IO, terminal record.

Internal validators and Entity Resolution do not use this boundary. The caller
owns model_task creation, product validation and the final promotion transaction.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx
from openai import APIStatusError, APITimeoutError
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from ontology_map.db import model_tasks as tasks
from ontology_map.model_studio import CallFailed


class ConfirmedProviderFailure(Exception):
    """A classified provider outcome; never pass provider exception text."""

    def __init__(
        self,
        outcome: tasks.Outcome,
        *,
        transient: bool = False,
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


def _retry_after(value: str | None) -> timedelta | None:
    if value is None:
        return None
    try:
        seconds = float(value)
        if math.isfinite(seconds) and seconds >= 0:
            return timedelta(seconds=seconds)
        return None
    except ValueError, OverflowError:
        try:
            at = parsedate_to_datetime(value)
            if at.utcoffset() is None:
                return None
            return max(at - datetime.now(UTC), timedelta(0))
        except ValueError, TypeError, OverflowError:
            return None


def _http_failure(
    status: int, retry_after: str | None
) -> ConfirmedProviderFailure | None:
    if status in (401, 403):
        return ConfirmedProviderFailure("AUTHENTICATION_ERROR")
    if status == 429:
        return ConfirmedProviderFailure(
            "RATE_LIMITED",
            transient=True,
            retry_after=_retry_after(retry_after),
        )
    if status in (408, 504):
        return ConfirmedProviderFailure("TIMEOUT", transient=True)
    if 500 <= status < 600:
        return ConfirmedProviderFailure("PROVIDER_ERROR", transient=True)
    if 400 <= status < 500:
        return ConfirmedProviderFailure("INVALID_REQUEST")
    return None


def classify_provider_error(error: Exception) -> ConfirmedProviderFailure | None:
    """Classify only typed/allowlisted provider signals without storing bodies.

    None means an unconfirmed transmission/result, not an invented provider error.
    This common durable transport rule is independent of task-specific DTOs.
    """
    if isinstance(error, ConfirmedProviderFailure):
        return error
    if isinstance(error, (httpx.TimeoutException, APITimeoutError)):
        # A local timeout can follow a partial write or a lost reply. Only an
        # explicit provider 408/504 response is a confirmed timeout outcome.
        return None
    # Broad network/SDK connection errors may follow a partial send or lost reply.
    # Only ConnectError identifies failure to establish the HTTP connection.
    if isinstance(error, httpx.ConnectError):
        return ConfirmedProviderFailure("PROVIDER_ERROR", transient=True)
    if isinstance(error, (httpx.HTTPStatusError, APIStatusError)):
        return _http_failure(
            error.response.status_code, error.response.headers.get("Retry-After")
        )
    if isinstance(error, ValidationError):
        return ConfirmedProviderFailure("OUTPUT_CONTRACT_ERROR")
    if isinstance(error, CallFailed) and error.code == "OUTPUT_CONTRACT_ERROR":
        return ConfirmedProviderFailure("OUTPUT_CONTRACT_ERROR")
    return None


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
            error.outcome,
            attempted_at,
            error.outcome,
            error.transient,
            error.retry_after,
        )
        with Session(engine) as session, session.begin():
            status = tasks.record_terminal(session, slot, result)
        return CallResult(status)
    except Exception:
        # Unknown exceptions are not automatically invented PROVIDER_ERRORs.
        raise UncertainProviderFailure("UNCONFIRMED_PROVIDER_RESULT") from None
    with Session(engine) as session, session.begin():
        tasks.record_terminal(
            session, slot, tasks.TerminalResult("SUCCESS", attempted_at)
        )
    return CallResult("RUNNING", value)
