from pathlib import Path

SCHEMA = Path("server/src/ontology_map/db/schema.py")
TOPIC_REFS = Path("server/src/ontology_map/db/topic_references.py")
POSTGRES_TEST = Path("server/tests/test_topic_references_postgres.py")

schema = SCHEMA.read_text()
start = schema.index("knowledge_item = sa.Table(\n")
end = schema.index("\nnode = sa.Table(\n", start)
knowledge_block = '''knowledge_item = sa.Table(
    "knowledge_item",
    metadata,
    sa.Column(
        "knowledge_item_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("item_kind", sa.Text, nullable=False),
    sa.Column(
        "lifecycle_kind",
        sa.Text,
        server_default=sa.text("'EVIDENCE_BACKED'"),
        nullable=False,
        comment=(
            "EVIDENCE_BACKED는 기존 promotion·state·Evidence/publication 수명주기, "
            "PRODUCT_REFERENCE는 승인된 제품 reference Node 수명주기다."
        ),
    ),
    sa.Column(
        "current_state",
        sa.Text,
        nullable=True,
        comment=(
            "EVIDENCE_VERIFIED는 출처와 구조 검사를 통과했다는 뜻이며 객관적 "
            "사실 확정이나 사람 승인을 뜻하지 않는다."
        ),
    ),
    sa.Column(
        "promotion_batch_id",
        sa.BigInteger,
        sa.ForeignKey(
            "promotion_batch.promotion_batch_id",
            name="fk_knowledge_item__promotion_batch",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint("knowledge_item_id", name="pk_knowledge_item"),
    sa.CheckConstraint(
        "item_kind IN ('NODE', 'RELATION', 'CLAIM')",
        name="ck_knowledge_item__item_kind",
    ),
    sa.CheckConstraint(
        "lifecycle_kind IN ('EVIDENCE_BACKED', 'PRODUCT_REFERENCE')",
        name="ck_knowledge_item__lifecycle_kind",
    ),
    sa.CheckConstraint(
        "current_state IN "
        "('EVIDENCE_VERIFIED', 'HUMAN_VERIFIED', 'ON_HOLD', 'REJECTED')",
        name="ck_knowledge_item__current_state",
    ),
    sa.CheckConstraint(
        "(lifecycle_kind = 'EVIDENCE_BACKED' "
        "AND current_state IS NOT NULL AND promotion_batch_id IS NOT NULL) OR "
        "(lifecycle_kind = 'PRODUCT_REFERENCE' AND item_kind = 'NODE' "
        "AND current_state IS NULL AND promotion_batch_id IS NULL)",
        name="ck_knowledge_item__lifecycle_shape",
    ),
    sa.CheckConstraint(
        "isfinite(created_at)",
        name="ck_knowledge_item__created_at_finite",
    ),
    comment=(
        "node·relation·claim의 공유 ID와 수명주기를 관리하는 상위 엔터티. "
        "EVIDENCE_BACKED는 기존 state·promotion을 필수로 사용하고, "
        "PRODUCT_REFERENCE는 승인된 reference Node에만 제한한다."
    ),
)
sa.Index(
    "ix_knowledge_item__promotion_batch",
    knowledge_item.c.promotion_batch_id,
    knowledge_item.c.knowledge_item_id,
)
'''
schema = schema[:start] + knowledge_block + schema[end:]

marker = 'sa.Index("ix_node__type", node.c.node_type_id, node.c.node_id)\n\nrelation = sa.Table(\n'
if schema.count(marker) != 1:
    raise SystemExit(f"node/relation marker count={schema.count(marker)}")

topic_block = '''sa.Index("ix_node__type", node.c.node_type_id, node.c.node_id)

topic_reference = sa.Table(
    "topic_reference",
    metadata,
    sa.Column(
        "node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_topic_reference__node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("topic_code", sa.Text, nullable=False),
    sa.Column("canonical_display_name", sa.Text, nullable=False),
    sa.Column(
        "is_active",
        sa.Boolean,
        server_default=sa.text("false"),
        nullable=False,
        comment=(
            "새 HAS_TOPIC mapping의 target으로 사용할 수 있는지 나타낸다. "
            "비활성화는 기존 relation의 의미·공개 여부를 바꾸지 않는다."
        ),
    ),
    sa.PrimaryKeyConstraint("node_id", name="pk_topic_reference"),
    sa.UniqueConstraint("topic_code", name="uq_topic_reference__code"),
    sa.CheckConstraint(
        "btrim(topic_code) <> ''",
        name="ck_topic_reference__code_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(canonical_display_name) <> ''",
        name="ck_topic_reference__display_name_nonblank",
    ),
    sa.CheckConstraint(
        (
            "(topic_code = 'SEMICONDUCTOR' "
            "AND canonical_display_name = '반도체') OR "
            "(topic_code = 'MEMORY_SEMICONDUCTOR' "
            "AND canonical_display_name = '메모리 반도체') OR "
            "(topic_code = 'ADVANCED_PACKAGING' "
            "AND canonical_display_name = '첨단 패키징') OR "
            "(topic_code = 'ARTIFICIAL_INTELLIGENCE' "
            "AND canonical_display_name = '인공지능') OR "
            "(topic_code = 'DATA_CENTER' "
            "AND canonical_display_name = '데이터센터') OR "
            "(topic_code = 'MANUFACTURING_PROCESS' "
            "AND canonical_display_name = '제조 공정') OR "
            "(topic_code = 'INVESTMENT' "
            "AND canonical_display_name = '투자') OR "
            "(topic_code = 'COMMERCIALIZATION' "
            "AND canonical_display_name = '상용화') OR "
            "(topic_code = 'REGULATION_POLICY' "
            "AND canonical_display_name = '규제·정책')"
        ),
        name="ck_topic_reference__approved_definition",
    ),
    comment=(
        "TOPIC Node identity에 연결된 제품 controlled vocabulary 정의. canonical "
        "이름과 active mapping 여부의 source of truth이며 Evidence가 아니다."
    ),
)

relation = sa.Table(
'''
schema = schema.replace(marker, topic_block)
SCHEMA.write_text(schema)

refs = TOPIC_REFS.read_text()
old_error = (
    '        raise ValueError('
    '"Topic reference definition is not in the approved #203 contract")\n'
)
new_error = '''        raise ValueError(
            "Topic reference definition is not in the approved #203 contract"
        )
'''
if refs.count(old_error) != 1:
    raise SystemExit(f"topic reference error marker count={refs.count(old_error)}")
TOPIC_REFS.write_text(refs.replace(old_error, new_error))

test = POSTGRES_TEST.read_text()
old_import = (
    "    source_document,\n"
    ")\n"
    "from ontology_map.db.session import get_engine\n"
    "from ontology_map.db.topic_reference_schema import topic_reference\n"
)
new_import = (
    "    source_document,\n"
    "    topic_reference,\n"
    ")\n"
    "from ontology_map.db.session import get_engine\n"
)
if test.count(old_import) != 1:
    raise SystemExit(f"postgres test import marker count={test.count(old_import)}")
POSTGRES_TEST.write_text(test.replace(old_import, new_import))
