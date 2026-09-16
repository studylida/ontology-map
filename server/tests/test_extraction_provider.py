import json

import httpx
import pytest
from pydantic import SecretStr

from ontology_map.db.extraction_tasks import ExecutionInput
from ontology_map.extraction import GENERATION_PROMPT, GenerationInput
from ontology_map.extraction_contracts import (
    KnowledgeProposals,
    Ontology,
    SourceSpan,
    digest,
)
from ontology_map.extraction_provider import ModelStudioGenerationAdapter
from ontology_map.extraction_runner import GenerationRequest
from ontology_map.model_studio import FLASH, CallFailed, CallLimits

BASE_URL = "https://ws-product-test.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"


def request(*, max_request_bytes: int = 100_000) -> GenerationRequest:
    quote = "한빛은 AI 제품을 발표했다."
    span = SourceSpan(
        source_id="s0",
        start=0,
        end=len(quote),
        quote=quote,
        quote_hash=digest(quote),
        paragraph_id="p0",
    )
    payload = GenerationInput(
        sources=[span],
        ontology=Ontology(
            node_types=("COMPANY", "TECHNOLOGY"),
            relations=(),
            attributes=(),
            topics=(),
        ),
        max_candidates=8,
    )
    return GenerationRequest(
        payload=payload,
        prompt=GENERATION_PROMPT,
        limits=CallLimits(
            max_input_tokens=2_000,
            max_output_tokens=1_024,
            max_request_bytes=max_request_bytes,
        ),
        execution=ExecutionInput(validator_version="v1", runtime_settings={}),
    )


def response(req: httpx.Request, content: str = '{"claims":[]}') -> httpx.Response:
    return httpx.Response(
        200,
        request=req,
        json={
            "id": "offline",
            "object": "chat.completion",
            "created": 0,
            "model": FLASH,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
            },
        },
    )


def test_prepare_builds_exact_model_studio_request_before_send() -> None:
    calls: list[dict[str, object]] = []

    def handle(req: httpx.Request) -> httpx.Response:
        assert str(req.url) == BASE_URL + "/chat/completions"
        payload = json.loads(req.content)
        calls.append(payload)
        assert payload["model"] == FLASH
        assert payload["temperature"] == 0
        assert payload["stream"] is False
        assert payload["enable_thinking"] is False
        assert payload["max_tokens"] == 1_024
        assert "max_completion_tokens" not in payload
        assert not {"tools", "tool_choice", "stream_options"} & payload.keys()
        assert payload["messages"][0] == {
            "role": "system",
            "content": GENERATION_PROMPT,
        }
        assert payload["messages"][1]["role"] == "user"
        assert json.loads(payload["messages"][1]["content"])["max_candidates"] == 8
        response_format = payload["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["name"] == "KnowledgeProposals"
        assert response_format["json_schema"]["strict"] is True
        assert response_format["json_schema"]["schema"]["additionalProperties"] is False
        return response(req)

    adapter = ModelStudioGenerationAdapter(
        SecretStr("offline-key"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(handle),
    )
    try:
        send = adapter.prepare(request())
        assert calls == []
        result = send()
    finally:
        adapter.close()
    assert isinstance(result, KnowledgeProposals)
    assert result.claims == []
    assert len(calls) == 1


def test_deterministic_preflight_failure_sends_nothing() -> None:
    calls = 0

    def handle(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(req)

    adapter = ModelStudioGenerationAdapter(
        SecretStr("offline-key"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(handle),
    )
    try:
        with pytest.raises(CallFailed, match="REQUEST_SIZE_LIMIT"):
            adapter.prepare(request(max_request_bytes=16))
    finally:
        adapter.close()
    assert calls == 0


def test_prepared_operation_never_retries_or_reuses_send() -> None:
    calls = 0

    def handle(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(req)

    adapter = ModelStudioGenerationAdapter(
        SecretStr("offline-key"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(handle),
    )
    try:
        send = adapter.prepare(request())
        send()
        with pytest.raises(CallFailed, match="UNEXPECTED_RETRY"):
            send()
    finally:
        adapter.close()
    assert calls == 1


def test_read_timeout_is_exposed_once_for_durable_unknown_fencing() -> None:
    calls = 0

    def handle(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("lost reply", request=req)

    adapter = ModelStudioGenerationAdapter(
        SecretStr("offline-key"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(handle),
    )
    try:
        send = adapter.prepare(request())
        with pytest.raises(httpx.ReadTimeout):
            send()
    finally:
        adapter.close()
    assert calls == 1


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"claims":[{"candidate_id":"bad"}]}',
    ],
)
def test_confirmed_malformed_structured_output_is_contract_failure(content: str) -> None:
    adapter = ModelStudioGenerationAdapter(
        SecretStr("offline-key"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(lambda req: response(req, content)),
    )
    try:
        send = adapter.prepare(request())
        with pytest.raises(CallFailed, match="OUTPUT_CONTRACT_ERROR"):
            send()
    finally:
        adapter.close()
