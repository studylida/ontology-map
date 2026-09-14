from collections.abc import Iterator
from decimal import Decimal
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

REHEARSAL_FLAG = "ONTOLOGY_MAP_MIGRATION_REHEARSAL"
SERVER_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = SERVER_DIR / "alembic.ini"

pytestmark = pytest.mark.skipif(
    os.getenv(REHEARSAL_FLAG) != "1",
    reason="#200 migration rehearsal 전용 격리 PostgreSQL에서만 실행한다.",
)


def _database_url() -> str:
    database_url = os.environ["ONTOLOGY_MAP_DATABASE_URL"]
    database_name = sa.engine.make_url(database_url).database or ""
    if "migration_rehearsal" not in database_name:
        raise RuntimeError(
            "migration rehearsal은 이름에 migration_rehearsal이 포함된 격리 DB에서만 "
            "실행할 수 있습니다."
        )
    return database_url


def _engine() -> Engine:
    return sa.create_engine(_database_url(), poolclass=NullPool)


def _alembic_config() -> Config:
    return Config(str(ALEMBIC_CONFIG))


def _upgrade(revision: str) -> None:
    command.upgrade(_alembic_config(), revision)


def _downgrade(revision: str) -> None:
    command.downgrade(_alembic_config(), revision)


def _reset_public_schema() -> None:
    engine = _engine()
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _clean_rehearsal_database() -> Iterator[None]:
    _reset_public_schema()
    yield
    _reset_public_schema()


def _version(connection: sa.Connection) -> str:
    return str(
        connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    )


def _table_exists(connection: sa.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            sa.text("SELECT to_regclass(:qualified_name)"),
            {"qualified_name": f"public.{table_name}"},
        ).scalar_one()
        is not None
    )


def _column_exists(
    connection: sa.Connection,
    *,
    table_name: str,
    column_name: str,
) -> bool:
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                      AND column_name = :column_name
                )
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).scalar_one()
    )


def _constraint_exists(connection: sa.Connection, constraint_name: str) -> bool:
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = :constraint_name
                      AND connamespace = 'public'::regnamespace
                )
                """
            ),
            {"constraint_name": constraint_name},
        ).scalar_one()
    )


def _insert_claim_scaffold(connection: sa.Connection) -> tuple[int, int, int]:
    node_type_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO node_type (
                    node_type_code,
                    display_name,
                    creation_rule,
                    is_active
                )
                VALUES (
                    'ISSUE_200_MIGRATION_TECHNOLOGY',
                    'Issue 200 migration 기술',
                    'Issue #200 migration rehearsal 전용 유형이다.',
                    true
                )
                RETURNING node_type_id
                """
            )
        ).scalar_one()
    )
    lint_policy_version_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO lint_policy_version (
                    version_no,
                    validator_version,
                    is_active
                )
                VALUES (200003, 'issue-200-migration-rehearsal', false)
                RETURNING lint_policy_version_id
                """
            )
        ).scalar_one()
    )
    promotion_batch_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO promotion_batch (lint_policy_version_id)
                VALUES (:lint_policy_version_id)
                RETURNING promotion_batch_id
                """
            ),
            {"lint_policy_version_id": lint_policy_version_id},
        ).scalar_one()
    )
    target_node_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO knowledge_item (
                    item_kind,
                    current_state,
                    promotion_batch_id
                )
                VALUES ('NODE', 'EVIDENCE_VERIFIED', :promotion_batch_id)
                RETURNING knowledge_item_id
                """
            ),
            {"promotion_batch_id": promotion_batch_id},
        ).scalar_one()
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO node (node_id, node_type_id)
            VALUES (:node_id, :node_type_id)
            """
        ),
        {"node_id": target_node_id, "node_type_id": node_type_id},
    )
    claim_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO knowledge_item (
                    item_kind,
                    current_state,
                    promotion_batch_id
                )
                VALUES ('CLAIM', 'EVIDENCE_VERIFIED', :promotion_batch_id)
                RETURNING knowledge_item_id
                """
            ),
            {"promotion_batch_id": promotion_batch_id},
        ).scalar_one()
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO claim (
                claim_id,
                statement_text,
                language,
                modality,
                asserted_from_precision,
                asserted_to_precision
            )
            VALUES (
                :claim_id,
                'Issue #200 migration rehearsal Claim',
                'ko',
                'FACT',
                'UNKNOWN',
                'UNKNOWN'
            )
            """
        ),
        {"claim_id": claim_id},
    )
    return node_type_id, target_node_id, claim_id


def _insert_legacy_number_value(
    connection: sa.Connection,
    *,
    unit_rule: str,
    unit_code: str,
    number_value: Decimal,
) -> tuple[int, int]:
    node_type_id, target_node_id, claim_id = _insert_claim_scaffold(connection)
    attribute_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO attribute (attribute_code)
                VALUES ('ISSUE_200_MIGRATION_NUMBER')
                RETURNING attribute_id
                """
            )
        ).scalar_one()
    )
    revision_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO attribute_revision (
                    attribute_id,
                    version_no,
                    display_name,
                    target_node_type_id,
                    allowed_value_kind,
                    unit_rule,
                    is_active
                )
                VALUES (
                    :attribute_id,
                    1,
                    'Issue 200 migration NUMBER',
                    :node_type_id,
                    'NUMBER',
                    :unit_rule,
                    true
                )
                RETURNING attribute_revision_id
                """
            ),
            {
                "attribute_id": attribute_id,
                "node_type_id": node_type_id,
                "unit_rule": unit_rule,
            },
        ).scalar_one()
    )
    value_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO claim_attribute_value (
                    claim_id,
                    target_node_id,
                    attribute_revision_id,
                    value_kind,
                    number_value,
                    unit_code,
                    date_from_precision,
                    date_to_precision
                )
                VALUES (
                    :claim_id,
                    :target_node_id,
                    :revision_id,
                    'NUMBER',
                    :number_value,
                    :unit_code,
                    'UNKNOWN',
                    'UNKNOWN'
                )
                RETURNING claim_attribute_value_id
                """
            ),
            {
                "claim_id": claim_id,
                "target_node_id": target_node_id,
                "revision_id": revision_id,
                "number_value": number_value,
                "unit_code": unit_code,
            },
        ).scalar_one()
    )
    return revision_id, value_id


def _insert_multi_unit_number_value(
    connection: sa.Connection,
) -> tuple[int, int]:
    node_type_id, target_node_id, claim_id = _insert_claim_scaffold(connection)
    attribute_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO attribute (attribute_code)
                VALUES ('MAX_MEMORY_BANDWIDTH')
                RETURNING attribute_id
                """
            )
        ).scalar_one()
    )
    revision_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO attribute_revision (
                    attribute_id,
                    version_no,
                    display_name,
                    target_node_type_id,
                    allowed_value_kind,
                    is_active
                )
                VALUES (
                    :attribute_id,
                    1,
                    '최대 메모리 대역폭',
                    :node_type_id,
                    'NUMBER',
                    true
                )
                RETURNING attribute_revision_id
                """
            ),
            {"attribute_id": attribute_id, "node_type_id": node_type_id},
        ).scalar_one()
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO attribute_revision_allowed_unit (
                attribute_revision_id,
                allowed_value_kind,
                unit_code
            )
            VALUES
                (:revision_id, 'NUMBER', 'GB_PER_S'),
                (:revision_id, 'NUMBER', 'TB_PER_S')
            """
        ),
        {"revision_id": revision_id},
    )
    value_id = int(
        connection.execute(
            sa.text(
                """
                INSERT INTO claim_attribute_value (
                    claim_id,
                    target_node_id,
                    attribute_revision_id,
                    value_kind,
                    number_value,
                    unit_code,
                    date_from_precision,
                    date_to_precision
                )
                VALUES (
                    :claim_id,
                    :target_node_id,
                    :revision_id,
                    'NUMBER',
                    1024.5,
                    'GB_PER_S',
                    'UNKNOWN',
                    'UNKNOWN'
                )
                RETURNING claim_attribute_value_id
                """
            ),
            {
                "claim_id": claim_id,
                "target_node_id": target_node_id,
                "revision_id": revision_id,
            },
        ).scalar_one()
    )
    return revision_id, value_id


def _stored_number_value(
    connection: sa.Connection,
    value_id: int,
) -> tuple[Decimal, str]:
    row = connection.execute(
        sa.text(
            """
            SELECT number_value, unit_code
            FROM claim_attribute_value
            WHERE claim_attribute_value_id = :value_id
            """
        ),
        {"value_id": value_id},
    ).one()
    return Decimal(row.number_value), str(row.unit_code)


def test_single_unit_legacy_data_round_trips_through_0003() -> None:
    _upgrade("0002")
    engine = _engine()
    try:
        with engine.begin() as connection:
            revision_id, value_id = _insert_legacy_number_value(
                connection,
                unit_rule="COUNT",
                unit_code="COUNT",
                number_value=Decimal("64.25"),
            )

        _upgrade("0003")
        with engine.connect() as connection:
            assert _version(connection) == "0003"
            assert _table_exists(connection, "attribute_revision_allowed_unit")
            assert not _column_exists(
                connection,
                table_name="attribute_revision",
                column_name="unit_rule",
            )
            assert _constraint_exists(
                connection,
                "fk_claim_attribute_value__allowed_unit",
            )
            allowed_units = connection.execute(
                sa.text(
                    """
                    SELECT allowed_value_kind, unit_code
                    FROM attribute_revision_allowed_unit
                    WHERE attribute_revision_id = :revision_id
                    """
                ),
                {"revision_id": revision_id},
            ).all()
            assert allowed_units == [("NUMBER", "COUNT")]
            assert _stored_number_value(connection, value_id) == (
                Decimal("64.25"),
                "COUNT",
            )
            referenced_unit = connection.execute(
                sa.text(
                    """
                    SELECT allowed_unit.unit_code
                    FROM claim_attribute_value AS cav
                    JOIN attribute_revision_allowed_unit AS allowed_unit
                      ON allowed_unit.attribute_revision_id = cav.attribute_revision_id
                     AND allowed_unit.unit_code = cav.unit_code
                    WHERE cav.claim_attribute_value_id = :value_id
                    """
                ),
                {"value_id": value_id},
            ).scalar_one()
            assert referenced_unit == "COUNT"

        _downgrade("0002")
        with engine.connect() as connection:
            assert _version(connection) == "0002"
            assert not _table_exists(connection, "attribute_revision_allowed_unit")
            assert _column_exists(
                connection,
                table_name="attribute_revision",
                column_name="unit_rule",
            )
            unit_rule = connection.execute(
                sa.text(
                    """
                    SELECT unit_rule
                    FROM attribute_revision
                    WHERE attribute_revision_id = :revision_id
                    """
                ),
                {"revision_id": revision_id},
            ).scalar_one()
            assert unit_rule == "COUNT"
            assert _stored_number_value(connection, value_id) == (
                Decimal("64.25"),
                "COUNT",
            )

        _upgrade("0003")
        with engine.connect() as connection:
            assert _version(connection) == "0003"
            allowed_units = connection.execute(
                sa.text(
                    """
                    SELECT unit_code
                    FROM attribute_revision_allowed_unit
                    WHERE attribute_revision_id = :revision_id
                    """
                ),
                {"revision_id": revision_id},
            ).scalars().all()
            assert allowed_units == ["COUNT"]
            assert _stored_number_value(connection, value_id) == (
                Decimal("64.25"),
                "COUNT",
            )
    finally:
        engine.dispose()


def test_legacy_unit_mismatch_upgrade_fails_without_partial_state() -> None:
    _upgrade("0002")
    engine = _engine()
    try:
        with engine.begin() as connection:
            revision_id, value_id = _insert_legacy_number_value(
                connection,
                unit_rule="COUNT",
                unit_code="RATIO",
                number_value=Decimal("2.5"),
            )

        with pytest.raises(RuntimeError, match="기존 NUMBER Claim"):
            _upgrade("0003")

        with engine.connect() as connection:
            assert _version(connection) == "0002"
            assert not _table_exists(connection, "attribute_revision_allowed_unit")
            assert _column_exists(
                connection,
                table_name="attribute_revision",
                column_name="unit_rule",
            )
            assert not _constraint_exists(
                connection,
                "fk_claim_attribute_value__allowed_unit",
            )
            unit_rule = connection.execute(
                sa.text(
                    """
                    SELECT unit_rule
                    FROM attribute_revision
                    WHERE attribute_revision_id = :revision_id
                    """
                ),
                {"revision_id": revision_id},
            ).scalar_one()
            assert unit_rule == "COUNT"
            assert _stored_number_value(connection, value_id) == (
                Decimal("2.5"),
                "RATIO",
            )
    finally:
        engine.dispose()


def test_multi_unit_downgrade_fails_without_data_loss() -> None:
    _upgrade("0003")
    engine = _engine()
    try:
        with engine.begin() as connection:
            revision_id, value_id = _insert_multi_unit_number_value(connection)

        with pytest.raises(RuntimeError, match="복수 허용 단위"):
            _downgrade("0002")

        with engine.connect() as connection:
            assert _version(connection) == "0003"
            assert _table_exists(connection, "attribute_revision_allowed_unit")
            assert not _column_exists(
                connection,
                table_name="attribute_revision",
                column_name="unit_rule",
            )
            assert _constraint_exists(
                connection,
                "fk_claim_attribute_value__allowed_unit",
            )
            allowed_units = set(
                connection.execute(
                    sa.text(
                        """
                        SELECT unit_code
                        FROM attribute_revision_allowed_unit
                        WHERE attribute_revision_id = :revision_id
                        """
                    ),
                    {"revision_id": revision_id},
                ).scalars()
            )
            assert allowed_units == {"GB_PER_S", "TB_PER_S"}
            assert _stored_number_value(connection, value_id) == (
                Decimal("1024.5"),
                "GB_PER_S",
            )
    finally:
        engine.dispose()
