"""Kimi International JSON transport shared by all LLM operations.

Preparation finishes before reservation. Each operation sends once, without
redirects or retries. Callers own product validation and durable lifecycle.
"""

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import SecretStr

from ontology_map.llm_config import (
    BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    MODEL_VERSION,
    json_messages,
    request_options,
)
from ontology_map.llm_contracts import (
    CallFailed,
    CallLimits,
    check_logging,
    validate_base_url,
)

if TYPE_CHECKING:
    from ontology_map.pilot_budget import PilotBudget


def _integer(value: object) -> int | None:
    return value if type(value) is int else None


def _checked_usage(payload: dict[str, Any], limits: CallLimits) -> tuple[int, int]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise CallFailed("RESPONSE_UNKNOWN", fatal=True)
    input_tokens = _integer(usage.get("prompt_tokens"))
    output_tokens = _integer(usage.get("completion_tokens"))
    total_tokens = _integer(usage.get("total_tokens"))
    if input_tokens is None or output_tokens is None or total_tokens is None:
        raise CallFailed("RESPONSE_UNKNOWN", fatal=True)
    if (
        total_tokens != input_tokens + output_tokens
        or not 0 < input_tokens <= limits.max_input_tokens
        or not 0 <= output_tokens <= limits.max_output_tokens
    ):
        raise CallFailed("RESPONSE_UNKNOWN", fatal=True)
    return input_tokens, output_tokens


def _checked_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise CallFailed("OUTPUT_CONTRACT_ERROR", fatal=False)
    choice = choices[0]
    if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
        raise CallFailed("OUTPUT_CONTRACT_ERROR", fatal=False)
    message = choice.get("message")
    if not isinstance(message, dict):
        raise CallFailed("OUTPUT_CONTRACT_ERROR", fatal=False)
    content = message.get("content")
    if (
        not isinstance(content, str)
        or message.get("tool_calls")
        or message.get("function_call")
    ):
        raise CallFailed("OUTPUT_CONTRACT_ERROR", fatal=False)
    return content


@dataclass(repr=False)
class PreparedJsonCall:
    """In-memory one-send operation; usage metadata contains no provider prose."""

    _owner: "KimiStructuredTransport"
    _request: httpx.Request = field(repr=False)
    _model: str
    _limits: CallLimits
    _pilot: "PilotBudget | None" = field(repr=False)
    _reservation: int | None
    request_hash: str
    sent: bool = field(default=False, init=False)
    usage: tuple[int, int] | None = field(default=None, init=False)
    _invoked: bool = field(default=False, init=False)

    def __call__(self) -> str:
        if self._invoked:
            raise CallFailed("UNEXPECTED_RETRY", fatal=True)
        self._invoked = True
        confirmed = False

        def confirm(input_tokens: int, output_tokens: int) -> None:
            nonlocal confirmed
            if self._pilot is not None and self._reservation is not None:
                self._pilot.confirm(
                    self._reservation, self._model, input_tokens, output_tokens
                )
            self.usage = (input_tokens, output_tokens)
            confirmed = True

        try:
            if self._pilot is not None:
                self._pilot.require_active()
            self.sent = True
            response = self._owner._client.send(self._request)
            response.raise_for_status()
            return self._owner._parse(
                response,
                model=self._model,
                limits=self._limits,
                on_usage=confirm,
            )
        except BaseException:
            if self._pilot is not None and not confirmed:
                self._pilot.stop()
            raise


class KimiStructuredTransport:
    """Only the fixed Kimi International model and endpoint are allowed."""

    def __init__(
        self,
        api_key: SecretStr,
        *,
        base_url: str = BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = validate_base_url(base_url)
        key = api_key.get_secret_value()
        if not key or any(character.isspace() for character in key):
            raise CallFailed("AUTHENTICATION_ERROR", fatal=True)
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise CallFailed("INVALID_REQUEST", fatal=True)
        self._endpoint = self._base_url + "/chat/completions"
        self._authorization = "Bearer " + key
        self._pilot_required = not isinstance(transport, httpx.MockTransport)
        self._client = httpx.Client(
            transport=transport or httpx.HTTPTransport(retries=0),
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(timeout_seconds),
        )

    @property
    def endpoint(self) -> str:
        return self._endpoint

    def close(self) -> None:
        self._client.close()

    def prepare(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
        limits: CallLimits,
    ) -> PreparedJsonCall:
        check_logging()
        if model != MODEL_VERSION:
            raise CallFailed("INVALID_REQUEST", fatal=True)
        try:
            CallLimits(
                limits.max_input_tokens,
                limits.max_output_tokens,
                limits.max_request_bytes,
            )
            body = {
                "model": model,
                "messages": json_messages(messages, schema_name, schema),
                "max_tokens": limits.max_output_tokens,
                **request_options(),
            }
            content = json.dumps(
                body, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            raise CallFailed("INVALID_REQUEST", fatal=True) from None
        if len(content) > limits.max_request_bytes:
            raise CallFailed("REQUEST_SIZE_LIMIT", fatal=True)
        prepared = self._client.build_request(
            "POST",
            self._endpoint,
            headers={
                "Authorization": self._authorization,
                "Content-Type": "application/json",
            },
            content=content,
        )
        # Lazy import avoids the legacy model_studio -> pilot_budget cycle.
        from ontology_map.pilot_budget import current_pilot, request_digest

        digest = request_digest(prepared)
        pilot = current_pilot(required=self._pilot_required)
        reservation = pilot.reserve(model, limits, digest) if pilot else None
        return PreparedJsonCall(
            self, prepared, model, limits, pilot, reservation, digest
        )

    @staticmethod
    def _parse(
        response: httpx.Response,
        *,
        model: str,
        limits: CallLimits,
        on_usage: Callable[[int, int], None],
    ) -> str:
        try:
            payload = response.json()
        except ValueError:
            raise CallFailed("RESPONSE_UNKNOWN", fatal=True) from None
        if not isinstance(payload, dict) or payload.get("model") != model:
            raise CallFailed("RESPONSE_UNKNOWN", fatal=True)
        on_usage(*_checked_usage(payload, limits))
        return _checked_content(payload)
