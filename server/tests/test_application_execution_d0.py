"""D0 guards: the offline plan cannot touch product state or send a call."""

import json
from hashlib import sha256
from types import SimpleNamespace

import pytest

from ontology_map import application_execution as app
from ontology_map.db import runtime_bootstrap as bootstrap


def _unexpected(*_args, **_kwargs):
    raise AssertionError("dry run reached a database or provider boundary")


def test_dry_run_uses_real_contracts_without_io(monkeypatch, capsys):
    monkeypatch.setattr(app, "Session", _unexpected)
    monkeypatch.setattr(app, "run_extraction", _unexpected)
    monkeypatch.setattr(app, "run_initial_publication", _unexpected)
    monkeypatch.setattr(
        app, "finalize_extraction_with_initial_publication", _unexpected
    )
    assert app.main(["--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["database_reads"] == plan["database_writes"] == 0
    assert plan["provider_sends"] == 0
    assert plan["blocking_gap"] == "PRODUCT_LINT_VALIDATOR_MISSING"
    assert set(plan["output_schema_sha256"]) == {
        "KNOWLEDGE_EXTRACTION",
        "NODE_CONTEXT",
        "FOLLOWUP_QUESTIONS",
        "NODE_INSIGHT",
    }
    assert all(
        plan["output_schema_sha256"][kind]
        == sha256(
            json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        and schema != {"type": "object"}
        for kind, schema in bootstrap.output_schemas().items()
    )


def test_product_lint_gap_blocks_execution_before_enqueue(monkeypatch):
    monkeypatch.setattr(bootstrap, "_require_ontology", lambda _session: None)
    monkeypatch.setattr(bootstrap, "_require_output_schemas", lambda _session: None)
    with pytest.raises(
        bootstrap.RuntimeNotReady, match="PRODUCT_LINT_VALIDATOR_MISSING"
    ):
        bootstrap.require_runtime_ready(object())


def test_schema_bootstrap_refuses_active_placeholder_without_writes(monkeypatch):
    class ActiveResult:
        def mappings(self):
            return self

        def all(self):
            return [
                {"is_active": True, "schema_json": {"type": "object"}, "version_no": 1}
            ]

    class FakeSession:
        calls = 0

        def in_transaction(self):
            return True

        def execute(self, _statement):
            self.calls += 1
            if self.calls != 1:
                raise AssertionError("attempted a definition write")
            return ActiveResult()

    monkeypatch.setattr(
        bootstrap, "output_schemas", lambda: {"NODE_CONTEXT": {"real": True}}
    )
    session = FakeSession()
    with pytest.raises(
        bootstrap.RuntimeNotReady, match="ACTIVE_OUTPUT_SCHEMA_MISMATCH"
    ):
        bootstrap.ensure_output_schemas(session)
    assert session.calls == 1


@pytest.mark.parametrize(
    ("disposition", "finalizable"),
    [
        ("NOT_CLAIMED", False),
        ("AWAITING_RECLAIM", False),
        ("LEASE_LOST", False),
        ("FAILED", False),
        ("ZERO_RESULT", True),
        ("ALL_BLOCKED", True),
        ("VERIFIED_RUNTIME", True),
    ],
)
def test_application_only_finalizes_claimed_runtime_results(
    monkeypatch, disposition, finalizable
):
    class FakeSession:
        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def begin(self):
            return self

    calls = []
    runner = SimpleNamespace(disposition=disposition)
    runtime = SimpleNamespace(
        document=SimpleNamespace(document_id="7"),
        ontology=object(),
        identity_settings=lambda: {"include_structure": False},
    )
    execution = SimpleNamespace(
        runtime_settings={"extraction_runner": runtime.identity_settings()}
    )
    monkeypatch.setattr(app, "_require_ready", lambda *_args: None)
    monkeypatch.setattr(app, "Session", FakeSession)
    monkeypatch.setattr(
        app.extraction_tasks,
        "enqueue_extraction",
        lambda *_args: SimpleNamespace(task_id=11),
    )
    monkeypatch.setattr(app, "run_extraction", lambda *_args: runner)

    def finalize(*_args, **_kwargs):
        calls.append("finalize")
        return "product"

    monkeypatch.setattr(app, "finalize_extraction_with_initial_publication", finalize)
    result = app.run_document(
        object(),
        7,
        "worker",
        execution,
        runtime,
        object(),
        _unexpected,
        _unexpected,
        _unexpected,
        _unexpected,
        _unexpected,
        _unexpected,
    )
    assert result == ("product" if finalizable else runner)
    assert calls == (["finalize"] if finalizable else [])
