from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:80]!r}")
    write(path, content.replace(old, new, 1))


# Repository query: split the combined FTS branch into identity and knowledge buckets.
path = "server/src/ontology_map/db/search.py"
content = read(path)
old = '''_SEARCH_VECTOR_EXPRESSION = """
(
    setweight(to_tsvector('simple', identity_text), 'A')
    ||
    setweight(to_tsvector('simple', knowledge_text), 'B')
)
"""
'''
new = '''_IDENTITY_FTS_EXPRESSION = "to_tsvector('simple', nsd.identity_text)"
_KNOWLEDGE_FTS_EXPRESSION = "to_tsvector('simple', nsd.knowledge_text)"
'''
if old not in content:
    raise RuntimeError("db/search.py: combined FTS expression not found")
content = content.replace(old, new, 1)
marker = "\ndef list_full_text_matches(\n"
index = content.find(marker)
if index < 0:
    raise RuntimeError("db/search.py: list_full_text_matches not found")
content = content[:index] + '''

def _list_fts_matches(
    session: Session,
    query: str,
    limit: int,
    expression: str,
) -> list[SearchNodeRow]:
    statement = sa.text(
        _SEARCHABLE_NODES_CTE
        + f"""
        , search_query AS (
            SELECT websearch_to_tsquery('simple', :query) AS value
        )
        SELECT
            sn.node_id,
            sn.name,
            sn.node_type_code,
            sn.node_type_display_name
        FROM searchable_nodes AS sn
        JOIN node_search_document AS nsd
          ON nsd.node_search_document_id = sn.node_search_document_id
         AND nsd.node_id = sn.node_id
        CROSS JOIN search_query AS sq
        WHERE {expression} @@ sq.value
        ORDER BY
            ts_rank_cd({expression}, sq.value) DESC,
            sn.node_id ASC
        LIMIT :limit
        """
    )
    return _rows(session.execute(statement, {"query": query, "limit": limit}))


def list_identity_text_matches(
    session: Session, query: str, limit: int
) -> list[SearchNodeRow]:
    return _list_fts_matches(session, query, limit, _IDENTITY_FTS_EXPRESSION)


def list_knowledge_text_matches(
    session: Session, query: str, limit: int
) -> list[SearchNodeRow]:
    return _list_fts_matches(session, query, limit, _KNOWLEDGE_FTS_EXPRESSION)
'''
write(path, content)

# Application service: simple domain result + stable global de-duplication.
write(
    "server/src/ontology_map/search.py",
    '''from dataclasses import dataclass
from unicodedata import normalize

from sqlalchemy.orm import Session

from ontology_map.db.search import (
    SearchNodeRow,
    list_exact_alias_matches,
    list_identity_text_matches,
    list_knowledge_text_matches,
)
from ontology_map.exploration import NodeType

MAX_SEARCH_LIMIT = 20


class InvalidSearchQueryError(Exception):
    pass


@dataclass(frozen=True)
class SearchNode:
    node_id: int
    name: str
    node_type: NodeType


def _search_node(row: SearchNodeRow) -> SearchNode:
    return SearchNode(
        node_id=row.node_id,
        name=row.name,
        node_type=NodeType(
            code=row.node_type_code,
            display_name=row.node_type_display_name,
        ),
    )


def search_nodes(session: Session, query: str, limit: int = 5) -> list[SearchNode]:
    normalized_query = normalize("NFC", query).strip()
    if not normalized_query or not 1 <= limit <= MAX_SEARCH_LIMIT:
        raise InvalidSearchQueryError

    seen_node_ids: set[int] = set()
    results: list[SearchNode] = []
    buckets = (
        list_exact_alias_matches(session, normalized_query, limit),
        list_identity_text_matches(session, normalized_query, limit),
        list_knowledge_text_matches(session, normalized_query, limit),
    )
    for rows in buckets:
        for row in rows:
            if row.node_id in seen_node_ids:
                continue
            seen_node_ids.add(row.node_id)
            results.append(_search_node(row))
            if len(results) == limit:
                return results
    return results
''',
)

# HTTP response no longer exposes ranking reasons.
replace_once(
    "server/src/ontology_map/api.py",
    '''class SearchResultResponse(BaseModel):
    node_id: str
    name: str
    node_type: NodeTypeResponse
    match_reasons: list[Literal["EXACT_ALIAS", "FULL_TEXT"]]
''',
    '''class SearchResultResponse(BaseModel):
    node_id: str
    name: str
    node_type: NodeTypeResponse
''',
)
replace_once(
    "server/src/ontology_map/api.py",
    '''            SearchResultResponse(
                node_id=str(result.node.node_id),
                name=result.node.name,
                node_type=NodeTypeResponse(
                    code=result.node.node_type.code,
                    display_name=result.node.node_type.display_name,
                ),
                match_reasons=list(result.match_reasons),
            )
''',
    '''            SearchResultResponse(
                node_id=str(result.node_id),
                name=result.name,
                node_type=NodeTypeResponse(
                    code=result.node_type.code,
                    display_name=result.node_type.display_name,
                ),
            )
''',
)

# Web adapter and UI no longer depend on match reasons.
replace_once(
    "web/src/data.ts",
    '''export type SearchMatchReason = "EXACT_ALIAS" | "FULL_TEXT";

export interface SearchCandidate {
  nodeId: string;
  name: string;
  kind: string;
  kindCode: string;
  matchReasons: SearchMatchReason[];
}
''',
    '''export interface SearchCandidate {
  nodeId: string;
  name: string;
  kind: string;
  kindCode: string;
}
''',
)
replace_once(
    "web/src/data.ts",
    '''function matchReason(value: unknown): SearchMatchReason {
  if (value === "EXACT_ALIAS" || value === "FULL_TEXT") return value;
  throw new APIRequestError("INVALID_RESPONSE", 0, true);
}

''',
    "",
)
replace_once(
    "web/src/data.ts",
    '''      kind: string(type.display_name),
      kindCode: string(type.code),
      matchReasons: array(item.match_reasons).map(matchReason),
''',
    '''      kind: string(type.display_name),
      kindCode: string(type.code),
''',
)

replace_once(
    "web/src/NodeSearch.tsx",
    '''import {
  APIRequestError,
  fetchNodeSearch,
  type SearchCandidate,
  type SearchMatchReason,
} from "./data";

type SearchStatus = "idle" | "loading" | "results" | "empty" | "error";

const reasonCopy: Record<SearchMatchReason, string> = {
  EXACT_ALIAS: "별칭 정확 일치",
  FULL_TEXT: "공개 지식 일치",
};
''',
    '''import { APIRequestError, fetchNodeSearch, type SearchCandidate } from "./data";

type SearchStatus = "idle" | "loading" | "results" | "empty" | "error";
''',
)
replace_once(
    "web/src/NodeSearch.tsx",
    '''      <span className={styles.candidateMain}>
        <strong>{candidate.name}</strong>
        <span>{candidate.kind}</span>
      </span>
      <span>
        {candidate.matchReasons.map((reason) => reasonCopy[reason]).join(" · ")}
      </span>
''',
    '''      <span className={styles.candidateMain}>
        <strong>{candidate.name}</strong>
        <span>{candidate.kind}</span>
      </span>
''',
)

replace_once(
    "web/src/App.test.tsx",
    '''      node_type: { code: "TECHNOLOGY", display_name: "기술" },
      match_reasons: ["EXACT_ALIAS", "FULL_TEXT"],
''',
    '''      node_type: { code: "TECHNOLOGY", display_name: "기술" },
''',
)
replace_once(
    "web/src/App.test.tsx",
    '''      node_type: { code: "TECHNOLOGY", display_name: "기술" },
      match_reasons: ["FULL_TEXT"],
''',
    '''      node_type: { code: "TECHNOLOGY", display_name: "기술" },
''',
)
replace_once(
    "web/src/App.test.tsx",
    '''    expect(options.map((option) => option.textContent)).toEqual([
      "HBF기술별칭 정확 일치 · 공개 지식 일치",
      "UCIe기술공개 지식 일치",
    ]);
''',
    '''    expect(options.map((option) => option.textContent)).toEqual([
      "HBF기술",
      "UCIe기술",
    ]);
''',
)

# Focused PostgreSQL/API tests for the approved three-bucket contract.
write(
    "server/tests/test_search.py",
    '''import asyncio
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
from ontology_map.search import search_nodes

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


def hold_existing_nodes(session: Session) -> None:
    session.execute(
        knowledge_item.update()
        .where(knowledge_item.c.item_kind == "NODE")
        .values(current_state="ON_HOLD")
    )


def insert_public_node(
    session: Session,
    name: str,
    *,
    identity_text: str | None = None,
    knowledge_text: str = "공개 Relation 없는 테스트 node",
) -> int:
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
            identity_text=identity_text or name,
            knowledge_text=knowledge_text,
            input_hash=sha256(f"search:{node_id}".encode()).digest(),
            generator_version="search-117-test-v1",
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


def add_alias(session: Session, node_id: int, alias: str) -> None:
    session.execute(
        node_alias.insert().values(
            node_id=node_id,
            alias_text=alias,
            language="ko",
            is_preferred=False,
        )
    )


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


def test_repository_orders_three_buckets_dedupes_and_preserves_limit() -> None:
    load_hbf_fixture()
    with rollback_session() as session:
        hold_existing_nodes(session)
        exact_id = insert_public_node(
            session,
            "정확 후보",
            identity_text="bucketterm",
            knowledge_text="bucketterm",
        )
        add_alias(session, exact_id, "bucketterm")
        identity_id = insert_public_node(
            session,
            "정체성 후보",
            identity_text="bucketterm",
            knowledge_text="bucketterm",
        )
        knowledge_id = insert_public_node(
            session,
            "설명 후보",
            identity_text="otheridentity",
            knowledge_text="bucketterm",
        )
        results = search_nodes(session, "bucketterm", 3)

    ids = [result.node_id for result in results]
    assert ids == [exact_id, identity_id, knowledge_id]
    assert len(ids) == len(set(ids)) == 3
    assert ids.count(identity_id) == 1


def test_exact_alias_bucket_uses_node_id_for_deterministic_order() -> None:
    load_hbf_fixture()
    with rollback_session() as session:
        hold_existing_nodes(session)
        first_id = insert_public_node(session, "exact-a")
        second_id = insert_public_node(session, "exact-b")
        add_alias(session, first_id, "same-exact")
        add_alias(session, second_id, "same-exact")
        results = search_nodes(session, "same-exact", 2)

    assert [result.node_id for result in results] == [first_id, second_id]


@pytest.mark.parametrize("field", ["identity", "knowledge"])
def test_fts_bucket_breaks_rank_ties_by_node_id(field: str) -> None:
    load_hbf_fixture()
    with rollback_session() as session:
        hold_existing_nodes(session)
        kwargs = (
            {"identity_text": "rankterm", "knowledge_text": "other"}
            if field == "identity"
            else {"identity_text": "other", "knowledge_text": "rankterm"}
        )
        first_id = insert_public_node(session, f"{field}-a", **kwargs)
        second_id = insert_public_node(session, f"{field}-b", **kwargs)
        results = search_nodes(session, "rankterm", 2)

    assert [result.node_id for result in results] == [first_id, second_id]


def test_exact_and_fts_converging_after_merge_return_canonical_once() -> None:
    load_hbf_fixture()
    with rollback_session() as session:
        hold_existing_nodes(session)
        source_id = insert_public_node(
            session,
            "merge-term",
            identity_text="merge-term",
            knowledge_text="merge-term",
        )
        canonical_id = insert_public_node(
            session,
            "canonical target",
            identity_text="merge-term",
            knowledge_text="merge-term",
        )
        session.execute(
            node_merge.insert().values(
                source_node_id=source_id,
                canonical_node_id=canonical_id,
                merge_reason="검색 #117 canonical dedupe 테스트",
                merged_at=NOW,
            )
        )
        results = search_nodes(session, "merge-term", 5)

    assert [result.node_id for result in results] == [canonical_id]
    assert results[0].name == "canonical target"


def test_repository_includes_relationless_public_node() -> None:
    load_hbf_fixture()
    with rollback_session() as session:
        node_id = insert_public_node(session, "독립 공개 node")
        results = search_nodes(session, "독립 공개 node", 5)

    assert len(results) == 1
    assert results[0].node_id == node_id


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

    assert all(result.node_id != node_ids["hbf"] for result in blocked)
    assert all(result.node_id != node_ids["sk_hynix"] for result in invalid_basis)


def test_http_contract_returns_minimal_items_and_empty_results() -> None:
    load_hbf_fixture()
    status, body = request("/api/v1/nodes/search?q=HBF&limit=2")
    empty_status, empty_body = request("/api/v1/nodes/search?q=no-such-node")

    assert status == 200
    assert set(body) == {"items"}
    assert len(body["items"]) == 2
    assert set(body["items"][0]) == {"node_id", "name", "node_type"}
    assert isinstance(body["items"][0]["node_id"], str)
    assert empty_status == 200
    assert empty_body == {"items": []}


def test_openapi_search_result_has_no_match_reasons() -> None:
    schema = app.openapi()["components"]["schemas"]["SearchResultResponse"]
    assert set(schema["properties"]) == {"node_id", "name", "node_type"}


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
''',
)

# Product/docs: make the current contract reflect #117 without touching archive/history.
replace_once(
    "docs/product/design.md",
    '| search | `items[] { node_id, name, node_type, match_reasons[] }` |',
    '| search | `items[] { node_id, name, node_type }` |',
)
replace_once(
    "docs/product/design.md",
    '''현재 search는 alias 정확 일치를 첫 bucket으로 반환한 뒤 `identity_text`와 `knowledge_text`를 함께 사용한 PostgreSQL `simple` FTS 결과를 이어서 반환하고 HTTP 응답과 web에 `match_reasons`를 노출한다. #121에 따라 node embedding 저장 구조와 pgvector 의존성, publication READY의 embedding 요구는 제거됐다. #117은 후속으로 exact alias → identity FTS → knowledge FTS의 세 bucket을 고정하고 `match_reasons`와 검색 이유 표시를 제거한다. 실제 한국어 단어 FTS 누락 사례가 확인될 때만 #80에서 tokenizer, `pg_trgm` 또는 BM25 같은 확장을 다시 검토한다.''',
    '''현재 search는 exact alias → `identity_text` 단어 FTS → `knowledge_text` 단어 FTS의 세 bucket을 순서대로 반환한다. exact alias bucket은 `node_id ASC`, 각 FTS bucket은 `ts_rank_cd DESC, node_id ASC`로 정렬하고 활성 merge를 해소한 같은 canonical Node는 전체 결과에서 한 번만 반환한다. HTTP 응답과 web 후보에는 `node_id`, 이름과 유형만 포함하며 검색 이유를 노출하지 않는다. READY, selected `search_document_basis`와 열린 `BLOCKING` lint 공개 필터를 유지하고 `node_context.context_text`는 검색 입력으로 사용하지 않는다. 실제 한국어 단어 FTS 누락 사례가 확인될 때만 #80에서 tokenizer, `pg_trgm` 또는 BM25 같은 확장을 다시 검토한다.''',
)
replace_once(
    "docs/product/design.md",
    '''검색 panel에는 `노드 검색`, 현재 중심 주변의 표시 node 수와 시간 범위만 둔다. 현재 snapshot은 검색 후보마다 node 이름, 유형과 `match_reasons` 기반의 짧은 검색 이유를 표시한다. 검색 input과 결과는 keyboard로 이동하고 선택할 수 있어야 하며, 후보를 선택하면 node 클릭과 같은 중심 이동을 실행한다. #117이 구현되면 검색 이유를 제거하고 후보에는 node 이름과 유형만 남긴다. 직접 이웃과 2단계 이웃의 개별 수는 기본 화면에 반복하지 않는다.''',
    '''검색 panel에는 `노드 검색`, 현재 중심 주변의 표시 node 수와 시간 범위만 둔다. 검색 후보에는 node 이름과 유형만 표시하고 순위 이유나 내부 점수는 노출하지 않는다. 검색 input과 결과는 keyboard로 이동하고 선택할 수 있어야 하며, 후보를 선택하면 node 클릭과 같은 중심 이동을 실행한다. 직접 이웃과 2단계 이웃의 개별 수는 기본 화면에 반복하지 않는다.''',
)

replace_once(
    "docs/data/logical-schema.md",
    '''현재 HTTP 검색은 alias 정확 일치 뒤 `identity_text`·`knowledge_text`를 합친 `simple` FTS 결과를 반환한다. [#121](https://github.com/studylida/ontology-map/issues/121)에 따라 query-time vector 검색과 node embedding 저장 경로는 제거됐다. [#117](https://github.com/studylida/ontology-map/issues/117)은 후속으로 alias → identity FTS → knowledge FTS bucket과 검색 응답 단순화를 구현하며, 그 전까지 검색 응답의 정확한 현재 형태는 [제품 설계](../product/design.md)를 따른다.''',
    '''현재 HTTP 검색은 exact alias → `identity_text` 단어 FTS → `knowledge_text` 단어 FTS의 세 bucket을 순서대로 반환한다. exact alias는 `node_id ASC`, 각 FTS bucket은 `ts_rank_cd DESC, node_id ASC`이며 활성 merge를 해소한 같은 canonical Node는 전체 결과에서 한 번만 반환한다. 검색 응답은 Node ID, 이름과 유형만 제공한다. `node_context.context_text`는 검색 입력이 아니며 READY, selected `search_document_basis`와 열린 `BLOCKING` lint 공개 필터를 유지한다. [#121](https://github.com/studylida/ontology-map/issues/121)에 따라 query-time vector 검색과 node embedding 저장 경로는 제거됐다.''',
)

replace_once(
    "docs/data/physical-schema.md",
    '''```sql
setweight(to_tsvector('simple', identity_text), 'A')
|| setweight(to_tsvector('simple', knowledge_text), 'B')
```

`node_context`, `followup_question`과 `node_insight`는 같은 검색 문서·node 조합을 물리 FK로 고정한다.''',
    '''```sql
setweight(to_tsvector('simple', identity_text), 'A')
|| setweight(to_tsvector('simple', knowledge_text), 'B')
```

사용자 검색은 이 저장 문서에서 exact alias → `identity_text` FTS → `knowledge_text` FTS를 별도 bucket으로 평가한다. exact alias는 `node_id ASC`, 각 FTS bucket은 `ts_rank_cd DESC, node_id ASC`로 정렬하고 canonical Node를 전체 결과에서 한 번만 반환한다. `node_context.context_text`는 검색 입력으로 사용하지 않는다. 이 검색 순위 변경은 table, column, migration이나 위 expression GIN을 변경하지 않는다.

`node_context`, `followup_question`과 `node_insight`는 같은 검색 문서·node 조합을 물리 FK로 고정한다.''',
)

replace_once(
    "docs/development/implementation-stack.md",
    '''| 검색 | alias 정확 일치 뒤 `identity_text`·`knowledge_text`를 합친 `simple` FTS, 응답에 `match_reasons` 포함 | [#117](https://github.com/studylida/ontology-map/issues/117): alias → identity FTS → knowledge FTS, 이유 필드 제거. #121 뒤 구현 |''',
    '''| 검색 | exact alias → `identity_text` FTS → `knowledge_text` FTS. exact alias는 `node_id ASC`, FTS는 `ts_rank_cd DESC, node_id ASC`; canonical Node 전역 중복 제거. 응답은 ID·이름·유형만 제공 | [#80](https://github.com/studylida/ontology-map/issues/80)은 실제 한국어 단어 FTS 누락이 재현될 때만 검토 |''',
)
replace_once(
    "docs/development/implementation-stack.md",
    '''| 검색 기반 | PostgreSQL native FTS만 사용하며 node embedding·pgvector 저장/실행 의존성은 없음 | [#121](https://github.com/studylida/ontology-map/issues/121)에서 초기 baseline 교체와 개발 DB 재생성 기준으로 제거. #117의 세 검색 bucket과 응답 단순화는 별도 후속 |''',
    '''| 검색 기반 | PostgreSQL native FTS만 사용하며 node embedding·pgvector 저장/실행 의존성은 없음 | [#121](https://github.com/studylida/ontology-map/issues/121)에서 초기 baseline 교체와 개발 DB 재생성 기준으로 제거 완료 |''',
)

write(
    "HANDOFF.md",
    '''# ontology-map #117 구현 인계

> 작업 기준: `main` `44bdc4bde22c1eca24f9106e4aa4490fdcb75744`에서 분기한 `feat/117-search-buckets`. #121은 PR #196 Rebase merge로 완료·종료됐다. 병합 전에는 GitHub의 실제 head와 검증 상태를 다시 확인한다.

## #117 현재 계약

- 사용자 검색 순서는 exact alias → `identity_text` FTS → `knowledge_text` FTS다.
- exact alias bucket은 `node_id ASC`, 각 FTS bucket은 `ts_rank_cd DESC, node_id ASC`다.
- 활성 merge를 해소한 canonical Node는 전체 결과에서 한 번만 반환하고, 앞 bucket 중복이 뒤 bucket의 고유 결과를 불필요하게 `limit` 밖으로 밀어내지 않게 한다.
- READY / selected `search_document_basis` / 열린 `BLOCKING` lint 필터와 NFC·빈 query·limit 검증을 유지한다.
- `node_context.context_text`는 검색 입력으로 사용하지 않는다.
- domain·HTTP·web에서 `match_reasons`와 검색 이유 표시를 제거하고 후보에는 Node ID·이름·유형만 남긴다.

## 제외 범위

- vector, semantic, fuzzy, BM25, `pg_trgm`, RRF, ANN을 추가하지 않는다.
- #128 Entity Resolution 후보 검색 코드를 수정·공용화하지 않는다.
- #80과 #193을 선제 구현하지 않는다.
- #192와 겹치는 #121 의존성/문서 변경은 이 Issue에서 다시 손대지 않는다.

## 다음 작업

- #117 구현과 검증이 끝나면 PR을 병합하지 않고 Feedback 검토를 기다린다.
- #126은 승인 ontology 목록이 있지만 제품 DB 적재·migration·fixture 변경은 아직 승인 범위가 아니다. `MAX_MEMORY_BANDWIDTH`의 `GB_PER_S | TB_PER_S`와 단일 `attribute_revision.unit_rule` 충돌은 제품 계약 재결정 전까지 구현하지 않는다. EVENT → TECHNOLOGY 새 Relation도 승인되지 않았다.
''',
)

print("#117 patch applied")
