import json
from hashlib import sha256

import httpx
import pytest
from pydantic import SecretStr

from ontology_map import node_context_generation as product
from ontology_map.model_studio import CallFailed
from ontology_map.node_context_generation_contracts import (
    NodeContextAgentInput,
    NodeContextProposal,
    PreparedNodeContext,
)
from ontology_map.node_context_provider import ModelStudioNodeContextAdapter

BASE_URL = "https://ws-product-test.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"


def prepared() -> PreparedNodeContext:
    return PreparedNodeContext(
        promotion_batch_id=1,
        node_search_document_id=2,
        search_document_input_hash=sha256(b"search").digest(),
        input_hash=sha256(b"context").digest(),
        agent_input=NodeContextAgentInput(
            node_id=3,
            node_type="COMPANY",
            preferred_alias="가상 노드",
            identity_text="가상 노드",
            knowledge_text="유형: 기업",
            basis_ids=(3,),
        ),
    )


def response(
    req: httpx.Request,
    content: str = '{"context_text":"짧은 공개 맥락입니다."}',
) -> httpx.Response:
    return httpx.Response(
        200,
        request=req,
        json={
            "id": "offline-node-context",
            "object": "chat.completion",
            "created": 0,
            "model": product.MODEL_VERSION,
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


def test_prepare_uses_exact_node_context_contract_and_sends_once() -> None:
    calls: list[dict[str, object]] = []
    snapshot = prepared()

    def handle(req: httpx.Request) -> httpx.Response:
        payload = json.loads(req.content)
        calls.append(payload)
        assert str(req.url) == BASE_URL + "/chat/completions"
        assert payload["model"] == product.MODEL_VERSION
        assert payload["temperature"] == 0
        assert payload["stream"] is False
        assert payload["enable_thinking"] is False
        assert not {"tools", "tool_choice", "stream_options"} & payload.keys()
        expected_messages = [
            {
                "role": "system" if role == "system" else "user",
                "content": content,
            }
            for role, content in product.build_messages(snapshot)
        ]
        assert payload["messages"] == expected_messages
        response_format = payload["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["name"] == "NodeContextProposal"
        assert response_format["json_schema"]["strict"] is True
        assert response_format["json_schema"]["schema"] == product.output_schema()
        return response(req)

    adapter = ModelStudioNodeContextAdapter(
        SecretStr("offline-key"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(handle),
    )
    try:
        send = adapter.prepare(snapshot)
        assert calls == []
        result = send()
        with pytest.raises(CallFailed, match="UNEXPECTED_RETRY"):
            send()
    finally:
        adapter.close()

    assert isinstance(result, NodeContextProposal)
    assert result.context_text == "짧은 공개 맥락입니다."
    assert len(calls) == 1


@pytest.mark.parametrize(
    "content",
    ["not-json", '{"context_text":""}', '{"context_text":"ok","extra":1}'],
)
def test_malformed_context_structured_output_is_contract_error(content: str) -> None:
    adapter = ModelStudioNodeContextAdapter(
        SecretStr("offline-key"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(lambda req: response(req, content)),
    )
    try:
        send = adapter.prepare(prepared())
        with pytest.raises(CallFailed, match="OUTPUT_CONTRACT_ERROR"):
            send()
    finally:
        adapter.close()


def test_read_timeout_is_exposed_without_hidden_retry() -> None:
    calls = 0

    def handle(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("lost reply", request=req)

    adapter = ModelStudioNodeContextAdapter(
        SecretStr("offline-key"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(handle),
    )
    try:
        send = adapter.prepare(prepared())
        with pytest.raises(httpx.ReadTimeout):
            send()
    finally:
        adapter.close()
    assert calls == 1
