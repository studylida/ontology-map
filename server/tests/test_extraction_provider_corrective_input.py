import json
from dataclasses import replace

import httpx
from pydantic import SecretStr

from ontology_map.extraction import GENERATION_PROMPT
from ontology_map.extraction_provider import (
    CORRECTIVE_INPUT_SEPARATOR,
    ModelStudioGenerationAdapter,
)
from test_extraction_provider import BASE_URL, request, response


def test_corrective_input_changes_serialized_request_before_send() -> None:
    serialized: list[bytes] = []

    def handle(req: httpx.Request) -> httpx.Response:
        serialized.append(req.content)
        return response(req)

    base = request()
    corrective = "이 재처리에서는 공동 발표의 두 주체를 모두 보존한다."
    corrected = replace(
        base,
        execution=base.execution.model_copy(update={"corrective_input": corrective}),
    )

    adapter = ModelStudioGenerationAdapter(
        SecretStr("offline-key"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(handle),
    )
    try:
        base_send = adapter.prepare(base)
        corrected_send = adapter.prepare(corrected)
        assert serialized == []
        base_send()
        corrected_send()
    finally:
        adapter.close()

    assert len(serialized) == 2
    assert serialized[0] != serialized[1]

    base_body = json.loads(serialized[0])
    corrected_body = json.loads(serialized[1])
    assert base_body["messages"][0]["content"] == GENERATION_PROMPT
    assert corrected_body["messages"][0]["content"] == (
        GENERATION_PROMPT + CORRECTIVE_INPUT_SEPARATOR + corrective
    )
    assert base_body["messages"][1] == corrected_body["messages"][1]
