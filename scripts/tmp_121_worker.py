from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one occurrence, found {count}")
    return text.replace(old, new, 1)


def replace_all(text: str, old: str, new: str, *, label: str, expected: int | None = None) -> str:
    count = text.count(old)
    if expected is not None and count != expected:
        raise RuntimeError(f"{label}: expected {expected} occurrences, found {count}")
    if count == 0:
        raise RuntimeError(f"{label}: no occurrence found")
    return text.replace(old, new)


def remove_between(text: str, start: str, end: str, *, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"{label}: start marker not found")
    end_index = text.find(end, start_index + len(start))
    if end_index < 0:
        raise RuntimeError(f"{label}: end marker not found")
    return text[:start_index] + end + text[end_index + len(end):]


def patch_schema() -> None:
    path = "server/src/ontology_map/db/schema.py"
    text = read(path)
    text = replace_once(text, "from pgvector.sqlalchemy import Vector\n", "", label="schema Vector import")
    text = replace_once(
        text,
        '    "\'FOLLOWUP_QUESTIONS\', \'NODE_INSIGHT\', \'EMBEDDING\'"\n',
        '    "\'FOLLOWUP_QUESTIONS\', \'NODE_INSIGHT\'"\n',
        label="schema model task kinds",
    )
    text = replace_once(
        text,
        """    sa.CheckConstraint(\n        \"(task_kind = 'EMBEDDING' AND output_schema_definition_id IS NULL \"\n        \"AND prompt_version IS NULL) OR \"\n        \"(task_kind <> 'EMBEDDING' AND output_schema_definition_id IS NOT NULL \"\n        \"AND prompt_version IS NOT NULL)\",\n        name=\"ck_model_task__output_contract\",\n    ),\n""",
        """    sa.CheckConstraint(\n        \"output_schema_definition_id IS NOT NULL AND prompt_version IS NOT NULL\",\n        name=\"ck_model_task__output_contract\",\n    ),\n""",
        label="schema model task output contract",
    )
    text = remove_between(
        text,
        "\nnode_embedding = sa.Table(",
        "\nnode_context = sa.Table(",
        label="schema node_embedding table",
    )
    text = replace_once(
        text,
        '    sa.Column("node_embedding_id", sa.BigInteger),\n',
        "",
        label="schema publication embedding column",
    )
    embedding_fk = """    sa.ForeignKeyConstraint(\n        (\"node_embedding_id\", \"node_search_document_id\", \"node_id\"),\n        (\n            \"node_embedding.node_embedding_id\",\n            \"node_embedding.node_search_document_id\",\n            \"node_embedding.node_id\",\n        ),\n        name=\"fk_publication_affected_node__embedding\",\n        ondelete=\"RESTRICT\",\n        onupdate=\"RESTRICT\",\n    ),\n"""
    text = replace_once(text, embedding_fk, "", label="schema publication embedding fk")
    embedding_check = """    sa.CheckConstraint(\n        \"node_embedding_id IS NULL OR node_search_document_id IS NOT NULL\",\n        name=\"ck_publication_affected_node__embedding_document\",\n    ),\n"""
    text = replace_once(text, embedding_check, "", label="schema publication embedding check")
    write(path, text)


def patch_migration() -> None:
    path = "server/migrations/versions/0001_create_frozen_schema.py"
    text = read(path)
    text = replace_once(text, "import pgvector.sqlalchemy\n", "", label="migration pgvector import")
    text = replace_once(text, '    op.execute("CREATE EXTENSION IF NOT EXISTS vector")\n', "", label="migration create vector extension")
    text = replace_once(text, '    op.execute("DROP EXTENSION IF EXISTS vector")\n', "", label="migration drop vector extension")
    text = replace_once(
        text,
        "task_kind IN ('KNOWLEDGE_EXTRACTION', 'ENTITY_RESOLUTION_PROPOSAL', 'EVIDENCE_LINEAGE_PROPOSAL', 'CONFLICT_SUMMARY', 'NODE_CONTEXT', 'FOLLOWUP_QUESTIONS', 'NODE_INSIGHT', 'EMBEDDING')",
        "task_kind IN ('KNOWLEDGE_EXTRACTION', 'ENTITY_RESOLUTION_PROPOSAL', 'EVIDENCE_LINEAGE_PROPOSAL', 'CONFLICT_SUMMARY', 'NODE_CONTEXT', 'FOLLOWUP_QUESTIONS', 'NODE_INSIGHT')",
        label="migration model task kinds",
    )
    text = replace_once(
        text,
        "(task_kind = 'EMBEDDING' AND output_schema_definition_id IS NULL AND prompt_version IS NULL) OR (task_kind <> 'EMBEDDING' AND output_schema_definition_id IS NOT NULL AND prompt_version IS NOT NULL)",
        "output_schema_definition_id IS NOT NULL AND prompt_version IS NOT NULL",
        label="migration model task output contract",
    )
    text = remove_between(
        text,
        '    op.create_table(\n        "node_embedding",',
        '    op.create_table(\n        "node_insight",',
        label="migration node_embedding table",
    )
    text = replace_once(
        text,
        '        sa.Column("node_embedding_id", sa.BigInteger(), nullable=True),\n',
        "",
        label="migration publication embedding column",
    )
    text = replace_once(
        text,
        """        sa.CheckConstraint(\n            \"node_embedding_id IS NULL OR node_search_document_id IS NOT NULL\",\n            name=\"ck_publication_affected_node__embedding_document\",\n        ),\n""",
        "",
        label="migration publication embedding check",
    )
    text = replace_once(
        text,
        """        sa.ForeignKeyConstraint(\n            [\"node_embedding_id\", \"node_search_document_id\", \"node_id\"],\n            [\n                \"node_embedding.node_embedding_id\",\n                \"node_embedding.node_search_document_id\",\n                \"node_embedding.node_id\",\n            ],\n            name=\"fk_publication_affected_node__embedding\",\n            onupdate=\"RESTRICT\",\n            ondelete=\"RESTRICT\",\n        ),\n""",
        "",
        label="migration publication embedding fk",
    )
    text = replace_once(
        text,
        '    op.drop_index("ix_node_embedding__search_document", table_name="node_embedding")\n    op.drop_table("node_embedding")\n',
        "",
        label="migration downgrade node_embedding",
    )
    write(path, text)


def patch_fixtures() -> None:
    path = "server/src/ontology_map/db/fixture.py"
    text = read(path)
    text = replace_once(text, "    node_embedding,\n", "", label="fixture node_embedding import")
    text = replace_once(
        text,
        """EMBEDDING_MODEL_VERSION = (\n    \"alibaba-model-studio:ap-southeast-1:qwen3.7-text-embedding:dense:1024:document-v1\"\n)\n\n""",
        "",
        label="fixture embedding model constant",
    )
    text = replace_once(
        text,
        """    for vector_slot, (node_key, node_name, _type_code, _evidence_key) in enumerate(\n        NODE_DEFINITIONS\n    ):\n""",
        """    for node_key, node_name, _type_code, _evidence_key in NODE_DEFINITIONS:\n""",
        label="fixture artifact loop",
    )
    text = remove_between(
        text,
        '        embedding_input_hash = _digest(f"{identity_text}\\n\\n{knowledge_text}")\n',
        "        context_task_id = _insert_successful_task(\n",
        label="fixture embedding artifact",
    )
    text = replace_once(
        text,
        "                node_embedding_id=embedding_id,\n",
        "",
        label="fixture publication embedding pointer",
    )
    write(path, text)

    path = "server/src/ontology_map/db/review_fixture.py"
    text = read(path)
    text = replace_once(text, "    vector_slot: int,\n", "", label="review fixture vector slot parameter")
    text = remove_between(
        text,
        "    task = _insert_successful_task(\n        c,\n        \"EMBEDDING\",\n",
        "    context_task = _insert_successful_task(\n",
        label="review fixture embedding artifact",
    )
    text = replace_once(text, "            node_embedding_id=embedding,\n", "", label="review fixture publication embedding pointer")
    text = replace_once(
        text,
        "            contracts,\n            index,\n        )\n",
        "            contracts,\n        )\n",
        label="review fixture artifacts call",
    )
    write(path, text)

    path = "server/src/ontology_map/db/panel_fixture.py"
    text = read(path)
    text = replace_once(
        text,
        "            contracts,\n            index + 120,\n        )\n",
        "            contracts,\n        )\n",
        label="panel fixture artifacts call",
    )
    write(path, text)


def patch_dependency_and_compose() -> None:
    path = "server/pyproject.toml"
    text = read(path)
    text = replace_once(text, '    "pgvector==0.5.0",\n', "", label="pyproject pgvector dependency")
    write(path, text)

    image = os.environ.get("ONTOLOGY_MAP_POSTGRES_IMAGE")
    if not image:
        raise RuntimeError("ONTOLOGY_MAP_POSTGRES_IMAGE is required")
    path = "compose.yaml"
    text = read(path)
    text = re.sub(
        r"(?m)^    image: pgvector/pgvector:0\.8\.6-pg18@sha256:[0-9a-f]+$",
        f"    image: {image}",
        text,
        count=1,
    )
    if image not in text:
        raise RuntimeError("compose PostgreSQL image replacement failed")
    write(path, text)


def patch_tests() -> None:
    path = "server/tests/test_schema.py"
    text = read(path)
    text = replace_once(text, "    assert len(application_tables) == 49\n", "    assert len(application_tables) == 48\n", label="schema table count")
    start = text.index("def test_postgresql_vector_and_fts_contract() -> None:\n")
    replacement = '''def test_postgresql_native_fts_without_vector_contract() -> None:\n    inspector = sa.inspect(get_engine())\n    assert "node_embedding" not in inspector.get_table_names()\n\n    checks = {\n        item["name"]: item["sqltext"]\n        for item in inspector.get_check_constraints("model_task")\n    }\n    assert "EMBEDDING" not in checks["ck_model_task__task_kind"]\n    assert "EMBEDDING" not in checks["ck_model_task__output_contract"]\n\n    with get_engine().connect() as connection:\n        server_version = connection.scalar(sa.text("SHOW server_version"))\n        vector_extension = connection.scalar(\n            sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")\n        )\n        fts_index = connection.scalar(\n            sa.text(\n                """\n                SELECT indexdef\n                FROM pg_indexes\n                WHERE schemaname = 'public'\n                  AND tablename = 'node_search_document'\n                  AND indexname = 'ix_node_search_document__fts'\n                """\n            )\n        )\n\n    assert str(server_version).startswith("18.6")\n    assert vector_extension is None\n    assert fts_index is not None\n    assert "USING gin" in fts_index\n    assert "to_tsvector('simple'::regconfig, identity_text)" in fts_index\n    assert "to_tsvector('simple'::regconfig, knowledge_text)" in fts_index\n    assert "setweight" in fts_index\n'''
    text = text[:start] + replacement
    write(path, text)

    path = "server/tests/test_fixture.py"
    text = read(path)
    text = replace_once(
        text,
        "                publication_affected_node.c.node_embedding_id.is_not(None),\n",
        "",
        label="fixture test embedding READY pointer",
    )
    write(path, text)


def patch_logical_schema() -> None:
    path = "docs/data/logical-schema.md"
    text = read(path)
    text = replace_once(
        text,
        "아래는 frozen schema의 논리 흐름이며 수집·모델 호출·승격·publication worker가 실행된다는 뜻은 아니다. 현재 실행 범위와 승인된 변경은 [구현 스택](../development/implementation-stack.md)이 구별한다. embedding 저장과 READY 의존성은 현재 schema에 남아 있지만 [#121](https://github.com/studylida/ontology-map/issues/121)에서 제거하기로 승인했다. 해당 구현 전에는 엔터티와 제약을 제거 완료로 표시하지 않는다.",
        "아래는 frozen schema의 논리 흐름이며 수집·모델 호출·승격·publication worker가 실행된다는 뜻은 아니다. 현재 실행 범위와 승인된 변경은 [구현 스택](../development/implementation-stack.md)이 구별한다. [#121](https://github.com/studylida/ontology-map/issues/121)에 따라 node embedding과 pgvector 의존성은 frozen baseline에서 제거했고 검색은 PostgreSQL native FTS를 사용한다.",
        label="logical flow intro",
    )
    text = text.replace("→ 검색 문서·임베딩·한국어 맥락·후속 질문·인사이트 생성", "→ 검색 문서·한국어 맥락·후속 질문·인사이트 생성")
    text = text.replace("    NODE_SEARCH_DOCUMENT ||--o{ NODE_EMBEDDING : input_to\n", "")
    text = text.replace("    MODEL_TASK ||--o{ NODE_EMBEDDING : creates\n", "")
    text = replace_once(
        text,
        "- `publication_affected_node`: `(promotion_batch_id, node_id)`와 선택된 `node_search_document_id`, `node_embedding_id`, `node_context_id`, `node_insight_model_task_id`\n",
        "- `publication_affected_node`: `(promotion_batch_id, node_id)`와 선택된 `node_search_document_id`, `node_context_id`, `node_insight_model_task_id`\n",
        label="logical publication pointers",
    )
    text = replace_once(
        text,
        "- `node_embedding`: 정확한 검색 문서와 성공한 embedding 작업에서 만든 불변 벡터\n",
        "",
        label="logical node_embedding entity",
    )
    text = replace_once(
        text,
        "현재 HTTP 검색은 alias 정확 일치 뒤 `identity_text`·`knowledge_text`를 합친 `simple` FTS 결과를 반환한다. embedding 모델 호출·vector branch·RRF는 실행되지 않는다. 과거 vector·RRF 도입안은 [#121](https://github.com/studylida/ontology-map/issues/121)의 embedding 제거안과 [#117](https://github.com/studylida/ontology-map/issues/117)의 alias → identity FTS → knowledge FTS 변경안으로 대체됐다. 현재 엔터티·READY의 embedding 참조는 #121 구현 전까지 유지하며 검색 응답의 정확한 현재 형태는 [제품 설계](../product/design.md)를 따른다.",
        "현재 HTTP 검색은 alias 정확 일치 뒤 `identity_text`·`knowledge_text`를 합친 PostgreSQL `simple` FTS 결과를 반환한다. frozen schema와 READY 계약에는 node embedding과 pgvector가 없고 검색 응답의 정확한 현재 형태는 [제품 설계](../product/design.md)를 따른다. exact alias → identity FTS → knowledge FTS 분리와 `match_reasons` 제거는 [#117](https://github.com/studylida/ontology-map/issues/117)이 소유한다.",
        label="logical current search",
    )
    text = text.replace("→ 검색 문서·embedding·context·질문·인사이트", "→ 검색 문서·context·질문·인사이트")
    write(path, text)


def patch_physical_schema() -> None:
    path = "docs/data/physical-schema.md"
    text = read(path)
    text = replace_once(
        text,
        "#41–#48에서 기본 매핑을 확정했고 #78에서 embedding 계약, #91에서 node 인사이트 확장을 추가했다. #95는 이 결과를 SQLAlchemy metadata와 Alembic migration으로 구현했다. migration과 metadata가 이 문서와 다르면 임의로 한쪽을 정답으로 바꾸지 않고 #116에서 의미 차이인지 구현 오류인지 감사한다.",
        "#41–#48에서 기본 매핑을 확정했고 #91에서 node 인사이트 확장을 추가했다. #95는 이 결과를 SQLAlchemy metadata와 Alembic migration으로 구현했다. 과거 #78의 embedding 계약은 [#121](https://github.com/studylida/ontology-map/issues/121)에서 대체되어 frozen baseline에서 제거됐다. migration과 metadata가 이 문서와 다르면 임의로 한쪽을 정답으로 바꾸지 않고 #116에서 의미 차이인지 구현 오류인지 감사한다.",
        label="physical history",
    )
    text = replace_once(text, "`publication_affected_node`는 한 batch가 영향을 준 node와 선택한 검색 문서, embedding, context와 `NODE_INSIGHT` 작업을 가리킨다. 이 행은 지도 구성원, 좌표나 전체 graph snapshot이 아니다.", "`publication_affected_node`는 한 batch가 영향을 준 node와 선택한 검색 문서, context와 `NODE_INSIGHT` 작업을 가리킨다. 이 행은 지도 구성원, 좌표나 전체 graph snapshot이 아니다.", label="physical publication description")
    text = replace_once(text, "READY 전환은 같은 transaction에서 모든 영향 node를 검사한다. 새 패널 계약에서는 각 node의 검색 문서·embedding·context와 두 기간별 node_question_set 및 성공한 NODE_INSIGHT 작업의 node_insight_window가 필요하다.", "READY 전환은 같은 transaction에서 모든 영향 node를 검사한다. 새 패널 계약에서는 각 node의 검색 문서·context와 두 기간별 node_question_set 및 성공한 NODE_INSIGHT 작업의 node_insight_window가 필요하다.", label="physical READY requirements")
    text = replace_once(text, "`node_embedding`은 같은 node와 검색 문서를 composite FK로 고정하고 성공한 `EMBEDDING` 작업 하나와 연결한다. `node_context`, `followup_question`과 `node_insight`도 같은 검색 문서·node 조합을 물리 FK로 고정한다.", "`node_context`, `followup_question`과 `node_insight`는 같은 검색 문서·node 조합을 물리 FK로 고정한다.", label="physical derived artifact")
    text = replace_once(text, "| 필수 외부 extension | pgvector 0.8.6 |", "| 필수 외부 extension | 없음 |", label="physical extension table")
    text = replace_once(text, "현재 필수 extension은 pgvector의 `vector` 하나뿐이다.", "현재 frozen schema에 필수 외부 PostgreSQL extension은 없다.", label="physical extension statement")
    text = replace_once(text, "`node_embedding.embedding_vector`는 #78에서 `qwen3.7-text-embedding`, dense 1024차원과 cosine distance를 하나의 호환 계약으로 확정했다.\n\n", "", label="physical qwen embedding contract")
    section_start = "### 6.7 벡터\n"
    section_end = "## 7. 닫힌 코드와 확장 가능한 참조 목록\n"
    start = text.index(section_start)
    end = text.index(section_end, start)
    replacement = """### 6.7 벡터\n\n현재 frozen schema는 검색 벡터, `node_embedding` table, pgvector extension과 vector distance 연산을 사용하지 않는다. 검색은 `node_search_document.identity_text`와 `knowledge_text`의 PostgreSQL native `simple` FTS를 사용한다. 과거 #78의 Qwen embedding·cosine·RRF 방향은 [#121](https://github.com/studylida/ontology-map/issues/121)에서 대체됐으며 별도 ANN index도 두지 않는다. 검색 bucket 분리와 응답 단순화는 [#117](https://github.com/studylida/ontology-map/issues/117)이 소유한다.\n\n"""
    text = text[:start] + replacement + text[end:]
    text = text.replace("검색 문서, embedding, context, question, insight, conflict summary", "검색 문서, context, question, insight, conflict summary")
    text = replace_once(text, "#78의 embedding dimension blocker는 해소되어 `vector(1024)`로 구현되었다. 의미가 불명확한 `TBD`, placeholder dimension과 가짜 actor FK는 frozen schema에 넣지 않는다.", "과거 #78의 embedding dimension 결정은 #121에서 대체되어 현재 frozen schema에 vector type을 두지 않는다. 의미가 불명확한 `TBD`, placeholder와 가짜 actor FK는 frozen schema에 넣지 않는다.", label="physical blocker")
    text = replace_once(text, "#41–#48의 table mapping, #78의 embedding 계약과 #91의 인사이트 확장은 `0001_create_frozen_schema.py`에 통합되어 있다.", "#41–#48의 table mapping과 #91의 인사이트 확장은 `0001_create_frozen_schema.py`에 통합되어 있다. #121은 승인된 일회성 breaking baseline 예외로 기존 `0001`에서 node embedding과 pgvector를 제거했다.", label="physical migration baseline")
    text = replace_once(text, "이미 `main`에 병합된 revision을 수정하거나 순서를 다시 쓰지 않는다.", "이미 `main`에 병합된 revision을 수정하거나 순서를 다시 쓰지 않는 것이 기본 원칙이며, #121의 승인된 frozen baseline 교체만 예외다.", label="physical migration rule")
    write(path, text)


def patch_product_design() -> None:
    path = "docs/product/design.md"
    text = read(path)
    old = "현재 search는 alias 정확 일치를 첫 bucket으로 반환한 뒤 `identity_text`와 `knowledge_text`를 함께 사용한 PostgreSQL `simple` FTS 결과를 이어서 반환하고 HTTP 응답과 web에 `match_reasons`를 노출한다. node embedding 저장 구조와 pgvector는 현재 schema·migration·fixture에 있지만 실제 검색 경로와 모델 호출에는 쓰이지 않는다. #121은 이 저장 구조와 READY embedding 의존성을 제거한다. 그 뒤 #117은 exact alias → identity FTS → knowledge FTS의 세 bucket을 고정하고 `match_reasons`와 검색 이유 표시를 제거한다. 실제 한국어 단어 FTS 누락 사례가 확인될 때만 #80에서 tokenizer, `pg_trgm` 또는 BM25 같은 확장을 다시 검토한다."
    new = "현재 search는 alias 정확 일치를 첫 bucket으로 반환한 뒤 `identity_text`와 `knowledge_text`를 함께 사용한 PostgreSQL `simple` FTS 결과를 이어서 반환하고 HTTP 응답과 web에 `match_reasons`를 노출한다. node embedding과 pgvector는 frozen schema·migration·fixture·READY 계약에서 제거됐으며 검색은 PostgreSQL native FTS만 사용한다. #117은 exact alias → identity FTS → knowledge FTS의 세 bucket을 고정하고 `match_reasons`와 검색 이유 표시를 제거한다. 실제 한국어 단어 FTS 누락 사례가 확인될 때만 #80에서 tokenizer, `pg_trgm` 또는 BM25 같은 확장을 다시 검토한다."
    text = replace_once(text, old, new, label="product search current state")
    write(path, text)


def patch_implementation_stack() -> None:
    path = "docs/development/implementation-stack.md"
    text = read(path)
    text = replace_once(text, "| PostgreSQL vector 확장 | pgvector | 0.8.6 |\n", "", label="stack pgvector runtime")
    text = replace_once(text, "`compose.yaml`은 digest로 고정한 `pgvector/pgvector:0.8.6-pg18` DB와 FastAPI `api` service만 제공한다.", "`compose.yaml`은 digest로 고정한 PostgreSQL 18.6 DB와 FastAPI `api` service만 제공한다.", label="stack compose image")
    text = replace_once(text, "| Python vector type | pgvector | 0.5.0 |\n", "", label="stack Python pgvector")
    text = replace_once(
        text,
        "| embedding·pgvector | schema·migration·의존성과 합성 fixture에 남아 있으나 검색 실행 경로와 실제 모델 호출은 없음 | [#121](https://github.com/studylida/ontology-map/issues/121): 초기 baseline 교체와 개발 DB 재생성으로 제거. Qwen vector·RRF 도입안은 대체됐고 #81은 종료 |",
        "| node embedding·pgvector | frozen schema·migration·의존성·합성 fixture에서 제거됨. PostgreSQL native FTS만 검색 기반으로 유지 | [#117](https://github.com/studylida/ontology-map/issues/117)이 exact alias → identity FTS → knowledge FTS와 `match_reasons` 제거를 후속 구현 |",
        label="stack implementation status",
    )
    write(path, text)


def patch_database_ops() -> None:
    path = "docs/operations/database.md"
    text = read(path)
    text = replace_once(text, "| pgvector image | 0.8.6 |\n", "", label="db ops pgvector version")
    text = replace_once(
        text,
        "이 절차는 pgvector가 남아 있는 현재 main의 실행 기준이다. [#121](https://github.com/studylida/ontology-map/issues/121)의 제거안은 초기 migration 교체와 기존 개발 DB 재생성을 포함하는 승인된 후속 변경이며 아직 적용되지 않았다. 이 문서 정리를 위해 DB를 초기화하거나 image를 교체하지 않는다.",
        "[#121](https://github.com/studylida/ontology-map/issues/121)에 따라 현재 frozen baseline은 node embedding과 pgvector를 사용하지 않는다. 이 변경은 기존 개발 DB의 in-place upgrade를 제공하지 않는 승인된 breaking baseline 교체이므로, 기존 volume을 새 baseline에 맞춰 전환할 때는 아래 백업·재생성 절차를 따른다. 공유 DB나 다른 세션이 사용하는 volume을 임의로 초기화하지 않는다.",
        label="db ops current baseline",
    )
    marker = "개발 DB를 완전히 다시 만들 때만 다음 명령을 사용한다. 이 명령은 `ontology-map-postgres` volume과 안의 로컬 데이터를 삭제하므로 되돌릴 수 없다."
    replacement = "개발 DB를 #121의 새 frozen baseline으로 전환하거나 완전히 다시 만들 때만 다음 명령을 사용한다. 먼저 이 문서의 백업 절차로 dump를 저장하고 다른 세션이 같은 volume을 사용하지 않는지 확인한다. 이 명령은 현재 Compose project의 PostgreSQL volume과 안의 로컬 데이터를 삭제하므로 되돌릴 수 없다."
    text = replace_once(text, marker, replacement, label="db ops reset warning")
    write(path, text)


def patch_handoff() -> None:
    path = "HANDOFF.md"
    text = read(path)
    text = replace_once(text, "> 확인일: 2026-09-10. 작업 기준은 `main`의 `6edea5498d54540f4c04029bb6f88adf60043f2f`이며, 이후 상태는 GitHub와 실제 commit을 다시 확인한다.", "> 확인일: 2026-09-14. #121 구현 기준은 `main`의 `eab6f6dd6e13b1e973071bbb9b25fe533c228166`이며, 이후 상태는 GitHub와 실제 commit을 다시 확인한다.", label="handoff date")
    anchor = "## 구현·검증 경계\n\n"
    insert = "- #121은 node embedding·`EMBEDDING` task·pgvector 의존성과 publication READY의 embedding 요구를 frozen baseline에서 제거했다. PostgreSQL native FTS와 panel/FOLLOWUP/NODE_INSIGHT 구조는 유지한다. 검색의 exact alias → identity FTS → knowledge FTS 분리와 `match_reasons` 제거는 #117이 소유한다.\n"
    text = replace_once(text, anchor, anchor + insert, label="handoff #121 boundary")
    write(path, text)


def patch_adr_index_and_create() -> None:
    path = "docs/architecture/decisions/README.md"
    text = read(path)
    anchor = "| [ADR-0006](current/0006-separate-promotion-and-publication.md) | accepted | 2026-08-31 | promotion과 publication 수명주기 분리 |\n"
    new = anchor + "| [ADR-0007](current/0007-store-panel-reading-results.md) | accepted | 2026-09-08 | 질문 답변과 발견별 보고서를 불변 읽기 결과로 저장 |\n| [ADR-0008](current/0008-remove-pgvector-node-embedding.md) | accepted | 2026-09-03 | node embedding과 pgvector 제거, PostgreSQL native FTS 유지 |\n"
    text = replace_once(text, anchor, new, label="ADR index rows")
    text = text.replace("\n- [ADR-0007: 질문 답변과 발견별 보고서 저장](current/0007-store-panel-reading-results.md)\n", "\n")
    write(path, text)

    adr = ROOT / "docs/architecture/decisions/current/0008-remove-pgvector-node-embedding.md"
    if adr.exists():
        raise RuntimeError("ADR-0008 already exists")
    adr.write_text(
        """---\nid: ADR-0008\ntitle: node embedding과 pgvector를 제거하고 PostgreSQL native FTS를 유지한다\nstatus: accepted\ndecision_date: 2026-09-03\nrecorded_date: 2026-09-14\nevidence: [#121](https://github.com/studylida/ontology-map/issues/121)\nsupersedes: none\nsuperseded_by: none\naffected_docs: [제품](../../../product/design.md), [논리 스키마](../../../data/logical-schema.md), [물리 스키마](../../../data/physical-schema.md), [구현 스택](../../../development/implementation-stack.md), [DB 운영](../../../operations/database.md)\n---\n\n# ADR-0008: node embedding과 pgvector를 제거하고 PostgreSQL native FTS를 유지한다\n\n## 배경\n\n현재 POC의 사용자 검색은 exact alias와 PostgreSQL `simple` FTS만 실행하며 제품 embedding worker, query embedding adapter, cosine·ANN 조회 경로가 없다. 반면 frozen schema와 초기 migration, 개발 fixture, Python·DB 의존성은 사용하지 않는 `node_embedding`과 pgvector를 요구해 빈 환경 재현과 publication READY 계약을 불필요하게 복잡하게 만든다.\n\n## 결정\n\n`node_embedding`, `EMBEDDING` model task 특례, `publication_affected_node.node_embedding_id`, Python `pgvector`, PostgreSQL `vector` extension과 pgvector DB image를 제거한다. 검색은 `node_search_document.identity_text`와 `knowledge_text`의 PostgreSQL native `simple` FTS를 유지한다. `node_context`, FOLLOWUP_QUESTIONS, NODE_INSIGHT와 panel 읽기 구조는 유지하며 검색의 세 bucket 분리와 `match_reasons` 제거는 #117에 남긴다.\n\n이번 변경은 기존 `0001_create_frozen_schema.py`를 새 frozen baseline으로 교체하는 승인된 일회성 예외다. 기존 개발 DB에 대한 in-place migration이나 선별 데이터 이관을 제공하지 않고, 공유 DB를 임의로 초기화하지 않는다.\n\n## 검토한 대안\n\n기존 `0001`을 유지하고 forward migration으로 `node_embedding`만 제거하면 새 DB도 migration 재생 동안 pgvector Python package와 DB extension을 계속 요구하므로 채택하지 않았다. 미래 semantic retrieval을 위해 사용하지 않는 vector infrastructure를 남기는 방식도 현재 POC의 실제 검색 경로와 맞지 않아 채택하지 않았다.\n\n## 결과\n\n새 환경은 PostgreSQL 18.6만으로 migration·fixture·API를 실행할 수 있다. native `tsvector`/GIN은 embedding vector와 별개이므로 유지한다. 기존 개발 volume은 제한된 백업 뒤 새 baseline으로 재생성해야 하며 #117, #80과 Entity Resolution 후속 범위는 이 결정으로 확장하지 않는다.\n\n## 근거\n\n제품 계약과 breaking baseline 예외, 제거 대상과 제외 범위는 #121의 현재 본문과 최신 정정 댓글을 따른다.\n""",
        encoding="utf-8",
    )


def main() -> None:
    patch_schema()
    patch_migration()
    patch_fixtures()
    patch_dependency_and_compose()
    patch_tests()
    patch_logical_schema()
    patch_physical_schema()
    patch_product_design()
    patch_implementation_stack()
    patch_database_ops()
    patch_handoff()
    patch_adr_index_and_create()


if __name__ == "__main__":
    main()
