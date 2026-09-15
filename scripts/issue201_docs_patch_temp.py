from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one marker in {path}: {old[:60]!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "docs/operations/database.md",
    "`0004` 자체는 제품 Topic row를 seed하지 않고 startup도 누락 Topic을 자동 생성하지 않는다. 승인 Topic 9개의 실제 활성화는 #201이 명시적 reference activation transaction으로 수행한다. 개발 fixture의 evidence-backed TOPIC과 제품 Reference Topic을 같은 데이터로 간주하지 않는다.\n\n## 3. 개발용 HBF fixture",
    """`0004` 자체는 제품 Topic row를 seed하지 않고 startup도 누락 Topic을 자동 생성하지 않는다. 승인 Topic 9개의 실제 활성화는 migration과 분리된 #201 명시적 reference activation transaction이 담당한다. 개발 fixture의 evidence-backed TOPIC과 제품 Reference Topic을 같은 데이터로 간주하지 않는다.

### 제품 ontology reference data 활성화

migration 적용 뒤 제품에서 사용할 승인 ontology reference data는 `server/`에서 다음 명령으로 명시적으로 활성화한다.

```bash
PYTHONPATH=src uv run --env-file ../.env python -m ontology_map.db.ontology_reference_data
```

이 명령은 [승인 ontology reference data](../data/ontology-reference-data.md)의 Relation 13개 + `HAS_TOPIC`, attribute 6개, Reference Topic 9개만 활성화한다. 앱 startup에서는 실행하지 않으며 재실행해도 stable code·revision·Topic row를 중복 생성하지 않는다. 이미 같은 code에 계약과 다른 active revision이 있으면 기존 의미를 덮어쓰거나 비활성화하지 않고 실패한다. 기존 HBF fixture의 `PUBLICLY_ASSOCIATED_WITH`, 저장 Relation·Claim·Evidence·promotion은 수정하지 않는다.

Reference Topic은 #203의 `PRODUCT_REFERENCE` activation 경계를 사용하므로 `source_document`, Observation, Claim, 일반 state, promotion batch 또는 READY publication을 만들지 않는다. `MAX_MEMORY_BANDWIDTH`는 하나의 NUMBER active revision 아래 `GB_PER_S`, `TB_PER_S` 두 허용 원문 단위를 등록하며 환산·정규화·비교를 수행하지 않는다.

## 3. 개발용 HBF fixture""",
)

replace_once(
    "docs/data/logical-schema.md",
    "제품 정의 Topic의 1:1 reference definition이다. 공유 `node_id` 정체성을 유지하면서 stable `topic_code`, canonical 표시 이름, `is_active`를 소유한다. canonical 이름은 `node_alias`나 외부 Evidence가 아니라 이 정의가 source of truth다. `is_active=false`는 새 `HAS_TOPIC` mapping 생성만 막으며 기존 Topic Node나 과거 Relation을 삭제·비공개·재해석하지 않는다. #203은 schema와 activation/read boundary만 제공하고 실제 승인 Topic 9개 row 활성화는 #201이 담당한다.",
    "제품 정의 Topic의 1:1 reference definition이다. 공유 `node_id` 정체성을 유지하면서 stable `topic_code`, canonical 표시 이름, `is_active`를 소유한다. canonical 이름은 `node_alias`나 외부 Evidence가 아니라 이 정의가 source of truth다. `is_active=false`는 새 `HAS_TOPIC` mapping 생성만 막으며 기존 Topic Node나 과거 Relation을 삭제·비공개·재해석하지 않는다. #203이 schema와 activation/read boundary를 제공하고 #201의 별도 idempotent activation이 승인 Topic 9개 row를 실제 제품 reference data로 만든다. 활성 목록과 실행 경계는 [승인 ontology reference data](ontology-reference-data.md)가 소유한다.",
)

replace_once(
    "docs/product/design.md",
    "제품 Reference Topic은 일반 evidence-backed 지식이 아니라 승인 controlled vocabulary다. canonical 표시 이름은 `topic_reference` 정의가 소유하고 일반 검색 문서나 alias Evidence를 만들지 않는다. #203은 lifecycle/schema/read boundary만 지원하며 실제 승인 Topic 9개 활성화는 #201이 담당한다.",
    "제품 Reference Topic은 일반 evidence-backed 지식이 아니라 승인 controlled vocabulary다. canonical 표시 이름은 `topic_reference` 정의가 소유하고 일반 검색 문서나 alias Evidence를 만들지 않는다. #203은 lifecycle/schema/read boundary를 제공하고 #201의 명시적 reference-data activation이 승인 Topic 9개를 실제 제품 row로 활성화한다. 앱 startup이 누락 Topic을 자동 생성하거나 보정하지 않는다.",
)

Path("docs/data/ontology-reference-data.md").write_text(
    """# 승인 ontology reference data

> 상태: #126·#203 사용자 승인 계약의 제품 reference-data activation 구현
>
> 구현 Issue: #201
>
> schema 선행: #200, #203

이 문서는 제품 DB에 명시적으로 활성화하는 초기 ontology reference data와 실행 경계를 기록한다. 개발 HBF fixture의 시험용 `PUBLICLY_ASSOCIATED_WITH`와 제품 승인 ontology는 서로 다른 데이터다.

## 활성화 경계

`server/`에서 migration을 먼저 적용한 뒤 다음 명령을 실행한다.

```bash
PYTHONPATH=src uv run --env-file ../.env python -m ontology_map.db.ontology_reference_data
```

앱 startup은 이 명령을 암묵적으로 실행하지 않는다. stable code가 이미 승인 의미와 같은 active revision을 가리키면 그대로 재사용한다. active revision이 없으면 의미가 정확히 같은 기존 inactive revision을 재활성화하고, 그런 revision도 없을 때만 다음 `version_no`의 새 immutable revision을 만든다. 같은 stable code에 계약과 다른 active revision이 있으면 fail-closed하며 기존 revision이나 저장 지식을 자동 rewrite하지 않는다.

clean migrated DB에는 ontology row가 없으므로 activation은 frozen logical schema의 초기 stable node type `PERSON`, `COMPANY`, `TECHNOLOGY`, `TOPIC`, `EVENT`도 공통 prerequisite로 보장한다. 이 다섯 type은 아래 제품 Relation·attribute·Topic payload와 HBF 개발 fixture가 공유하는 기반 코드이며, fixture의 시험 Relation을 제품 ontology로 승격시키지 않는다.

## Relation

일반 Relation 13개와 Topic 연결 `HAS_TOPIC` 하나를 활성화한다.

| code | endpoint | directionality |
| --- | --- | --- |
| `AFFILIATED_WITH` | PERSON → COMPANY | DIRECTED |
| `DEVELOPS` | COMPANY 또는 PERSON → TECHNOLOGY | DIRECTED |
| `COLLABORATES_WITH` | COMPANY ↔ COMPANY | SYMMETRIC |
| `ANNOUNCES` | COMPANY 또는 PERSON → TECHNOLOGY 또는 EVENT | DIRECTED |
| `INVESTS_IN` | COMPANY → COMPANY 또는 TECHNOLOGY | DIRECTED |
| `ADOPTS` | COMPANY → TECHNOLOGY | DIRECTED |
| `TESTS` | COMPANY → TECHNOLOGY | DIRECTED |
| `SUPPLIES` | COMPANY → TECHNOLOGY | DIRECTED |
| `SUPPLIES_TO` | COMPANY → COMPANY | DIRECTED |
| `INCLUDES` | TECHNOLOGY → TECHNOLOGY | DIRECTED |
| `PARTICIPATES_IN` | COMPANY 또는 PERSON → EVENT | DIRECTED |
| `MENTIONS` | COMPANY 또는 PERSON → COMPANY, PERSON, TECHNOLOGY 또는 EVENT | DIRECTED |
| `RELATED_TO` | EVENT ↔ TECHNOLOGY | SYMMETRIC |
| `HAS_TOPIC` | COMPANY, PERSON, TECHNOLOGY 또는 EVENT → TOPIC | DIRECTED |

`RELATED_TO`는 fallback-only다. 같은 문서·문장 동시 등장만으로 생성하지 않고 Claim이 EVENT와 TECHNOLOGY의 직접 의미 연관을 지지해야 한다. 더 구체적인 승인 Relation이 있으면 그것을 우선한다.

## Attribute

| code | target | value kind | 허용 원문 단위 |
| --- | --- | --- | --- |
| `ROLE_TITLE` | PERSON | STRING | 없음 |
| `TECHNOLOGY_VERSION` | TECHNOLOGY | STRING | 없음 |
| `COMMERCIALIZATION_STATUS` | TECHNOLOGY | STRING | 없음 |
| `COMMERCIALIZATION_SCHEDULE` | TECHNOLOGY | STRING | 없음 |
| `CORE_COUNT` | TECHNOLOGY | NUMBER | `COUNT` |
| `MAX_MEMORY_BANDWIDTH` | TECHNOLOGY | NUMBER | `GB_PER_S`, `TB_PER_S` |

`MAX_MEMORY_BANDWIDTH`는 하나의 stable attribute와 하나의 active NUMBER revision을 사용한다. 두 unit은 허용되는 원문 단위 집합일 뿐 canonical unit, 환산, normalization 또는 cross-unit comparison 규칙이 아니다.

## Reference Topic

| stable code | canonical display name |
| --- | --- |
| `SEMICONDUCTOR` | 반도체 |
| `MEMORY_SEMICONDUCTOR` | 메모리 반도체 |
| `ADVANCED_PACKAGING` | 첨단 패키징 |
| `ARTIFICIAL_INTELLIGENCE` | 인공지능 |
| `DATA_CENTER` | 데이터센터 |
| `MANUFACTURING_PROCESS` | 제조 공정 |
| `INVESTMENT` | 투자 |
| `COMMERCIALIZATION` | 상용화 |
| `REGULATION_POLICY` | 규제·정책 |

Topic은 #203의 explicit `ensure_topic_reference()` 경계를 통해서만 생성·재사용한다. 각 row는 `PRODUCT_REFERENCE` Node lifecycle을 사용하며 일반 `current_state`, `promotion_batch_id`, `node_alias`, Evidence, `node_search_document` 또는 READY publication을 만들지 않는다.

## 보존과 검증

activation은 Relation type/revision/endpoint, attribute/revision/unit과 Topic reference만 다룬다. 기존 Relation·Claim·Evidence·publication과 HBF fixture를 새 제품 code로 소급 변환하지 않는다. 실제 PostgreSQL 검증에서는 activation 재실행 시 동일 revision/Topic ID가 유지되는지, HBF fixture 이후 실행해도 fixture Relation·Claim·source·Observation·promotion·검색 문서 수가 바뀌지 않는지 확인한다.
""",
    encoding="utf-8",
)
