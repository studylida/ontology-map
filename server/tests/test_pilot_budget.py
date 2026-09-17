"""Offline checks for the pilot-wide paid-send cap."""

import json
import os
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from ontology_map import durable_provider
from ontology_map.application_execution import dry_run
from ontology_map.extraction import BodyInput
from ontology_map.extraction_contracts import BodySelection
from ontology_map.model_studio import (
    FLASH,
    MAX_INPUT_TOKENS,
    Budget,
    CallFailed,
    CallLimits,
    ModelStudio,
    token_cost,
)
from ontology_map.pilot_budget import PilotBudget, PilotBudgetError
from ontology_map.structured_provider import ModelStudioStructuredTransport

BASE_URL = "https://ws-pilot-test.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
LIMITS = CallLimits(2_000, 1_024, 100_000)


def _response(request: httpx.Request, *, usage: bool = True) -> httpx.Response:
    body = json.loads(request.content)
    return httpx.Response(
        200,
        request=request,
        json={
            "model": body["model"],
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"source_ids":[]}'},
                }
            ],
            **(
                {
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 10,
                        "total_tokens": 110,
                    }
                }
                if usage
                else {}
            ),
        },
    )


def _prepare(transport: ModelStudioStructuredTransport):
    return transport.prepare(
        model=FLASH,
        messages=[{"role": "system", "content": "private prompt"}],
        schema_name="BodySelection",
        schema=BodySelection.model_json_schema(),
        limits=LIMITS,
    )


def test_helper_and_two_durable_tasks_accumulate_before_each_send(tmp_path):
    path = tmp_path / "pilot.jsonl"
    observed = []

    def handle(request: httpx.Request) -> httpx.Response:
        events = [json.loads(line) for line in path.read_text().splitlines()]
        assert events[-1]["kind"] == "reserved"
        observed.append(events[-1]["sequence"])
        return _response(request)

    pilot = PilotBudget("three-doc-pilot", 3, Decimal("1"), path)
    helper = ModelStudio(
        SecretStr("private-key"),
        Budget(1, Decimal("1")),
        base_url=BASE_URL,
        transport=httpx.MockTransport(handle),
    )
    durable = ModelStudioStructuredTransport(
        SecretStr("private-key"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(handle),
    )
    try:
        with pilot.activate():
            assert (
                helper.call(
                    "body",
                    "private prompt",
                    BodyInput(sources=[]),
                    BodySelection,
                    LIMITS,
                ).source_ids
                == []
            )
            assert _prepare(durable)() == '{"source_ids":[]}'
            assert _prepare(durable)() == '{"source_ids":[]}'
            with pytest.raises(PilotBudgetError, match="PILOT_LIMIT_REACHED"):
                _prepare(durable)
    finally:
        helper.close()
        durable.close()
        pilot.close()
    assert observed == [1, 2, 3]
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert [event["kind"] for event in events[1:]] == [
        "reserved",
        "confirmed",
        "reserved",
        "confirmed",
        "reserved",
        "confirmed",
    ]
    assert all(
        event["input_tokens"] == 100 and event["output_tokens"] == 10
        for event in events
        if event.get("kind") == "confirmed"
    )
    assert all(
        event["charged_upper_usd"] == str(token_cost(FLASH, 100, 10))
        for event in events
        if event.get("kind") == "confirmed"
    )
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert "private-key" not in path.read_text()
    assert "private prompt" not in path.read_text()
    assert "source_ids" not in path.read_text()


def test_unknown_usage_stops_pilot_and_existing_file_refuses_resume(tmp_path):
    path = tmp_path / "unknown.jsonl"
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return _response(request, usage=False)

    pilot = PilotBudget("unknown-pilot", 3, Decimal("1"), path)
    transport = ModelStudioStructuredTransport(
        SecretStr("offline"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(handle),
    )
    try:
        with pytest.raises(CallFailed, match="RESPONSE_UNKNOWN"):
            with pilot.activate():
                _prepare(transport)()
        assert pilot.stopped
        with pytest.raises(PilotBudgetError, match="PILOT_STOPPED"):
            with pilot.activate():
                _prepare(transport)()
        pilot.close()  # A fresh process still cannot reuse the pilot file.
        with pytest.raises(PilotBudgetError, match="PILOT_FILE_UNAVAILABLE"):
            PilotBudget("unknown-pilot", 3, Decimal("1"), path)
    finally:
        transport.close()
        pilot.close()
    assert calls == [1]
    assert [json.loads(line).get("kind") for line in path.read_text().splitlines()] == [
        None,
        "reserved",
    ]


def test_usd_cap_uses_confirmed_cost_plus_next_worst_case(tmp_path):
    estimate = token_cost(FLASH, MAX_INPUT_TOKENS, LIMITS.max_output_tokens)
    actual = token_cost(FLASH, 100, 10)
    pilot = PilotBudget(
        "usd-pilot", 3, actual + estimate - Decimal("0.000001"), tmp_path / "usd.jsonl"
    )
    try:
        first = pilot.reserve(FLASH, LIMITS)
        pilot.confirm(first, FLASH, 100, 10)
        with pytest.raises(PilotBudgetError, match="PILOT_LIMIT_REACHED"):
            pilot.reserve(FLASH, LIMITS)
        assert pilot.calls == 1
    finally:
        pilot.close()


def test_same_pilot_rejects_overlapping_execution(tmp_path):
    pilot = PilotBudget("sequential", 1, Decimal("1"), tmp_path / "sequential.jsonl")
    try:
        with pilot.activate():
            with pytest.raises(PilotBudgetError, match="PILOT_CONCURRENT_RUN"):
                with pilot.activate():
                    pass
        assert pilot.stopped
    finally:
        pilot.close()


def test_failed_fsync_blocks_before_http(tmp_path, monkeypatch):
    path = tmp_path / "fsync.jsonl"
    pilot = PilotBudget("fsync-pilot", 1, Decimal("1"), path)
    calls = []
    transport = ModelStudioStructuredTransport(
        SecretStr("offline"),
        base_url=BASE_URL,
        transport=httpx.MockTransport(
            lambda request: calls.append(1) or _response(request)
        ),
    )
    try:
        with pilot.activate():
            monkeypatch.setattr(
                os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError("offline"))
            )
            with pytest.raises(PilotBudgetError, match="PILOT_FILE_WRITE_FAILED"):
                _prepare(transport)
        assert pilot.stopped
    finally:
        transport.close()
        pilot.close()
    assert calls == []


def test_dry_run_never_creates_pilot_file(tmp_path):
    assert dry_run()["provider_sends"] == 0
    assert list(tmp_path.iterdir()) == []


def test_budget_refusal_never_writes_a_provider_outcome(monkeypatch):
    monkeypatch.setattr(
        durable_provider,
        "Session",
        lambda _engine: (_ for _ in ()).throw(AssertionError("DB touched")),
    )

    def refused():
        raise PilotBudgetError("PILOT_LIMIT_REACHED")

    with pytest.raises(PilotBudgetError, match="PILOT_LIMIT_REACHED"):
        durable_provider.execute_call(object(), object(), refused)


@pytest.mark.parametrize("supplied_transport", [False, True])
def test_live_transport_requires_explicit_pilot(supplied_transport):
    transport = ModelStudioStructuredTransport(
        SecretStr("offline"),
        base_url=BASE_URL,
        transport=httpx.HTTPTransport(retries=0) if supplied_transport else None,
    )
    try:
        with pytest.raises(PilotBudgetError, match="PILOT_BUDGET_REQUIRED"):
            _prepare(transport)
    finally:
        transport.close()
