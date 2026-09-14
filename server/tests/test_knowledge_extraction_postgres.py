"""Actual migrated PostgreSQL + HTTP mock: product path, never a paid provider.

Each test creates and drops only its own randomly named loopback test database.
Reference rows here do not install or modify product/development fixtures.
"""

import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import sqlalchemy as sa
from pydantic import SecretStr
from sqlalchemy.orm import Session

from ontology_map import knowledge_extraction as worker
from ontology_map.db import extraction_promotion as storage
from ontology_map.db import model_tasks as tasks
from ontology_map.db import schema as db
from ontology_map.extraction import ExtractionLimits
from ontology_map.extraction_contracts import KnowledgeProposals, digest
from ontology_map.knowledge_extraction_contracts import VALIDATOR_VERSION, WorkerOptions
from ontology_map.model_studio import Budget, CallLimits, ModelStudio

URL = os.environ.get("ONTOLOGY_MAP_KE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="isolated KE PostgreSQL URL not supplied")
SERVER = Path(__file__).resolve().parents[1]


def scalar(engine, table):
    with engine.connect() as c:
        return c.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()


@pytest.fixture
def database():
    url = sa.engine.make_url(URL)
    assert url.get_backend_name() == "postgresql"
    assert url.host in {"localhost", "127.0.0.1", "::1"}
    assert url.database and url.database.endswith("_ke127_test")
    name = f"ke127_{uuid4().hex}_ke127_test"
    admin = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    engine = sa.create_engine(url.set(database=name))
    with admin.connect() as c:
        c.execute(sa.text(f'CREATE DATABASE "{name}"'))
    try:
        env = dict(os.environ, ONTOLOGY_MAP_DATABASE_URL=url.set(database=name).render_as_string(hide_password=False))
        migration = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=SERVER, env=env, capture_output=True, text=True)
        assert migration.returncode == 0, migration.stderr
        seed(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.execute(sa.text(f'DROP DATABASE "{name}"'))
        admin.dispose()


def seed(engine):
    with engine.begin() as c:
        for code in ("COMPANY", "PERSON", "TECHNOLOGY", "EVENT", "TOPIC"):
            c.execute(sa.insert(db.node_type).values(node_type_code=code, display_name=code, creation_rule="공개 원문 식별과 근거가 필요하다.", is_active=True))
        c.execute(sa.insert(db.output_schema_definition).values(task_kind="KNOWLEDGE_EXTRACTION", version_no=1, schema_json=KnowledgeProposals.model_json_schema(), is_active=True))
        policy = c.execute(sa.insert(db.lint_policy_version).values(version_no=1, validator_version=VALIDATOR_VERSION, is_active=True, activated_at=datetime.now(UTC)).returning(db.lint_policy_version.c.lint_policy_version_id)).scalar_one()
        rule = c.execute(sa.insert(db.lint_rule).values(rule_code="EVIDENCE_TRACE_COMPLETE", display_name="근거", description="정확한 원문 근거", evaluation_scope="BOTH").returning(db.lint_rule.c.lint_rule_id)).scalar_one()
        c.execute(sa.insert(db.lint_policy_rule).values(lint_policy_version_id=policy, lint_rule_id=rule, severity="BLOCKING"))
        relation = c.execute(sa.insert(db.relation_type).values(relation_code="COLLABORATES_WITH").returning(db.relation_type.c.relation_type_id)).scalar_one()
        revision = c.execute(sa.insert(db.relation_type_revision).values(relation_type_id=relation, version_no=1, display_name="협력", directionality="SYMMETRIC", is_active=True).returning(db.relation_type_revision.c.relation_type_revision_id)).scalar_one()
        company_type = c.execute(sa.select(db.node_type.c.node_type_id).where(db.node_type.c.node_type_code == "COMPANY")).scalar_one()
        c.execute(sa.insert(db.relation_endpoint_rule).values(relation_type_revision_id=revision, source_node_type_id=company_type, target_node_type_id=company_type))
        technology = c.execute(sa.select(db.node_type.c.node_type_id).where(db.node_type.c.node_type_code == "TECHNOLOGY")).scalar_one()
        attr = c.execute(sa.insert(db.attribute).values(attribute_code="CORE_COUNT").returning(db.attribute.c.attribute_id)).scalar_one()
        c.execute(sa.insert(db.attribute_revision).values(attribute_id=attr, version_no=1, display_name="코어 수", target_node_type_id=technology, allowed_value_kind="NUMBER", unit_rule="COUNT", is_active=True))


def document(engine, body="슬롯회사A와 슬롯회사B가 협력한다."):
    with engine.begin() as c:
        group = c.execute(sa.insert(db.evidence_group).returning(db.evidence_group.c.evidence_group_id)).scalar_one()
        return c.execute(sa.insert(db.source_document).values(
            evidence_group_id=group, source_key=f"ke127:{uuid4().hex}", version_no=1,
            canonical_url="https://example.invalid/ke127", publisher_name="합성 시험", title="합성 원문",
            original_language="ko", normalized_body=body, body_hash=bytes.fromhex(digest(body)),
            published_precision="UNKNOWN", modified_precision="UNKNOWN", last_checked_at=datetime.now(UTC), last_check_status="SUCCESS",
        ).returning(db.source_document.c.source_document_id)).scalar_one()


def options():
    limit = CallLimits(2000, 1024, 100000)
    return WorkerOptions(ExtractionLimits(limit, limit, limit, 8))


def relation_claim(candidate="c1", first="슬롯회사A", second="슬롯회사B"):
    return {"candidate_id": candidate, "statement": f"{first}와 {second}가 협력한다.", "modality": "FACT", "source_ids": ["s1"],
            "mentions": [{"mention_id": "a", "text": first, "node_type": "COMPANY", "source_ids": ["s1"], "topic_name": None},
                         {"mention_id": "b", "text": second, "node_type": "COMPANY", "source_ids": ["s1"], "topic_name": None}],
            "bindings": [{"kind": "RELATION", "binding_id": "r1", "code": "COLLABORATES_WITH", "source_mention": "a", "target_mention": "b", "stance": "SUPPORT"}]}


def bandwidth_claim():
    return {"candidate_id": "bad", "statement": "시험칩의 최대 대역폭은 1 TB/s다.", "modality": "FACT", "source_ids": ["s1"],
            "mentions": [{"mention_id": "t", "text": "시험칩", "node_type": "TECHNOLOGY", "source_ids": ["s1"], "topic_name": None}],
            "bindings": [{"kind": "ATTRIBUTE", "binding_id": "bw", "code": "MAX_MEMORY_BANDWIDTH", "target_mention": "t", "value": {"kind": "NUMBER", "value": "1", "unit": "TB_PER_S"}}]}


class Model:
    def __init__(self, engine, claims):
        self.engine, self.claims = engine, claims
        self.calls = []
        self.fail_generation = None
        self.reclaim_on_generation = False
        self.client = ModelStudio(SecretStr("synthetic-not-a-credential"), Budget(100, Decimal("100")), base_url="https://test.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1", transport=httpx.MockTransport(self.respond))

    def respond(self, request):
        wire = json.loads(request.content)
        prompt = wire["messages"][0]["content"]
        payload = json.loads(wire["messages"][1]["content"])
        self.calls.append((prompt, payload))
        if "본문 추출 역할" in prompt:
            output = {"source_ids": [s["source_id"] for s in payload["sources"]]}
        elif "지식 생성 역할" in prompt:
            with self.engine.connect() as c:
                reserved = c.execute(sa.select(db.provider_call_slot).where(db.provider_call_slot.c.state == "RESERVED")).mappings().one()
            if self.reclaim_on_generation:
                with self.engine.begin() as c:
                    c.execute(sa.update(db.model_task).where(db.model_task.c.model_task_id == reserved["model_task_id"]).values(lease_expires_at=sa.func.clock_timestamp() - sa.text("interval '1 second'")))
                with Session(self.engine) as s, s.begin():
                    tasks.claim_task(s, reserved["model_task_id"], "replacement")
            if self.fail_generation:
                status = self.fail_generation
                self.fail_generation = None
                return httpx.Response(status, headers={"Retry-After": "13"}, json={"error": {"message": "synthetic", "type": "synthetic", "code": "synthetic"}}, request=request)
            output = {"claims": self.claims}
        elif "동일 대상만 판정" in prompt:
            candidates = payload["candidates"]
            output = {"decision": "SAME" if candidates else "NEW", "node_id": candidates[0]["node_id"] if candidates else None}
        else:
            output = {"verdict": "TRUE"}
        return httpx.Response(200, request=request, json={
            "id": "synthetic", "object": "chat.completion", "created": 1, "model": wire["model"],
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(output, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        })

    def close(self):
        self.client.close()


def run(engine, doc, model, opts=None):
    opts = opts or options()
    task = worker.enqueue(engine, doc, opts)
    return worker.run_task(engine, task, model.client, opts)


def test_end_to_end_new_nodes_promotion_and_idempotent_success(database):
    doc = document(database)
    model = Model(database, [relation_claim()])
    try:
        result = run(database, doc, model)
        assert result.status == "SUCCESS"
        assert len(result.applied_claim_ids) == 1
        for table, expected in ((db.node, 2), (db.relation, 1), (db.claim, 1), (db.observation, 1), (db.node_alias, 2), (db.provider_call_slot, 1), (db.agent_attempt, 1)):
            assert scalar(database, table) == expected
        with database.connect() as c:
            batch = c.execute(sa.select(db.promotion_batch)).mappings().one()
        assert (batch["promotion_status"], batch["publication_status"]) == ("COMMITTED", "NOT_STARTED")
        count_before = len(model.calls)
        repeated = run(database, doc, model)
        assert repeated.task_id == result.task_id and repeated.status == "SUCCESS"
        assert len(model.calls) == count_before
        assert scalar(database, db.provider_call_slot) == 1
        assert len(model.calls) > 1  # Helpers ran, but did not consume durable slots.
    finally:
        model.close()


def test_existing_claim_semantic_reuse_adds_direct_evidence_only(database):
    first, second = document(database), document(database)
    model = Model(database, [relation_claim()])
    try:
        a, b = run(database, first, model), run(database, second, model)
        assert a.applied_claim_ids == b.applied_claim_ids
        assert scalar(database, db.claim) == 1
        assert scalar(database, db.relation) == 1
        assert scalar(database, db.node) == 2
        assert scalar(database, db.claim_observation) == 2
        assert any("두 Claim의 동일 의미" in prompt for prompt, _ in model.calls)
    finally:
        model.close()


@pytest.mark.parametrize("mode, expected", [("zero", "SUCCESS"), ("blocked", "VALIDATION_BLOCKED"), ("partial", "SUCCESS")])
def test_normal_zero_blocked_and_independent_partial_results(database, mode, expected):
    doc = document(database, "슬롯회사A와 슬롯회사B가 협력한다. 시험칩의 최대 대역폭은 1 TB/s다.")
    proposals = [] if mode == "zero" else [bandwidth_claim()]
    if mode == "partial":
        proposals.insert(0, relation_claim())
    model = Model(database, proposals)
    try:
        result = run(database, doc, model)
        assert result.status == expected
        assert "MAX_MEMORY_BANDWIDTH" in result.unavailable
        assert scalar(database, db.claim) == (1 if mode == "partial" else 0)
        assert scalar(database, db.claim_attribute_value) == 0
        assert scalar(database, db.promotion_batch) == (1 if mode == "partial" else 0)
        assert scalar(database, db.provider_call_slot) == 1
    finally:
        model.close()


@pytest.mark.parametrize("missing", ["contract", "ontology", "validator"])
def test_unregistered_active_reference_data_is_not_silently_seeded(database, missing):
    doc = document(database)
    table = {"contract": db.output_schema_definition, "ontology": db.relation_type_revision, "validator": db.lint_policy_version}[missing]
    with database.begin() as c:
        c.execute(sa.update(table).values(is_active=False))
        if missing == "ontology":
            c.execute(sa.update(db.attribute_revision).values(is_active=False))
    with pytest.raises(ValueError, match="MISSING|MISMATCHED"):
        worker.enqueue(database, doc, options())
    assert scalar(database, db.model_task) == scalar(database, db.provider_call_slot) == 0


def test_rate_limit_retries_product_only_with_new_slot_and_retry_after(database):
    doc = document(database)
    model = Model(database, [relation_claim()])
    model.fail_generation = 429
    try:
        first = run(database, doc, model)
        assert first.status == "RETRY_WAIT"
        with database.connect() as c:
            assert c.execute(sa.select(db.agent_attempt.c.outcome)).scalar_one() == "RATE_LIMITED"
        before = len(model.calls)
        assert run(database, doc, model).status == "RETRY_WAIT"
        assert len(model.calls) == before
        with database.begin() as c:
            c.execute(sa.update(db.model_task).values(next_attempt_at=sa.func.clock_timestamp()))
        model.close()
        model = Model(database, [relation_claim()])
        assert run(database, doc, model).status == "SUCCESS"
        assert scalar(database, db.provider_call_slot) == scalar(database, db.agent_attempt) == 2
    finally:
        model.close()


def test_auth_terminal_manual_reprocess_requires_new_task_generation(database):
    doc = document(database)
    model = Model(database, [relation_claim()])
    model.fail_generation = 401
    try:
        failed = run(database, doc, model)
        assert failed.status == "FINAL_FAILED"
        assert scalar(database, db.provider_call_slot) == 1
        opts = replace(options(), execution_generation="explicit-environment-fix-2")
        with pytest.raises(ValueError, match="REQUIRES_FAILED_TASK"):
            worker.enqueue(database, doc, opts)
        task = worker.enqueue(database, doc, opts, manual_from_task_id=failed.task_id)
        assert task != failed.task_id
        model.close()
        model = Model(database, [relation_claim()])
        assert worker.run_task(database, task, model.client, opts).status == "SUCCESS"
        with database.connect() as c:
            assert c.execute(sa.select(db.model_task.c.status).where(db.model_task.c.model_task_id == failed.task_id)).scalar_one() == "FINAL_FAILED"
    finally:
        model.close()


def test_promotion_failure_rolls_back_new_graph_but_keeps_prior_document(database, monkeypatch):
    first = document(database)
    model = Model(database, [relation_claim()])
    try:
        assert run(database, first, model).status == "SUCCESS"
        second = document(database, "다른회사C와 다른회사D가 협력한다.")
        model.claims = [relation_claim(first="다른회사C", second="다른회사D")]
        original = storage.write_prepared

        def fail_after_writes(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("synthetic-writer-failure")

        monkeypatch.setattr(storage, "write_prepared", fail_after_writes)
        with pytest.raises(RuntimeError, match="synthetic-writer-failure"):
            run(database, second, model)
        assert scalar(database, db.claim) == scalar(database, db.relation) == 1
        assert scalar(database, db.node) == scalar(database, db.source_document) == 2
        assert scalar(database, db.promotion_batch) == 1
        assert scalar(database, db.provider_call_slot) == 2
        with database.connect() as c:
            assert c.execute(sa.select(db.model_task.c.status).where(db.model_task.c.source_document_id == second)).scalar_one() == "FINAL_FAILED"
    finally:
        model.close()


def test_late_provider_return_cannot_resurrect_reclaimed_slot(database):
    doc = document(database)
    model = Model(database, [relation_claim()])
    model.reclaim_on_generation = True
    try:
        result = run(database, doc, model)
        assert result.status == "RUNNING"
        assert result.excluded == (("execution", "LEASE_LOST"),)
        assert scalar(database, db.agent_attempt) == scalar(database, db.claim) == 0
        with database.connect() as c:
            assert c.execute(sa.select(db.provider_call_slot.c.state)).scalar_one() == "UNKNOWN"
    finally:
        model.close()


@pytest.mark.parametrize("kind", ["attribute", "event"])
def test_approved_attribute_and_event_values_have_direct_evidence(database, kind):
    value = {"kind": "NUMBER", "value": "8", "unit": "COUNT"}
    binding = {"kind": "ATTRIBUTE", "binding_id": "b", "code": "CORE_COUNT", "target_mention": "m", "value": value}
    statement, name, node_type = "시험칩은 코어가 8개다.", "시험칩", "TECHNOLOGY"
    if kind == "event":
        statement, name, node_type = "시험발표회는 2026년 9월에 열린다.", "시험발표회", "EVENT"
        binding = {"kind": "EVENT_TIME", "binding_id": "b", "event_mention": "m",
                   "start": {"value": "2026-09-01T00:00:00Z", "precision": "MONTH"},
                   "end": {"value": None, "precision": "UNKNOWN"}}
    proposal = {"candidate_id": "one", "statement": statement, "modality": "FACT", "source_ids": ["s1"],
                "mentions": [{"mention_id": "m", "text": name, "node_type": node_type, "source_ids": ["s1"], "topic_name": None}], "bindings": [binding]}
    model = Model(database, [proposal])
    try:
        assert run(database, document(database, statement), model).status == "SUCCESS"
        assert scalar(database, db.claim_observation) == scalar(database, db.node) == 1
        assert scalar(database, db.claim_attribute_value if kind == "attribute" else db.event_temporal_basis) == 1
        with database.connect() as c:
            claim = c.execute(sa.select(db.claim)).mappings().one()
        assert claim["asserted_from"] is None and claim["asserted_from_precision"] == "UNKNOWN"
    finally:
        model.close()
