# #42 온톨로지와 노드 정체성의 PostgreSQL 물리 매핑

## 문서 상태

- 관련 Issue: #42
- 선행 결정: #40, #41, #69
- 공통 규칙: [`physical-data-schema.md`](../physical-data-schema.md)
- 현재 커밋 범위: 온톨로지 코드·revision·endpoint·속성 규칙

## 1. 공통 결정

- `ontology_version`, `ontology_member`는 만들지 않는다.
- `node_type`, `relation_type`, `attribute`는 확장 가능한 코드 테이블이다.
- 닫힌 저장 구조인 방향성·값 종류만 `text + CHECK`로 제한한다.
- relation·attribute revision은 의미 필드가 바뀌면 새 행을 만들며, 참조된 행을 수정하지 않는다.
- `is_active`는 새 지식 생성 허용 여부만 뜻한다. 비활성화된 유형·revision을 참조하는 기존 지식은 계속 유효하고 조회 가능하다.
- 다른 행을 읽어야 하는 활성화·역관계·endpoint 전체 검증은 서비스 트랜잭션이 한 곳에서 책임진다. 같은 검사를 DB custom trigger로 복제하지 않는다.
- 모든 FK는 별도 언급이 없으면 `ON DELETE RESTRICT ON UPDATE RESTRICT`다.

## 2. `node_type`

### 2.1 책임

사람·회사·기술·주제·사건처럼 노드가 속할 수 있는 안정된 유형과 생성 근거 규칙을 관리한다. 별도 revision 테이블은 만들지 않는다.

### 2.2 컬럼

| 컬럼 | 타입 | NULL | 기본값 | 변경 규칙 |
|---|---|---:|---|---|
| `node_type_id` | `bigint` | 불가 | `GENERATED ALWAYS AS IDENTITY` | 불변 |
| `node_type_code` | `text` | 불가 | 없음 | 사용 후 불변 |
| `display_name` | `text` | 불가 | 없음 | 통제된 표시 수정 가능 |
| `creation_rule` | `text` | 불가 | 없음 | 사용 후 불변 |
| `is_active` | `boolean` | 불가 | `false` | 새 노드 생성 허용 전환 |

### 2.3 제약과 인덱스

- PK `pk_node_type (node_type_id)`
- UNIQUE `uq_node_type__code (node_type_code)`
- `node_type_code`, `display_name`, `creation_rule`은 nonblank
- 초기 seed는 `PERSON`, `COMPANY`, `TECHNOLOGY`, `TOPIC`, `EVENT`지만 코드 추가를 막는 `CHECK IN`은 두지 않는다.
- 코드 테이블 크기가 작으므로 `is_active` 단독 인덱스는 만들지 않는다.

### 2.4 서비스 규칙

- `is_active = true`인 유형만 새 node에 사용할 수 있다.
- 한 번이라도 node가 참조한 `node_type_code`, `creation_rule`은 수정하지 않는다.
- 의미가 달라지면 새 `node_type` code를 만든다.
- 비활성화는 기존 node의 상태나 공개 여부를 바꾸지 않는다.

### 2.5 주석

```sql
COMMENT ON TABLE node_type IS
'노드의 안정된 유형 코드와 생성 근거 규칙. is_active는 새 노드 생성 허용 여부이며 기존 노드의 공개 상태가 아니다.';
```

## 3. 관계 유형

### 3.1 `relation_type`

#### 책임

관계 의미를 식별하는 불변 `relation_code`를 관리한다. 표시 이름·방향·endpoint 규칙은 revision이 소유한다.

#### 컬럼

| 컬럼 | 타입 | NULL | 기본값 | 변경 규칙 |
|---|---|---:|---|---|
| `relation_type_id` | `bigint` | 불가 | `GENERATED ALWAYS AS IDENTITY` | 불변 |
| `relation_code` | `text` | 불가 | 없음 | 사용 후 불변 |

#### 제약

- PK `pk_relation_type (relation_type_id)`
- UNIQUE `uq_relation_type__code (relation_code)`
- `btrim(relation_code) <> ''`
- 활성 플래그를 두지 않는다. 활성 revision이 없으면 새 관계 생성에 사용할 수 없다.

### 3.2 `relation_type_revision`

#### 책임

같은 관계 의미에 적용하는 표시 이름, 방향성과 inverse 계약의 불변 버전이다.

#### 컬럼

| 컬럼 | 타입 | NULL | 기본값 | 변경 규칙 |
|---|---|---:|---|---|
| `relation_type_revision_id` | `bigint` | 불가 | `GENERATED ALWAYS AS IDENTITY` | 불변 |
| `relation_type_id` | `bigint` | 불가 | 없음 | 불변 |
| `version_no` | `integer` | 불가 | 없음 | 불변 |
| `display_name` | `text` | 불가 | 없음 | 사용 후 불변 |
| `directionality` | `text` | 불가 | 없음 | 사용 후 불변 |
| `inverse_relation_type_revision_id` | `bigint` | 허용 | 없음 | 사용 후 불변 |
| `is_active` | `boolean` | 불가 | `false` | 새 관계 생성 허용 전환 |

#### 키와 제약

- PK `pk_relation_type_revision (relation_type_revision_id)`
- FK `fk_relation_type_revision__relation_type`
- self FK `fk_relation_type_revision__inverse`
- UNIQUE `uq_relation_type_revision__version (relation_type_id, version_no)`
- partial UNIQUE index:

```sql
CREATE UNIQUE INDEX uq_relation_type_revision__active
ON relation_type_revision (relation_type_id)
WHERE is_active;
```

- `version_no >= 1`
- `btrim(display_name) <> ''`
- `directionality IN ('DIRECTED', 'SYMMETRIC')`
- `inverse_relation_type_revision_id IS NULL OR inverse_relation_type_revision_id <> relation_type_revision_id`
- `directionality = 'SYMMETRIC'`이면 inverse는 반드시 `NULL`

#### 인덱스

- `ix_relation_type_revision__inverse (inverse_relation_type_revision_id)` WHERE inverse가 값 있음
- 관계 코드의 revision 조회는 `uq_relation_type_revision__version`이 지원한다.

#### 서비스 규칙

활성화 트랜잭션은 다음을 원자적으로 수행한다.

1. revision의 endpoint 규칙 전체를 검증한다.
2. inverse가 있으면 대상도 `DIRECTED`인지 확인한다.
3. `A.inverse = B`이면 `B.inverse = A`인지 확인한다.
4. 같은 `relation_type_id`의 기존 활성 revision을 비활성화한다.
5. 새 revision을 활성화한다.

승격 트랜잭션은 저장 직전에 exact revision이 여전히 활성인지 다시 읽는다.

### 3.3 `relation_endpoint_rule`

#### 책임

관계 revision이 허용하는 시작·도착 node type 쌍을 저장한다.

#### 컬럼과 키

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---:|---|
| `relation_type_revision_id` | `bigint` | 불가 | 없음 |
| `source_node_type_id` | `bigint` | 불가 | 없음 |
| `target_node_type_id` | `bigint` | 불가 | 없음 |

- PK `pk_relation_endpoint_rule (relation_type_revision_id, source_node_type_id, target_node_type_id)`
- 세 컬럼은 각각 revision과 `node_type`을 참조하는 FK다.
- 별도 대리 ID는 두지 않는다.

#### 방향별 저장 규칙

- `DIRECTED`: 허용 방향 그대로 저장한다.
- `SYMMETRIC`: 두 유형 ID를 오름차순으로 정규화하고 `source_node_type_id <= target_node_type_id` CHECK를 적용한다.
- 반대 방향 행을 함께 만들지 않는다.

revision과 두 endpoint type을 모두 알고 검증하므로 복합 PK가 승인 검사를 지원한다. node type만으로 관계 revision을 역탐색하는 조회가 실제 API에서 필요해질 때만 후속 인덱스를 추가한다.

### 3.4 관계 유형 주석

```sql
COMMENT ON TABLE relation_type IS
'관계 의미를 식별하는 안정된 코드 테이블. 활성 상태와 방향·endpoint 규칙은 revision이 소유한다.';

COMMENT ON COLUMN relation_type_revision.is_active IS
'새 관계를 생성할 때 사용할 수 있는 exact revision인지 표시한다. 기존 관계를 숨기거나 재해석하지 않는다.';

COMMENT ON TABLE relation_endpoint_rule IS
'관계 revision이 허용하는 시작·도착 node type 쌍. 실제 관계 endpoint 검증은 승격 서비스가 수행한다.';
```

## 4. 속성 정의

### 4.1 `attribute`

#### 책임

구조화된 노드 속성의 안정된 code를 관리한다. 실제 값이나 대상 노드는 저장하지 않는다.

#### 컬럼과 제약

| 컬럼 | 타입 | NULL | 기본값 | 변경 규칙 |
|---|---|---:|---|---|
| `attribute_id` | `bigint` | 불가 | `GENERATED ALWAYS AS IDENTITY` | 불변 |
| `attribute_code` | `text` | 불가 | 없음 | 사용 후 불변 |

- PK `pk_attribute (attribute_id)`
- UNIQUE `uq_attribute__code (attribute_code)`
- `btrim(attribute_code) <> ''`
- 활성 플래그를 두지 않는다. 활성 revision이 없으면 새 속성값에 사용할 수 없다.

### 4.2 `attribute_revision`

#### 책임

속성의 표시 이름, 단일 대상 node type, 허용 값 종류와 NUMBER의 canonical 단위를 보존하는 불변 규칙 버전이다.

#### 컬럼

| 컬럼 | 타입 | NULL | 기본값 | 변경 규칙 |
|---|---|---:|---|---|
| `attribute_revision_id` | `bigint` | 불가 | `GENERATED ALWAYS AS IDENTITY` | 불변 |
| `attribute_id` | `bigint` | 불가 | 없음 | 불변 |
| `version_no` | `integer` | 불가 | 없음 | 불변 |
| `display_name` | `text` | 불가 | 없음 | 사용 후 불변 |
| `target_node_type_id` | `bigint` | 불가 | 없음 | 사용 후 불변 |
| `allowed_value_kind` | `text` | 불가 | 없음 | 사용 후 불변 |
| `unit_rule` | `text` | 허용 | 없음 | 사용 후 불변 |
| `is_active` | `boolean` | 불가 | `false` | 새 속성값 생성 허용 전환 |

#### 키와 제약

- PK `pk_attribute_revision (attribute_revision_id)`
- FK `attribute_id → attribute`
- FK `target_node_type_id → node_type`
- UNIQUE `uq_attribute_revision__version (attribute_id, version_no)`
- UNIQUE `uq_attribute_revision__kind (attribute_revision_id, allowed_value_kind)`
  - #43의 `(attribute_revision_id, value_kind)` 복합 FK 대상
- partial UNIQUE index:

```sql
CREATE UNIQUE INDEX uq_attribute_revision__active
ON attribute_revision (attribute_id)
WHERE is_active;
```

- `version_no >= 1`
- `btrim(display_name) <> ''`
- `allowed_value_kind IN ('STRING', 'NUMBER', 'DATE', 'PERIOD', 'BOOLEAN')`
- `allowed_value_kind = 'NUMBER'`일 때만 nonblank `unit_rule`이 필수다.
- 다른 값 종류에서는 `unit_rule IS NULL`이어야 한다.

`unit_rule`은 POC에서 한 revision이 허용하는 canonical 단위 code 하나다. 자동 환산식이나 단위 목록 JSON이 아니다.

#### 인덱스

- `ix_attribute_revision__target_type (target_node_type_id, attribute_revision_id)`
  - 한 node type에 사용 가능한 속성 revision 조회
- revision 버전과 현재 활성 조회는 고유 인덱스가 지원한다.

#### 서비스 규칙

- 새 revision 활성화 전에 target node type, 값 종류와 단위 계약을 함께 검증한다.
- 같은 attribute의 기존 활성 revision 비활성화와 새 revision 활성화를 한 트랜잭션에서 처리한다.
- 승격 시 target node의 실제 type, exact revision의 `allowed_value_kind`, `is_active`를 다시 검증한다.
- 여러 대상 유형이 실제 요구가 되기 전에는 `attribute_target_rule`을 추가하지 않는다.

### 4.3 속성 주석

```sql
COMMENT ON TABLE attribute IS
'구조화된 Claim 속성의 안정된 코드 테이블. 실제 값과 사용 규칙은 attribute_revision과 claim_attribute_value가 소유한다.';

COMMENT ON COLUMN attribute_revision.unit_rule IS
'NUMBER revision이 허용하는 canonical 단위 code 하나. 자동 단위 환산 규칙이나 표시 문자열 목록이 아니다.';
```

## 5. 현재 단계의 되돌리기 지점

- 전체 활성 규칙 snapshot이 필요하면 #69의 manifest 구조를 전부 복원한다.
- 외부 관리자가 code를 직접 추가하면 안 되는 완전한 폐쇄형 목록이 되면 코드 테이블을 제거하고 `CHECK IN`으로 전환할 수 있다. 이 경우 기존 FK와 seed·관리 경로를 함께 제거해야 한다.
- DB가 교차 행 규칙을 단독으로 방어해야 한다는 운영 요구가 생기면 relation revision 활성화용 좁은 deferred constraint trigger를 별도 Issue로 추가한다. 서비스와 같은 검사를 중복 유지하지 않는다.
