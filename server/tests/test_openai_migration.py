"""OpenAI migration contract checks: synthetic only, no network or database.

These fixtures test transport/DTO boundaries, NOT actual API acceptance or model
quality. In particular an empty valid fixture does not establish D1 success.
"""

import json
import socket
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256

import httpx
import pytest
from openai_cases import CASES
from pydantic import SecretStr, ValidationError

from ontology_map.kimi_response_archive import response_task
from ontology_map.kimi_transport import OpenAIStructuredTransport
from ontology_map.llm_config import (
    BASE_URL,
    BILLABLE_INPUT_CEILING,
    RESERVATION_REQUEST_BYTE_CEILING,
    ROLE_PROFILES,
    request_identity_settings,
    role_model,
)
from ontology_map.llm_contracts import Budget, CallFailed, CallLimits, token_cost
from ontology_map.llm_diagnostics import failure_diagnostic
from ontology_map.llm_pacing import (
    ProcessPacer,
    pacing_scope,
    provider_lease,
    provider_turn,
)
from ontology_map.llm_response_metadata import rate_limit_kind, safe_headers
from ontology_map.model_studio import KimiModels
from ontology_map.openai_schema import wire_schema
from ontology_map.pilot_budget import PilotBudget

LIMITS = CallLimits(2000, 1024, 100_000)


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("ONTOLOGY_MAP_OPENAI_RESPONSE_DIR", str(tmp_path / "responses"))
    for key in ("OPENAI_API_KEY", "MOONSHOT_API_KEY", "ONTOLOGY_MAP_DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        socket.socket, "connect", lambda *a, **k: pytest.fail("NETWORK_FORBIDDEN")
    )


def prepare(client, role="body", **changes):
    schema, _ = CASES[role]
    values = {
        "model": role_model(role),
        "messages": [{"role": "system", "content": "Synthetic input only."}],
        "schema_name": schema.__name__,
        "schema": schema.model_json_schema(),
        "limits": LIMITS,
    }
    values.update(changes)
    return client.prepare(**values)


def response(request, role="body", *, change=None):
    _, value = CASES[role]
    payload = {
        "id": "chatcmpl-offline-240",
        "model": role_model(role),
        "choices": [
            {"finish_reason": "stop", "message": {"content": json.dumps(value)}}
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "prompt_tokens_details": {"cached_tokens": 40, "cache_write_tokens": 20},
            "completion_tokens_details": {"reasoning_tokens": 15},
        },
    }
    if change:
        change(payload)
    return httpx.Response(
        200, request=request, content=(" \n" + json.dumps(payload) + "\n").encode()
    )


@pytest.mark.parametrize("role", tuple(CASES))
def test_all_nine_roles_strict_wire_and_original_dto(role, tmp_path):
    schema, value = CASES[role]
    original = deepcopy(schema.model_json_schema())
    seen = []

    def handle(request):
        wire = json.loads(request.content)
        assert str(request.url) == BASE_URL + "/chat/completions"
        assert wire["model"] == ROLE_PROFILES[role][0]
        assert wire["reasoning_effort"] == ROLE_PROFILES[role][1]
        assert wire["max_completion_tokens"] == LIMITS.max_output_tokens
        assert wire["stream"] is False and wire["store"] is False
        assert not {"thinking", "max_tokens", "tools", "temperature"} & wire.keys()
        assert wire["response_format"] == {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "strict": True,
                "schema": wire_schema(original),
            },
        }
        result = response(request, role)
        seen.append(result.content)
        return result

    client = OpenAIStructuredTransport(
        SecretStr("fake-key"), transport=httpx.MockTransport(handle)
    )
    try:
        with response_task(240, 1):
            operation = prepare(client, role)
            parsed = operation.parse(
                lambda raw: schema.model_validate_json(raw, strict=True)
            )
        assert parsed.model_dump(mode="json") == value
        assert schema.model_json_schema() == original
        assert operation.usage == (100, 20)  # reasoning is NOT added a second time.
        with pytest.raises(CallFailed, match="UNEXPECTED_RETRY"):
            operation()
        directory = operation.archive.directory
        assert (
            directory is not None
            and (directory / "response.body").read_bytes() == seen[0]
        )
        metadata = json.loads((directory / "metadata.json").read_text())
        assert metadata["provider"] == "openai" and metadata[
            "request_model"
        ] == role_model(role)
        assert metadata["role"] == role and metadata["model_task_id"] == 240
        assert metadata["response_sha256"] == sha256(seen[0]).hexdigest()
        envelope = json.loads((directory / "envelope.json").read_text())
        assert envelope["provider_response_id"] == "chatcmpl-offline-240"
        assert envelope["reasoning_tokens"] == 15
        assert envelope["cache_write_tokens"] == 20
    finally:
        client.close()
    assert len(seen) == 1


@pytest.mark.parametrize("role", tuple(CASES))
def test_refusal_never_becomes_success_or_empty(role):
    def refuse(payload):
        payload["choices"][0]["message"]["refusal"] = "private refusal"

    client = OpenAIStructuredTransport(
        SecretStr("fake"),
        transport=httpx.MockTransport(lambda req: response(req, role, change=refuse)),
    )
    try:
        operation = prepare(client, role)
        with pytest.raises(CallFailed, match="OUTPUT_CONTRACT_ERROR") as failure:
            operation()
        diagnostic = failure_diagnostic(failure.value)
        assert diagnostic["reason"] == "REFUSAL" and diagnostic["role"] == role
        assert operation.usage == (100, 20)
        assert "private refusal" not in json.dumps(diagnostic)
    finally:
        client.close()


@pytest.mark.parametrize(
    "bad_model", ["kimi-k2.6", "gpt-5.6-luna-2099-01-01", "gpt-5.6-terra"]
)
def test_model_response_aliases_are_not_guessed(bad_model):
    def mutate(payload):
        payload["model"] = bad_model

    client = OpenAIStructuredTransport(
        SecretStr("fake"),
        transport=httpx.MockTransport(lambda req: response(req, change=mutate)),
    )
    try:
        operation = prepare(client)
        with pytest.raises(CallFailed, match="RESPONSE_UNKNOWN"):
            operation()
        assert operation.usage is None
    finally:
        client.close()


@pytest.mark.parametrize(
    "keyword,value",
    [
        ("allOf", []),
        ("if", {}),
        ("dependentRequired", {}),
        ("unevaluatedProperties", False),
    ],
)
def test_unsupported_semantics_fail_before_reservation(keyword, value, tmp_path):
    schema = CASES["body"][0].model_json_schema()
    schema[keyword] = value
    calls = []
    client = OpenAIStructuredTransport(
        SecretStr("fake"),
        transport=httpx.MockTransport(lambda req: calls.append(req) or response(req)),
    )
    pilot = PilotBudget("schema-reject", 1, Decimal("1"), tmp_path / "ledger")
    try:
        with pilot.activate(), pytest.raises(CallFailed, match="INVALID_REQUEST"):
            prepare(client, schema=schema)
        assert pilot.calls == 0 and not calls
    finally:
        pilot.close()
        client.close()


def test_required_nullable_const_pattern_format_and_original_validator():
    original = CASES["generation"][0].model_json_schema()
    converted = wire_schema(original)
    assert (
        converted["$defs"]["Mention"]["properties"]["topic_name"]["anyOf"]
        == original["$defs"]["Mention"]["properties"]["topic_name"]["anyOf"]
    )
    assert (
        converted["$defs"]["TemporalPoint"]["properties"]["value"]["anyOf"][0]["format"]
        == "date-time"
    )
    assert "pattern" in converted["$defs"]["Mention"]["properties"]["text"]
    duplicate = wire_schema(CASES["claim_duplicate"][0].model_json_schema())
    assert set(duplicate["required"]) == set(duplicate["properties"])
    assert "default" not in duplicate["properties"]["claim_id"]
    with pytest.raises(ValidationError):
        CASES["claim_duplicate"][0](decision="SAME", claim_id=None)
    constant = wire_schema(
        {
            "type": "object",
            "properties": {"kind": {"type": "string", "const": "A"}},
            "additionalProperties": False,
        }
    )
    assert constant["properties"]["kind"]["enum"] == ["A"]


class Clock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    def clock(self):
        return self.now

    def wait(self, delay):
        self.waits.append(delay)
        self.now += delay


def test_shared_pacing_after_long_generation_and_idle(tmp_path):
    clock = Clock()
    pacer = ProcessPacer(7, clock=clock.clock, wait=clock.wait)
    starts = []

    def handle(req):
        starts.append(clock.now)
        name = json.loads(req.content)["response_format"]["json_schema"]["name"]
        role = "generation" if name == "KnowledgeProposals" else "claim_support"
        if role == "generation":
            clock.now += 90
        return response(req, role)

    client = OpenAIStructuredTransport(
        SecretStr("fake"), transport=httpx.MockTransport(handle)
    )
    pilot = PilotBudget("pace", 4, Decimal("2"), tmp_path / "ledger")
    try:
        with pilot.activate(), pacing_scope(pacer):
            prepare(client, "generation")()
            prepare(client, "claim_support")()
            prepare(client, "claim_support")()
            clock.now += 100
            prepare(client, "claim_support")()
        assert starts == [0, 90, 97, 197]
        assert clock.waits == [7]
        assert pilot.calls == 4
    finally:
        pilot.close()
        client.close()


def test_wait_then_lease_loss_consumes_no_helper_or_pilot_reservation(tmp_path):
    clock = Clock()
    pacer = ProcessPacer(7, clock=clock.clock, wait=clock.wait)
    calls = []

    def handle(req):
        calls.append(req)
        return response(req)

    helper = KimiModels(
        SecretStr("fake"),
        Budget(2, Decimal("2")),
        transport=httpx.MockTransport(handle),
    )
    pilot = PilotBudget("lease-lost", 2, Decimal("2"), tmp_path / "ledger")

    class LeaseLost(Exception):
        pass

    def check():
        if clock.now >= 7:
            raise LeaseLost()

    try:
        with pilot.activate(), pacing_scope(pacer), provider_lease(check):
            helper.call(
                "body",
                "synthetic",
                CASES["body"][0](source_ids=[]),
                CASES["body"][0],
                LIMITS,
            )
            before = pilot.charged_upper_usd
            with pytest.raises(LeaseLost):
                helper.call(
                    "body",
                    "synthetic",
                    CASES["body"][0](source_ids=[]),
                    CASES["body"][0],
                    LIMITS,
                )
        assert clock.waits == [7] and len(calls) == 1 and pilot.calls == 1
        assert len(helper.budget.records) == 1 and pilot.charged_upper_usd == before
    finally:
        helper.close()
        pilot.close()


def test_wait_occurs_before_caller_durable_reservation():
    clock = Clock()
    pacer = ProcessPacer(5, clock=clock.clock, wait=clock.wait)
    pacer.mark_send()
    active_transaction = False

    def wait(delay):
        assert not active_transaction
        clock.wait(delay)

    pacer.wait = wait
    with pacing_scope(pacer), provider_turn():
        assert clock.now == 5
        active_transaction = True  # caller may reserve only after entering turn
    assert clock.waits == [5]


@pytest.mark.parametrize(
    "code,expected",
    [
        ("insufficient_quota", "QUOTA_OR_BILLING"),
        ("billing_hard_limit_reached", "QUOTA_OR_BILLING"),
        ("rate_limit_exceeded", "TEMPORARY_RATE_LIMIT"),
        ("not-approved-code", "UNKNOWN_429"),
    ],
)
def test_429_is_single_send_and_preserves_unknown_reservation(code, expected, tmp_path):
    calls = []

    def handle(req):
        calls.append(req)
        return httpx.Response(
            429,
            request=req,
            json={"error": {"code": code, "message": "private"}},
            headers={
                "Retry-After": "7",
                "x-ratelimit-reset-requests": "1m2.5s",
                "x-ratelimit-remaining-requests": "0",
                "Authorization": "private-key",
            },
        )

    client = OpenAIStructuredTransport(
        SecretStr("fake"), transport=httpx.MockTransport(handle)
    )
    pilot = PilotBudget("rate-limit", 2, Decimal("1"), tmp_path / "ledger")
    try:
        with pilot.activate():
            operation = prepare(client)
            with pytest.raises(httpx.HTTPStatusError) as failure:
                operation()
            assert rate_limit_kind(failure.value.response) == expected
            diagnostic = failure_diagnostic(failure.value)
            assert diagnostic["rate_limit_kind"] == expected
            assert dict(diagnostic["rate_limit_headers"])["retry-after"] == "7"
            assert "private" not in json.dumps(diagnostic)
        assert len(calls) == 1 and pilot.stopped
        events = [json.loads(line) for line in pilot.path.read_text().splitlines()]
        assert [event.get("kind") for event in events] == [None, "reserved"]
        assert pilot.charged_upper_usd == token_cost(
            role_model("body"), BILLABLE_INPUT_CEILING, 1024
        )
    finally:
        client.close()
        pilot.close()


@pytest.mark.parametrize(
    "raw,accepted",
    [
        ("7", "7"),
        ("1.5", "1.5"),
        ("Fri, 18 Sep 2026 06:00:00 GMT", "Fri, 18 Sep 2026 06:00:00 GMT"),
        ("-1", None),
        ("NaN", None),
        ("private-token", None),
        ("", None),
    ],
)
def test_retry_after_safety(raw, accepted):
    assert (
        safe_headers(httpx.Headers({"Retry-After": raw})).get("retry-after") == accepted
    )


def test_identity_and_budget_do_not_relabel_history_or_double_count():
    profiles = request_identity_settings()["role_profiles"]
    assert set(profiles) == set(CASES)
    for role in CASES:
        identity = request_identity_settings(role)
        assert identity["model"] == role_model(role)
        assert identity["output_option"] == "max_completion_tokens"
        assert identity["wire_schema_version"]
    assert token_cost("kimi-k2.6", 100, 20) == Decimal("0.000175")
    assert token_cost(role_model("body"), 100, 20) == Decimal("0.000049")
    assert token_cost(role_model("generation"), 100, 20) == Decimal("0.000490")


def test_large_wire_request_fails_before_reservation_without_expanding_budget(tmp_path):
    calls = []
    client = OpenAIStructuredTransport(
        SecretStr("fake"),
        transport=httpx.MockTransport(
            lambda request: calls.append(request) or response(request)
        ),
    )
    pilot = PilotBudget("large-wire", 1, Decimal("1"), tmp_path / "ledger")
    try:
        with pilot.activate():
            with pytest.raises(CallFailed, match="REQUEST_SIZE_LIMIT"):
                prepare(
                    client,
                    messages=[
                        {
                            "role": "system",
                            "content": "x" * RESERVATION_REQUEST_BYTE_CEILING,
                        }
                    ],
                )
        assert not calls and pilot.calls == 0 and pilot.charged_upper_usd == 0
    finally:
        client.close()
        pilot.close()


def test_live_transport_requires_explicit_positive_pacing_without_sending(tmp_path):
    class NeverSend(httpx.BaseTransport):
        def handle_request(self, request):
            pytest.fail("LIVE_SEND_FORBIDDEN")

    client = OpenAIStructuredTransport(SecretStr("fake"), transport=NeverSend())
    pilot = PilotBudget("pacing-required", 1, Decimal("1"), tmp_path / "ledger")
    try:
        with pilot.activate(), pacing_scope(ProcessPacer(0)):
            with pytest.raises(CallFailed, match="PACING_REQUIRED"):
                prepare(client)
        assert pilot.calls == 0 and pilot.charged_upper_usd == 0
    finally:
        client.close()
        pilot.close()
