from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, got {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new))


logical = "docs/data/logical-schema.md"
replace_once(logical, "> 변경 기준일: 2026-09-14\n", "> 변경 기준일: 2026-09-15\n")
replace_once(
    logical,
    "> 관련 변경: Issue #41, #64, #69, #91, #110, #200\n",
    "> 관련 변경: Issue #41, #64, #69, #91, #110, #200, #203\n",
)
replace_once(
    logical,
    "- 모든 공개 지식은 Claim과 정확한 observation을 거쳐 `source_document`까지 추적할 수 있어야 한다.\n",
    "- 모든 evidence-backed 공개 지식은 Claim과 정확한 observation을 거쳐 `source_document`까지 추적할 수 있어야 한다. 제품 Reference Topic 자체는 Evidence가 아닌 controlled vocabulary이며 별도 lifecycle로 식별한다.\n",
)
replace_once(
    logical,
    "    NODE_TYPE ||--o{ NODE : classifies\n    NODE ||--o{ NODE_ALIAS : names\n",
    "    NODE_TYPE ||--o{ NODE : classifies\n    NODE ||--o| TOPIC_REFERENCE : reference_definition\n    NODE ||--o{ NODE_ALIAS : names\n",
)
node_type = "`node_type_id`, 안정된 `node_type_code`, 표시 이름, 생성 규칙과 `is_active`를 가진다. 초기 코드는 `PERSON`, `COMPANY`, `TECHNOLOGY`, `TOPIC`, `EVENT`다. 비활성화는 기존 노드를 삭제·거절·숨김 처리하지 않는다.\n"
replace_once(
    logical,
    node_type,
    node_type
    + "\n#203 이후 `TOPIC` type 자체가 Evidence 예외를 뜻하지 않는다. 기존 evidence-backed TOPIC Node는 기존 lifecycle로 보존할 수 있고, 제품 controlled vocabulary로 만드는 Reference Topic만 `PRODUCT_REFERENCE` lifecycle과 정확히 하나의 `topic_reference` 정의를 가진다. 일반 Agent/entity-resolution 경로는 새 TOPIC Node를 만들지 않고 active Reference Topic만 재사용한다.\n\n#### `topic_reference`\n\n제품 정의 Topic의 1:1 reference definition이다. 공유 `node_id` 정체성을 유지하면서 stable `topic_code`, canonical 표시 이름, `is_active`를 소유한다. canonical 이름은 `node_alias`나 외부 Evidence가 아니라 이 정의가 source of truth다. `is_active=false`는 새 `HAS_TOPIC` mapping 생성만 막으며 기존 Topic Node나 과거 Relation을 삭제·비공개·재해석하지 않는다. #203은 schema와 activation/read boundary만 제공하고 실제 승인 Topic 9개 row 활성화는 #201이 담당한다.\n",
)
knowledge = "`knowledge_item`은 ID, `item_kind`, `current_state`, `promotion_batch_id`, `created_at`을 가진다. 정확히 하나의 `node`, `relation`, `claim` 하위 행과 대응한다.\n\n초기 `근거 확인됨`은 시스템 생성 상태이며 사람 이벤트를 만들지 않는다. `knowledge_state_event`는 사람의 상태 변경만 append-only로 기록한다. 처리자 물리 계약은 관리자 기능까지 보류한다.\n"
replace_once(
    logical,
    knowledge,
    "`knowledge_item`은 ID, `item_kind`, `lifecycle_kind`, `current_state`, `promotion_batch_id`, `created_at`을 가진다. 정확히 하나의 `node`, `relation`, `claim` 하위 행과 대응한다.\n\n`EVIDENCE_BACKED` lifecycle은 기존 지식 계약으로 `current_state`와 `promotion_batch_id`가 모두 필수이며 Evidence Trace·lint·publication을 그대로 따른다. `PRODUCT_REFERENCE`는 승인된 Reference Topic Node에만 허용되고 두 값은 모두 비어 있어야 한다. 이 NULL 허용은 기존 지식 제약 완화가 아니라 lifecycle별 조건부 무결성이다. Reference Topic 자체에는 가짜 `EVIDENCE_VERIFIED`, promotion batch 또는 publication READY를 만들지 않는다.\n\n초기 `근거 확인됨`은 evidence-backed 시스템 생성 상태이며 사람 이벤트를 만들지 않는다. `knowledge_state_event`는 사람의 상태 변경만 append-only로 기록한다. 처리자 물리 계약은 관리자 기능까지 보류한다.\n",
)

physical = "docs/data/physical-schema.md"
replace_once(physical, "- 확인일: 2026-09-14\n", "- 확인일: 2026-09-15\n")
replace_once(
    physical,
    "- 관련 Issue: [#40 Define PostgreSQL physical schema conventions](https://github.com/studylida/ontology-map/issues/40), [#200 NUMBER attribute 복수 허용 단위 지원](https://github.com/studylida/ontology-map/issues/200)\n",
    "- 관련 Issue: [#40 Define PostgreSQL physical schema conventions](https://github.com/studylida/ontology-map/issues/40), [#200 NUMBER attribute 복수 허용 단위 지원](https://github.com/studylida/ontology-map/issues/200), [#203 Topic reference lifecycle 지원](https://github.com/studylida/ontology-map/issues/203)\n",
)
replace_once(
    physical,
    "- 구현: #95, `server/migrations/versions/0001_create_frozen_schema.py`; #200, `server/migrations/versions/0003_support_multiple_number_attribute_units.py`\n",
    "- 구현: #95, `server/migrations/versions/0001_create_frozen_schema.py`; #200, `server/migrations/versions/0003_support_multiple_number_attribute_units.py`; #203, `server/migrations/versions/0004_support_topic_reference_lifecycle.py`\n",
)
replace_once(
    physical,
    "- Alembic revision: `0001_create_frozen_schema.py` → `0002_add_panel_reading_contracts.py` → `0003_support_multiple_number_attribute_units.py`\n",
    "- Alembic revision: `0001_create_frozen_schema.py` → `0002_add_panel_reading_contracts.py` → `0003_support_multiple_number_attribute_units.py` → `0004_support_topic_reference_lifecycle.py`\n",
)
publication = "일반 사용자 조회는 node별 `ready_at DESC, promotion_batch_id DESC` 순서의 최신 `COMMITTED + READY`를 선택한다. node, Relation, Claim과 파생 결과의 basis 지식이 `EVIDENCE_VERIFIED | HUMAN_VERIFIED` 상태이고 열린 `BLOCKING` lint가 없는지 read-time에서 다시 확인한다. 새 publication이 실패하면 기준 지식과 과거 산출물을 삭제하지 않고 이전 READY를 계속 제공한다. 이전 READY가 전혀 없으면 현재 exploration 계열 API는 `503 PUBLICATION_NOT_READY`를 반환한다.\n"
replace_once(
    physical,
    publication,
    publication
    + "\n제품 Reference Topic은 일반 READY를 흉내 내는 예외가 아니라 별도 lifecycle/read contract다. `PRODUCT_REFERENCE` row에는 일반 state/promotion을 넣지 않고 `node_search_document`와 `publication_affected_node`도 금지한다. Topic 중심 조회는 `topic_reference` canonical 이름과 공개 가능한 direct `HAS_TOPIC` Relation을 역조회하며, 그 Relation과 지지 Claim은 계속 `EVIDENCE_BACKED` lifecycle·Evidence Trace·lint·publication basis 검증을 따라야 한다.\n",
)
subtype = "“정확히 한 subtype”의 교차 행 검증은 짧은 승격 transaction이 담당하며 공유 PK와 item kind의 로컬 조건은 DB가 보장한다.\n"
replace_once(
    physical,
    subtype,
    subtype
    + "\n#203의 `knowledge_item.lifecycle_kind`는 공유 ID를 유지하면서 `EVIDENCE_BACKED`와 `PRODUCT_REFERENCE`를 구분한다. 전자는 `current_state`와 `promotion_batch_id`를 필수로 유지하고 후자는 `NODE + NULL state/batch` 형태만 허용한다. `topic_reference`와 deferred constraint trigger는 product-reference row가 실제 TOPIC node와 1:1인지 검증한다. 기존 evidence-backed TOPIC은 자동 변환하지 않는다. 새 `HAS_TOPIC` INSERT/target 변경은 active reference target만 허용하며 reference 비활성화는 기존 Relation을 손대지 않는다.\n",
)

policy = "docs/data/source-intake-policy.md"
replace_once(policy, "> 확정일: 2026-09-10\n", "> 확정일: 2026-09-15\n")
lint = "Structured Output 계약을 만족한 후보만 승격 전 lint에 들어간다. 현재 정책의 분류는 다음과 같다.\n"
replace_once(
    policy,
    lint,
    lint
    + "\n#203의 제품 Reference Topic 자체는 외부 사실 주장이 아니라 승인 controlled vocabulary이므로 `PRODUCT_REFERENCE` lifecycle로 식별하고 아래 Evidence Trace lint 대상에서 제외한다. 이는 `node_type=TOPIC` 전체를 건너뛰는 예외가 아니다. 기존 evidence-backed TOPIC, `HAS_TOPIC` Relation과 지지 Claim은 기존 Evidence Trace·ontology·lint 계약을 그대로 따른다. Reference Topic을 위해 가짜 `source_document`, Observation, Claim, 상태, promotion 또는 publication READY를 만들지 않는다.\n",
)

product = "docs/product/design.md"
overview = "UI 문구는 한국어를 기본으로 한다. node type, relation type, model identifier, ontology code와 API 값처럼 정확한 식별이 필요한 값은 원래 영어 표기를 보존한다.\n\n"
replace_once(
    product,
    overview,
    overview
    + "## Reference Topic 읽기 계약\n\n제품 Reference Topic은 일반 evidence-backed 지식이 아니라 승인 controlled vocabulary다. canonical 표시 이름은 `topic_reference` 정의가 소유하고 일반 검색 문서나 alias Evidence를 만들지 않는다. #203은 lifecycle/schema/read boundary만 지원하며 실제 승인 Topic 9개 활성화는 #201이 담당한다.\n\n일반 검색에는 Reference Topic을 포함하지 않는다. Topic 진입은 승인 Topic/카테고리 목록 또는 일반 graph에 이미 표시된 Topic 선택을 전제로 한다. `GET /api/v1/topics/{topic_node_id}/exploration?time_window=RECENT_90_DAYS|RECENT_1_YEAR`는 공개 가능한 direct `HAS_TOPIC` membership만 반환하고 Topic 중심 2-hop·3-hop 확장은 하지 않는다. 응답은 전체 공개 membership 수와 선택 기간의 최근 member 수·최근 Evidence Group 수를 구분한다.\n\nTopic이 비활성화되어도 기존 유효 membership은 삭제·비공개·재해석하지 않고 새 `HAS_TOPIC` 생성만 차단한다. 연결된 일반 Node를 선택하면 기존 exploration을 그대로 사용한다. 일반 Node exploration의 직접 이웃 상한은 24개이며 direct `HAS_TOPIC` Reference Topic도 같은 후보군에 포함하지만 Topic 전용 quota·별도 graph layer는 두지 않는다.\n\n",
)

operations = "docs/operations/database.md"
replace_once(
    operations,
    "현재 기준 revision은 `0001_create_frozen_schema.py` → `0002_add_panel_reading_contracts.py` → `0003_support_multiple_number_attribute_units.py`다. PostgreSQL 객체는 `public` schema에 만들며 migration과 SQLAlchemy metadata는 같은 schema를 표현한다. #121 이후 `0001`에는 `vector` extension, `node_embedding` table과 `EMBEDDING` task 허용 계약이 없다.\n",
    "현재 기준 revision은 `0001_create_frozen_schema.py` → `0002_add_panel_reading_contracts.py` → `0003_support_multiple_number_attribute_units.py` → `0004_support_topic_reference_lifecycle.py`다. PostgreSQL 객체는 `public` schema에 만들며 migration과 SQLAlchemy metadata는 같은 schema를 표현한다. #121 이후 `0001`에는 `vector` extension, `node_embedding` table과 `EMBEDDING` task 허용 계약이 없다.\n",
)
migration = "`0003`은 기존 NUMBER `attribute_revision.unit_rule`을 `attribute_revision_allowed_unit`의 허용 단위 행으로 옮긴 뒤 `claim_attribute_value(attribute_revision_id, unit_code)`를 그 허용 집합에 FK로 연결한다. 기존 단일 단위 revision은 한 행으로 그대로 이관한다. 기존 Claim의 unit이 legacy `unit_rule`과 다르면 값을 환산하거나 수정하지 않고 migration을 실패시킨다. 복수 허용 단위가 생성된 뒤 `0002`로 downgrade하면 의미를 한 문자열로 되돌릴 수 없으므로 downgrade도 중단한다.\n"
replace_once(
    operations,
    migration,
    migration
    + "\n`0004`는 `knowledge_item.lifecycle_kind`와 `topic_reference`를 추가한다. 기존 행은 모두 `EVIDENCE_BACKED`로 해석되어 state/promotion 값을 그대로 유지하며 기존 evidence-backed TOPIC도 자동 변환하지 않는다. 새 `PRODUCT_REFERENCE` Topic만 일반 state/promotion 없이 저장할 수 있고 DB 무결성이 TOPIC node + reference definition 조합으로 제한한다. Reference Topic row가 존재하면 `0003` downgrade는 의미 손실을 막기 위해 실패한다.\n\n`0004` 자체는 제품 Topic row를 seed하지 않고 startup도 누락 Topic을 자동 생성하지 않는다. 승인 Topic 9개의 실제 활성화는 #201이 명시적 reference activation transaction으로 수행한다. 개발 fixture의 evidence-backed TOPIC과 제품 Reference Topic을 같은 데이터로 간주하지 않는다.\n",
)
