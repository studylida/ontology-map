from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, got {count}")
    return text.replace(old, new, 1)


def patch_review_fixtures() -> None:
    path = "server/src/ontology_map/db/review_fixture.py"
    text = read(path)
    text = replace_once(text, "    contracts: dict[str, int],\n    vector_slot: int,\n", "    contracts: dict[str, int],\n", "review artifacts signature")
    start = text.index('    task = _insert_successful_task(\n        c,\n        "EMBEDDING",\n')
    end = text.index("    context_task = _insert_successful_task(\n", start)
    text = text[:start] + text[end:]
    text = replace_once(text, "            node_embedding_id=embedding,\n", "", "review publication embedding")
    text = replace_once(text, "            contracts,\n            index,\n        )\n", "            contracts,\n        )\n", "review artifacts call")
    write(path, text)

    path = "server/src/ontology_map/db/panel_fixture.py"
    text = read(path)
    text = replace_once(text, "            contracts,\n            index + 120,\n        )\n", "            contracts,\n        )\n", "panel artifacts call")
    write(path, text)


def patch_logical_schema() -> None:
    path = "docs/data/logical-schema.md"
    text = read(path)
    text = text.replace(
        "아래는 frozen schema의 논리 흐름이며 수집·모델 호출·승격·publication worker가 실행된다는 뜻은 아니다. 현재 실행 범위와 승인된 변경은 [구현 스택](../development/implementation-stack.md)이 구별한다. embedding 저장과 READY 의존성은 현재 schema에 남아 있지만 [#121](https://github.com/studylida/ontology-map/issues/121)에서 제거하기로 승인했다. 해당 구현 전에는 엔터티와 제약을 제거 완료로 표시하지 않는다.",
        "아래는 frozen schema의 논리 흐름이며 수집·모델 호출·승격·publication worker가 실행된다는 뜻은 아니다. 현재 실행 범위와 승인된 변경은 [구현 스택](../development/implementation-stack.md)이 구별한다. [#121](https://github.com/studylida/ontology-map/issues/121)에 따라 node embedding과 pgvector 의존성은 frozen baseline에서 제거했으며 검색은 PostgreSQL native FTS를 사용한다.",
    )
    text = text.replace("→ 검색 문서·임베딩·한국어 맥락·후속 질문·인사이트 생성", "→ 검색 문서·한국어 맥락·후속 질문·인사이트 생성")
    text = text.replace("    NODE_SEARCH_DOCUMENT ||--o{ NODE_EMBEDDING : input_to\n", "")
    text = text.replace("    MODEL_TASK ||--o{ NODE_EMBEDDING : creates\n", "")
    text = text.replace(
        "- `publication_affected_node`: `(promotion_batch_id, node_id)`와 선택된 `node_search_document_id`, `node_embedding_id`, `node_context_id`, `node_insight_model_task_id`",
        "- `publication_affected_node`: `(promotion_batch_id, node_id)`와 선택된 `node_search_document_id`, `node_context_id`, `node_insight_model_task_id`",
    )
    text = text.replace("- `node_embedding`: 정확한 검색 문서와 성공한 embedding 작업에서 만든 불변 벡터\n", "")
    text = text.replace(
        "새 공개 계약은 모든 영향 node의 필수 결과와 같은 context의 두 기간별 질문 묶음, 성공한 `NODE_INSIGHT` 작업의 두 기간별 준비 결과가 완결되고 공개 조건을 통과해야 READY로 전환한다.",
        "새 공개 계약은 모든 영향 node의 검색 문서·context와 같은 context의 두 기간별 질문 묶음, 성공한 `NODE_INSIGHT` 작업의 두 기간별 준비 결과가 완결되고 공개 조건을 통과해야 READY로 전환한다.",
    )
    text = text.replace(
        "현재 HTTP 검색은 alias 정확 일치 뒤 `identity_text`·`knowledge_text`를 합친 `simple` FTS 결과를 반환한다. embedding 모델 호출·vector branch·RRF는 실행되지 않는다. 과거 vector·RRF 도입안은 [#121](https://github.com/studylida/ontology-map/issues/121)의 embedding 제거안과 [#117](https://github.com/studylida/ontology-map/issues/117)의 alias → identity FTS → knowledge FTS 변경안으로 대체됐다. 현재 엔터티·READY의 embedding 참조는 #121 구현 전까지 유지하며 검색 응답의 정확한 현재 형태는 [제품 설계](../product/design.md)를 따른다.",
        "현재 HTTP 검색은 alias 정확 일치 뒤 `identity_text`·`knowledge_text`를 합친 `simple` FTS 결과를 반환한다. [#121](https://github.com/studylida/ontology-map/issues/121)에 따라 query-time vector 검색과 node embedding 저장 경로는 제거됐다. [#117](https://github.com/studylida/ontology-map/issues/117)은 후속으로 alias → identity FTS → knowledge FTS bucket과 검색 응답 단순화를 구현하며, 그 전까지 검색 응답의 정확한 현재 형태는 [제품 설계](../product/design.md)를 따른다.",
    )
    text = text.replace("→ 검색 문서·embedding·context·질문·인사이트", "→ 검색 문서·context·질문·인사이트")
    write(path, text)


def patch_physical_schema() -> None:
    path = "docs/data/physical-schema.md"
    text = read(path)
    text = text.replace(
        "#41–#48에서 기본 매핑을 확정했고 #78에서 embedding 계약, #91에서 node 인사이트 확장을 추가했다. #95는 이 결과를 SQLAlchemy metadata와 Alembic migration으로 구현했다.",
        "#41–#48에서 기본 매핑을 확정했고 #91에서 node 인사이트 확장을 추가했다. #95는 이 결과를 SQLAlchemy metadata와 Alembic migration으로 구현했으며, #78의 embedding 계약은 [#121](https://github.com/studylida/ontology-map/issues/121)에서 폐기했다.",
    )
    text = text.replace(
        "`publication_affected_node`는 한 batch가 영향을 준 node와 선택한 검색 문서, embedding, context와 `NODE_INSIGHT` 작업을 가리킨다.",
        "`publication_affected_node`는 한 batch가 영향을 준 node와 선택한 검색 문서, context와 `NODE_INSIGHT` 작업을 가리킨다.",
    )
    text = text.replace(
        "READY 전환은 같은 transaction에서 모든 영향 node를 검사한다. 새 패널 계약에서는 각 node의 검색 문서·embedding·context와 두 기간별 node_question_set 및 성공한 NODE_INSIGHT 작업의 node_insight_window가 필요하다.",
        "READY 전환은 같은 transaction에서 모든 영향 node를 검사한다. 새 패널 계약에서는 각 node의 검색 문서·context와 두 기간별 node_question_set 및 성공한 NODE_INSIGHT 작업의 node_insight_window가 필요하다.",
    )
    text = text.replace(
        "`node_embedding`은 같은 node와 검색 문서를 composite FK로 고정하고 성공한 `EMBEDDING` 작업 하나와 연결한다. `node_context`, `followup_question`과 `node_insight`도 같은 검색 문서·node 조합을 물리 FK로 고정한다.",
        "`node_context`, `followup_question`과 `node_insight`는 같은 검색 문서·node 조합을 물리 FK로 고정한다.",
    )
    text = text.replace("- PostgreSQL과 필수 extension 기준\n", "- PostgreSQL 기준\n")
    text = text.replace("- HNSW·IVFFlat 등 근사 검색 인덱스\n", "")
    text = text.replace("| 필수 외부 extension | pgvector 0.8.6 |\n", "| 필수 외부 extension | 없음 |\n")
    text = text.replace("| pgvector 설치 schema | `public` |\n", "")
    text = text.replace(
        "PostgreSQL과 pgvector의 정확한 버전은 [구현 스택](../development/implementation-stack.md)을 따른다. 버전 갱신은 별도 Issue와 호환성 검증 없이 이루어지지 않는다.",
        "PostgreSQL의 정확한 버전은 [구현 스택](../development/implementation-stack.md)을 따른다. 버전 갱신은 별도 Issue와 호환성 검증 없이 이루어지지 않는다.",
    )
    text = text.replace("현재 필수 extension은 pgvector의 `vector` 하나뿐이다.\n\n", "현재 필수 외부 PostgreSQL extension은 없다.\n\n")
    text = text.replace("- `pg_trgm`\n", "- `pg_trgm`\n")
    text = text.replace("`node_embedding.embedding_vector`는 #78에서 `qwen3.7-text-embedding`, dense 1024차원과 cosine distance를 하나의 호환 계약으로 확정했다.\n\n", "")
    text = text.replace("- pgvector의 타입·연산자·인덱스 지원 객체\n", "")
    start = text.find("### 6.7 벡터\n")
    if start != -1:
        end = text.find("\n## 7. 닫힌 코드와 확장 가능한 참조 목록", start)
        if end == -1:
            raise RuntimeError("physical vector section end not found")
        text = text[:start] + text[end + 1 :]
    text = text.replace("문서 버전, relation·claim, ontology revision, 검색 문서, embedding, context, question, insight, conflict summary", "문서 버전, relation·claim, ontology revision, 검색 문서, context, question, insight, conflict summary")
    text = text.replace("#78의 embedding dimension blocker는 해소되어 `vector(1024)`로 구현되었다. 의미가 불명확한 `TBD`, placeholder dimension과 가짜 actor FK는 frozen schema에 넣지 않는다.\n\n", "의미가 불명확한 `TBD`, placeholder 값과 가짜 actor FK는 frozen schema에 넣지 않는다.\n\n")
    text = text.replace(
        "#41–#48의 table mapping, #78의 embedding 계약과 #91의 인사이트 확장은 `0001_create_frozen_schema.py`에 통합되어 있다.",
        "#41–#48의 table mapping과 #91의 인사이트 확장은 `0001_create_frozen_schema.py`에 통합되어 있다. #121은 현재 POC에서 사용하지 않는 #78의 embedding 계약을 제거하기 위해 예외적으로 이 frozen baseline을 교체했다.",
    )
    text = text.replace(
        "이미 `main`에 병합된 revision을 수정하거나 순서를 다시 쓰지 않는다.",
        "이미 `main`에 병합된 revision을 수정하거나 순서를 다시 쓰지 않는 것이 원칙이다. 다만 #121은 빈 환경에서도 pgvector가 필요하지 않도록 기존 개발 DB 재생성을 전제로 `0001` baseline 교체를 명시적으로 승인한 예외다.",
    )
    write(path, text)


def patch_design() -> None:
    path = "docs/product/design.md"
    text = read(path)
    old = "현재 search는 alias 정확 일치를 첫 bucket으로 반환한 뒤 `identity_text`와 `knowledge_text`를 함께 사용한 PostgreSQL `simple` FTS 결과를 이어서 반환하고 HTTP 응답과 web에 `match_reasons`를 노출한다. node embedding 저장 구조와 pgvector는 현재 schema·migration·fixture에 있지만 실제 검색 경로와 모델 호출에는 쓰이지 않는다. #121은 이 저장 구조와 READY embedding 의존성을 제거한다. 그 뒤 #117은 exact alias → identity FTS → knowledge FTS의 세 bucket을 고정하고 `match_reasons`와 검색 이유 표시를 제거한다. 실제 한국어 단어 FTS 누락 사례가 확인될 때만 #80에서 tokenizer, `pg_trgm` 또는 BM25 같은 확장을 다시 검토한다."
    new = "현재 search는 alias 정확 일치를 첫 bucket으로 반환한 뒤 `identity_text`와 `knowledge_text`를 함께 사용한 PostgreSQL `simple` FTS 결과를 이어서 반환하고 HTTP 응답과 web에 `match_reasons`를 노출한다. #121에 따라 node embedding 저장 구조와 pgvector 의존성, publication READY의 embedding 요구는 제거됐다. #117은 후속으로 exact alias → identity FTS → knowledge FTS의 세 bucket을 고정하고 `match_reasons`와 검색 이유 표시를 제거한다. 실제 한국어 단어 FTS 누락 사례가 확인될 때만 #80에서 tokenizer, `pg_trgm` 또는 BM25 같은 확장을 다시 검토한다."
    text = replace_once(text, old, new, "design search state")
    write(path, text)


def patch_implementation_stack() -> None:
    path = "docs/development/implementation-stack.md"
    text = read(path)
    text = text.replace("| PostgreSQL vector 확장 | pgvector | 0.8.6 |\n", "")
    text = text.replace(
        "`compose.yaml`은 digest로 고정한 `pgvector/pgvector:0.8.6-pg18` DB와 FastAPI `api` service만 제공한다.",
        "`compose.yaml`은 digest로 고정한 공식 `postgres:18.6` DB와 FastAPI `api` service만 제공한다.",
    )
    text = text.replace("| Python vector type | pgvector | 0.5.0 |\n", "")
    text = text.replace(
        "| embedding·pgvector | schema·migration·의존성과 합성 fixture에 남아 있으나 검색 실행 경로와 실제 모델 호출은 없음 | [#121](https://github.com/studylida/ontology-map/issues/121): 초기 baseline 교체와 개발 DB 재생성으로 제거. Qwen vector·RRF 도입안은 대체됐고 #81은 종료 |",
        "| 검색 기반 | PostgreSQL native FTS만 사용하며 node embedding·pgvector 저장/실행 의존성은 없음 | [#121](https://github.com/studylida/ontology-map/issues/121)에서 초기 baseline 교체와 개발 DB 재생성 기준으로 제거. #117의 세 검색 bucket과 응답 단순화는 별도 후속 |",
    )
    write(path, text)


def patch_database_ops() -> None:
    path = "docs/operations/database.md"
    text = read(path)
    text = text.replace("| pgvector image | 0.8.6 |\n", "")
    text = text.replace(
        "이 절차는 pgvector가 남아 있는 현재 main의 실행 기준이다. [#121](https://github.com/studylida/ontology-map/issues/121)의 제거안은 초기 migration 교체와 기존 개발 DB 재생성을 포함하는 승인된 후속 변경이며 아직 적용되지 않았다. 이 문서 정리를 위해 DB를 초기화하거나 image를 교체하지 않는다.",
        "[#121](https://github.com/studylida/ontology-map/issues/121)에 따라 개발 DB는 공식 PostgreSQL 18.6 image만 사용하며 pgvector extension과 Python pgvector 패키지를 요구하지 않는다. #121 이전 `0001`로 만든 개발 volume은 in-place upgrade 대상이 아니며, 필요한 백업을 확인한 뒤 새 frozen baseline으로 재생성한다. 공유 DB나 다른 세션의 volume은 자동으로 초기화하지 않는다.",
    )
    marker = "현재 기준 revision은 `0001_create_frozen_schema.py` 이후 패널 읽기 계약을 추가한 `0002_add_panel_reading_contracts.py`다. PostgreSQL 객체는 `public` schema에 만들며 migration과 SQLAlchemy metadata는 같은 frozen schema를 표현한다."
    replacement = marker + " #121 이후 `0001`에는 `vector` extension, `node_embedding` table과 `EMBEDDING` task 허용 계약이 없다."
    text = replace_once(text, marker, replacement, "database migration paragraph")
    text = text.replace(
        "개발 DB를 완전히 다시 만들 때만 다음 명령을 사용한다. 이 명령은 `ontology-map-postgres` volume과 안의 로컬 데이터를 삭제하므로 되돌릴 수 없다.",
        "개발 DB를 완전히 다시 만들 때만 다음 명령을 사용한다. #121 이전 frozen baseline의 개발 volume을 새 baseline으로 전환할 때도 이 재생성 경로를 사용한다. 먼저 필요한 `pg_dump` 백업과 복구 가능성을 확인하고 다른 세션이 해당 volume을 쓰지 않는지 확인한다. 이 명령은 `ontology-map-postgres` volume과 안의 로컬 데이터를 삭제하므로 되돌릴 수 없다.",
    )
    write(path, text)


def patch_handoff() -> None:
    path = "HANDOFF.md"
    write(
        path,
        """# ontology-map #121 구현 인계\n\n> 작업 기준: `main` `eab6f6dd6e13b1e973071bbb9b25fe533c228166`에서 분기한 `refactor/121-remove-pgvector`, Draft PR #195. 병합 전에는 GitHub의 실제 head와 검증 상태를 다시 확인한다.\n\n## #121 현재 계약\n\n- 현재 POC의 `node_embedding`, `EMBEDDING` model task, Python/DB pgvector 의존성과 publication READY의 embedding 요구를 제거한다.\n- PostgreSQL native FTS, `node_search_document`, `search_document_basis`, `node_context`, FOLLOWUP/NODE_INSIGHT 저장·읽기 구조와 panel migration `0002`는 유지한다.\n- 이번 변경은 승인된 breaking development baseline 예외다. 기존 개발 DB의 in-place 이관을 제공하지 않고 새 `0001`로 재생성한다. 공유 DB나 다른 세션의 volume은 자동 초기화하지 않는다.\n- #117이 소유하는 exact alias → identity FTS → knowledge FTS bucket과 `match_reasons` 제거는 #121에서 구현하지 않는다.\n\n## 병렬 PR overlap\n\n- Draft PR #192는 `server/pyproject.toml`, `server/uv.lock`, `docs/development/implementation-stack.md`, `docs/operations/database.md`를 함께 변경하고 있어 #121과 integration conflict 가능성이 있다. #192의 branch나 코드는 이 PR에서 수정하지 않는다.\n- #124/#125/#127/#128/#130/#193의 구현 범위도 가져오지 않는다.\n\n## 다음 작업\n\n- #121 PR 검토가 끝나면 #117에서 사용자 검색을 exact alias → identity FTS → knowledge FTS로 분리하고 `match_reasons`를 제거한다. READY/search basis/BLOCKING lint 공개 필터와 canonical merge 해소는 유지한다.\n- #126은 승인 ontology 목록이 있지만 제품 DB 적재·migration·fixture 변경은 아직 승인 범위가 아니다. `MAX_MEMORY_BANDWIDTH`의 `GB_PER_S | TB_PER_S`와 단일 `attribute_revision.unit_rule` 충돌은 제품 계약 재결정 전까지 구현하지 않는다. EVENT → TECHNOLOGY 새 Relation도 승인되지 않았다.\n""",
    )


def add_adr() -> None:
    path = "docs/architecture/decisions/current/0008-remove-node-embedding-pgvector.md"
    if not (ROOT / path).exists():
        write(
            path,
            """---\nid: ADR-0008\ntitle: POC 검색에서 node embedding과 pgvector를 제거한다\nstatus: accepted\ndecision_date: 2026-09-03\nrecorded_date: 2026-09-14\nevidence: [#121](https://github.com/studylida/ontology-map/issues/121), [PR #195](https://github.com/studylida/ontology-map/pull/195)\nsupersedes: none\nsuperseded_by: none\naffected_docs: [제품](../../../product/design.md), [논리 스키마](../../../data/logical-schema.md), [물리 스키마](../../../data/physical-schema.md), [구현 스택](../../../development/implementation-stack.md), [DB 운영](../../../operations/database.md)\n---\n\n# ADR-0008: POC 검색에서 node embedding과 pgvector를 제거한다\n\n## 배경\n\n현재 사용자 검색은 exact alias와 PostgreSQL native FTS만 실행하며 node embedding을 소비하지 않는다. production embedding worker와 query embedding adapter도 없고, 개발 fixture의 합성 vector만 frozen schema와 실행 의존성을 유지하고 있었다.\n\n## 결정\n\n현재 POC에서 `node_embedding`, `EMBEDDING` model task, Python pgvector 의존성, PostgreSQL `vector` extension과 pgvector DB image를 제거한다. publication READY는 검색 문서·context·질문·insight의 승인된 완결성을 유지하되 embedding 산출물을 기다리지 않는다. PostgreSQL의 `tsvector`/`to_tsvector` FTS는 vector embedding과 다른 기능이므로 유지한다.\n\n이번 변경은 빈 환경에서도 pgvector가 필요하지 않게 하기 위해 기존 `0001` frozen baseline을 교체하는 승인된 예외다. 기존 개발 DB의 in-place upgrade·downgrade나 선별 데이터 이관은 제공하지 않고, 필요한 백업을 확인한 뒤 새 baseline으로 재생성한다.\n\n## 검토한 대안\n\n기존 `0001`을 보존하고 forward migration으로 `node_embedding`만 삭제하면 빈 DB의 migration replay에 Python pgvector와 pgvector DB image가 계속 필요하므로 채택하지 않았다. 미래 retrieval 용도를 위해 vector abstraction이나 대체 vector store를 남기는 방안도 실제 POC 소비 경로가 없어 채택하지 않았다.\n\n## 결과\n\n검색 인프라는 PostgreSQL native FTS만 필요로 한다. #117의 exact alias → identity FTS → knowledge FTS bucket 분리와 `match_reasons` 제거는 별도 제품 검색 계약이므로 이 결정에 포함하지 않는다. 과거 embedding 계약 문서와 archive는 역사 기록으로 보존한다.\n\n## 근거\n\nIssue #121의 승인된 breaking baseline 계약과 구현 PR #195를 따른다.\n""",
        )

    index_path = "docs/architecture/decisions/README.md"
    text = read(index_path)
    row = "| [ADR-0008](current/0008-remove-node-embedding-pgvector.md) | accepted | 2026-09-03 | POC 검색에서 node embedding·pgvector 제거 |\n"
    if row not in text:
        anchor = "| [ADR-0006](current/0006-separate-promotion-and-publication.md) | accepted | 2026-08-31 | promotion과 publication 수명주기 분리 |\n"
        text = replace_once(text, anchor, anchor + row, "ADR index anchor")
    write(index_path, text)


def main() -> None:
    patch_review_fixtures()
    patch_logical_schema()
    patch_physical_schema()
    patch_design()
    patch_implementation_stack()
    patch_database_ops()
    patch_handoff()
    add_adr()


if __name__ == "__main__":
    main()
