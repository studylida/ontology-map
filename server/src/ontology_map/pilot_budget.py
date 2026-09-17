"""Private, single-process paid-send cap for one explicitly approved pilot."""

import fcntl
import json
import os
import re
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from ontology_map.model_studio import MAX_INPUT_TOKENS, RATES, CallLimits, token_cost


class PilotBudgetError(RuntimeError):
    """Stop application sequencing without recording a provider outcome."""


_active: ContextVar["PilotBudget | None"] = ContextVar("pilot_budget", default=None)


def current_pilot(*, required: bool) -> "PilotBudget | None":
    pilot = _active.get()
    if pilot is None and required:
        raise PilotBudgetError("PILOT_BUDGET_REQUIRED")
    return pilot


class PilotBudget:
    """One new 0600 file per pilot; an existing file forbids automatic resume."""

    def __init__(
        self, pilot_id: str, max_calls: int, max_usd: Decimal, path: Path
    ) -> None:
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", pilot_id)
            or type(max_calls) is not int
            or max_calls <= 0
            or not isinstance(max_usd, Decimal)
            or not max_usd.is_finite()
            or max_usd <= 0
            or not path.is_absolute()
        ):
            raise PilotBudgetError("INVALID_PILOT_BUDGET")
        self.pilot_id = pilot_id
        self.max_calls = max_calls
        self.max_usd = max_usd
        self.path = path
        self.stopped = False
        self.calls = 0
        self.charged_upper_usd = Decimal(0)
        self._estimates: dict[int, tuple[str, int, Decimal]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._fd = -1
        try:
            self._fd = os.open(
                path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
            )
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._append(
                {
                    "version": 1,
                    "pilot_id": pilot_id,
                    "max_calls": max_calls,
                    "max_usd": str(max_usd),
                }
            )
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except (OSError, PilotBudgetError) as error:
            self.stopped = True
            if self._fd >= 0:
                os.close(self._fd)
                self._fd = -1
            raise PilotBudgetError("PILOT_FILE_UNAVAILABLE") from error

    def _append(self, event: dict[str, object]) -> None:
        data = (
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        try:
            if os.write(self._fd, data) != len(data):
                raise OSError("short pilot ledger write")
            os.fsync(self._fd)
        except OSError as error:
            self.stopped = True
            raise PilotBudgetError("PILOT_FILE_WRITE_FAILED") from error

    @contextmanager
    def activate(self) -> Iterator[None]:
        with self._lock:
            if self.stopped or self._fd < 0:
                raise PilotBudgetError("PILOT_STOPPED")
            if self._running:
                self.stopped = True
                raise PilotBudgetError("PILOT_CONCURRENT_RUN")
            self._running = True
        token = _active.set(self)
        try:
            yield
        except BaseException:
            self.stopped = True
            raise
        finally:
            _active.reset(token)
            with self._lock:
                self._running = False

    def reserve(self, model: str, limits: CallLimits) -> int:
        with self._lock:
            if self.stopped or self._fd < 0:
                raise PilotBudgetError("PILOT_STOPPED")
            if model not in RATES:
                self.stopped = True
                raise PilotBudgetError("PILOT_MODEL_UNPRICED")
            estimate = token_cost(model, MAX_INPUT_TOKENS, limits.max_output_tokens)
            if (
                self.calls >= self.max_calls
                or self.charged_upper_usd + estimate > self.max_usd
            ):
                self.stopped = True
                raise PilotBudgetError("PILOT_LIMIT_REACHED")
            sequence = self.calls + 1
            self._append(
                {
                    "kind": "reserved",
                    "sequence": sequence,
                    "model": model,
                    "estimated_upper_usd": str(estimate),
                }
            )
            self.calls = sequence
            self.charged_upper_usd += estimate
            self._estimates[sequence] = (model, limits.max_output_tokens, estimate)
            return sequence

    def confirm(
        self, sequence: int, model: str, input_tokens: int, output_tokens: int
    ) -> None:
        with self._lock:
            if self.stopped or sequence not in self._estimates:
                raise PilotBudgetError("PILOT_STOPPED")
            reserved_model, max_output, estimate = self._estimates[sequence]
            if (
                model != reserved_model
                or type(input_tokens) is not int
                or type(output_tokens) is not int
                or not 0 < input_tokens <= MAX_INPUT_TOKENS
                or not 0 <= output_tokens <= max_output
            ):
                self.stopped = True
                raise PilotBudgetError("PILOT_USAGE_INVALID")
            actual = token_cost(model, input_tokens, output_tokens)
            if actual > estimate:
                self.stopped = True
                raise PilotBudgetError("PILOT_USAGE_EXCEEDS_RESERVATION")
            self._append(
                {
                    "kind": "confirmed",
                    "sequence": sequence,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "charged_upper_usd": str(actual),
                }
            )
            self.charged_upper_usd += actual - estimate
            del self._estimates[sequence]

    def stop(self) -> None:
        self.stopped = True

    def require_active(self) -> None:
        if self.stopped or self._fd < 0:
            raise PilotBudgetError("PILOT_STOPPED")

    def close(self) -> None:
        self.stopped = True
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1
