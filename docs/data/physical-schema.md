# ontology-map PostgreSQL 물리 데이터 스키마

## 문서 상태

- 상태: Physical Schema v2 — 동결 및 migration 구현 완료
- 확인일: 2026-09-03
- 관련 Issue: [#40 Define PostgreSQL physical schema conventions](https://github.com/studylida/ontology-map/issues/40)
- 논리 모델: [논리 스키마](logical-schema.md)
- 생성 목록: [스키마 참고 문서](schema-reference.md)
- 구현 스택: [구현 스택](../development/implementation-stack.md)
- 코드·migration 규칙: [코드 규칙](../development/code-conventions.md)
- 구현: #95, `server/migrations/versions/0001_create_frozen_schema.py`

이 문서는 Logical Schema v1.2의 의미를 PostgreSQL로 옮기는 공통 표현 규칙을 정의한다. 실제 table, column, constraint와 index 목록은 SQLAlchemy metadata에서 생성한 [스키마 참고 문서](schema-reference.md)가 소유한다.

#41–#48에서 기본 매핑을 확정했고 #91에서 node 인사이트 확장을 추가했다. #95는 이 결과를 SQLAlchemy metadata와 Alembic migration으로 구현했으며, #78의 embedding 계약은 [#121](https://github.com/studylida/ontology-map/issues/121)에서 폐기했다. migration과 metadata가 이 문서와 다르면 임의로 한쪽을 정답으로 바꾸지 않고 #116에서 의미 차이인지 구현 오류인지 감사한다.

## 현재 구현 기준

- SQLAlchemy metadata: `server/src/ontology_map/db/schema.py`
- Alembic revision: `0001_create_frozen_schema.py` → `0002_add_panel_reading_contracts.py`
- 개발 fixture: `server/src/ontology_map/db/fixture.py`
- PostgreSQL namespace: `public`
- 현재 metadata에 구현된 table 수와 각 객체의 세부 정의는 [스키마 참고 문서](schema-reference.md)에서 확인한다.
- 논리 모델에는 있지만 actor 계약이 없어 구현을 보류한 table은 `knowledge_state_event`와 `conflict_state_event`다.

Evidence Trace는 새 사본을 만들지 않고 다음 경로를 사용한다.

```text
claim
→ claim_observation
→ observation
→ source_document
→ evidence_group
```

Relation의 stance는 `claim_relation`, 구조화 속성값은 `claim_attribute_value`, 사건 시간 근거는 `event_temporal_basis`가 Claim에 연결한다. node 인사이트도 `node_insight_claim`에서 기존 Claim으로 이어져 같은 Evidence Trace를 재사용한다.

`publication_affected_node`는 한 batch가 영향을 준 node와 선택한 검색 문서, context와 `NODE_INSIGHT` 작업을 가리킨다. 이 행은 지도 구성원, 좌표나 전체 graph snapshot이 아니다.

### Publication과 공개 조회

`promotion_batch.promotion_status`는 기준 지식의 원자 저장 결과이고 `publication_status`는 파생 결과 준비 상태다. 둘을 하나의 상태로 합치지 않는다.

```text
promotion_status:   PENDING → COMMITTED | FAILED
publication_status: NOT_STARTED → PREPARING → READY
                                          └→ FAILED → PREPARING
```

READY 전환은 같은 transaction에서 모든 영향 node를 검사한다. 새 패널 계약에서는 각 node의 검색 문서·context와 두 기간별 node_question_set 및 성공한 NODE_INSIGHT 작업의 node_insight_window가 필요하다. 질문 묶음은 0개 이상의 답변, 인사이트 window는 0개 또는 1개 보고서를 선택한다. 기존 followup_question과 slot 1–3 인사이트는 호환 데이터로 보존한다. 현재 공개 가능한 basis 지식과 열린 `BLOCKING` lint 부재도 함께 검사한다.

이 완결성은 여러 table의 개수, task kind와 상태를 함께 읽어야 하므로 DB의 nullable column만으로 보장하지 않고 publication application service가 짧은 transaction 안에서 보장한다. `READY` 뒤 선택 pointer와 산출물은 바꾸지 않는다.

일반 사용자 조회는 node별 `ready_at DESC, promotion_batch_id DESC` 순서의 최신 `COMMITTED + READY`를 선택한다. node, Relation, Claim과 파생 결과의 basis 지식이 `EVIDENCE_VERIFIED | HUMAN_VERIFIED` 상태이고 열린 `BLOCKING` lint가 없는지 read-time에서 다시 확인한다. 새 publication이 실패하면 기준 지식과 과거 산출물을 삭제하지 않고 이전 READY를 계속 제공한다. 이전 READY가 전혀 없으면 현재 exploration 계열 API는 `503 PUBLICATION_NOT_READY`를 반환한다.

관계가 없는 공개 node도 각자 완전한 READY 결과를 가지면 검색과 주변부 조회에 포함할 수 있다. 검색, node 선택, 후속 질문과 주변부 이동은 Relation을 새로 만들지 않는다.

### 검색과 파생 산출물

`node_search_document`는 `identity_text`와 `knowledge_text`를 분리하고 `search_document_basis`가 사용한 공개 `knowledge_item`을 연결한다. migration은 다음 expression GIN을 구현한다.

```sql
setweight(to_tsvector('simple', identity_text), 'A')
|| setweight(to_tsvector('simple', knowledge_text), 'B')
```

`node_context`, `followup_question`과 `node_insight`는 같은 검색 문서·node 조합을 물리 FK로 고정한다. `followup_question.slot`은 1 또는 2이고 `target_node_id`는 필수지만 target과 중심 사이 Relation을 뜻하지 않는다.

`node_insight`는 `RECENT_90_DAYS | RECENT_1_YEAR`, slot 1–3, `as_of_at`, 제목, 요약, 종합 해석과 유의점을 가진 불변 행이다. `node_insight_claim`은 기존 Claim을 `KEY_CLAIM | SUPPORTING_CLAIM | CONTRASTING_CLAIM`으로 연결한다. 인사이트 근거 수는 column으로 저장하지 않고 Evidence Trace에서 `COUNT(DISTINCT evidence_group_id)`로 계산한다.

지도 좌표, 카메라, node 밝기와 opacity, 화면 표시 단계, 전역 graph/map version, 검색 rank와 의미가 섞인 confidence는 저장하지 않는다.

## 1. 설계 경계

### 1.1 이 문서가 결정하는 것

- PostgreSQL 기준
- PostgreSQL schema namespace와 객체 소유 경계
- 내부 식별자와 공유 기본 키 전략
- 데이터베이스 객체 이름 규칙
- 공통 문자열, JSON, 해시, 시간, 숫자와 Boolean 표현
- 닫힌 상태·코드와 확장 가능한 참조 목록의 표현
- `NULL`, 빈 문자열과 기본값 정책
- 외래 키 삭제·갱신 정책
- 불변 버전, append-only 이력과 운영 상태의 수명주기 분류
- 공통 인덱스 원칙
- PostgreSQL `COMMENT ON` 작성 기준
- blocker와 후속 결정 기록 방식

### 1.2 이 문서가 결정하지 않는 것

- HTTP DTO와 화면용 표현
- 외부 source 선정, raw snapshot과 수집 manifest
- 실제 lint 정책에 포함할 entity·event·relation 범위
- 다른 행이나 테이블을 함께 검사하는 application-service 함수의 구현 세부사항
- 사용자·관리자 인증과 권한 모델
- 운영 규모의 성능 benchmark

## 2. PostgreSQL 기준과 extension

### 2.1 승인된 기준

| 항목 | 기준 |
|---|---|
| 데이터베이스 | PostgreSQL 18.6 |
| 필수 외부 extension | 없음 |
| 데이터베이스 이름 | `ontology_map` |
| 애플리케이션 schema | `public` |

PostgreSQL의 정확한 버전은 [구현 스택](../development/implementation-stack.md)을 따른다. 버전 갱신은 별도 Issue와 호환성 검증 없이 이루어지지 않는다.

### 2.2 extension 최소화

현재 필수 외부 PostgreSQL extension은 없다.

다음 extension은 현재 물리 스키마의 선행 요구사항이 아니다.

- `uuid-ossp`
- `pgcrypto`
- `pg_trgm`
- `unaccent`
- `btree_gist`

내부 식별자는 `bigint` identity를 사용하므로 UUID 생성 extension을 추가하지 않는다. 오타 검색, 문자 정규화나 고급 제약에 별도 extension이 실제로 필요해지면 해당 조회나 무결성을 소유하는 후속 Issue에서 근거와 함께 승인한다.

## 3. PostgreSQL namespace와 객체 소유

### 3.1 단일 `public` schema

POC는 전용 PostgreSQL 데이터베이스 하나를 하나의 애플리케이션이 사용하므로, 다음 객체를 모두 `public` schema에 둔다.

- 애플리케이션 테이블과 뷰
- PK·FK·UNIQUE·CHECK
- 인덱스
- 승인된 함수와 trigger

별도의 `ontology_map`, `extensions` 또는 도메인별 PostgreSQL schema를 만들지 않는다. 이 선택은 논리 모델의 영역 구분을 없애는 것이 아니라, 현재 규모에서 불필요한 `search_path`, SQLAlchemy, Alembic과 테스트 설정 복잡도를 추가하지 않기 위한 것이다.

`public`은 PostgreSQL namespace 이름이며 네트워크 공개나 모든 사용자의 데이터 접근을 의미하지 않는다.

### 3.2 변경 책임

지속되는 데이터베이스 객체의 생성·변경·삭제는 승인된 migration 경로만 수행한다.

API와 worker 런타임은 다음 작업을 수행하지 않는다.

- `CREATE`
- `ALTER`
- `DROP`
- 일반적인 `TRUNCATE`
- 기준·근거·이력 데이터를 대상으로 한 범용 물리 `DELETE`

실제 PostgreSQL role과 `GRANT` 구성은 실행 환경 Issue에서 구현하더라도, 논리적인 책임은 다음처럼 분리한다.

```text
migration owner
→ schema, extension, table, constraint, index, function과 trigger 변경

API / worker runtime
→ 승인된 조회와 데이터 상태 전이만 수행
```

데이터베이스가 여러 애플리케이션에 공유되거나 객체 소유 경계가 실제로 달라질 때만 전용 schema 도입을 다시 검토한다.

### 3.3 migration search_path

migration connection은 `public`을 명시적으로 사용하고, PostgreSQL extension이 필요해질 때는 extension 설치 위치도 같은 revision에서 고정한다. 현재 필수 외부 extension은 없다.

## 4. 내부 식별자

### 4.1 대리 기본 키

독립적인 수명주기를 가진 엔터티의 대리 기본 키는 PostgreSQL `bigint`를 사용한다.

새 식별자는 다음 원칙으로 생성한다.

```text
bigint GENERATED ALWAYS AS IDENTITY
```

Agent 출력과 애플리케이션 입력은 내부 기본 키 값을 선택하거나 재사용하지 않는다.

숫자 식별자의 대소나 정렬 순서는 다음 의미를 갖지 않는다.

- 업무 발생 시각
- 공개 순서
- 상태 변경 순서
- 근거 강도
- 의미상 우선순위

이 의미에는 각각 명시적인 시각, 상태와 정렬 규칙을 사용한다.

### 4.2 공유 기본 키 subtype

`knowledge_item`이 `node`, `relation`, `claim`의 공통 식별자를 발급한다.

```text
knowledge_item.knowledge_item_id
= node.node_id
= relation.relation_id
= claim.claim_id
```

하나의 실제 행이 세 subtype을 동시에 가진다는 뜻이 아니다. 하나의 `knowledge_item`은 정확히 하나의 subtype만 가져야 한다.

- `knowledge_item`의 기본 키만 identity를 가진다.
- `node`, `relation`, `claim`의 공유 기본 키에는 별도의 identity나 default를 두지 않는다.
- subtype 행은 같은 트랜잭션에서 상위 식별자를 전달받아 생성한다.

“정확히 한 subtype”의 교차 행 검증은 짧은 승격 transaction이 담당하며 공유 PK와 item kind의 로컬 조건은 DB가 보장한다.

### 4.3 연결 테이블과 순번

순수 N:M 연결 테이블은 다른 엔터티가 그 연결 행 자체를 참조해야 하는 승인된 요구가 없는 한 관련 FK 조합을 복합 기본 키로 사용한다.

예:

```text
claim_observation
→ (claim_id, observation_id)

claim_relation
→ (claim_id, relation_id)
```

다음 값은 대리 기본 키와 구분한다.

| 용도 | 물리 타입 |
|---|---|
| 같은 부모 안의 버전 번호 | `integer` |
| 모델 호출 시도 순번 | `integer` |
| 후속 질문 슬롯 1·2 | `smallint` |
| 안정된 온톨로지·lint 코드 | 고유 `text` |

현재 단일 PostgreSQL POC에는 UUID를 도입하지 않는다. 여러 독립 데이터베이스의 병합, 분산 ID 생성이나 불투명 공개 식별자가 실제 요구가 되면 별도 설계로 검토한다.

## 5. 데이터베이스 객체 이름

### 5.1 table과 column

- PostgreSQL 식별자는 소문자 `snake_case`를 사용한다.
- table 이름은 단수형 명사를 사용한다.
- 기본 키 column은 `<entity>_id`를 사용한다.
- 다른 엔터티를 가리키는 FK도 대상 기본 키 이름을 그대로 사용한다.
- Boolean은 `is_`, `has_`, `allow_`처럼 의미가 드러나는 이름을 사용한다.
- timestamp는 `_at`, 날짜는 `_date`, 반열린 기간 경계는 `_from`, `_to`를 사용한다.
- 안정된 업무 식별 문자열은 `_code`, 외부 원천의 식별자는 `_key`를 사용한다.

### 5.2 constraint 이름

모든 명시적 constraint 이름은 다음 접두사를 사용한다.

| 종류 | 접두사 | 형식 |
|---|---|---|
| primary key | `pk_` | `pk_<table>` |
| foreign key | `fk_` | `fk_<table>__<역할>` |
| unique | `uq_` | `uq_<table>__<의미>` |
| check | `ck_` | `ck_<table>__<의미>` |
| exclude | `ex_` | `ex_<table>__<의미>` |

같은 table에서 이름은 중복되지 않아야 한다. 자동 생성 이름에 의존하지 않는다.

### 5.3 index 이름

인덱스는 다음 형식을 사용한다.

```text
ix_<table>__<선두 열 또는 목적>
```

partial unique index는 unique constraint가 아니라 unique index이므로 `uq_<table>__<의미>` 이름을 유지할 수 있다. 이 경우 문서에서 index임을 명시한다.

## 6. 공통 자료형

### 6.1 문자열

도메인 문자열은 길이 추정이 필요하지 않으면 PostgreSQL `text`를 기본으로 한다.

다음 값은 `text`다.

- 이름과 alias
- URL
- 원문과 인용문
- Claim 문장
- ontology code
- 상태·종류 코드
- model·prompt version
- 오류 reason

`varchar(n)`은 외부 protocol이 실제 최대 길이를 강제하고 애플리케이션 경계에서도 같은 제한을 검증할 때만 사용한다.

### 6.2 JSON

반복 필드 또는 미정 의미를 피하기 위해 JSON을 기본 저장 수단으로 쓰지 않는다.

`jsonb`는 구조가 실제로 self-contained이고 기준 관계와 Evidence Trace를 침범하지 않을 때만 사용한다.

현재 frozen schema에서 `jsonb`는 `output_schema_definition.json_schema`처럼 불변 계약 자체가 JSON인 경우에 쓴다.

Provider의 전체 응답, Agent 후보 payload, 임시 debug 정보, graph snapshot과 화면 상태를 `jsonb`로 저장하지 않는다.

### 6.3 해시

SHA-256은 PostgreSQL `bytea` 32바이트로 저장한다.

- `source_document.body_hash`
- `observation.quote_hash`
- `model_task.input_hash`
- `model_task.cache_key`
- `blocked_fingerprint.fingerprint`

문자열 hex는 API나 로그 표시 형식일 수 있지만 기준 DB의 해시 저장 형식은 아니다.

### 6.4 시간과 날짜

절대 시각은 `timestamptz`로 저장한다.

- 실행 시각
- lease 만료 시각
- 검토·상태 변경 시각
- source가 제공한 정확한 instant

애플리케이션은 UTC aware datetime만 DB에 전달한다. naive datetime을 삽입하지 않는다.

부분 날짜·기간은 논리 모델의 precision과 함께 저장한다.

- 월·연도는 저장용 `date_from`에 그 기간의 첫날을 둘 수 있다.
- `precision`을 잃지 않는다.
- 사용자에게 더 정확한 날짜처럼 표시하지 않는다.

PostgreSQL의 `infinity`, `-infinity`는 사용하지 않는다. 열린 구간은 `NULL`과 precision으로 표현한다.

### 6.5 숫자

정밀도가 중요한 도메인 값은 `numeric`을 사용한다.

- 구조화 속성의 수량
- 출처 값
- 향후 계산되는 신뢰 관련 수치

float는 모델 score, UI layout과 같이 기준 지식이 아닌 값에서만 별도 승인 후 사용할 수 있다.

### 6.6 Boolean

Boolean은 실제 두 상태만 있을 때 PostgreSQL `boolean`을 사용한다.

`UNKNOWN`, `NOT_APPLICABLE`, 여러 승인 상태를 `false`로 압축하지 않는다.

## 7. 닫힌 코드와 확장 가능한 참조 목록

### 7.1 닫힌 상태·종류 코드

다음처럼 허용 집합이 작고 제품 코드가 새 값을 먼저 이해해야 하는 값은 `text + CHECK`로 구현한다.

예:

- knowledge item kind
- knowledge state
- Claim modality
- Publication status
- model task status
- model attempt outcome
- lint scope와 severity
- conflict status
- date precision

schema-level PostgreSQL enum은 사용하지 않는다. 값 추가가 필요한 경우 코드와 migration의 배포 순서를 명확히 관리한다.

### 7.2 확장 가능한 참조 목록

사용자가 실제로 참조하고 과거 의미 보존이 필요한 목록은 table과 revision을 사용한다.

예:

- `node_type`
- `relation_type` + `relation_type_revision`
- `attribute` + `attribute_revision`
- `output_schema_definition`
- `lint_rule` + `lint_policy_version`

“목록이 늘어날 수 있다”는 이유만으로 모두 table로 만들지 않는다. 별도 의미 필드, 수명주기, 참조 FK 또는 revision이 필요한지 확인한다.

## 8. NULL, 빈 문자열과 기본값

### 8.1 `NULL`

`NULL`은 “모름”, “해당 없음” 또는 “아직 없음”의 의미가 계약에 있을 때만 허용한다.

예:

- 선택적 작성자
- 알 수 없는 사건 종료 시점
- 아직 시작되지 않은 `started_at`
- 성공 작업에는 필요 없는 `failure_reason`

필수 문자열을 nullable로 만든 뒤 애플리케이션에서 채우기를 기대하지 않는다.

### 8.2 빈 문자열

코드, 이름, 제목, Claim 문장, URL, 언어와 이유 같은 의미 있는 문자열은 빈 문자열을 허용하지 않는다.

DB `CHECK (btrim(column) <> '')` 또는 같은 의미의 application validation을 사용한다.

`NULL`과 `''`가 서로 다른 제품 의미를 가지지 않으면 둘 중 하나만 사용한다.

### 8.3 기본값

DB default는 저장 레이어가 의미를 결정해도 안전한 값에만 둔다.

적합한 예:

- `CURRENT_TIMESTAMP`
- `false`인 초기 `is_active`
- `0` 또는 `1`로 시작하는 명확한 카운터
- 초기 상태가 계약으로 고정된 status

사용자나 Agent가 결정해야 하는 내용, 사건 시점, ontology revision, 근거 출처, Claim modality에는 추측 default를 두지 않는다.

## 9. 외래 키와 삭제·갱신 정책

### 9.1 기본 정책

frozen schema의 일반 FK는 기본적으로 다음 동작을 사용한다.

```text
ON DELETE RESTRICT
ON UPDATE RESTRICT
```

기준 지식, 근거, revision과 이력은 물리 cascade로 지우지 않는다.

### 9.2 삭제

POC에서는 immutable append-only 역사와 Evidence Trace를 보존한다.

- 문서 버전을 지워서 지식을 정리하지 않는다.
- Node merge는 source Node를 삭제하지 않는다.
- 지식 거절은 상태 이력으로 표현한다.
- conflict 해결은 member나 Claim을 삭제하지 않는다.

향후 보존 기간이나 사용자 삭제가 필요해지면 이 정책과 별도의 retention·purge 설계를 먼저 결정한다.

### 9.3 갱신

identity PK, ontology code와 revision identity는 변경하지 않는다.

허용되는 갱신은 의미가 명확한 운영 상태에 한정한다.

- `is_active`
- node merge reversal 시각
- conflict 현재 상태
- task lease와 retry 상태
- source 마지막 확인 정보

불변 본문, Observation 범위, Claim 문장, relation endpoint와 과거 ontology revision 의미는 수정하지 않는다.

## 10. 불변성, 버전과 이력

### 10.1 불변 객체

다음은 생성 뒤 의미 필드를 수정하지 않는다.

- `source_document`
- `observation`
- `output_schema_definition`
- `relation_type_revision`
- `attribute_revision`
- `node_search_document`
- `node_context`
- `followup_question`
- `node_insight`
- `node_question_set`
- `node_question`
- `node_question_claim`
- `node_insight_window`
- `node_insight_section`
- `node_insight_section_claim`

새 의미가 필요하면 새 row나 새 revision을 만든다.

### 10.2 append-only 이력

다음은 이력 보존이 목적인 append-only 행이다.

- `agent_attempt`
- `knowledge_state_event`
- `conflict_state_event`
- `lint_run`
- `lint_finding`

현재 구현에서 actor 계약이 미정인 `knowledge_state_event`와 `conflict_state_event`는 물리 table을 만들지 않는다. 나머지는 승인된 현재 metadata를 따른다.

### 10.3 현재 상태를 함께 가지는 엔터티

다음 엔터티는 빠른 조회를 위해 현재 상태와 이력을 함께 가질 수 있다.

- `model_task`
- `node_merge`
- `conflict_set`
- `promotion_batch`
- `source_document`의 확인 상태

현재 상태 변경은 허용된 상태 전이만 수행하며 이력만으로 현재 상태를 추론하게 만들지 않는다.

## 11. 무결성 제약 배치

### 11.1 DB에 두는 제약

한 행 또는 선언적 FK·UNIQUE·CHECK로 정확히 표현할 수 있는 규칙은 DB에 둔다.

예:

- ID 양수
- 문자열 nonblank
- 상태 허용값
- 날짜 precision과 값 존재 일치
- `start <= end`
- Observation 범위와 길이
- 값 kind에 맞는 정확한 value column 하나
- active revision 최대 하나
- model attempt 순번 고유성

### 11.2 짧은 트랜잭션 서비스에 두는 제약

다음은 여러 행을 함께 봐야 하거나 DB trigger를 만들 이유가 부족하므로 application service의 짧은 transaction에서 보장한다.

- `knowledge_item`의 정확히 한 subtype
- 새 Node 생성 시 활성 `node_type` 사용
- 새 Relation·attribute 값 생성 시 현재 활성 revision 선택
- relation endpoint와 revision 허용 조합
- Claim의 의미 target 최소 하나
- Relation 지지 Claim 최소 하나
- Evidence Trace 완결성
- 동일 대상 판정 뒤 node merge 적용
- publication 전 node별 파생 결과 완결성
- 전체 공개 basis 지식과 blocking lint 부재

서비스 검증 뒤 같은 transaction 안에서 write를 완료한다. “application service가 보장한다”는 말은 비동기 뒷정리나 best-effort 검사를 뜻하지 않는다.

### 11.3 partial unique index

“활성 row 최대 하나”처럼 `NULL` 또는 Boolean 조건이 붙는 고유성은 partial unique index를 사용한다.

예:

```text
ontology revision당 active 최대 하나
WHERE is_active

노드별 preferred alias 최대 하나
WHERE is_preferred

원본 노드당 활성 merge 최대 하나
WHERE reversed_at IS NULL

finding key당 열린 finding 최대 하나
WHERE resolved_at IS NULL
```

partial unique index가 “최대 하나”를 보장해도 “공개 시 정확히 하나” 같은 최소 개수 규칙까지 보장하지는 않는다. 정확한 개수는 publication 검증 등 해당 트랜잭션이 담당한다.

### 11.4 특수 인덱스

현재 migration은 `node_search_document`의 `simple` A/B `tsvector` 표현식 GIN만 구현한다. JSON GIN과 대규모 covering index는 없다.

새 특수 인덱스는 실제 query와 측정 결과를 소유하는 Issue에서만 결정한다.

## 12. 데이터베이스 주석

### 12.1 필수 범위

모든 애플리케이션 테이블에 `COMMENT ON TABLE`을 작성한다.

다음 객체에는 의미가 자명하지 않을 때 주석을 작성한다.

- 컬럼
- partial index
- 복합 FK
- CHECK constraint

주석은 다음 의미를 설명한다.

- 행이 무엇을 뜻하는지
- 다른 비슷한 개념과 어떻게 다른지
- 불변인지 현재 상태인지
- 어떤 상위 객체의 revision을 참조하는지
- Evidence Trace와의 관계

### 12.2 언어와 표현

데이터베이스 comment는 한국어를 기본으로 하고 다음 식별자는 코드 표기를 유지한다.

- table·column 이름
- 상태와 종류 코드
- model identifier
- ontology code

주석은 과거 논의나 Issue 번호를 적는 장소가 아니다. 현재 의미만 설명한다.

## 13. 인덱스 원칙

### 13.1 PK·UNIQUE

PK와 UNIQUE가 이미 필요한 접근 경로를 제공하면 중복 index를 만들지 않는다.

### 13.2 FK 보조 index

PostgreSQL은 FK column에 자동 index를 만들지 않으므로 다음 조건을 만족할 때 명시적 index를 둔다.

- 자식에서 부모로 자주 조회한다.
- publication·lint·conflict 검사에 반복 사용한다.
- 대량 자료에서 full scan을 피해야 한다.

### 13.3 시간·상태 index

다음과 같이 실제 조회가 확인된 경우에만 만든다.

```text
(status, next_attempt_at)
(node_id, ready_at DESC)
(source_key, version_no DESC)
```

고정된 POC 데이터만 보고 미래 운영 query를 추정해 인덱스를 추가하지 않는다.

### 13.4 JSON과 전문 검색 index

현재 승인된 것은 `node_search_document`의 `identity_text`와 `knowledge_text`를 합친 `simple` FTS expression GIN뿐이다.

`jsonb` GIN, trigram, 다른 tokenizer와 BM25는 실제 누락 사례·query·측정 근거가 생길 때 별도 Issue에서 검토한다. [#117](https://github.com/studylida/ontology-map/issues/117)은 FTS를 exact alias → identity FTS → knowledge FTS 세 bucket으로 분리하고, [#80](https://github.com/studylida/ontology-map/issues/80)은 구현 후에도 한국어 단어 누락이 실제로 재현될 때만 확장 검색을 검토한다.

## 14. blocker와 후속 결정

현재 frozen schema 구현을 막는 physical blocker는 없다.

의미가 불명확한 `TBD`, placeholder 값과 가짜 actor FK는 frozen schema에 넣지 않는다.

## 15. Migration과 변경 기준

#41–#48의 table mapping과 #91의 인사이트 확장은 `0001_create_frozen_schema.py`에 통합되어 있다. #121은 현재 POC에서 사용하지 않는 #78의 embedding 계약을 제거하기 위해 예외적으로 이 frozen baseline을 교체했다. `server/src/ontology_map/db/schema.py`는 Alembic 비교와 query 작성에 쓰는 같은 metadata를 제공한다.

이미 `main`에 병합된 revision을 수정하거나 순서를 다시 쓰지 않는 것이 원칙이다. 다만 #121은 빈 환경에서도 pgvector가 필요하지 않도록 기존 개발 DB 재생성을 전제로 `0001` baseline 교체를 명시적으로 승인한 예외다. 저장 의미, 제약이나 publication 계약이 바뀌면 먼저 logical·physical 결정 Issue를 승인하고 새 Alembic revision으로 변경한다. HTTP DTO나 화면 전용 상태는 DB column을 추가하지 않고 [제품 설계](../product/design.md)의 API 경계에 기록한다.

migration 변경은 논리 필드와 물리 컬럼, PostgreSQL type, `NULL`과 default, PK·FK·UNIQUE·CHECK, 삭제·갱신 동작, lifecycle, index, 한국어 DB comment, DB와 service의 무결성 책임 및 정상·실패 검증을 함께 설명해야 한다.

## 16. 관련 문서

- [Logical Schema v1.2](logical-schema.md)
- [생성된 스키마 참고 문서](schema-reference.md)
- [구현 스택](../development/implementation-stack.md)
- [코드 규칙](../development/code-conventions.md)
- [제품 설계](../product/design.md)
