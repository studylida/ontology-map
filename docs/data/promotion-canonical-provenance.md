# promotion canonical-change provenance

> 상태: Issue #216 구현 계약
>
> 기준일: 2026-09-16
>
> 관련 Issue: [#216](https://github.com/studylida/ontology-map/issues/216), [#215](https://github.com/studylida/ontology-map/issues/215), [#23](https://github.com/studylida/ontology-map/issues/23), [#46](https://github.com/studylida/ontology-map/issues/46), [#42](https://github.com/studylida/ontology-map/issues/42), [#43](https://github.com/studylida/ontology-map/issues/43), [#180](https://github.com/studylida/ontology-map/issues/180)

## 1. 목적과 경계

새 `Node`, `Relation`, `Claim` 자체를 만든 promotion은 기존 `knowledge_item.promotion_batch_id`로 정확히 복원한다. 기존 canonical object를 재사용하면서 새 association이나 구조화 값을 추가한 경우처럼 기존 schema만으로 그 변경을 만든 promotion을 알 수 없는 경우에만 `promotion_canonical_change`가 불변 provenance를 보완한다.

이 테이블은 다음 역할을 하지 않는다.

- publication job, attempt 또는 workflow 상태
- `publication_affected_node`나 affected-node projection
- staging/result payload
- generic event sourcing
- 임의 JSON audit log
- retry attempt 이력

publication의 `PREPARING | READY | FAILED` 변화와 관계없이 기록한 provenance는 UPDATE하거나 소비·삭제하지 않는다.

## 2. 승인된 change kind와 exact target

change kind는 다음 여섯 종류로 닫혀 있다.

| `change_kind` | exact canonical target |
| --- | --- |
| `NODE_ALIAS_CHANGED` | `node_alias_id` |
| `NODE_ALIAS_EVIDENCE_ADDED` | `(node_alias_id, observation_id)` |
| `CLAIM_OBSERVATION_ADDED` | `(claim_id, observation_id)` |
| `CLAIM_RELATION_ADDED` | `(claim_id, relation_id)` |
| `CLAIM_ATTRIBUTE_VALUE_ADDED` | `claim_attribute_value_id` |
| `EVENT_TEMPORAL_BASIS_ADDED` | `(event_node_id, claim_id)` |

`promotion_canonical_change`는 위 target을 위한 전용 nullable FK column만 가진다. `change_kind`별 CHECK가 필요한 column만 non-NULL이고 관계없는 target column은 모두 NULL임을 강제한다. association kind는 가능한 경우 단일 ID를 복제하지 않고 실제 canonical association의 복합 키를 FK로 참조한다.

## 3. 물리 shape

```text
promotion_canonical_change
--------------------------
promotion_canonical_change_id  bigint GENERATED ALWAYS AS IDENTITY PK
promotion_batch_id             bigint NOT NULL FK -> promotion_batch
change_kind                    text NOT NULL, closed CHECK
node_alias_id                  bigint NULL
observation_id                 bigint NULL
claim_id                       bigint NULL
relation_id                    bigint NULL
claim_attribute_value_id       bigint NULL
event_node_id                  bigint NULL
```

정확한 CHECK, FK와 index 이름은 [generated schema reference](schema-reference.md)가 source of truth다. 구현 metadata는 `server/src/ontology_map/db/metadata.py`, DDL migration은 `server/migrations/versions/0005_add_promotion_canonical_change.py`다.

## 4. idempotency와 transaction

의미적 identity는 `promotion_batch + change_kind + exact canonical target`이다. PostgreSQL nullable UNIQUE 하나로 전체 행을 묶지 않고 kind별 partial unique index 여섯 개를 둔다.

canonical mutation과 provenance insert는 항상 같은 caller-owned promotion transaction에서 일어난다.

```text
promotion transaction
→ canonical mutation 시도
→ 실제 새 association/value/alias가 생겼으면 exact provenance 기록
→ 나머지 canonical write
→ promotion_status = COMMITTED
→ commit
```

canonical insert가 `ON CONFLICT ... DO NOTHING`으로 no-op이면 provenance도 만들지 않는다. 기존 object를 재사용했는지는 기준이 아니다. 예를 들어 Observation이 이미 있어도 새 `(claim_id, observation_id)`를 만든 promotion은 `CLAIM_OBSERVATION_ADDED`를 기록한다.

동시 promotion이 같은 canonical association을 경쟁하면 canonical insert에 실제 성공한 transaction만 provenance를 기록한다. transaction rollback이면 canonical mutation과 provenance가 함께 사라진다.

## 5. production write boundary

현재 Entity Resolution promotion 경로의 alias 저장은 batch ID를 명시적으로 전달한다.

- 새 `node_alias` row를 실제 insert한 경우에만 `NODE_ALIAS_CHANGED`
- 기존 alias를 재사용해도 새 `(node_alias_id, observation_id)`를 만든 경우 `NODE_ALIAS_EVIDENCE_ADDED`
- 같은 evidence association retry는 no-op이며 새 provenance 없음

Claim/Relation/attribute/event temporal basis를 promotion transaction에서 쓰는 caller는 `ontology_map.db.promotion_provenance`의 provenance-aware canonical writer를 사용한다.

- `add_claim_observation`
- `add_claim_relation`
- `add_claim_attribute_value`
- `add_event_temporal_basis`

`claim_relation`의 기존 association을 다른 `stance`로 바꾸는 요청처럼 승인된 여섯 kind로 표현할 수 없는 mutation은 조용히 덮어쓰지 않고 실패시킨다. 별도 제품 계약 없이 새 provenance kind를 추가하지 않는다.

## 6. restart-safe read와 #215 경계

`changes_for_batch(session, promotion_batch_id)`는 process-local memory 없이 DB의 exact change-set을 다시 읽는다. 이 read helper는 publication state를 변경하지 않는다.

#216은 "promotion이 실제로 무엇을 바꿨는가"까지만 소유한다. 어떤 Node가 affected인지의 projection과 `publication_affected_node`, `PREPARING`, 검색 문서, `NODE_CONTEXT`, 질문, 인사이트, `READY` 전환은 #215의 책임이다.

따라서 provenance에 `affected_node_id`를 저장하거나 2-hop 전파 결과를 기록하지 않는다. #215는 exact target과 기존 canonical row를 읽어 direct target을 계산한다.

## 7. historical cutover

migration `0005`는 기존 association을 timestamp, row order, `started_at`/`committed_at` window로 추정해 backfill하지 않는다. migration 이전 READY history에 `promotion_canonical_change`가 없는 것은 정상이다.

initial publication coordinator를 enable하기 전에 다음 batch가 하나라도 있으면 cutover를 막는다.

```sql
promotion_status = 'COMMITTED'
AND publication_status = 'NOT_STARTED'
```

runtime helper `legacy_committed_not_started_batch_ids()`와 `assert_initial_publication_cutover_safe()`는 이 상태를 읽고 차단만 한다. 자동 attribution, 자동 skip, remediation, publication mutation은 하지 않는다. 실제 product/shared DB 상태를 확인한 뒤 one-time remediation은 별도 운영 판단으로 수행한다.

## 8. 검증

#216 전용 PostgreSQL regression은 다음을 고정한다.

- closed kind CHECK와 kind별 exact target shape
- exact association FK
- 여섯 partial unique index
- migration의 historical no-backfill
- canonical mutation + provenance의 같은 transaction commit/rollback
- no-op/retry와 existing object reuse 구분
- concurrent promotion에서 mutation winner만 provenance 보유
- process restart를 가정한 DB-only change-set reload
- legacy `COMMITTED + NOT_STARTED` enable guard
- publication `PREPARING | FAILED | READY` 이후에도 provenance 보존
- Relation endpoint, attribute target, Event Node, evidence-only existing Claim, multi-target Claim의 projection 입력 복원
- provenance 자체가 2-hop propagation을 저장하지 않음

PostgreSQL 기준 버전은 [물리 스키마](physical-schema.md)의 18.6이며, CI는 격리 DB에서 migration rehearsal과 regression을 실행한다.
