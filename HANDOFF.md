# ontology-map #121 구현 인계

> 작업 기준: 최신 `main` `b4064cee3105dc52b06c30fa3cabaec2b870f575` 위에 재구성한 `refactor/121-remove-pgvector-clean`, Draft PR #196. PR #195의 임시/fixup history는 이 clean integration PR에 포함하지 않는다. 병합 전에는 GitHub의 실제 head와 검증 상태를 다시 확인한다.

## #121 현재 계약

- 현재 POC의 `node_embedding`, `EMBEDDING` model task, Python/DB pgvector 의존성과 publication READY의 embedding 요구를 제거한다.
- PostgreSQL native FTS, `node_search_document`, `search_document_basis`, `node_context`, FOLLOWUP/NODE_INSIGHT 저장·읽기 구조와 panel migration `0002`는 유지한다.
- 이번 변경은 승인된 breaking development baseline 예외다. 기존 개발 DB의 in-place 이관을 제공하지 않고 새 `0001`로 재생성한다. 공유 DB나 다른 세션의 volume은 자동 초기화하지 않는다.
- #117이 소유하는 exact alias → identity FTS → knowledge FTS bucket과 `match_reasons` 제거는 #121에서 구현하지 않는다.

## 병렬 PR overlap

- Draft PR #192는 `server/pyproject.toml`, `server/uv.lock`, `docs/development/implementation-stack.md`, `docs/operations/database.md`를 함께 변경하고 있어 #121과 integration conflict 가능성이 있다. #192의 branch나 코드는 이 PR에서 수정하지 않는다.
- #124/#125/#127/#128/#130/#193의 구현 범위도 가져오지 않는다. 최신 main에 이미 병합된 #128 Entity Resolution 구현과 문서 경계는 그대로 보존한다.

## 다음 작업

- #121 PR 검토가 끝나면 #117에서 사용자 검색을 exact alias → identity FTS → knowledge FTS로 분리하고 `match_reasons`를 제거한다. READY/search basis/BLOCKING lint 공개 필터와 canonical merge 해소는 유지한다.
- #126은 승인 ontology 목록이 있지만 제품 DB 적재·migration·fixture 변경은 아직 승인 범위가 아니다. `MAX_MEMORY_BANDWIDTH`의 `GB_PER_S | TB_PER_S`와 단일 `attribute_revision.unit_rule` 충돌은 제품 계약 재결정 전까지 구현하지 않는다. EVENT → TECHNOLOGY 새 Relation도 승인되지 않았다.
