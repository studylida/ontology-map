"""Production Model Studio generation adapter for the durable #127 runner.

All deterministic request construction happens in ``prepare``. The returned
operation owns exactly one HTTP send and contains no retry loop. Raw provider
responses never leave this module.
"""

from collections.abc import Callable
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from ontology_map import extraction as harness
from ontology_map.db import extraction_tasks as inputs
from ontology_map.extraction_contracts import KnowledgeProposals
from ontology_map.extraction_runner import (
    GenerationRequest,
    RunnerResult,
    RuntimeInput,
    run_extraction,
)
from ontology_map.model_studio import FLASH, CallFailed
from ontology_map.structured_provider import (
    DEFAULT_TIMEOUT_SECONDS,
    ModelStudioStructuredTransport,
)

CORRECTIVE_INPUT_SEPARATOR = "\n\n명시적 corrective input:\n"


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
        self._transport = ModelStudioStructuredTransport(
            api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

    @property
    def endpoint(self) -> str:
        return self._transport.endpoint

    def close(self) -> None:
        self._transport.close()

    def prepare(self, request: GenerationRequest) -> Callable[[], KnowledgeProposals]:
        """Return an exactly-once send operation after deterministic preflight."""
        if request.model != FLASH or request.output_schema is not KnowledgeProposals:
            raise CallFailed("INVALID_REQUEST", fatal=True)
        if not request.prompt.strip():
            raise CallFailed("INVALID_REQUEST", fatal=True)

        system_content = request.prompt
        if request.execution.corrective_input is not None:
            system_content += (
                CORRECTIVE_INPUT_SEPARATOR + request.execution.corrective_input
            )
        raw_send = self._transport.prepare(
            model=FLASH,
            messages=(
                {"role": "system", "content": system_content},
                {"role": "user", "content": request.payload.model_dump_json()},
            ),
            schema_name=KnowledgeProposals.__name__,
            schema=KnowledgeProposals.model_json_schema(),
            limits=request.limits,
        )

        def send() -> KnowledgeProposals:
            content = raw_send()
            try:
                return KnowledgeProposals.model_validate_json(content, strict=True)
            except ValidationError:
                raise CallFailed("OUTPUT_CONTRACT_ERROR", fatal=False) from None

        return send


def run_model_studio_extraction(
    engine: Any,
    task_id: int,
    worker_name: str,
    execution: inputs.ExecutionInput,
    runtime: RuntimeInput,
    helpers: harness.ExtractionModels,
    adapter: ModelStudioGenerationAdapter,
) -> RunnerResult:
    """Compose the approved durable runner with one production Flash send."""
    return run_extraction(
        engine,
        task_id,
        worker_name,
        execution,
        runtime,
        helpers,
        adapter.prepare,
    )
