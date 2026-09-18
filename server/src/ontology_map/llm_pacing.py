"""Explicit, process-wide sequential pacing and caller-owned lease fences.

No account limits are inferred. No DB is imported, no reservations/retries are
created. A turn spans preflight/reservation/send; waiting precedes reservations.
Callers must acquire turns OUTSIDE transactions and supply short lease checks.
"""

import math
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic, sleep

from ontology_map.llm_contracts import CallFailed

_guard: ContextVar[Callable[[], None] | None] = ContextVar("llm_lease", default=None)
_pacer: ContextVar["ProcessPacer | None"] = ContextVar("llm_pacer", default=None)
_process_lock = threading.RLock()
_last_send: float | None = None


class ProcessPacer:
    """One interpreter only. Other processes/projects require operator coordination."""

    def __init__(
        self,
        min_interval_seconds: float,
        *,
        clock: Callable[[], float] = monotonic,
        wait: Callable[[float], None] = sleep,
    ) -> None:
        if not math.isfinite(min_interval_seconds) or min_interval_seconds < 0:
            raise ValueError("INVALID_PACING_INTERVAL")
        self.interval = min_interval_seconds
        self.clock = clock
        self.wait = wait
        self._local = threading.local()
        self._last: float | None = None

    def _previous_send(self) -> float | None:
        return _last_send if self.clock is monotonic else self._last

    @contextmanager
    def turn(self) -> Iterator[None]:
        with _process_lock:
            depth = getattr(self._local, "depth", 0)
            if depth == 0:
                last = self._previous_send()
                if last is not None:
                    remaining = last + self.interval - self.clock()
                    while remaining > 0:
                        self.wait(remaining)
                        remaining = last + self.interval - self.clock()
            check_lease()
            self._local.depth = depth + 1
            try:
                yield
            finally:
                self._local.depth = depth

    def mark_send(self) -> None:
        global _last_send
        self._last = self.clock()
        if self.clock is monotonic:
            _last_send = self._last


@contextmanager
def pacing_scope(pacer: ProcessPacer | None) -> Iterator[None]:
    """Application wiring owns the explicit interval; nested callers reuse it."""
    token = _pacer.set(pacer if pacer is not None else _pacer.get())
    try:
        yield
    finally:
        _pacer.reset(token)


@contextmanager
def provider_lease(check: Callable[[], None]) -> Iterator[None]:
    token = _guard.set(check)
    try:
        yield
    finally:
        _guard.reset(token)


def check_lease() -> None:
    guard = _guard.get()
    if guard is not None:
        guard()


def require_pacer(*, live: bool) -> None:
    pacer = _pacer.get()
    if live and (pacer is None or pacer.interval <= 0):
        raise CallFailed("PACING_REQUIRED", fatal=True)


@contextmanager
def provider_turn() -> Iterator[None]:
    pacer = _pacer.get()
    if pacer is None:
        yield
    else:
        with pacer.turn():
            yield


def mark_send() -> None:
    check_lease()
    pacer = _pacer.get()
    if pacer is not None:
        pacer.mark_send()
