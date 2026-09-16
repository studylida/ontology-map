"""Production Model Studio generation adapter for the durable #127 runner.

All deterministic request construction happens in ``prepare``. The returned
operation owns exactly one HTTP send and contains no retry loop. Raw provider
responses never leave this module.
"""

import json
import logging
import math
from collections.abc import Callable
from typing import Any

import httpx
from langchain_core.globals import get_debug, get_verbose
from pydantic import SecretStr, ValidationError

from ontology_map.extraction_contracts import KnowledgeProposals
from ontology_map.extraction_runner import GenerationRequest
from ontology_map.model_studio import FLASH, CallFailed, validate_base_url

DEFAULT_TIMEOUT_SECONDS = 60.0


def _safe_logging() -> None:
    if get_debug() or get_verbose():
        raise CallFailed("UNSAFE_LOGGING_CONFIGURATION", fatal=True)
    for name in ("openai", "httpx", "httpcore", "langchain_core", "langsmith"):
        if logging.getLogger(name).isEnabledFor(logging.DEBUG):
            raise CallFailed("UNSAFE_LOGGING_CONFIGURATION", fatal=True)


def _integer(value: object) -> int | None:
    return value if type(value) is int else None


class ModelStudioGenerationAdapter:
    """Prepare one approved Flash Structured Output request before reservation."""

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

    def prepare(self, request: GenerationRequest) -> Callable[[], KnowledgeProposals]:
        """Return an exactly-once send operation after deterministic preflight."""
        _safe_logging()
        if request.model != FLASH or request.output_schema is not KnowledgeProposals:
            raise CallFailed("INVALID_REQUEST", fatal=True)
        if not request.prompt.strip():
            raise CallFailed("INVALID_REQUEST", fatal=True)

        schema = KnowledgeProposals.model_json_schema()
        response_format: dict[str, Any] = {
            "type": "json_schema",
            "json_schema": {
                "name": KnowledgeProposals.__name__,
                "strict": True,
                "schema": schema,
            },
        }
        body = {
            "model": FLASH,
            "messages": [
                {"role": "system", "content": request.prompt},
                {"role": "user", "content": request.payload.model_dump_json()},
            ],
            "temperature": 0,
            "stream": False,
            "enable_thinking": False,
            "max_tokens": request.limits.max_output_tokens,
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
        if len(content) > request.limits.max_request_bytes:
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
        sent = False

        def send() -> KnowledgeProposals:
            nonlocal sent
            if sent:
                raise CallFailed("UNEXPECTED_RETRY", fatal=True)
            sent = True
            response = self._client.send(prepared)
            response.raise_for_status()
            return self._parse(response, request)

        return send

    @staticmethod
    def _parse(
        response: httpx.Response, request: GenerationRequest
    ) -> KnowledgeProposals:
        try:
            payload = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            raise CallFailed("RESPONSE_UNKNOWN", fatal=True) from None
        if not isinstance(payload, dict) or payload.get("model") != FLASH:
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
            or not 0 < input_tokens <= request.limits.max_input_tokens
            or not 0 <= output_tokens <= request.limits.max_output_tokens
        ):
            raise CallFailed("RESPONSE_UNKNOWN", fatal=True)

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
        try:
            return KnowledgeProposals.model_validate_json(content, strict=True)
        except ValidationError:
            raise CallFailed("OUTPUT_CONTRACT_ERROR", fatal=False) from None
