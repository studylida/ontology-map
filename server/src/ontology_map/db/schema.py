import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData()

TIME_PRECISIONS = "'INSTANT', 'DAY', 'MONTH', 'YEAR', 'UNKNOWN'"
DATE_PRECISIONS = "'DAY', 'MONTH', 'YEAR', 'UNKNOWN'"
MODEL_TASK_KINDS = (
    "'KNOWLEDGE_EXTRACTION', 'ENTITY_RESOLUTION_PROPOSAL', "
    "'EVIDENCE_LINEAGE_PROPOSAL', 'CONFLICT_SUMMARY', 'NODE_CONTEXT', "
    "'FOLLOWUP_QUESTIONS', 'NODE_INSIGHT', 'EMBEDDING'"
)
OUTPUT_TASK_KINDS = (
    "'KNOWLEDGE_EXTRACTION', 'ENTITY_RESOLUTION_PROPOSAL', "
    "'EVIDENCE_LINEAGE_PROPOSAL', 'CONFLICT_SUMMARY', 'NODE_CONTEXT', "
    "'FOLLOWUP_QUESTIONS', 'NODE_INSIGHT'"
)


node_type = sa.Table(
    "node_type",
    metadata,
    sa.Column(
        "node_type_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("node_type_code", sa.Text, nullable=False),
    sa.Column("display_name", sa.Text, nullable=False),
    sa.Column("creation_rule", sa.Text, nullable=False),
    sa.Column("is_active", sa.Boolean, server_default=sa.text("false"), nullable=False),
    sa.PrimaryKeyConstraint("node_type_id", name="pk_node_type"),
    sa.UniqueConstraint("node_type_code", name="uq_node_type__code"),
    sa.CheckConstraint(
        "btrim(node_type_code) <> ''",
        name="ck_node_type__code_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(display_name) <> ''",
        name="ck_node_type__display_name_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(creation_rule) <> ''",
        name="ck_node_type__creation_rule_nonblank",
    ),
    comment=(
        "노드의 안정된 유형 코드와 생성 근거 규칙. is_active는 새 노드 생성 "
        "허용 여부이며 기존 노드의 공개 상태가 아니다."
    ),
)

relation_type = sa.Table(
    "relation_type",
    metadata,
    sa.Column(
        "relation_type_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("relation_code", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("relation_type_id", name="pk_relation_type"),
    sa.UniqueConstraint("relation_code", name="uq_relation_type__code"),
    sa.CheckConstraint(
        "btrim(relation_code) <> ''",
        name="ck_relation_type__code_nonblank",
    ),
    comment=(
        "관계 의미를 식별하는 안정된 코드 테이블. 활성 상태와 방향·endpoint "
        "규칙은 revision이 소유한다."
    ),
)

attribute = sa.Table(
    "attribute",
    metadata,
    sa.Column(
        "attribute_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("attribute_code", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("attribute_id", name="pk_attribute"),
    sa.UniqueConstraint("attribute_code", name="uq_attribute__code"),
    sa.CheckConstraint(
        "btrim(attribute_code) <> ''",
        name="ck_attribute__code_nonblank",
    ),
    comment=(
        "구조화된 Claim 속성의 안정된 코드 테이블. 실제 값과 사용 규칙은 "
        "attribute_revision과 claim_attribute_value가 소유한다."
    ),
)

output_schema_definition = sa.Table(
    "output_schema_definition",
    metadata,
    sa.Column(
        "output_schema_definition_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("task_kind", sa.Text, nullable=False),
    sa.Column("version_no", sa.Integer, nullable=False),
    sa.Column("schema_json", JSONB, nullable=False),
    sa.Column("is_active", sa.Boolean, server_default=sa.text("false"), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint(
        "output_schema_definition_id",
        name="pk_output_schema_definition",
    ),
    sa.UniqueConstraint(
        "task_kind",
        "version_no",
        name="uq_output_schema_definition__version",
    ),
    sa.CheckConstraint(
        "version_no >= 1",
        name="ck_output_schema_definition__version_positive",
    ),
    sa.CheckConstraint(
        "jsonb_typeof(schema_json) = 'object'",
        name="ck_output_schema_definition__schema_object",
    ),
    sa.CheckConstraint(
        f"task_kind IN ({OUTPUT_TASK_KINDS})",
        name="ck_output_schema_definition__task_kind",
    ),
    sa.CheckConstraint(
        "isfinite(created_at)",
        name="ck_output_schema_definition__created_at_finite",
    ),
    comment=(
        "모델이 반환해야 할 JSON Schema 계약의 불변 버전. 응답 인스턴스나 "
        "provider 원문을 저장하지 않는다."
    ),
)
sa.Index(
    "uq_output_schema_definition__active",
    output_schema_definition.c.task_kind,
    unique=True,
    postgresql_where=output_schema_definition.c.is_active,
)

lint_rule = sa.Table(
    "lint_rule",
    metadata,
    sa.Column(
        "lint_rule_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("rule_code", sa.Text, nullable=False),
    sa.Column("display_name", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("evaluation_scope", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("lint_rule_id", name="pk_lint_rule"),
    sa.UniqueConstraint("rule_code", name="uq_lint_rule__code"),
    sa.CheckConstraint("btrim(rule_code) <> ''", name="ck_lint_rule__code_nonblank"),
    sa.CheckConstraint(
        "btrim(display_name) <> ''",
        name="ck_lint_rule__display_name_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(description) <> ''",
        name="ck_lint_rule__description_nonblank",
    ),
    sa.CheckConstraint(
        "evaluation_scope IN ('PRE_PROMOTION', 'PERSISTED_GRAPH', 'BOTH')",
        name="ck_lint_rule__evaluation_scope",
    ),
    comment=(
        "안정된 lint 규칙 정의와 평가 범위. 정책별 사용 여부와 "
        "BLOCKING/WARNING 심각도는 lint_policy_rule이 소유한다."
    ),
)

lint_policy_version = sa.Table(
    "lint_policy_version",
    metadata,
    sa.Column(
        "lint_policy_version_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("version_no", sa.Integer, nullable=False),
    sa.Column("validator_version", sa.Text, nullable=False),
    sa.Column("is_active", sa.Boolean, server_default=sa.text("false"), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.Column("activated_at", sa.DateTime(timezone=True)),
    sa.PrimaryKeyConstraint(
        "lint_policy_version_id",
        name="pk_lint_policy_version",
    ),
    sa.UniqueConstraint("version_no", name="uq_lint_policy_version__number"),
    sa.CheckConstraint(
        "version_no >= 1",
        name="ck_lint_policy_version__version_positive",
    ),
    sa.CheckConstraint(
        "btrim(validator_version) <> ''",
        name="ck_lint_policy_version__validator_nonblank",
    ),
    sa.CheckConstraint(
        "isfinite(created_at) AND (activated_at IS NULL OR isfinite(activated_at))",
        name="ck_lint_policy_version__timestamps_finite",
    ),
    sa.CheckConstraint(
        "NOT is_active OR activated_at IS NOT NULL",
        name="ck_lint_policy_version__active_timestamp",
    ),
    comment=("판정 결과에 영향을 주는 validator와 규칙 선택의 불변 정책 버전."),
)
sa.Index(
    "uq_lint_policy_version__active",
    sa.literal_column("(true)"),
    unique=True,
    postgresql_where=lint_policy_version.c.is_active,
)

relation_type_revision = sa.Table(
    "relation_type_revision",
    metadata,
    sa.Column(
        "relation_type_revision_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "relation_type_id",
        sa.BigInteger,
        sa.ForeignKey(
            "relation_type.relation_type_id",
            name="fk_relation_type_revision__relation_type",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("version_no", sa.Integer, nullable=False),
    sa.Column("display_name", sa.Text, nullable=False),
    sa.Column("directionality", sa.Text, nullable=False),
    sa.Column(
        "inverse_relation_type_revision_id",
        sa.BigInteger,
        sa.ForeignKey(
            "relation_type_revision.relation_type_revision_id",
            name="fk_relation_type_revision__inverse",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    ),
    sa.Column(
        "is_active",
        sa.Boolean,
        server_default=sa.text("false"),
        nullable=False,
        comment=(
            "새 관계를 생성할 때 사용할 수 있는 exact revision인지 표시한다. "
            "기존 관계를 숨기거나 재해석하지 않는다."
        ),
    ),
    sa.PrimaryKeyConstraint(
        "relation_type_revision_id",
        name="pk_relation_type_revision",
    ),
    sa.UniqueConstraint(
        "relation_type_id",
        "version_no",
        name="uq_relation_type_revision__version",
    ),
    sa.CheckConstraint(
        "version_no >= 1",
        name="ck_relation_type_revision__version_positive",
    ),
    sa.CheckConstraint(
        "btrim(display_name) <> ''",
        name="ck_relation_type_revision__display_name_nonblank",
    ),
    sa.CheckConstraint(
        "directionality IN ('DIRECTED', 'SYMMETRIC')",
        name="ck_relation_type_revision__directionality",
    ),
    sa.CheckConstraint(
        "inverse_relation_type_revision_id IS NULL OR "
        "inverse_relation_type_revision_id <> relation_type_revision_id",
        name="ck_relation_type_revision__not_self_inverse",
    ),
    sa.CheckConstraint(
        "directionality <> 'SYMMETRIC' OR inverse_relation_type_revision_id IS NULL",
        name="ck_relation_type_revision__symmetric_inverse",
    ),
    comment=(
        "관계 표시·방향·inverse 계약의 불변 버전. 비활성화는 기존 관계를 숨기지 않는다."
    ),
)
sa.Index(
    "uq_relation_type_revision__active",
    relation_type_revision.c.relation_type_id,
    unique=True,
    postgresql_where=relation_type_revision.c.is_active,
)
sa.Index(
    "ix_relation_type_revision__inverse",
    relation_type_revision.c.inverse_relation_type_revision_id,
    postgresql_where=relation_type_revision.c.inverse_relation_type_revision_id.is_not(
        None
    ),
)

relation_endpoint_rule = sa.Table(
    "relation_endpoint_rule",
    metadata,
    sa.Column(
        "relation_type_revision_id",
        sa.BigInteger,
        sa.ForeignKey(
            "relation_type_revision.relation_type_revision_id",
            name="fk_relation_endpoint_rule__revision",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "source_node_type_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node_type.node_type_id",
            name="fk_relation_endpoint_rule__source_type",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "target_node_type_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node_type.node_type_id",
            name="fk_relation_endpoint_rule__target_type",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint(
        "relation_type_revision_id",
        "source_node_type_id",
        "target_node_type_id",
        name="pk_relation_endpoint_rule",
    ),
    comment=(
        "관계 revision이 허용하는 시작·도착 node type 쌍. 실제 관계 endpoint "
        "검증은 승격 서비스가 수행한다."
    ),
)

attribute_revision = sa.Table(
    "attribute_revision",
    metadata,
    sa.Column(
        "attribute_revision_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "attribute_id",
        sa.BigInteger,
        sa.ForeignKey(
            "attribute.attribute_id",
            name="fk_attribute_revision__attribute",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("version_no", sa.Integer, nullable=False),
    sa.Column("display_name", sa.Text, nullable=False),
    sa.Column(
        "target_node_type_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node_type.node_type_id",
            name="fk_attribute_revision__target_type",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("allowed_value_kind", sa.Text, nullable=False),
    sa.Column(
        "unit_rule",
        sa.Text,
        comment=(
            "NUMBER revision이 허용하는 canonical 단위 code 하나. 자동 단위 "
            "환산 규칙이나 표시 문자열 목록이 아니다."
        ),
    ),
    sa.Column("is_active", sa.Boolean, server_default=sa.text("false"), nullable=False),
    sa.PrimaryKeyConstraint(
        "attribute_revision_id",
        name="pk_attribute_revision",
    ),
    sa.UniqueConstraint(
        "attribute_id",
        "version_no",
        name="uq_attribute_revision__version",
    ),
    sa.UniqueConstraint(
        "attribute_revision_id",
        "allowed_value_kind",
        name="uq_attribute_revision__kind",
    ),
    sa.CheckConstraint(
        "version_no >= 1",
        name="ck_attribute_revision__version_positive",
    ),
    sa.CheckConstraint(
        "btrim(display_name) <> ''",
        name="ck_attribute_revision__display_name_nonblank",
    ),
    sa.CheckConstraint(
        "allowed_value_kind IN ('STRING', 'NUMBER', 'DATE', 'PERIOD', 'BOOLEAN')",
        name="ck_attribute_revision__value_kind",
    ),
    sa.CheckConstraint(
        "(allowed_value_kind = 'NUMBER' AND unit_rule IS NOT NULL AND "
        "btrim(unit_rule) <> '') OR "
        "(allowed_value_kind <> 'NUMBER' AND unit_rule IS NULL)",
        name="ck_attribute_revision__unit_rule",
    ),
    comment=("속성의 대상 유형·값 종류·canonical 단위를 보존하는 불변 규칙 버전."),
)
sa.Index(
    "uq_attribute_revision__active",
    attribute_revision.c.attribute_id,
    unique=True,
    postgresql_where=attribute_revision.c.is_active,
)
sa.Index(
    "ix_attribute_revision__target_type",
    attribute_revision.c.target_node_type_id,
    attribute_revision.c.attribute_revision_id,
)

lint_policy_rule = sa.Table(
    "lint_policy_rule",
    metadata,
    sa.Column(
        "lint_policy_rule_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "lint_policy_version_id",
        sa.BigInteger,
        sa.ForeignKey(
            "lint_policy_version.lint_policy_version_id",
            name="fk_lint_policy_rule__policy",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "lint_rule_id",
        sa.BigInteger,
        sa.ForeignKey(
            "lint_rule.lint_rule_id",
            name="fk_lint_policy_rule__rule",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("severity", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("lint_policy_rule_id", name="pk_lint_policy_rule"),
    sa.UniqueConstraint(
        "lint_policy_version_id",
        "lint_rule_id",
        name="uq_lint_policy_rule__selection",
    ),
    sa.CheckConstraint(
        "severity IN ('BLOCKING', 'WARNING')",
        name="ck_lint_policy_rule__severity",
    ),
    comment=("한 lint policy가 선택한 stable rule과 해당 심각도의 불변 연결."),
)
sa.Index(
    "ix_lint_policy_rule__rule",
    lint_policy_rule.c.lint_rule_id,
    lint_policy_rule.c.lint_policy_version_id,
)

evidence_group = sa.Table(
    "evidence_group",
    metadata,
    sa.Column(
        "evidence_group_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint("evidence_group_id", name="pk_evidence_group"),
    sa.CheckConstraint(
        "isfinite(created_at)",
        name="ck_evidence_group__created_at_finite",
    ),
    comment=(
        "같은 원문 계보로 판단된 문서를 독립 근거 하나로 세기 위한 최소 묶음. "
        "출처 신뢰도나 사실의 진실성을 뜻하지 않는다."
    ),
)

source_document = sa.Table(
    "source_document",
    metadata,
    sa.Column(
        "source_document_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "evidence_group_id",
        sa.BigInteger,
        sa.ForeignKey(
            "evidence_group.evidence_group_id",
            name="fk_source_document__evidence_group",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
        comment=(
            "현재 독립 근거 계보 묶음. 재배정 이력은 보존하지 않으며 승인된 "
            "정정 경로만 수정할 수 있다."
        ),
    ),
    sa.Column("source_key", sa.Text, nullable=False),
    sa.Column("version_no", sa.Integer, nullable=False),
    sa.Column("canonical_url", sa.Text, nullable=False),
    sa.Column("publisher_name", sa.Text, nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("author_text", sa.Text),
    sa.Column("original_language", sa.Text, nullable=False),
    sa.Column("normalized_body", sa.Text, nullable=False),
    sa.Column(
        "body_hash",
        sa.LargeBinary,
        nullable=False,
        comment=(
            "normalized_body의 UTF-8 바이트 SHA-256. 문서 행을 합치는 키가 "
            "아니라 정확한 본문 복제 후보와 근거 묶음 판정에 사용한다."
        ),
    ),
    sa.Column("published_at", sa.DateTime(timezone=True)),
    sa.Column("published_precision", sa.Text, nullable=False),
    sa.Column("source_modified_at", sa.DateTime(timezone=True)),
    sa.Column("modified_precision", sa.Text, nullable=False),
    sa.Column(
        "last_checked_at",
        sa.DateTime(timezone=True),
        nullable=False,
        comment=(
            "준비 레이어가 같은 자료를 마지막으로 확인한 시점. 출처 게시 "
            "시점이나 노드 활동량 계산 시점이 아니다."
        ),
    ),
    sa.Column("last_check_status", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint("source_document_id", name="pk_source_document"),
    sa.UniqueConstraint(
        "source_key",
        "version_no",
        name="uq_source_document__version",
    ),
    sa.CheckConstraint(
        "version_no >= 1",
        name="ck_source_document__version_positive",
    ),
    sa.CheckConstraint(
        "btrim(source_key) <> ''",
        name="ck_source_document__source_key_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(canonical_url) <> ''",
        name="ck_source_document__url_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(publisher_name) <> ''",
        name="ck_source_document__publisher_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(title) <> ''",
        name="ck_source_document__title_nonblank",
    ),
    sa.CheckConstraint(
        "author_text IS NULL OR btrim(author_text) <> ''",
        name="ck_source_document__author_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(original_language) <> ''",
        name="ck_source_document__language_nonblank",
    ),
    sa.CheckConstraint(
        "char_length(normalized_body) > 0",
        name="ck_source_document__body_nonempty",
    ),
    sa.CheckConstraint(
        "octet_length(body_hash) = 32",
        name="ck_source_document__body_hash_length",
    ),
    sa.CheckConstraint(
        f"published_precision IN ({TIME_PRECISIONS})",
        name="ck_source_document__published_precision",
    ),
    sa.CheckConstraint(
        f"modified_precision IN ({TIME_PRECISIONS})",
        name="ck_source_document__modified_precision",
    ),
    sa.CheckConstraint(
        "(published_at IS NULL AND published_precision = 'UNKNOWN') OR "
        "(published_at IS NOT NULL AND published_precision <> 'UNKNOWN')",
        name="ck_source_document__published_value_precision",
    ),
    sa.CheckConstraint(
        "(source_modified_at IS NULL AND modified_precision = 'UNKNOWN') OR "
        "(source_modified_at IS NOT NULL AND modified_precision <> 'UNKNOWN')",
        name="ck_source_document__modified_value_precision",
    ),
    sa.CheckConstraint(
        "(published_at IS NULL OR isfinite(published_at)) AND "
        "(source_modified_at IS NULL OR isfinite(source_modified_at)) AND "
        "isfinite(last_checked_at) AND isfinite(created_at)",
        name="ck_source_document__timestamps_finite",
    ),
    sa.CheckConstraint(
        "last_check_status IN ('SUCCESS', 'FAILED')",
        name="ck_source_document__last_check_status",
    ),
    comment=(
        "제품 밖에서 준비한 정규화 문서의 불변 버전. 발견·GDELT·크롤링·HTML·"
        "HTTP 시도는 저장하지 않는다."
    ),
)
sa.Index("ix_source_document__body_hash", source_document.c.body_hash)
sa.Index(
    "ix_source_document__evidence_group",
    source_document.c.evidence_group_id,
    source_document.c.source_document_id,
)

observation = sa.Table(
    "observation",
    metadata,
    sa.Column(
        "observation_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "source_document_id",
        sa.BigInteger,
        sa.ForeignKey(
            "source_document.source_document_id",
            name="fk_observation__source_document",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("start_char", sa.Integer, nullable=False),
    sa.Column("end_char", sa.Integer, nullable=False),
    sa.Column("quote_text", sa.Text, nullable=False),
    sa.Column("quote_hash", sa.LargeBinary, nullable=False),
    sa.Column("paragraph_number", sa.Integer),
    sa.Column(
        "observed_at",
        sa.DateTime(timezone=True),
        nullable=False,
        comment=(
            "시스템이 원문 범위를 근거로 식별한 시점. 출처 게시 시점이나 "
            "노드 활동량 계산 시점이 아니다."
        ),
    ),
    sa.PrimaryKeyConstraint("observation_id", name="pk_observation"),
    sa.UniqueConstraint(
        "source_document_id",
        "start_char",
        "end_char",
        name="uq_observation__document_range",
    ),
    sa.CheckConstraint("start_char >= 0", name="ck_observation__start_nonnegative"),
    sa.CheckConstraint("end_char > start_char", name="ck_observation__range"),
    sa.CheckConstraint(
        "char_length(quote_text) = end_char - start_char",
        name="ck_observation__quote_length",
    ),
    sa.CheckConstraint(
        "octet_length(quote_hash) = 32",
        name="ck_observation__quote_hash_length",
    ),
    sa.CheckConstraint(
        "paragraph_number IS NULL OR paragraph_number >= 1",
        name="ck_observation__paragraph_positive",
    ),
    sa.CheckConstraint(
        "isfinite(observed_at)",
        name="ck_observation__observed_at_finite",
    ),
    comment=(
        "불변 source_document의 정확한 Unicode 문자 범위에서 근거를 식별한 "
        "기록. 출처의 발화를 증명하지만 객관적 진실을 증명하지 않는다."
    ),
)

model_task = sa.Table(
    "model_task",
    metadata,
    sa.Column(
        "model_task_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("task_kind", sa.Text, nullable=False),
    sa.Column(
        "source_document_id",
        sa.BigInteger,
        sa.ForeignKey(
            "source_document.source_document_id",
            name="fk_model_task__source_document",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    ),
    sa.Column("input_hash", sa.LargeBinary, nullable=False),
    sa.Column(
        "output_schema_definition_id",
        sa.BigInteger,
        sa.ForeignKey(
            "output_schema_definition.output_schema_definition_id",
            name="fk_model_task__output_contract",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    ),
    sa.Column("model_version", sa.Text, nullable=False),
    sa.Column("prompt_version", sa.Text),
    sa.Column("cache_key", sa.LargeBinary, nullable=False),
    sa.Column(
        "status",
        sa.Text,
        server_default=sa.text("'PENDING'"),
        nullable=False,
    ),
    sa.Column(
        "attempt_count",
        sa.Integer,
        server_default=sa.text("0"),
        nullable=False,
        comment=(
            "이 논리 작업에서 실제 provider를 호출한 누계. cache 적중은 증가시키지 "
            "않으며 agent_attempt 행과 같은 트랜잭션에서 유지한다."
        ),
    ),
    sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
    sa.Column("lease_owner", sa.Text),
    sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.Column("finished_at", sa.DateTime(timezone=True)),
    sa.PrimaryKeyConstraint("model_task_id", name="pk_model_task"),
    sa.UniqueConstraint("cache_key", name="uq_model_task__cache_key"),
    sa.CheckConstraint(
        f"task_kind IN ({MODEL_TASK_KINDS})",
        name="ck_model_task__task_kind",
    ),
    sa.CheckConstraint(
        "status IN ('PENDING', 'RUNNING', 'SUCCESS', 'RETRY_WAIT', "
        "'VALIDATION_BLOCKED', 'FINAL_FAILED')",
        name="ck_model_task__status",
    ),
    sa.CheckConstraint(
        "octet_length(input_hash) = 32",
        name="ck_model_task__input_hash_length",
    ),
    sa.CheckConstraint(
        "octet_length(cache_key) = 32",
        name="ck_model_task__cache_key_length",
    ),
    sa.CheckConstraint(
        "btrim(model_version) <> ''",
        name="ck_model_task__model_version_nonblank",
    ),
    sa.CheckConstraint(
        "prompt_version IS NULL OR btrim(prompt_version) <> ''",
        name="ck_model_task__prompt_version_nonblank",
    ),
    sa.CheckConstraint(
        "attempt_count BETWEEN 0 AND 5",
        name="ck_model_task__attempt_count",
    ),
    sa.CheckConstraint(
        "(task_kind = 'EMBEDDING' AND output_schema_definition_id IS NULL "
        "AND prompt_version IS NULL) OR "
        "(task_kind <> 'EMBEDDING' AND output_schema_definition_id IS NOT NULL "
        "AND prompt_version IS NOT NULL)",
        name="ck_model_task__output_contract",
    ),
    sa.CheckConstraint(
        "lease_owner IS NULL OR btrim(lease_owner) <> ''",
        name="ck_model_task__lease_owner_nonblank",
    ),
    sa.CheckConstraint(
        "isfinite(created_at) AND "
        "(next_attempt_at IS NULL OR isfinite(next_attempt_at)) AND "
        "(lease_expires_at IS NULL OR isfinite(lease_expires_at)) AND "
        "(finished_at IS NULL OR isfinite(finished_at))",
        name="ck_model_task__timestamps_finite",
    ),
    sa.CheckConstraint(
        "(status = 'PENDING' AND finished_at IS NULL AND next_attempt_at IS NULL "
        "AND lease_owner IS NULL AND lease_expires_at IS NULL) OR "
        "(status = 'RUNNING' AND finished_at IS NULL AND next_attempt_at IS NULL "
        "AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
        "(status = 'RETRY_WAIT' AND finished_at IS NULL "
        "AND next_attempt_at IS NOT NULL AND lease_owner IS NULL "
        "AND lease_expires_at IS NULL AND attempt_count < 5) OR "
        "(status IN ('SUCCESS', 'VALIDATION_BLOCKED', 'FINAL_FAILED') "
        "AND finished_at IS NOT NULL AND next_attempt_at IS NULL "
        "AND lease_owner IS NULL AND lease_expires_at IS NULL)",
        name="ck_model_task__status_shape",
    ),
    comment=(
        "재시도 전체를 묶는 논리 모델 작업. 실제 호출 누계와 현재 실행 상태를 "
        "소유하며 모델 응답 payload를 저장하지 않는다."
    ),
)
sa.Index(
    "ix_model_task__runnable",
    model_task.c.status,
    model_task.c.next_attempt_at,
    model_task.c.created_at,
    model_task.c.model_task_id,
    postgresql_where=model_task.c.status.in_(("PENDING", "RETRY_WAIT")),
)
sa.Index(
    "ix_model_task__expired_lease",
    model_task.c.lease_expires_at,
    model_task.c.model_task_id,
    postgresql_where=model_task.c.status == "RUNNING",
)
sa.Index(
    "ix_model_task__source_document",
    model_task.c.source_document_id,
    model_task.c.model_task_id,
    postgresql_where=model_task.c.source_document_id.is_not(None),
)
sa.Index(
    "ix_model_task__contract",
    model_task.c.output_schema_definition_id,
    model_task.c.model_task_id,
)

agent_attempt = sa.Table(
    "agent_attempt",
    metadata,
    sa.Column(
        "agent_attempt_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "model_task_id",
        sa.BigInteger,
        sa.ForeignKey(
            "model_task.model_task_id",
            name="fk_agent_attempt__model_task",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("attempt_no", sa.Integer, nullable=False),
    sa.Column("outcome", sa.Text, nullable=False),
    sa.Column("failure_reason", sa.Text),
    sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("agent_attempt_id", name="pk_agent_attempt"),
    sa.UniqueConstraint(
        "model_task_id",
        "attempt_no",
        name="uq_agent_attempt__number",
    ),
    sa.CheckConstraint(
        "attempt_no BETWEEN 1 AND 5",
        name="ck_agent_attempt__attempt_no",
    ),
    sa.CheckConstraint(
        "outcome IN ('SUCCESS', 'TIMEOUT', 'RATE_LIMITED', 'PROVIDER_ERROR', "
        "'AUTHENTICATION_ERROR', 'INVALID_REQUEST', 'OUTPUT_CONTRACT_ERROR')",
        name="ck_agent_attempt__outcome",
    ),
    sa.CheckConstraint(
        "(outcome = 'SUCCESS' AND failure_reason IS NULL) OR "
        "(outcome <> 'SUCCESS' AND failure_reason IS NOT NULL "
        "AND btrim(failure_reason) <> '')",
        name="ck_agent_attempt__failure_reason",
    ),
    sa.CheckConstraint(
        "isfinite(attempted_at)",
        name="ck_agent_attempt__attempted_at_finite",
    ),
    comment=(
        "한 논리 모델 작업의 실제 provider 호출 한 번을 기록하는 append-only 이력."
    ),
)

blocked_fingerprint = sa.Table(
    "blocked_fingerprint",
    metadata,
    sa.Column(
        "blocked_fingerprint_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("fingerprint", sa.LargeBinary, nullable=False),
    sa.Column(
        "source_document_id",
        sa.BigInteger,
        sa.ForeignKey(
            "source_document.source_document_id",
            name="fk_blocked_fingerprint__source_document",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "output_schema_definition_id",
        sa.BigInteger,
        sa.ForeignKey(
            "output_schema_definition.output_schema_definition_id",
            name="fk_blocked_fingerprint__output_contract",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "lint_policy_rule_id",
        sa.BigInteger,
        sa.ForeignKey(
            "lint_policy_rule.lint_policy_rule_id",
            name="fk_blocked_fingerprint__policy_rule",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("first_blocked_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_blocked_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        "blocked_count",
        sa.Integer,
        server_default=sa.text("1"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint(
        "blocked_fingerprint_id",
        name="pk_blocked_fingerprint",
    ),
    sa.UniqueConstraint(
        "fingerprint",
        "source_document_id",
        "output_schema_definition_id",
        "lint_policy_rule_id",
        name="uq_blocked_fingerprint__identity",
    ),
    sa.CheckConstraint(
        "octet_length(fingerprint) = 32",
        name="ck_blocked_fingerprint__length",
    ),
    sa.CheckConstraint(
        "blocked_count >= 1",
        name="ck_blocked_fingerprint__count_positive",
    ),
    sa.CheckConstraint(
        "isfinite(first_blocked_at) AND isfinite(last_blocked_at) "
        "AND last_blocked_at >= first_blocked_at",
        name="ck_blocked_fingerprint__timestamps",
    ),
    comment=(
        "후보 payload를 저장하지 않고 같은 차단 후보의 반복 검증·승격을 억제한다."
    ),
)
sa.Index(
    "ix_blocked_fingerprint__source",
    blocked_fingerprint.c.source_document_id,
    blocked_fingerprint.c.last_blocked_at.desc(),
)
sa.Index(
    "ix_blocked_fingerprint__policy_rule",
    blocked_fingerprint.c.lint_policy_rule_id,
    blocked_fingerprint.c.last_blocked_at.desc(),
)

promotion_batch = sa.Table(
    "promotion_batch",
    metadata,
    sa.Column(
        "promotion_batch_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "lint_policy_version_id",
        sa.BigInteger,
        sa.ForeignKey(
            "lint_policy_version.lint_policy_version_id",
            name="fk_promotion_batch__lint_policy_version",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "promotion_status",
        sa.Text,
        server_default=sa.text("'PENDING'"),
        nullable=False,
    ),
    sa.Column(
        "publication_status",
        sa.Text,
        server_default=sa.text("'NOT_STARTED'"),
        nullable=False,
        comment=(
            "검색 문서·임베딩·맥락·질문·인사이트의 공개 준비 상태. 기준 그래프 "
            "저장 결과인 promotion_status와 별개다."
        ),
    ),
    sa.Column(
        "started_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.Column("committed_at", sa.DateTime(timezone=True)),
    sa.Column("ready_at", sa.DateTime(timezone=True)),
    sa.Column("promotion_failure_reason", sa.Text),
    sa.Column("publication_failure_reason", sa.Text),
    sa.PrimaryKeyConstraint("promotion_batch_id", name="pk_promotion_batch"),
    sa.CheckConstraint(
        "promotion_status IN ('PENDING', 'COMMITTED', 'FAILED')",
        name="ck_promotion_batch__promotion_status",
    ),
    sa.CheckConstraint(
        "publication_status IN ('NOT_STARTED', 'PREPARING', 'READY', 'FAILED')",
        name="ck_promotion_batch__publication_status",
    ),
    sa.CheckConstraint(
        "isfinite(started_at) AND "
        "(committed_at IS NULL OR isfinite(committed_at)) AND "
        "(ready_at IS NULL OR isfinite(ready_at))",
        name="ck_promotion_batch__timestamps_finite",
    ),
    sa.CheckConstraint(
        "committed_at IS NULL OR committed_at >= started_at",
        name="ck_promotion_batch__committed_order",
    ),
    sa.CheckConstraint(
        "ready_at IS NULL OR (committed_at IS NOT NULL AND ready_at >= committed_at)",
        name="ck_promotion_batch__ready_order",
    ),
    sa.CheckConstraint(
        "promotion_failure_reason IS NULL OR btrim(promotion_failure_reason) <> ''",
        name="ck_promotion_batch__promotion_failure_nonblank",
    ),
    sa.CheckConstraint(
        "publication_failure_reason IS NULL OR btrim(publication_failure_reason) <> ''",
        name="ck_promotion_batch__publication_failure_nonblank",
    ),
    sa.CheckConstraint(
        "(promotion_status = 'PENDING' AND publication_status = 'NOT_STARTED' "
        "AND committed_at IS NULL AND ready_at IS NULL "
        "AND promotion_failure_reason IS NULL "
        "AND publication_failure_reason IS NULL) OR "
        "(promotion_status = 'FAILED' AND publication_status = 'NOT_STARTED' "
        "AND committed_at IS NULL AND ready_at IS NULL "
        "AND promotion_failure_reason IS NOT NULL "
        "AND publication_failure_reason IS NULL) OR "
        "(promotion_status = 'COMMITTED' AND publication_status = 'NOT_STARTED' "
        "AND committed_at IS NOT NULL AND ready_at IS NULL "
        "AND promotion_failure_reason IS NULL "
        "AND publication_failure_reason IS NULL) OR "
        "(promotion_status = 'COMMITTED' AND publication_status = 'PREPARING' "
        "AND committed_at IS NOT NULL AND ready_at IS NULL "
        "AND promotion_failure_reason IS NULL "
        "AND publication_failure_reason IS NULL) OR "
        "(promotion_status = 'COMMITTED' AND publication_status = 'FAILED' "
        "AND committed_at IS NOT NULL AND ready_at IS NULL "
        "AND promotion_failure_reason IS NULL "
        "AND publication_failure_reason IS NOT NULL) OR "
        "(promotion_status = 'COMMITTED' AND publication_status = 'READY' "
        "AND committed_at IS NOT NULL AND ready_at IS NOT NULL "
        "AND promotion_failure_reason IS NULL "
        "AND publication_failure_reason IS NULL)",
        name="ck_promotion_batch__state_shape",
    ),
    comment=(
        "기준 지식의 원자 승격 결과와 그 변경의 공개 준비 상태를 분리해 관리한다. "
        "전체 활성 온톨로지 snapshot이나 지도 버전을 저장하지 않는다."
    ),
)
sa.Index(
    "ix_promotion_batch__promotion_pending",
    promotion_batch.c.started_at,
    promotion_batch.c.promotion_batch_id,
    postgresql_where=promotion_batch.c.promotion_status == "PENDING",
)
sa.Index(
    "ix_promotion_batch__publication_work",
    promotion_batch.c.publication_status,
    promotion_batch.c.promotion_batch_id,
    postgresql_where=sa.and_(
        promotion_batch.c.promotion_status == "COMMITTED",
        promotion_batch.c.publication_status.in_(
            ("NOT_STARTED", "PREPARING", "FAILED")
        ),
    ),
)
sa.Index(
    "ix_promotion_batch__ready",
    promotion_batch.c.ready_at.desc(),
    promotion_batch.c.promotion_batch_id.desc(),
    postgresql_where=sa.and_(
        promotion_batch.c.promotion_status == "COMMITTED",
        promotion_batch.c.publication_status == "READY",
    ),
)

knowledge_item = sa.Table(
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
        "current_state",
        sa.Text,
        nullable=False,
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
        nullable=False,
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
        "current_state IN "
        "('EVIDENCE_VERIFIED', 'HUMAN_VERIFIED', 'ON_HOLD', 'REJECTED')",
        name="ck_knowledge_item__current_state",
    ),
    sa.CheckConstraint(
        "isfinite(created_at)",
        name="ck_knowledge_item__created_at_finite",
    ),
    comment=(
        "node·relation·claim의 공유 ID, 현재 지식 상태와 생성 batch를 관리하는 "
        "상위 엔터티. 정확히 한 subtype은 승격 서비스가 커밋 전에 검증한다."
    ),
)
sa.Index(
    "ix_knowledge_item__promotion_batch",
    knowledge_item.c.promotion_batch_id,
    knowledge_item.c.knowledge_item_id,
)

node = sa.Table(
    "node",
    metadata,
    sa.Column(
        "node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "knowledge_item.knowledge_item_id",
            name="fk_node__knowledge_item",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "node_type_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node_type.node_type_id",
            name="fk_node__node_type",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint("node_id", name="pk_node"),
    comment=(
        "지식그래프 대상의 불변 정체성과 안정된 node type만 저장하는 "
        "knowledge_item subtype. 이름과 세부 사실을 직접 저장하지 않는다."
    ),
)
sa.Index("ix_node__type", node.c.node_type_id, node.c.node_id)

relation = sa.Table(
    "relation",
    metadata,
    sa.Column(
        "relation_id",
        sa.BigInteger,
        sa.ForeignKey(
            "knowledge_item.knowledge_item_id",
            name="fk_relation__knowledge_item",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "source_node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_relation__source_node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "target_node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_relation__target_node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "relation_type_revision_id",
        sa.BigInteger,
        sa.ForeignKey(
            "relation_type_revision.relation_type_revision_id",
            name="fk_relation__type_revision",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("relation_identity_key", sa.LargeBinary, nullable=False),
    sa.PrimaryKeyConstraint("relation_id", name="pk_relation"),
    sa.UniqueConstraint("relation_identity_key", name="uq_relation__identity"),
    sa.CheckConstraint(
        "octet_length(relation_identity_key) = 32",
        name="ck_relation__identity_length",
    ),
    comment=(
        "정확한 relation revision으로 두 node를 연결하는 기준 연결. 출처·사건 "
        "맥락·유효 기간은 직접 저장하지 않고 Claim과 명시적 사건 endpoint로 표현한다."
    ),
)
sa.Index(
    "ix_relation__source",
    relation.c.source_node_id,
    relation.c.relation_type_revision_id,
    relation.c.target_node_id,
)
sa.Index(
    "ix_relation__target",
    relation.c.target_node_id,
    relation.c.relation_type_revision_id,
    relation.c.source_node_id,
)

claim = sa.Table(
    "claim",
    metadata,
    sa.Column(
        "claim_id",
        sa.BigInteger,
        sa.ForeignKey(
            "knowledge_item.knowledge_item_id",
            name="fk_claim__knowledge_item",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("statement_text", sa.Text, nullable=False),
    sa.Column("language", sa.Text, nullable=False),
    sa.Column(
        "modality",
        sa.Text,
        nullable=False,
        comment=(
            "원문 표현이 사실 주장, 계획·목표, 예측·추정, 의견·평가 중 무엇인지 "
            "나타낸다. PLAN_OR_TARGET 값을 확정 사실로 표시해서는 안 된다."
        ),
    ),
    sa.Column("asserted_from", sa.DateTime(timezone=True)),
    sa.Column("asserted_to", sa.DateTime(timezone=True)),
    sa.Column("asserted_from_precision", sa.Text, nullable=False),
    sa.Column("asserted_to_precision", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("claim_id", name="pk_claim"),
    sa.CheckConstraint(
        "btrim(statement_text) <> ''",
        name="ck_claim__statement_nonblank",
    ),
    sa.CheckConstraint("btrim(language) <> ''", name="ck_claim__language_nonblank"),
    sa.CheckConstraint(
        "modality IN ('FACT', 'PLAN_OR_TARGET', 'PREDICTION_OR_ESTIMATE', "
        "'OPINION_OR_EVALUATION')",
        name="ck_claim__modality",
    ),
    sa.CheckConstraint(
        f"asserted_from_precision IN ({TIME_PRECISIONS})",
        name="ck_claim__from_precision",
    ),
    sa.CheckConstraint(
        f"asserted_to_precision IN ({TIME_PRECISIONS})",
        name="ck_claim__to_precision",
    ),
    sa.CheckConstraint(
        "(asserted_from IS NULL AND asserted_from_precision = 'UNKNOWN') OR "
        "(asserted_from IS NOT NULL AND asserted_from_precision <> 'UNKNOWN')",
        name="ck_claim__from_value_precision",
    ),
    sa.CheckConstraint(
        "(asserted_to IS NULL AND asserted_to_precision = 'UNKNOWN') OR "
        "(asserted_to IS NOT NULL AND asserted_to_precision <> 'UNKNOWN')",
        name="ck_claim__to_value_precision",
    ),
    sa.CheckConstraint(
        "(asserted_from IS NULL OR isfinite(asserted_from)) AND "
        "(asserted_to IS NULL OR isfinite(asserted_to))",
        name="ck_claim__timestamps_finite",
    ),
    comment=(
        "출처가 주장한 원자 문장과 표현 성격·주장 시간을 보존하는 불변 "
        "knowledge_item subtype."
    ),
)

node_alias = sa.Table(
    "node_alias",
    metadata,
    sa.Column(
        "node_alias_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_node_alias__node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("alias_text", sa.Text, nullable=False),
    sa.Column("language", sa.Text, nullable=False),
    sa.Column(
        "is_preferred",
        sa.Boolean,
        server_default=sa.text("false"),
        nullable=False,
        comment=(
            "현재 화면 대표 이름으로 선택된 alias인지 표시한다. 유일한 공식 명칭이나 "
            "유일한 검색 이름이라는 뜻이 아니다."
        ),
    ),
    sa.PrimaryKeyConstraint("node_alias_id", name="pk_node_alias"),
    sa.UniqueConstraint(
        "node_id",
        "alias_text",
        "language",
        name="uq_node_alias__value",
    ),
    sa.CheckConstraint(
        "btrim(alias_text) <> ''",
        name="ck_node_alias__alias_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(language) <> ''",
        name="ck_node_alias__language_nonblank",
    ),
    comment=(
        "대표 이름과 검색 alias를 불변 node ID에 연결한다. 기간과 이름 종류는 "
        "저장하지 않는다."
    ),
)
sa.Index(
    "uq_node_alias__preferred",
    node_alias.c.node_id,
    unique=True,
    postgresql_where=node_alias.c.is_preferred,
)
sa.Index("ix_node_alias__text", node_alias.c.alias_text, node_alias.c.node_id)

node_alias_evidence = sa.Table(
    "node_alias_evidence",
    metadata,
    sa.Column(
        "node_alias_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node_alias.node_alias_id",
            name="fk_node_alias_evidence__alias",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "observation_id",
        sa.BigInteger,
        sa.ForeignKey(
            "observation.observation_id",
            name="fk_node_alias_evidence__observation",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint(
        "node_alias_id",
        "observation_id",
        name="pk_node_alias_evidence",
    ),
    comment="alias가 확인된 원문 위치를 다대다로 연결한다.",
)
sa.Index(
    "ix_node_alias_evidence__observation",
    node_alias_evidence.c.observation_id,
    node_alias_evidence.c.node_alias_id,
)

external_identifier = sa.Table(
    "external_identifier",
    metadata,
    sa.Column(
        "external_identifier_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_external_identifier__node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("identifier_system", sa.Text, nullable=False),
    sa.Column("identifier_value", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint(
        "external_identifier_id",
        name="pk_external_identifier",
    ),
    sa.UniqueConstraint(
        "identifier_system",
        "identifier_value",
        name="uq_external_identifier__business",
    ),
    sa.CheckConstraint(
        "btrim(identifier_system) <> ''",
        name="ck_external_identifier__system_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(identifier_value) <> ''",
        name="ck_external_identifier__value_nonblank",
    ),
    sa.CheckConstraint(
        "identifier_system IN ('KRX', 'WIKIDATA', 'ORCID', 'LEI')",
        name="ck_external_identifier__system",
    ),
    comment=(
        "신뢰된 자료 준비 단계가 제공한 외부 식별 체계와 값. 일반 Agent 본문 "
        "추출이나 Claim·observation Evidence Trace를 저장하는 곳이 아니다."
    ),
)
sa.Index(
    "ix_external_identifier__node",
    external_identifier.c.node_id,
    external_identifier.c.external_identifier_id,
)

node_merge = sa.Table(
    "node_merge",
    metadata,
    sa.Column(
        "node_merge_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "source_node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_node_merge__source",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "canonical_node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_node_merge__canonical",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("merge_reason", sa.Text, nullable=False),
    sa.Column("merged_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("reversed_reason", sa.Text),
    sa.Column(
        "reversed_at",
        sa.DateTime(timezone=True),
        comment=(
            "값이 없으면 활성 병합, 값이 있으면 취소된 과거 병합이다. 취소 행을 "
            "삭제하거나 다시 활성화하지 않는다."
        ),
    ),
    sa.PrimaryKeyConstraint("node_merge_id", name="pk_node_merge"),
    sa.CheckConstraint(
        "source_node_id <> canonical_node_id",
        name="ck_node_merge__not_self",
    ),
    sa.CheckConstraint(
        "btrim(merge_reason) <> ''",
        name="ck_node_merge__reason_nonblank",
    ),
    sa.CheckConstraint(
        "(reversed_at IS NULL AND reversed_reason IS NULL) OR "
        "(reversed_at IS NOT NULL AND reversed_reason IS NOT NULL "
        "AND btrim(reversed_reason) <> '')",
        name="ck_node_merge__reversal_shape",
    ),
    sa.CheckConstraint(
        "isfinite(merged_at) AND "
        "(reversed_at IS NULL OR "
        "(isfinite(reversed_at) AND reversed_at >= merged_at))",
        name="ck_node_merge__timestamps",
    ),
    comment=(
        "동일 대상으로 확인된 source node ID를 canonical node ID로 해석하는 "
        "리디렉션 이력. alias 변경이나 기존 근거의 물리 이동이 아니다."
    ),
)
sa.Index(
    "uq_node_merge__active_source",
    node_merge.c.source_node_id,
    unique=True,
    postgresql_where=node_merge.c.reversed_at.is_(None),
)
sa.Index(
    "ix_node_merge__active_canonical",
    node_merge.c.canonical_node_id,
    node_merge.c.source_node_id,
    postgresql_where=node_merge.c.reversed_at.is_(None),
)
sa.Index(
    "ix_node_merge__source_history",
    node_merge.c.source_node_id,
    node_merge.c.merged_at.desc(),
)

event_temporal_extent = sa.Table(
    "event_temporal_extent",
    metadata,
    sa.Column(
        "event_node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_event_temporal_extent__node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "start_at",
        sa.DateTime(timezone=True),
        comment=(
            "precision이 MONTH 또는 YEAR이면 범위 계산을 위한 시작 anchor다. "
            "실제 월 1일 또는 1월 1일 발생을 뜻하지 않는다."
        ),
    ),
    sa.Column("end_at", sa.DateTime(timezone=True)),
    sa.Column("start_precision", sa.Text, nullable=False),
    sa.Column("end_precision", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("event_node_id", name="pk_event_temporal_extent"),
    sa.CheckConstraint(
        f"start_precision IN ({TIME_PRECISIONS})",
        name="ck_event_temporal_extent__start_precision",
    ),
    sa.CheckConstraint(
        f"end_precision IN ({TIME_PRECISIONS})",
        name="ck_event_temporal_extent__end_precision",
    ),
    sa.CheckConstraint(
        "(start_at IS NULL AND start_precision = 'UNKNOWN') OR "
        "(start_at IS NOT NULL AND start_precision <> 'UNKNOWN')",
        name="ck_event_temporal_extent__start_value_precision",
    ),
    sa.CheckConstraint(
        "(end_at IS NULL AND end_precision = 'UNKNOWN') OR "
        "(end_at IS NOT NULL AND end_precision <> 'UNKNOWN')",
        name="ck_event_temporal_extent__end_value_precision",
    ),
    sa.CheckConstraint(
        "(start_at IS NULL OR isfinite(start_at)) AND "
        "(end_at IS NULL OR isfinite(end_at))",
        name="ck_event_temporal_extent__timestamps_finite",
    ),
    comment=(
        "사건 node의 채택 시간 범위. 출처별 모든 주장 시간을 저장하는 곳이 "
        "아니며 근거 Claim은 event_temporal_basis로 연결한다."
    ),
)
sa.Index(
    "ix_event_temporal_extent__start",
    event_temporal_extent.c.start_at,
    postgresql_where=event_temporal_extent.c.start_at.is_not(None),
)

claim_relation = sa.Table(
    "claim_relation",
    metadata,
    sa.Column(
        "claim_id",
        sa.BigInteger,
        sa.ForeignKey(
            "claim.claim_id",
            name="fk_claim_relation__claim",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "relation_id",
        sa.BigInteger,
        sa.ForeignKey(
            "relation.relation_id",
            name="fk_claim_relation__relation",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("stance", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("claim_id", "relation_id", name="pk_claim_relation"),
    sa.CheckConstraint(
        "stance IN ('SUPPORT', 'DISPUTE')",
        name="ck_claim_relation__stance",
    ),
    comment=(
        "Claim이 관계를 지지하거나 반박하는 의미 연결. 근거 강도와 충돌 상태를 "
        "합친 점수는 저장하지 않는다."
    ),
)
sa.Index(
    "ix_claim_relation__relation",
    claim_relation.c.relation_id,
    claim_relation.c.stance,
    claim_relation.c.claim_id,
)

claim_attribute_value = sa.Table(
    "claim_attribute_value",
    metadata,
    sa.Column(
        "claim_attribute_value_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "claim_id",
        sa.BigInteger,
        sa.ForeignKey(
            "claim.claim_id",
            name="fk_claim_attribute_value__claim",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "target_node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_claim_attribute_value__target_node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("attribute_revision_id", sa.BigInteger, nullable=False),
    sa.Column("value_kind", sa.Text, nullable=False),
    sa.Column("string_value", sa.Text),
    sa.Column("number_value", sa.Numeric),
    sa.Column("unit_code", sa.Text),
    sa.Column("date_from", sa.Date),
    sa.Column("date_to", sa.Date),
    sa.Column("date_from_precision", sa.Text, nullable=False),
    sa.Column("date_to_precision", sa.Text, nullable=False),
    sa.Column(
        "boolean_value",
        sa.Boolean,
        comment=(
            "false도 원문 근거가 있는 명시적 부정이다. 값 행이 없는 미상과 구분한다."
        ),
    ),
    sa.PrimaryKeyConstraint(
        "claim_attribute_value_id",
        name="pk_claim_attribute_value",
    ),
    sa.ForeignKeyConstraint(
        ("attribute_revision_id", "value_kind"),
        (
            "attribute_revision.attribute_revision_id",
            "attribute_revision.allowed_value_kind",
        ),
        name="fk_claim_attribute_value__attribute_kind",
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    ),
    sa.CheckConstraint(
        "value_kind IN ('STRING', 'NUMBER', 'DATE', 'PERIOD', 'BOOLEAN')",
        name="ck_claim_attribute_value__value_kind",
    ),
    sa.CheckConstraint(
        f"date_from_precision IN ({DATE_PRECISIONS})",
        name="ck_claim_attribute_value__from_precision",
    ),
    sa.CheckConstraint(
        f"date_to_precision IN ({DATE_PRECISIONS})",
        name="ck_claim_attribute_value__to_precision",
    ),
    sa.CheckConstraint(
        "number_value IS NULL OR number_value NOT IN "
        "('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)",
        name="ck_claim_attribute_value__number_finite",
    ),
    sa.CheckConstraint(
        "string_value IS NULL OR btrim(string_value) <> ''",
        name="ck_claim_attribute_value__string_nonblank",
    ),
    sa.CheckConstraint(
        "unit_code IS NULL OR btrim(unit_code) <> ''",
        name="ck_claim_attribute_value__unit_nonblank",
    ),
    sa.CheckConstraint(
        "(value_kind = 'STRING' AND string_value IS NOT NULL "
        "AND number_value IS NULL AND unit_code IS NULL AND date_from IS NULL "
        "AND date_to IS NULL AND boolean_value IS NULL "
        "AND date_from_precision = 'UNKNOWN' "
        "AND date_to_precision = 'UNKNOWN') OR "
        "(value_kind = 'NUMBER' AND string_value IS NULL "
        "AND number_value IS NOT NULL AND unit_code IS NOT NULL "
        "AND date_from IS NULL AND date_to IS NULL AND boolean_value IS NULL "
        "AND date_from_precision = 'UNKNOWN' "
        "AND date_to_precision = 'UNKNOWN') OR "
        "(value_kind = 'DATE' AND string_value IS NULL AND number_value IS NULL "
        "AND unit_code IS NULL AND date_from IS NOT NULL AND date_to IS NULL "
        "AND boolean_value IS NULL "
        "AND date_from_precision IN ('DAY', 'MONTH', 'YEAR') "
        "AND date_to_precision = 'UNKNOWN') OR "
        "(value_kind = 'PERIOD' AND string_value IS NULL "
        "AND number_value IS NULL AND unit_code IS NULL AND date_from IS NOT NULL "
        "AND boolean_value IS NULL "
        "AND date_from_precision IN ('DAY', 'MONTH', 'YEAR') AND "
        "((date_to IS NULL AND date_to_precision = 'UNKNOWN') OR "
        "(date_to IS NOT NULL AND date_to_precision IN ('DAY', 'MONTH', 'YEAR')))) "
        "OR (value_kind = 'BOOLEAN' AND string_value IS NULL "
        "AND number_value IS NULL AND unit_code IS NULL AND date_from IS NULL "
        "AND date_to IS NULL AND boolean_value IS NOT NULL "
        "AND date_from_precision = 'UNKNOWN' "
        "AND date_to_precision = 'UNKNOWN')",
        name="ck_claim_attribute_value__tagged_union",
    ),
    comment=(
        "Claim이 node 속성에 관해 주장한 구조화 값. target node의 현재 확정 "
        "프로필 값이나 사실 판정 결과가 아니다."
    ),
)
sa.Index(
    "ix_claim_attribute_value__claim",
    claim_attribute_value.c.claim_id,
    claim_attribute_value.c.claim_attribute_value_id,
)
sa.Index(
    "ix_claim_attribute_value__target",
    claim_attribute_value.c.target_node_id,
    claim_attribute_value.c.attribute_revision_id,
    claim_attribute_value.c.claim_id,
)
sa.Index(
    "ix_claim_attribute_value__attribute",
    claim_attribute_value.c.attribute_revision_id,
    claim_attribute_value.c.target_node_id,
    claim_attribute_value.c.claim_id,
)

claim_observation = sa.Table(
    "claim_observation",
    metadata,
    sa.Column(
        "claim_id",
        sa.BigInteger,
        sa.ForeignKey(
            "claim.claim_id",
            name="fk_claim_observation__claim",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "observation_id",
        sa.BigInteger,
        sa.ForeignKey(
            "observation.observation_id",
            name="fk_claim_observation__observation",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint(
        "claim_id",
        "observation_id",
        name="pk_claim_observation",
    ),
    comment="Claim과 정확한 원문 범위를 다대다로 연결하는 Evidence Trace다.",
)
sa.Index(
    "ix_claim_observation__observation",
    claim_observation.c.observation_id,
    claim_observation.c.claim_id,
)

event_temporal_basis = sa.Table(
    "event_temporal_basis",
    metadata,
    sa.Column(
        "event_node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "event_temporal_extent.event_node_id",
            name="fk_event_temporal_basis__event",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "claim_id",
        sa.BigInteger,
        sa.ForeignKey(
            "claim.claim_id",
            name="fk_event_temporal_basis__claim",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint(
        "event_node_id",
        "claim_id",
        name="pk_event_temporal_basis",
    ),
    comment="사건 node의 채택 시간 범위를 직접 뒷받침하는 Claim 연결이다.",
)
sa.Index(
    "ix_event_temporal_basis__claim",
    event_temporal_basis.c.claim_id,
    event_temporal_basis.c.event_node_id,
)

lint_run = sa.Table(
    "lint_run",
    metadata,
    sa.Column(
        "lint_run_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "lint_policy_version_id",
        sa.BigInteger,
        sa.ForeignKey(
            "lint_policy_version.lint_policy_version_id",
            name="fk_lint_run__policy",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "scope_kind",
        sa.Text,
        server_default=sa.text("'FULL_GRAPH'"),
        nullable=False,
    ),
    sa.Column(
        "status",
        sa.Text,
        server_default=sa.text("'PENDING'"),
        nullable=False,
    ),
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("completed_at", sa.DateTime(timezone=True)),
    sa.PrimaryKeyConstraint("lint_run_id", name="pk_lint_run"),
    sa.CheckConstraint(
        "scope_kind = 'FULL_GRAPH'",
        name="ck_lint_run__scope_kind",
    ),
    sa.CheckConstraint(
        "status IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')",
        name="ck_lint_run__status",
    ),
    sa.CheckConstraint(
        "(started_at IS NULL OR isfinite(started_at)) AND "
        "(completed_at IS NULL OR isfinite(completed_at)) AND "
        "(completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)",
        name="ck_lint_run__timestamps",
    ),
    sa.CheckConstraint(
        "(status = 'PENDING' AND started_at IS NULL AND completed_at IS NULL) OR "
        "(status = 'RUNNING' AND started_at IS NOT NULL "
        "AND completed_at IS NULL) OR "
        "(status IN ('SUCCESS', 'FAILED') AND started_at IS NOT NULL "
        "AND completed_at IS NOT NULL)",
        name="ck_lint_run__status_shape",
    ),
    comment=(
        "이미 저장된 기준 지식그래프를 한 lint policy로 재검사한 full graph "
        "실행. 후보 검사나 promotion 실패를 기록하지 않는다."
    ),
)
sa.Index(
    "uq_lint_run__in_progress",
    lint_run.c.lint_policy_version_id,
    unique=True,
    postgresql_where=lint_run.c.status.in_(("PENDING", "RUNNING")),
)
sa.Index(
    "ix_lint_run__status",
    lint_run.c.status,
    lint_run.c.lint_run_id,
    postgresql_where=lint_run.c.status.in_(("PENDING", "RUNNING")),
)
sa.Index(
    "ix_lint_run__policy",
    lint_run.c.lint_policy_version_id,
    lint_run.c.lint_run_id.desc(),
)

lint_finding = sa.Table(
    "lint_finding",
    metadata,
    sa.Column(
        "lint_finding_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("finding_key", sa.LargeBinary, nullable=False),
    sa.Column(
        "knowledge_item_id",
        sa.BigInteger,
        sa.ForeignKey(
            "knowledge_item.knowledge_item_id",
            name="fk_lint_finding__knowledge_item",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "lint_policy_rule_id",
        sa.BigInteger,
        sa.ForeignKey(
            "lint_policy_rule.lint_policy_rule_id",
            name="fk_lint_finding__policy_rule",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "first_detected_run_id",
        sa.BigInteger,
        sa.ForeignKey(
            "lint_run.lint_run_id",
            name="fk_lint_finding__first_run",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "latest_detected_run_id",
        sa.BigInteger,
        sa.ForeignKey(
            "lint_run.lint_run_id",
            name="fk_lint_finding__latest_run",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        "detection_count",
        sa.Integer,
        server_default=sa.text("1"),
        nullable=False,
    ),
    sa.Column("message", sa.Text, nullable=False),
    sa.Column("details_json", JSONB),
    sa.Column(
        "resolved_by_run_id",
        sa.BigInteger,
        sa.ForeignKey(
            "lint_run.lint_run_id",
            name="fk_lint_finding__resolved_run",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    ),
    sa.Column("resolved_at", sa.DateTime(timezone=True)),
    sa.Column("resolution_reason", sa.Text),
    sa.PrimaryKeyConstraint("lint_finding_id", name="pk_lint_finding"),
    sa.CheckConstraint(
        "octet_length(finding_key) = 32",
        name="ck_lint_finding__key_length",
    ),
    sa.CheckConstraint(
        "detection_count >= 1",
        name="ck_lint_finding__count_positive",
    ),
    sa.CheckConstraint(
        "btrim(message) <> ''",
        name="ck_lint_finding__message_nonblank",
    ),
    sa.CheckConstraint(
        "details_json IS NULL OR jsonb_typeof(details_json) = 'object'",
        name="ck_lint_finding__details_object",
    ),
    sa.CheckConstraint(
        "isfinite(first_detected_at) AND isfinite(last_detected_at) "
        "AND last_detected_at >= first_detected_at AND "
        "(resolved_at IS NULL OR "
        "(isfinite(resolved_at) AND resolved_at >= last_detected_at))",
        name="ck_lint_finding__timestamps",
    ),
    sa.CheckConstraint(
        "(resolved_by_run_id IS NULL AND resolved_at IS NULL "
        "AND resolution_reason IS NULL) OR "
        "(resolved_by_run_id IS NOT NULL AND resolved_at IS NOT NULL "
        "AND resolution_reason IS NOT NULL AND btrim(resolution_reason) <> '')",
        name="ck_lint_finding__resolution_shape",
    ),
    comment=(
        "저장된 knowledge item의 결정적 문제 인스턴스. 사람의 거절 상태가 "
        "아니며 열린 BLOCKING finding은 공개 조회에서만 제외한다."
    ),
)
sa.Index(
    "uq_lint_finding__open_key",
    lint_finding.c.finding_key,
    unique=True,
    postgresql_where=lint_finding.c.resolved_at.is_(None),
)
sa.Index(
    "ix_lint_finding__item_open",
    lint_finding.c.knowledge_item_id,
    lint_finding.c.lint_policy_rule_id,
    lint_finding.c.lint_finding_id,
    postgresql_where=lint_finding.c.resolved_at.is_(None),
)
sa.Index(
    "ix_lint_finding__blocking_open",
    lint_finding.c.lint_policy_rule_id,
    lint_finding.c.knowledge_item_id,
    postgresql_where=lint_finding.c.resolved_at.is_(None),
)
sa.Index(
    "ix_lint_finding__latest_run",
    lint_finding.c.latest_detected_run_id,
    lint_finding.c.lint_finding_id,
)

conflict_set = sa.Table(
    "conflict_set",
    metadata,
    sa.Column(
        "conflict_set_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "relation_id",
        sa.BigInteger,
        sa.ForeignKey(
            "relation.relation_id",
            name="fk_conflict_set__relation",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    ),
    sa.Column(
        "target_node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_conflict_set__target_node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    ),
    sa.Column(
        "attribute_revision_id",
        sa.BigInteger,
        sa.ForeignKey(
            "attribute_revision.attribute_revision_id",
            name="fk_conflict_set__attribute_revision",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    ),
    sa.Column(
        "event_node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "event_temporal_extent.event_node_id",
            name="fk_conflict_set__event",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    ),
    sa.Column("modality", sa.Text, nullable=False),
    sa.Column(
        "current_state",
        sa.Text,
        nullable=False,
        comment=(
            "Agent 제안에 대한 사람의 선택적 확인·거절 상태. member Claim의 "
            "knowledge state를 변경하지 않는다."
        ),
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint("conflict_set_id", name="pk_conflict_set"),
    sa.CheckConstraint(
        "(relation_id IS NOT NULL AND target_node_id IS NULL "
        "AND attribute_revision_id IS NULL AND event_node_id IS NULL) OR "
        "(relation_id IS NULL AND target_node_id IS NOT NULL "
        "AND attribute_revision_id IS NOT NULL AND event_node_id IS NULL) OR "
        "(relation_id IS NULL AND target_node_id IS NULL "
        "AND attribute_revision_id IS NULL AND event_node_id IS NOT NULL)",
        name="ck_conflict_set__target_shape",
    ),
    sa.CheckConstraint(
        "modality IN ('FACT', 'PLAN_OR_TARGET', 'PREDICTION_OR_ESTIMATE', "
        "'OPINION_OR_EVALUATION')",
        name="ck_conflict_set__modality",
    ),
    sa.CheckConstraint(
        "current_state IN ('AGENT_PROPOSED', 'HUMAN_CONFIRMED', 'REJECTED')",
        name="ck_conflict_set__current_state",
    ),
    sa.CheckConstraint(
        "isfinite(created_at)",
        name="ck_conflict_set__created_at_finite",
    ),
    comment=(
        "관계·노드 속성·사건 시간 중 한 의미 대상을 비교하는 불변 Claim "
        "snapshot. 어느 Claim이 참인지 자동 판정하지 않는다."
    ),
)
sa.Index(
    "ix_conflict_set__relation",
    conflict_set.c.relation_id,
    conflict_set.c.current_state,
    conflict_set.c.conflict_set_id,
    postgresql_where=conflict_set.c.relation_id.is_not(None),
)
sa.Index(
    "ix_conflict_set__attribute",
    conflict_set.c.target_node_id,
    conflict_set.c.attribute_revision_id,
    conflict_set.c.current_state,
    conflict_set.c.conflict_set_id,
    postgresql_where=conflict_set.c.target_node_id.is_not(None),
)
sa.Index(
    "ix_conflict_set__event",
    conflict_set.c.event_node_id,
    conflict_set.c.current_state,
    conflict_set.c.conflict_set_id,
    postgresql_where=conflict_set.c.event_node_id.is_not(None),
)

conflict_member = sa.Table(
    "conflict_member",
    metadata,
    sa.Column(
        "conflict_set_id",
        sa.BigInteger,
        sa.ForeignKey(
            "conflict_set.conflict_set_id",
            name="fk_conflict_member__set",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "claim_id",
        sa.BigInteger,
        sa.ForeignKey(
            "claim.claim_id",
            name="fk_conflict_member__claim",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("position_key", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint(
        "conflict_set_id",
        "claim_id",
        name="pk_conflict_member",
    ),
    sa.CheckConstraint(
        "btrim(position_key) <> ''",
        name="ck_conflict_member__position_nonblank",
    ),
    comment=(
        "정확한 Claim 구성과 같은 관점 그룹을 보존하는 불변 conflict snapshot member다."
    ),
)
sa.Index(
    "ix_conflict_member__claim",
    conflict_member.c.claim_id,
    conflict_member.c.conflict_set_id,
)
sa.Index(
    "ix_conflict_member__position",
    conflict_member.c.conflict_set_id,
    conflict_member.c.position_key,
    conflict_member.c.claim_id,
)

conflict_summary = sa.Table(
    "conflict_summary",
    metadata,
    sa.Column(
        "conflict_summary_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "conflict_set_id",
        sa.BigInteger,
        sa.ForeignKey(
            "conflict_set.conflict_set_id",
            name="fk_conflict_summary__set",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "model_task_id",
        sa.BigInteger,
        sa.ForeignKey(
            "model_task.model_task_id",
            name="fk_conflict_summary__model_task",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("common_ground_text", sa.Text, nullable=False),
    sa.Column("viewpoint_summary_text", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint("conflict_summary_id", name="pk_conflict_summary"),
    sa.UniqueConstraint("model_task_id", name="uq_conflict_summary__model_task"),
    sa.CheckConstraint(
        "btrim(common_ground_text) <> ''",
        name="ck_conflict_summary__common_ground_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(viewpoint_summary_text) <> ''",
        name="ck_conflict_summary__viewpoint_nonblank",
    ),
    sa.CheckConstraint(
        "isfinite(created_at)",
        name="ck_conflict_summary__created_at_finite",
    ),
    comment=(
        "불변 conflict member 집합으로 생성한 공통점과 관점 요약. 자동 승자 "
        "판정이 아니다."
    ),
)
sa.Index(
    "ix_conflict_summary__set",
    conflict_summary.c.conflict_set_id,
    conflict_summary.c.created_at.desc(),
    conflict_summary.c.conflict_summary_id.desc(),
)

node_search_document = sa.Table(
    "node_search_document",
    metadata,
    sa.Column(
        "node_search_document_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_node_search_document__node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("identity_text", sa.Text, nullable=False),
    sa.Column(
        "knowledge_text",
        sa.Text,
        nullable=False,
        comment=(
            "결정적으로 정렬한 공개 기준 지식의 검색 표현. source 문서 전체나 "
            "생성된 맥락 설명을 복사한 필드가 아니다."
        ),
    ),
    sa.Column("input_hash", sa.LargeBinary, nullable=False),
    sa.Column("generator_version", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint(
        "node_search_document_id",
        name="pk_node_search_document",
    ),
    sa.UniqueConstraint(
        "node_id",
        "input_hash",
        "generator_version",
        name="uq_node_search_document__version",
    ),
    sa.UniqueConstraint(
        "node_search_document_id",
        "node_id",
        name="uq_node_search_document__node_reference",
    ),
    sa.CheckConstraint(
        "char_length(identity_text) > 0",
        name="ck_node_search_document__identity_nonempty",
    ),
    sa.CheckConstraint(
        "char_length(knowledge_text) > 0",
        name="ck_node_search_document__knowledge_nonempty",
    ),
    sa.CheckConstraint(
        "octet_length(input_hash) = 32",
        name="ck_node_search_document__input_hash_length",
    ),
    sa.CheckConstraint(
        "btrim(generator_version) <> ''",
        name="ck_node_search_document__generator_nonblank",
    ),
    sa.CheckConstraint(
        "isfinite(created_at)",
        name="ck_node_search_document__created_at_finite",
    ),
    comment=(
        "공개 가능한 한 node를 키워드·벡터 검색의 공통 대상으로 만드는 불변 "
        "텍스트 버전. 생성된 node_context를 입력으로 되돌려 넣지 않는다."
    ),
)
sa.Index(
    "ix_node_search_document__node",
    node_search_document.c.node_id,
    node_search_document.c.created_at.desc(),
    node_search_document.c.node_search_document_id.desc(),
)
sa.Index(
    "ix_node_search_document__fts",
    (
        sa.func.setweight(
            sa.func.to_tsvector(
                sa.literal_column("'simple'"),
                node_search_document.c.identity_text,
            ),
            sa.literal_column("'A'"),
        ).op("||")(
            sa.func.setweight(
                sa.func.to_tsvector(
                    sa.literal_column("'simple'"),
                    node_search_document.c.knowledge_text,
                ),
                sa.literal_column("'B'"),
            )
        )
    ),
    postgresql_using="gin",
)

search_document_basis = sa.Table(
    "search_document_basis",
    metadata,
    sa.Column(
        "node_search_document_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node_search_document.node_search_document_id",
            name="fk_search_document_basis__search_document",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "knowledge_item_id",
        sa.BigInteger,
        sa.ForeignKey(
            "knowledge_item.knowledge_item_id",
            name="fk_search_document_basis__knowledge_item",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint(
        "node_search_document_id",
        "knowledge_item_id",
        name="pk_search_document_basis",
    ),
    comment=(
        "검색 문서 생성에 기여한 공개 기준 지식 계보. 벡터 점수의 문장별 "
        "인과 설명이 아니다."
    ),
)
sa.Index(
    "ix_search_document_basis__knowledge_item",
    search_document_basis.c.knowledge_item_id,
    search_document_basis.c.node_search_document_id,
)

node_embedding = sa.Table(
    "node_embedding",
    metadata,
    sa.Column(
        "node_embedding_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("node_id", sa.BigInteger, nullable=False),
    sa.Column("node_search_document_id", sa.BigInteger, nullable=False),
    sa.Column(
        "model_task_id",
        sa.BigInteger,
        sa.ForeignKey(
            "model_task.model_task_id",
            name="fk_node_embedding__model_task",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("embedding_vector", Vector(1024), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint("node_embedding_id", name="pk_node_embedding"),
    sa.ForeignKeyConstraint(
        ("node_search_document_id", "node_id"),
        (
            "node_search_document.node_search_document_id",
            "node_search_document.node_id",
        ),
        name="fk_node_embedding__search_document",
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    ),
    sa.UniqueConstraint("model_task_id", name="uq_node_embedding__model_task"),
    sa.UniqueConstraint(
        "node_embedding_id",
        "node_search_document_id",
        "node_id",
        name="uq_node_embedding__publication_reference",
    ),
    sa.CheckConstraint(
        "isfinite(created_at)",
        name="ck_node_embedding__created_at_finite",
    ),
    comment=(
        "정확한 node_search_document에서 만든 불변 검색 벡터. 모델·입력 hash·"
        "재시도 이력은 model_task가 소유하며 동일 대상 판정이나 관계 생성에 "
        "사용하지 않는다."
    ),
)
sa.Index(
    "ix_node_embedding__search_document",
    node_embedding.c.node_search_document_id,
    node_embedding.c.node_id,
    node_embedding.c.node_embedding_id,
)

node_context = sa.Table(
    "node_context",
    metadata,
    sa.Column(
        "node_context_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("node_id", sa.BigInteger, nullable=False),
    sa.Column("node_search_document_id", sa.BigInteger, nullable=False),
    sa.Column(
        "model_task_id",
        sa.BigInteger,
        sa.ForeignKey(
            "model_task.model_task_id",
            name="fk_node_context__model_task",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("language", sa.Text, nullable=False),
    sa.Column("context_text", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint("node_context_id", name="pk_node_context"),
    sa.ForeignKeyConstraint(
        ("node_search_document_id", "node_id"),
        (
            "node_search_document.node_search_document_id",
            "node_search_document.node_id",
        ),
        name="fk_node_context__search_document",
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    ),
    sa.UniqueConstraint("model_task_id", name="uq_node_context__model_task"),
    sa.UniqueConstraint(
        "node_context_id",
        "node_search_document_id",
        "node_id",
        name="uq_node_context__publication_reference",
    ),
    sa.CheckConstraint(
        "btrim(language) <> ''",
        name="ck_node_context__language_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(context_text) <> ''",
        name="ck_node_context__context_nonblank",
    ),
    sa.CheckConstraint(
        "isfinite(created_at)",
        name="ck_node_context__created_at_finite",
    ),
    comment=(
        "정확한 검색 문서에서 사전 생성한 사용자용 맥락 설명. 검색 문서 입력으로 "
        "되돌려 넣지 않으며 클릭 시 모델을 호출하지 않는다."
    ),
)
sa.Index(
    "ix_node_context__search_document",
    node_context.c.node_search_document_id,
    node_context.c.node_id,
    node_context.c.node_context_id,
)

followup_question = sa.Table(
    "followup_question",
    metadata,
    sa.Column(
        "followup_question_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column(
        "node_context_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node_context.node_context_id",
            name="fk_followup_question__context",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "model_task_id",
        sa.BigInteger,
        sa.ForeignKey(
            "model_task.model_task_id",
            name="fk_followup_question__model_task",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("slot", sa.SmallInteger, nullable=False),
    sa.Column("question_text", sa.Text, nullable=False),
    sa.Column(
        "target_node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_followup_question__target_node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
        comment=(
            "질문 클릭 뒤 새 중심으로 탐색할 node. 질문의 완전한 답이나 두 node "
            "사이의 근거 있는 Relation을 뜻하지 않는다."
        ),
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint(
        "followup_question_id",
        name="pk_followup_question",
    ),
    sa.UniqueConstraint(
        "node_context_id",
        "slot",
        name="uq_followup_question__slot",
    ),
    sa.CheckConstraint("slot IN (1, 2)", name="ck_followup_question__slot"),
    sa.CheckConstraint(
        "btrim(question_text) <> ''",
        name="ck_followup_question__text_nonblank",
    ),
    sa.CheckConstraint(
        "isfinite(created_at)",
        name="ck_followup_question__created_at_finite",
    ),
    comment=(
        "한 node_context에서 다음 지도 중심으로 이동할 질문 두 개와 대상 node를 "
        "저장한다. target은 Relation을 뜻하지 않는다."
    ),
)
sa.Index(
    "ix_followup_question__target",
    followup_question.c.target_node_id,
    followup_question.c.followup_question_id,
)
sa.Index(
    "ix_followup_question__model_task",
    followup_question.c.model_task_id,
    followup_question.c.slot,
)

node_insight = sa.Table(
    "node_insight",
    metadata,
    sa.Column(
        "node_insight_id",
        sa.BigInteger,
        sa.Identity(always=True),
        nullable=False,
    ),
    sa.Column("node_id", sa.BigInteger, nullable=False),
    sa.Column("node_search_document_id", sa.BigInteger, nullable=False),
    sa.Column(
        "model_task_id",
        sa.BigInteger,
        sa.ForeignKey(
            "model_task.model_task_id",
            name="fk_node_insight__model_task",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("time_window", sa.Text, nullable=False),
    sa.Column(
        "as_of_at",
        sa.DateTime(timezone=True),
        nullable=False,
        comment=(
            "RECENT_90_DAYS와 RECENT_1_YEAR 입력 범위를 계산한 기준 시각. 모델 "
            "호출 시각이나 공개 완료 시각이 아니다."
        ),
    ),
    sa.Column("slot", sa.SmallInteger, nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("summary_text", sa.Text, nullable=False),
    sa.Column(
        "synthesis_text",
        sa.Text,
        nullable=False,
        comment=(
            "여러 근거를 연결한 모델의 종합 해석. 원문에서 직접 확인된 사실 "
            "문장으로 표시해서는 안 된다."
        ),
    ),
    sa.Column("caveat_text", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint("node_insight_id", name="pk_node_insight"),
    sa.ForeignKeyConstraint(
        ("node_search_document_id", "node_id"),
        (
            "node_search_document.node_search_document_id",
            "node_search_document.node_id",
        ),
        name="fk_node_insight__search_document",
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    ),
    sa.UniqueConstraint(
        "model_task_id",
        "time_window",
        "slot",
        name="uq_node_insight__task_window_slot",
    ),
    sa.CheckConstraint(
        "time_window IN ('RECENT_90_DAYS', 'RECENT_1_YEAR')",
        name="ck_node_insight__time_window",
    ),
    sa.CheckConstraint("slot IN (1, 2, 3)", name="ck_node_insight__slot"),
    sa.CheckConstraint("btrim(title) <> ''", name="ck_node_insight__title_nonblank"),
    sa.CheckConstraint(
        "btrim(summary_text) <> ''",
        name="ck_node_insight__summary_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(synthesis_text) <> ''",
        name="ck_node_insight__synthesis_nonblank",
    ),
    sa.CheckConstraint(
        "btrim(caveat_text) <> ''",
        name="ck_node_insight__caveat_nonblank",
    ),
    sa.CheckConstraint(
        "isfinite(as_of_at) AND isfinite(created_at)",
        name="ck_node_insight__timestamps_finite",
    ),
    comment=(
        "한 node의 공개 검색 문서와 근거 Claim을 모델이 미리 종합한 불변 "
        "분석 리포트. 클릭 시 생성하지 않으며 사실·관계·원문 사본을 저장하지 않는다."
    ),
)
sa.Index(
    "ix_node_insight__node_window",
    node_insight.c.node_id,
    node_insight.c.node_search_document_id,
    node_insight.c.time_window,
    node_insight.c.model_task_id,
    node_insight.c.slot,
)

node_insight_claim = sa.Table(
    "node_insight_claim",
    metadata,
    sa.Column(
        "node_insight_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node_insight.node_insight_id",
            name="fk_node_insight_claim__insight",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "claim_id",
        sa.BigInteger,
        sa.ForeignKey(
            "claim.claim_id",
            name="fk_node_insight_claim__claim",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "role",
        sa.Text,
        nullable=False,
        comment=(
            "KEY_CLAIM은 근거로 확인된 내용, SUPPORTING_CLAIM은 보조 근거, "
            "CONTRASTING_CLAIM은 엇갈리는 관점이나 유의점의 근거다."
        ),
    ),
    sa.Column("display_order", sa.SmallInteger, nullable=False),
    sa.PrimaryKeyConstraint(
        "node_insight_id",
        "claim_id",
        name="pk_node_insight_claim",
    ),
    sa.UniqueConstraint(
        "node_insight_id",
        "display_order",
        name="uq_node_insight_claim__display_order",
    ),
    sa.CheckConstraint(
        "role IN ('KEY_CLAIM', 'SUPPORTING_CLAIM', 'CONTRASTING_CLAIM')",
        name="ck_node_insight_claim__role",
    ),
    sa.CheckConstraint(
        "display_order >= 1",
        name="ck_node_insight_claim__display_order_positive",
    ),
    comment=(
        "인사이트가 사용한 기존 Claim과 화면 역할을 연결한다. 확인된 사실·원문·"
        "Relation 사본이 아니며 Evidence Trace는 Claim에서 조회한다."
    ),
)
sa.Index(
    "ix_node_insight_claim__claim",
    node_insight_claim.c.claim_id,
    node_insight_claim.c.node_insight_id,
)

publication_affected_node = sa.Table(
    "publication_affected_node",
    metadata,
    sa.Column(
        "promotion_batch_id",
        sa.BigInteger,
        sa.ForeignKey(
            "promotion_batch.promotion_batch_id",
            name="fk_publication_affected_node__batch",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column(
        "node_id",
        sa.BigInteger,
        sa.ForeignKey(
            "node.node_id",
            name="fk_publication_affected_node__node",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("node_search_document_id", sa.BigInteger),
    sa.Column("node_embedding_id", sa.BigInteger),
    sa.Column("node_context_id", sa.BigInteger),
    sa.Column(
        "node_insight_model_task_id",
        sa.BigInteger,
        sa.ForeignKey(
            "model_task.model_task_id",
            name="fk_publication_affected_node__insight_task",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    ),
    sa.PrimaryKeyConstraint(
        "promotion_batch_id",
        "node_id",
        name="pk_publication_affected_node",
    ),
    sa.ForeignKeyConstraint(
        ("node_search_document_id", "node_id"),
        (
            "node_search_document.node_search_document_id",
            "node_search_document.node_id",
        ),
        name="fk_publication_affected_node__search_document",
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    ),
    sa.ForeignKeyConstraint(
        ("node_embedding_id", "node_search_document_id", "node_id"),
        (
            "node_embedding.node_embedding_id",
            "node_embedding.node_search_document_id",
            "node_embedding.node_id",
        ),
        name="fk_publication_affected_node__embedding",
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    ),
    sa.ForeignKeyConstraint(
        ("node_context_id", "node_search_document_id", "node_id"),
        (
            "node_context.node_context_id",
            "node_context.node_search_document_id",
            "node_context.node_id",
        ),
        name="fk_publication_affected_node__context",
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    ),
    sa.CheckConstraint(
        "node_embedding_id IS NULL OR node_search_document_id IS NOT NULL",
        name="ck_publication_affected_node__embedding_document",
    ),
    sa.CheckConstraint(
        "node_context_id IS NULL OR node_search_document_id IS NOT NULL",
        name="ck_publication_affected_node__context_document",
    ),
    comment=(
        "한 batch의 공개 준비 영향 범위와 최종 선택 artifact·인사이트 작업을 "
        "저장한다. 지도 구성원·좌표·전체 공개 그래프 snapshot이 아니다."
    ),
)
sa.Index(
    "ix_publication_affected_node__node",
    publication_affected_node.c.node_id,
    publication_affected_node.c.promotion_batch_id.desc(),
)
