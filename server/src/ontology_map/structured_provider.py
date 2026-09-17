"""Small shared Model Studio JSON-Schema HTTP helper for durable product calls.

This is transport only: callers own product DTOs, prompts, parsing, task identity,
leases and retries. ``prepare`` completes deterministic request construction and
returns one operation that can send at most once.
"""

import json
import logging
import math
from collections.abc import Callable, Sequence
from typing import Any

import httpx
from langchain_core.globals import get_debug, get_verbose
from pydantic import SecretStr

from ontology_map.model_studio import CallFailed, CallLimits, validate_base_url
from ontology_map.pilot_budget import PilotBudget, current_pilot

DEFAULT_TIMEOUT_SECONDS = 60.0
REQUEST_TEMPERATURE = 0
REQUEST_STREAM = False
REQUEST_ENABLE_THINKING = False
REQUEST_RESPONSE_FORMAT = "json_schema"
REQUEST_SCHEMA_STRICT = True


def request_identity_settings() -> dict[str, object]:
    """Return request knobs shared by transport construction and task identity."""
    return {
        "temperature": REQUEST_TEMPERATURE,
        "stream": REQUEST_STREAM,
        "enable_thinking": REQUEST_ENABLE_THINKING,
        "response_format": REQUEST_RESPONSE_FORMAT,
        "schema_strict": REQUEST_SCHEMA_STRICT,
    }


def _safe_logging() -> None:
    if get_debug() or get_verbose():
        raise CallFailed("UNSAFE_LOGGING_CONFIGURATION", fatal=True)
    for name in ("openai", "httpx", "httpcore", "langchain_core", "langsmith"):
        if logging.getLogger(name).isEnabledFor(logging.DEBUG):
            raise CallFailed("UNSAFE_LOGGING_CONFIGURATION", fatal=True)


def _integer(value: object) -> int | None:
    return value if type(value) is int else None


class ModelStudioStructuredTransport:
    """Prepare one strict Structured Output HTTP request before slot reservation."""

    def __init__(
        self,
        api_key: SecretStr,
        *,
        base_url: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key.get_secret_value()
        if not key or key.isspace():
            raise CallFailed("AUTHENTICATION_ERROR", fatal=True)
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise CallFailed("INVALID_REQUEST", fatal=True)
        self._base_url = validate_base_url(base_url)
        self._endpoint = self._base_url + "/chat/completions"
        self._authorization = "Bearer " + key
        self._pilot_required = not isinstance(transport, httpx.MockTransport)
        selected_transport = transport or httpx.HTTPTransport(retries=0)
        self._client = httpx.Client(
            transport=selected_transport,
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
    ) -> Callable[[], str]:
        """Return a one-send operation with no retry, stream, or raw retention."""
        _safe_logging()
        if not model.strip() or not schema_name.strip() or not messages:
            raise CallFailed("INVALID_REQUEST", fatal=True)
        if any(
            message.get("role") not in ("system", "user")
            or not message.get("content", "").strip()
            for message in messages
        ):
            raise CallFailed("INVALID_REQUEST", fatal=True)

        response_format: dict[str, Any] = {
            "type": REQUEST_RESPONSE_FORMAT,
            "json_schema": {
                "name": schema_name,
                "strict": REQUEST_SCHEMA_STRICT,
                "schema": schema,
            },
        }
        body = {
            "model": model,
            "messages": list(messages),
            "temperature": REQUEST_TEMPERATURE,
            "stream": REQUEST_STREAM,
            "enable_thinking": REQUEST_ENABLE_THINKING,
            "max_tokens": limits.max_output_tokens,
            "response_format": response_format,
        }
        try:
            content = json.dumps(
                body,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as error:
            raise CallFailed("INVALID_REQUEST", fatal=True) from error
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
        pilot = current_pilot(required=self._pilot_required)
        reservation = pilot.reserve(model, limits) if pilot else None
        sent = False

        def send() -> str:
            nonlocal sent
            if sent:
                raise CallFailed("UNEXPECTED_RETRY", fatal=True)
            sent = True
            return self._send(prepared, model, limits, pilot, reservation)

        return send

    def _send(
        self,
        prepared: httpx.Request,
        model: str,
        limits: CallLimits,
        pilot: PilotBudget | None,
        reservation: int | None,
    ) -> str:
        confirmed = False

        def confirm(input_tokens: int, output_tokens: int) -> None:
            nonlocal confirmed
            if pilot is not None and reservation is not None:
                pilot.confirm(reservation, model, input_tokens, output_tokens)
                confirmed = True

        try:
            if pilot is not None:
                pilot.require_active()
            response = self._client.send(prepared)
            response.raise_for_status()
            return self._parse(response, model=model, limits=limits, on_usage=confirm)
        except BaseException:
            if pilot is not None and not confirmed:
                pilot.stop()
            raise

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
        except json.JSONDecodeError, UnicodeDecodeError, ValueError:
            raise CallFailed("RESPONSE_UNKNOWN", fatal=True) from None
        if not isinstance(payload, dict) or payload.get("model") != model:
            raise CallFailed("RESPONSE_UNKNOWN", fatal=True)

        usage = payload.get("usage")
        if not isinstance(usage, dict):
            raise CallFailed("RESPONSE_UNKNOWN", fatal=True)
        input_tokens = _integer(usage.get("prompt_tokens"))
        output_tokens = _integer(usage.get("completion_tokens"))
        total_tokens = _integer(usage.get("total_tokens"))
        if (
            input_tokens is None
            or output_tokens is None
            or total_tokens is None
            or total_tokens != input_tokens + output_tokens
            or not 0 < input_tokens <= limits.max_input_tokens
            or not 0 <= output_tokens <= limits.max_output_tokens
        ):
            raise CallFailed("RESPONSE_UNKNOWN", fatal=True)
        on_usage(input_tokens, output_tokens)

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
        if not isinstance(content, str) or message.get("tool_calls"):
            raise CallFailed("OUTPUT_CONTRACT_ERROR", fatal=False)
        return content
