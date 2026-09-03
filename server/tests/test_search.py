import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from starlette.types import Message, Scope

from ontology_map.db.fixture import load_hbf_fixture
from ontology_map.db.schema import (
    knowledge_item,
    lint_finding,
    lint_policy_rule,
    lint_run,
    node,
    node_alias,
    node_merge,
    node_search_document,
    promotion_batch,
    publication_affected_node,
    search_document_basis,
)
from ontology_map.db.session import get_engine
from ontology_map.main import app
from ontology_map.search import MatchReason, search_nodes

NOW = datetime(2026, 9, 3, 0, 0, tzinfo=UTC)


@contextmanager
def rollback_session() -> Iterator[Session]:
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection) as session:
                yield session
        finally:
            transaction.rollback()


async def asgi_get(target: str) -> tuple[int, dict[str, Any]]:
    parsed = urlsplit(target)
    messages: list[Message] = []
    request_sent = False

    async def receive() -> Message:
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": parsed.path,
        "raw_path": parsed.path.encode(),
        "query_string": parsed.query.encode(),
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "state": {},
    }
    await app(scope, receive, send)
    start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return int(start["status"]), json.loads(body)


def request(target: str) -> tuple[int, dict[str, Any]]:
    return asyncio.run(asgi_get(target))


def insert_relationless_public_node(session: Session, name: str) -> int:
    batch_id = session.scalar(
        sa.select(promotion_batch.c.promotion_batch_id)
        .where(promotion_batch.c.publication_status == "READY")
        .order_by(
            promotion_batch.c.ready_at.desc(),
            promotion_batch.c.promotion_batch_id.desc(),
        )
        .limit(1)
    )
    node_type_id = session.scalar(sa.select(node.c.node_type_id).limit(1))
    assert batch_id is not None
    assert node_type_id is not None
    node_id = session.execute(
        knowledge_item.insert()
        .values(
            item_kind="NODE",
            current_state="EVIDENCE_VERIFIED",
            promotion_batch_id=batch_id,
        )
        .returning(knowledge_item.c.knowledge_item_id)
    ).scalar_one()
    session.execute(node.insert().values(node_id=node_id, node_type_id=node_type_id))
    session.execute(
        node_alias.insert().values(
            node_id=node_id,
            alias_text=name,
            language="ko",
            is_preferred=True,
        )
    )
    search_document_id = session.execute(
        node_search_document.insert()
        .values(
            node_id=node_id,
            identity_text=name,
            knowledge_text="공개되었지만 Relation이 없는 node",
            input_hash=sha256(f"search:{node_id}".encode()).digest(),
            generator_version="integration-test-v1",
        )
        .returning(node_search_document.c.node_search_document_id)
    ).scalar_one()
    session.execute(
        search_document_basis.insert().values(
            node_search_document_id=search_document_id,
            knowledge_item_id=node_id,
        )
    )
    session.execute(
        publication_affected_node.insert().values(
            promotion_batch_id=batch_id,
            node_id=node_id,
            node_search_document_id=search_document_id,
        )
    )
    return int(node_id)


def add_blocking_finding(session: Session, node_id: int) -> None:
    policy_rule = session.execute(
        sa.select(
            lint_policy_rule.c.lint_policy_rule_id,
            lint_policy_rule.c.lint_policy_version_id,
        )
        .where(lint_policy_rule.c.severity == "BLOCKING")
        .limit(1)
    ).one()
    run_id = session.execute(
        lint_run.insert()
        .values(
            lint_policy_version_id=policy_rule.lint_policy_version_id,
            status="SUCCESS",
            started_at=NOW - timedelta(seconds=1),
            completed_at=NOW,
        )
        .returning(lint_run.c.lint_run_id)
    ).scalar_one()
    session.execute(
        lint_finding.insert().values(
            finding_key=sha256(f"search-test:{node_id}".encode()).digest(),
            knowledge_item_id=node_id,
            lint_policy_rule_id=policy_rule.lint_policy_rule_id,
            first_detected_run_id=run_id,
            latest_detected_run_id=run_id,
            first_detected_at=NOW,
            last_detected_at=NOW,
            message="검색 통합 테스트 차단 finding",
        )
    )


def test_repository_prioritizes_exact_alias_then_fts_with_stable_ties() -> None:
    _created, node_ids = load_hbf_fixture()
    with rollback_session() as session:
        session.execute(
            node_alias.insert().values(
                node_id=node_ids["hbf"],
                alias_text="공개",
                language="ko",
                is_preferred=False,
            )
        )
        results = search_nodes(session, "공개", 3)

    assert [result.node.node_id for result in results] == [
        node_ids["hbf"],
        node_ids["sk_hynix"],
        node_ids["sandisk"],
    ]
    assert results[0].match_reasons == (
        MatchReason.EXACT_ALIAS,
        MatchReason.FULL_TEXT,
    )
    assert results[1].match_reasons == (MatchReason.FULL_TEXT,)


def test_repository_follows_active_merge_chain_to_canonical_node() -> None:
    _created, node_ids = load_hbf_fixture()
    with rollback_session() as session:
        session.execute(
            node_merge.insert(),
            [
                {
                    "source_node_id": node_ids["sk_hynix"],
                    "canonical_node_id": node_ids["sandisk"],
                    "merge_reason": "검색 통합 테스트",
                    "merged_at": NOW,
                },
                {
                    "source_node_id": node_ids["sandisk"],
                    "canonical_node_id": node_ids["hbf"],
                    "merge_reason": "검색 통합 테스트",
                    "merged_at": NOW,
                },
            ],
        )
        results = search_nodes(session, "SK하이닉스", 5)

    assert results[0].node.node_id == node_ids["hbf"]
    assert results[0].node.name == "HBF"
    assert MatchReason.EXACT_ALIAS in results[0].match_reasons


def test_repository_includes_relationless_public_node() -> None:
    load_hbf_fixture()
    with rollback_session() as session:
        node_id = insert_relationless_public_node(session, "독립 공개 node")
        results = search_nodes(session, "독립 공개 node", 5)

    assert len(results) == 1
    assert results[0].node.node_id == node_id
    assert results[0].match_reasons[0] == MatchReason.EXACT_ALIAS


def test_repository_rechecks_node_lint_and_selected_basis() -> None:
    _created, node_ids = load_hbf_fixture()
    with rollback_session() as session:
        add_blocking_finding(session, node_ids["hbf"])
        blocked = search_nodes(session, "HBF", 20)

        basis_item_id = session.scalar(
            sa.select(search_document_basis.c.knowledge_item_id)
            .join(
                publication_affected_node,
                publication_affected_node.c.node_search_document_id
                == search_document_basis.c.node_search_document_id,
            )
            .join(
                promotion_batch,
                promotion_batch.c.promotion_batch_id
                == publication_affected_node.c.promotion_batch_id,
            )
            .where(
                publication_affected_node.c.node_id == node_ids["sk_hynix"],
                promotion_batch.c.publication_status == "READY",
                search_document_basis.c.knowledge_item_id != node_ids["sk_hynix"],
            )
            .order_by(
                promotion_batch.c.ready_at.desc(),
                promotion_batch.c.promotion_batch_id.desc(),
                search_document_basis.c.knowledge_item_id,
            )
            .limit(1)
        )
        assert basis_item_id is not None
        session.execute(
            knowledge_item.update()
            .where(knowledge_item.c.knowledge_item_id == basis_item_id)
            .values(current_state="ON_HOLD")
        )
        invalid_basis = search_nodes(session, "SK하이닉스", 20)

    assert all(result.node.node_id != node_ids["hbf"] for result in blocked)
    assert all(result.node.node_id != node_ids["sk_hynix"] for result in invalid_basis)


def test_http_contract_returns_string_ids_and_empty_results() -> None:
    load_hbf_fixture()
    status, body = request("/api/v1/nodes/search?q=HBF&limit=2")
    empty_status, empty_body = request("/api/v1/nodes/search?q=no-such-node")

    assert status == 200
    assert set(body) == {"items"}
    assert len(body["items"]) == 2
    assert set(body["items"][0]) == {
        "node_id",
        "name",
        "node_type",
        "match_reasons",
    }
    assert isinstance(body["items"][0]["node_id"], str)
    assert body["items"][0]["match_reasons"][0] == "EXACT_ALIAS"
    assert empty_status == 200
    assert empty_body == {"items": []}


@pytest.mark.parametrize(
    "target",
    [
        "/api/v1/nodes/search",
        "/api/v1/nodes/search?q=%20%20",
        "/api/v1/nodes/search?q=HBF&limit=0",
        "/api/v1/nodes/search?q=HBF&limit=21",
    ],
)
def test_http_contract_rejects_invalid_query(target: str) -> None:
    load_hbf_fixture()
    status, body = request(target)
    assert status == 422
    assert body == {"error": {"code": "INVALID_REQUEST", "retryable": False}}
