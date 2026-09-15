"""#203 Topic reference lifecycle extension for the shared SQLAlchemy metadata."""

import sqlalchemy as sa

from ontology_map.db import schema as base_schema

EVIDENCE_BACKED = "EVIDENCE_BACKED"
PRODUCT_REFERENCE = "PRODUCT_REFERENCE"

APPROVED_TOPIC_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("SEMICONDUCTOR", "반도체"),
    ("MEMORY_SEMICONDUCTOR", "메모리 반도체"),
    ("ADVANCED_PACKAGING", "첨단 패키징"),
    ("ARTIFICIAL_INTELLIGENCE", "인공지능"),
    ("DATA_CENTER", "데이터센터"),
    ("MANUFACTURING_PROCESS", "제조 공정"),
    ("INVESTMENT", "투자"),
    ("COMMERCIALIZATION", "상용화"),
    ("REGULATION_POLICY", "규제·정책"),
)

knowledge_item = base_schema.knowledge_item
knowledge_item.c.current_state.nullable = True
knowledge_item.c.promotion_batch_id.nullable = True
knowledge_item.append_column(
    sa.Column(
        "lifecycle_kind",
        sa.Text,
        server_default=sa.text("'EVIDENCE_BACKED'"),
        nullable=False,
        comment=(
            "EVIDENCE_BACKED는 기존 promotion·state·Evidence/publication 수명주기, "
            "PRODUCT_REFERENCE는 승인된 제품 reference Node 수명주기다."
        ),
    )
)
knowledge_item.append_constraint(
    sa.CheckConstraint(
        "lifecycle_kind IN ('EVIDENCE_BACKED', 'PRODUCT_REFERENCE')",
        name="ck_knowledge_item__lifecycle_kind",
    )
)
knowledge_item.append_constraint(
    sa.CheckConstraint(
        "(lifecycle_kind = 'EVIDENCE_BACKED' "
        "AND current_state IS NOT NULL AND promotion_batch_id IS NOT NULL) OR "
        "(lifecycle_kind = 'PRODUCT_REFERENCE' AND item_kind = 'NODE' "
        "AND current_state IS NULL AND promotion_batch_id IS NULL)",
        name="ck_knowledge_item__lifecycle_shape",
    )
)
knowledge_item.comment = (
    "node·relation·claim의 공유 ID와 수명주기를 관리하는 상위 엔터티. "
    "EVIDENCE_BACKED는 기존 state·promotion을 필수로 사용하고, "
    "PRODUCT_REFERENCE는 승인된 reference Node에만 제한한다."
)

_APPROVED_TOPIC_CHECK = " OR ".join(
    "(topic_code = '{code}' AND canonical_display_name = '{name}')".format(
        code=code,
        name=name.replace("'", "''"),
    )
    for code, name in APPROVED_TOPIC_DEFINITIONS
)

topic_reference = sa.Table(
    "topic_reference",
    base_schema.metadata,
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
        f"({_APPROVED_TOPIC_CHECK})",
        name="ck_topic_reference__approved_definition",
    ),
    comment=(
        "TOPIC Node identity에 연결된 제품 controlled vocabulary 정의. canonical "
        "이름과 active mapping 여부의 source of truth이며 Evidence가 아니다."
    ),
)
