"""Provider-call limits and safe errors; no transmission or persistence."""

import logging
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from ontology_map.llm_config import (
    BASE_URL,
    MAX_INPUT_TOKENS,
    MAX_OUTPUT_TOKENS,
    MODEL_VERSION,
)

Role = Literal[
    "body",
    "generation",
    "claim_support",
    "meaning_support",
    "entity_resolution",
    "claim_duplicate",
]
# Uncached USD / million tokens, official Kimi International page, 2026-09-18.
# No cache discounts, vouchers or account balance are assumed.
RATES = {MODEL_VERSION: (Decimal("0.95"), Decimal("4.00"))}


@dataclass(frozen=True)
class CallLimits:
    max_input_tokens: int
    max_output_tokens: int
    max_request_bytes: int

    def __post_init__(self) -> None:
        if (
            type(self.max_input_tokens) is not int
            or not 0 < self.max_input_tokens <= MAX_INPUT_TOKENS
        ):
            raise ValueError("INVALID_INPUT_LIMIT")
        if (
            type(self.max_output_tokens) is not int
            or not 0 < self.max_output_tokens <= MAX_OUTPUT_TOKENS
            or type(self.max_request_bytes) is not int
            or self.max_request_bytes <= 0
        ):
            raise ValueError("INVALID_REQUEST_LIMIT")


@dataclass(frozen=True)
class CallRecord:
    role: Role
    model: str
    request_hash: str
    status: str
    input_tokens: int | None
    output_tokens: int | None
    reserved_usd: Decimal
    charged_upper_usd: Decimal
    elapsed_seconds: float


@dataclass
class Budget:
    max_calls: int
    max_usd: Decimal
    charged_upper_usd: Decimal = field(default=Decimal(0), init=False)
    records: list[CallRecord] = field(default_factory=list, init=False)
    stopped: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (
            type(self.max_calls) is not int
            or self.max_calls < 0
            or not self.max_usd.is_finite()
            or self.max_usd < 0
        ):
            raise ValueError("INVALID_BUDGET")

    def reserve(self, amount: Decimal) -> None:
        if self.stopped or len(self.records) >= self.max_calls:
            self.stopped = True
            raise CallFailed("CALL_LIMIT", fatal=True)
        if self.charged_upper_usd + amount > self.max_usd:
            self.stopped = True
            raise CallFailed("COST_LIMIT", fatal=True)
        self.charged_upper_usd += amount


class CallFailed(Exception):
    """Only an allowlisted code escapes; never use provider exception text."""

    def __init__(self, code: str, *, fatal: bool) -> None:
        super().__init__(code)
        self.code = code
        self.fatal = fatal


def validate_base_url(base_url: str) -> str:
    if base_url != BASE_URL:
        raise CallFailed("UNAPPROVED_ENDPOINT", fatal=True)
    return base_url


def token_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    input_rate, output_rate = RATES[model]
    return (input_rate * input_tokens + output_rate * output_tokens) / 1_000_000


def check_logging() -> None:
    # No LangChain callbacks/tracing are used by this HTTP transport. Still reject
    # an already-enabled legacy global debug/verbose configuration.
    globals_module = sys.modules.get("langchain_core.globals")
    if globals_module is not None and (
        getattr(globals_module, "get_debug")()
        or getattr(globals_module, "get_verbose")()
    ):
        raise CallFailed("UNSAFE_LOGGING_CONFIGURATION", fatal=True)
    for name in ("openai", "httpx", "httpcore", "langchain_core", "langsmith"):
        if logging.getLogger(name).isEnabledFor(logging.DEBUG):
            raise CallFailed("UNSAFE_LOGGING_CONFIGURATION", fatal=True)
