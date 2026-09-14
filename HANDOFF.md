# ontology-map #117 구현 인계

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
