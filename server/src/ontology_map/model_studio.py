"""The fixed Model Studio call boundary; no task persistence or retry scheduler."""

import json
import logging
import re
from contextvars import Context
from dataclasses import dataclass, field
from decimal import Decimal
from time import monotonic
from typing import TYPE_CHECKING, Literal

import httpx
from langchain_core.globals import get_debug, get_verbose
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langsmith import tracing_context
from pydantic import BaseModel, SecretStr, ValidationError

if TYPE_CHECKING:
    from ontology_map.pilot_budget import PilotBudget

FLASH = "qwen3.7-flash-2026-07-15"
PLUS = "qwen3.7-plus-2026-05-26"
Role = Literal[
    "body",
    "generation",
    "claim_support",
    "meaning_support",
    "entity_resolution",
    "claim_duplicate",
]

# Singapore list-price upper tiers, checked 2026-09-10. No cache/promo credit.
# Reserve the entire documented 1M input ceiling, not a guessed tokenizer count.
MAX_INPUT_TOKENS = 1_000_000
RATES = {
    FLASH: (Decimal("0.2"), Decimal("0.8")),
    PLUS: (Decimal("1.2"), Decimal("4.8")),
}


@dataclass(frozen=True)
class CallLimits:
    max_input_tokens: int
    max_output_tokens: int
    max_request_bytes: int

    def __post_init__(self) -> None:
        if not 0 < self.max_input_tokens <= MAX_INPUT_TOKENS:
            raise ValueError("INVALID_INPUT_LIMIT")
        if not 0 < self.max_output_tokens <= 32_768 or self.max_request_bytes <= 0:
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
        if self.max_calls < 0 or not self.max_usd.is_finite() or self.max_usd < 0:
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
    def __init__(self, code: str, *, fatal: bool) -> None:
        super().__init__(code)
        self.code = code
        self.fatal = fatal


def validate_base_url(base_url: str) -> str:
    if not re.fullmatch(
        r"https://[a-z0-9]+(?:-[a-z0-9]+)*\.ap-southeast-1\.maas\.aliyuncs\.com"
        r"/compatible-mode/v1",
        base_url,
    ):
        raise CallFailed("UNAPPROVED_ENDPOINT", fatal=True)
    return base_url


def token_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    input_rate, output_rate = RATES[model]
    return (input_rate * input_tokens + output_rate * output_tokens) / 1_000_000


def _check_logging() -> None:
    if get_debug() or get_verbose():
        raise CallFailed("UNSAFE_LOGGING_CONFIGURATION", fatal=True)
    for name in ("openai", "httpx", "httpcore", "langchain_core", "langsmith"):
        if logging.getLogger(name).isEnabledFor(logging.DEBUG):
            raise CallFailed("UNSAFE_LOGGING_CONFIGURATION", fatal=True)


def _usage(raw: AIMessage, limits: CallLimits) -> tuple[int, int]:
    usage = raw.usage_metadata
    if not usage:
        raise CallFailed("USAGE_UNKNOWN", fatal=True)
    input_tokens, output_tokens = usage["input_tokens"], usage["output_tokens"]
    if type(input_tokens) is not int or type(output_tokens) is not int:
        raise CallFailed("USAGE_UNKNOWN", fatal=True)
    if usage["total_tokens"] != input_tokens + output_tokens:
        raise CallFailed("USAGE_UNKNOWN", fatal=True)
    if not 0 < input_tokens <= limits.max_input_tokens:
        raise CallFailed("INPUT_TOKEN_LIMIT", fatal=True)
    if not 0 <= output_tokens <= limits.max_output_tokens:
        raise CallFailed("OUTPUT_TOKEN_LIMIT", fatal=True)
    return input_tokens, output_tokens


def _checked_raw(response: dict[str, object], model: str) -> AIMessage:
    raw = response.get("raw")
    if not isinstance(raw, AIMessage):
        raise CallFailed("RESPONSE_UNKNOWN", fatal=True)
    if raw.response_metadata.get("model_name") != model:
        raise CallFailed("MODEL_MISMATCH", fatal=True)
    return raw


class ModelStudio:
    """One sequential execution's clients and budget. Not shared across workers."""

    def __init__(
        self,
        api_key: SecretStr,
        budget: Budget,
        *,
        base_url: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = validate_base_url(base_url)
        self.budget = budget
        self._request_limit = 0
        self._request_sent = False
        self._request_hash = ""
        self._request_error: str | None = None
        self._pilot_required = not isinstance(transport, httpx.MockTransport)
        self._pilot_for_request: PilotBudget | None = None
        self._pilot_reservation: int | None = None
        self._http = httpx.Client(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=60,
            event_hooks={"request": [self._check_request]},
        )
        self._models = {
            model: ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=self._base_url,
                http_client=self._http,
                max_retries=0,
                timeout=60,
                temperature=0,
                streaming=False,
                stream_usage=False,
                use_responses_api=False,
                cache=False,
                verbose=False,
                callbacks=[],
            )
            for model in (FLASH, PLUS)
        }

    def close(self) -> None:
        self._http.close()

    def _check_request(self, request: httpx.Request) -> None:
        from ontology_map.pilot_budget import request_digest

        if str(request.url) != self._base_url + "/chat/completions":
            self._request_error = "ENDPOINT_CONTRACT_ERROR"
            if self._pilot_for_request is not None:
                self._pilot_for_request.stop()
            raise CallFailed("ENDPOINT_CONTRACT_ERROR", fatal=True)
        if len(request.content) > self._request_limit:
            self._request_error = "REQUEST_SIZE_LIMIT"
            if self._pilot_for_request is not None:
                self._pilot_for_request.stop()
            raise CallFailed("REQUEST_SIZE_LIMIT", fatal=True)
        if self._request_sent:
            self._request_error = "UNEXPECTED_RETRY"
            if self._pilot_for_request is not None:
                self._pilot_for_request.stop()
            raise CallFailed("UNEXPECTED_RETRY", fatal=True)
        try:
            request_hash = request_digest(request)
        except BaseException:
            if self._pilot_for_request is not None:
                self._pilot_for_request.stop()
            raise
        if self._pilot_for_request is not None:
            self._pilot_reservation = self._pilot_for_request.reserve(
                self._request_model, self._request_limits, request_hash
            )
        self._request_sent = True
        self._request_hash = request_hash

    def call[T: BaseModel](
        self,
        role: Role,
        prompt: str,
        payload: BaseModel,
        schema: type[T],
        limits: CallLimits,
    ) -> T:
        """Return only validated data; exceptions and raw provider data never escape."""
        if role not in (
            "body",
            "generation",
            "claim_support",
            "meaning_support",
            "entity_resolution",
            "claim_duplicate",
        ):
            raise CallFailed("UNKNOWN_ROLE", fatal=True)
        _check_logging()
        from ontology_map.pilot_budget import current_pilot

        pilot = current_pilot(required=self._pilot_required)
        # A clean context also excludes callbacks inherited from an outer LC chain.
        return Context().run(self._call, role, prompt, payload, schema, limits, pilot)

    def _confirm_pilot_usage(
        self,
        pilot: PilotBudget | None,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> bool:
        if pilot is None or self._pilot_reservation is None:
            return False
        pilot.confirm(self._pilot_reservation, model, input_tokens, output_tokens)
        return True

    def _stop_unconfirmed_pilot(
        self, pilot: PilotBudget | None, confirmed: bool
    ) -> None:
        if pilot is not None and self._pilot_reservation is not None and not confirmed:
            pilot.stop()

    def _call[T: BaseModel](
        self,
        role: Role,
        prompt: str,
        payload: BaseModel,
        schema: type[T],
        limits: CallLimits,
        pilot: PilotBudget | None,
    ) -> T:
        from ontology_map.pilot_budget import PilotBudgetError

        model = FLASH if role in ("body", "generation") else PLUS
        messages = [("system", prompt), ("human", payload.model_dump_json())]
        # Binding kwargs to the outer RunnableParallel drops provider options.
        configured = self._models[model].model_copy(
            update={
                "extra_body": {
                    "enable_thinking": False,
                    "max_tokens": limits.max_output_tokens,
                }
            }
        )
        runnable = configured.with_structured_output(
            schema.model_json_schema(),
            method="json_schema",
            strict=True,
            include_raw=True,
        )
        # Include the schema in the byte budget, not just the user text.
        request_text = json.dumps(
            [messages, schema.model_json_schema()], ensure_ascii=False, sort_keys=True
        )
        if len(request_text.encode("utf-8")) > limits.max_request_bytes:
            raise CallFailed("REQUEST_SIZE_LIMIT", fatal=True)
        reservation = token_cost(model, MAX_INPUT_TOKENS, limits.max_output_tokens)
        self.budget.reserve(reservation)
        self._pilot_for_request = pilot
        self._pilot_reservation = None
        self._request_model = model
        self._request_limits = limits
        self._request_sent = False
        self._request_error = None
        self._request_limit = limits.max_request_bytes
        started = monotonic()
        input_tokens = output_tokens = None
        charged = reservation
        status = "RESPONSE_UNKNOWN"
        pilot_confirmed = False
        try:
            with tracing_context(enabled=False, parent=False):
                response = runnable.invoke(messages, config={"callbacks": []})
            raw = _checked_raw(response, model)
            input_tokens, output_tokens = _usage(raw, limits)
            pilot_confirmed = self._confirm_pilot_usage(
                pilot, model, input_tokens, output_tokens
            )
            charged = token_cost(model, input_tokens, output_tokens)
            if raw.response_metadata.get("finish_reason") != "stop":
                raise CallFailed("OUTPUT_CONTRACT_ERROR", fatal=False)
            if not isinstance(raw.content, str) or raw.tool_calls:
                raise CallFailed("OUTPUT_CONTRACT_ERROR", fatal=False)
            result = schema.model_validate_json(raw.content, strict=True)
            status = "SUCCESS"
            return result
        except ValidationError:
            unknown_usage = input_tokens is None
            status = "RESPONSE_UNKNOWN" if unknown_usage else "OUTPUT_CONTRACT_ERROR"
            self.budget.stopped = unknown_usage
            raise CallFailed(status, fatal=unknown_usage) from None
        except CallFailed as error:
            status = error.code
            self.budget.stopped = error.fatal
            raise
        except PilotBudgetError:
            self.budget.stopped = True
            raise
        except Exception:
            # Provider errors may contain request/response bodies and credentials.
            self.budget.stopped = True
            status = self._request_error or status
            raise CallFailed(status, fatal=True) from None
        finally:
            self._stop_unconfirmed_pilot(pilot, pilot_confirmed)
            if self._request_sent:
                self.budget.charged_upper_usd += charged - reservation
                self.budget.records.append(
                    CallRecord(
                        role,
                        model,
                        self._request_hash,
                        status,
                        input_tokens,
                        output_tokens,
                        reservation,
                        charged,
                        monotonic() - started,
                    )
                )
            else:
                self.budget.charged_upper_usd -= reservation
