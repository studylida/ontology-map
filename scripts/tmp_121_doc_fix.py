from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one occurrence, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "docs/data/logical-schema.md",
    "| `output_schema_definition_id` | 정확한 출력 계약. `EMBEDDING`만 비움 |",
    "| `output_schema_definition_id` | 정확한 출력 계약 |",
)
replace_once(
    "docs/data/logical-schema.md",
    "허용 작업은 `KNOWLEDGE_EXTRACTION`, `ENTITY_RESOLUTION_PROPOSAL`, `EVIDENCE_LINEAGE_PROPOSAL`, `CONFLICT_SUMMARY`, `NODE_CONTEXT`, `FOLLOWUP_QUESTIONS`, `NODE_INSIGHT`와 schema가 없는 `EMBEDDING`이다.",
    "허용 작업은 `KNOWLEDGE_EXTRACTION`, `ENTITY_RESOLUTION_PROPOSAL`, `EVIDENCE_LINEAGE_PROPOSAL`, `CONFLICT_SUMMARY`, `NODE_CONTEXT`, `FOLLOWUP_QUESTIONS`, `NODE_INSIGHT`다. 모든 허용 작업은 정확한 output schema와 prompt version을 가진다.",
)
replace_once(
    "docs/data/physical-schema.md",
    "현재 migration은 `node_search_document`의 `simple` A/B `tsvector` 표현식 GIN만 구현한다. JSON GIN, vector HNSW·IVFFlat과 대규모 covering index는 없다.\n\n새 특수 인덱스는 실제 query와 측정 결과를 소유하는 Issue에서만 결정한다. 초기 vector 검색은 cosine exact search이므로 근사 검색 인덱스를 미리 만들지 않는다.",
    "현재 migration은 `node_search_document`의 `simple` A/B `tsvector` 표현식 GIN만 구현한다. JSON GIN과 대규모 covering index는 없다.\n\n새 특수 인덱스는 실제 query와 측정 결과를 소유하는 Issue에서만 결정한다.",
)
